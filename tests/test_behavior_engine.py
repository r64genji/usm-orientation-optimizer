"""Tests for BV-05: behavior execution in engine.

Covers:
1. Leftover split from member/cohort readiness (mixed readiness within one unit)
2. Multiple splits preserving identities and hostel sums, no empty mover
3. Readiness cutoff at 1 ms before / at / after cutoff
4. Missing next vehicle leaving conserved unfinished remainder
5. FIFO queue ordering vs enacted and refused queue jumps
6. Station intercept with staff vs miss with empty post
7. Empty-path leftover walk occupancy
8. Packed path leftover walk occupancy
9. Withdrawal during queue vs travel (travel waits for boundary)
10. Campus no-behavior and Restu 17 Sep replay completion
"""

from __future__ import annotations

import copy
import pytest

from usm_sim import (
    build_artificial_single_server_case,
    build_restu_17sep_replay,
    build_whole_campus_origins_case,
    simulate,
)
from usm_sim.campus import FREE_WALK_M_S, SLOWER_WALK_M_S
from usm_sim.errors import SimulationError


def _valid_all_families_dict() -> dict[str, dict]:
    from usm_sim.behavior import ALL_PHENOMENON_FAMILIES
    return {fam: {} for fam in ALL_PHENOMENON_FAMILIES}


def test_1_ten_declared_two_noshow_three_late():
    """1. 10 declared, 2 no-show, 3 late: attending 8; 3-member late part exists; 2 no-shows never travel."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 10
    unit["resolved_attendance"] = 8
    unit["estimated_attendance"] = 10
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(10)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 10},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(10)
            ],
            "student_count": 10,
        }
    ]

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_ten_declared",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_ontime",
                    "count": 5,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "readiness_s": 0,
                    "evidence": {"category": "assumed", "note": "on-time cohort"},
                },
                {
                    "cohort_id": "c_late",
                    "count": 3,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 120,
                    "readiness_s": 120,
                    "evidence": {"category": "assumed", "note": "late cohort"},
                },
                {
                    "cohort_id": "c_noshow",
                    "count": 2,
                    "attendance_state": "no_show",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "readiness_s": 0,
                    "evidence": {"category": "assumed", "note": "no-show cohort"},
                },
            ]
        },
        "events": [],
    }

    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 60
    policy["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "split-and-go",
            }
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    assert res["measures"]["attending_students"] == 8

    trace_splits = [e for e in res["event_trace"] if e.get("event_type") == "part_split"]
    assert len(trace_splits) >= 1
    split_event = trace_splits[0]
    counts = split_event["counts"]
    assert 5 in counts.values()
    assert 3 in counts.values()

    completions = res["outcomes"]["student_completions"]
    assert len(completions) == 8


def test_2_split_twice_identities_and_hostel_sums_survive():
    """2. Split twice: identities and hostel sums survive; no empty mover."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 6
    unit["resolved_attendance"] = 6
    unit["estimated_attendance"] = 6
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(6)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 6},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(6)
            ],
            "student_count": 6,
        }
    ]

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_split_twice",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_early",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "readiness_s": 0,
                    "evidence": {"category": "assumed", "note": "early"},
                },
                {
                    "cohort_id": "c_mid",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 100,
                    "readiness_s": 100,
                    "evidence": {"category": "assumed", "note": "mid"},
                },
                {
                    "cohort_id": "c_late",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 200,
                    "readiness_s": 200,
                    "evidence": {"category": "assumed", "note": "late"},
                },
            ]
        },
        "events": [],
    }

    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 50
    policy["grouping"]["assembly_wait_anchor"] = "earliest_ready"
    policy["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "split-and-go",
            },
            {
                "trigger": "mixed_readiness",
                "action": "split-and-go",
            },
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    splits = [e for e in res["event_trace"] if e.get("event_type") == "part_split"]
    assert len(splits) == 2, f"Expected exactly 2 splits, got {len(splits)}"

    for event in res["event_trace"]:
        if event.get("event_type") in ("departure", "arrival", "part_ready", "part_split"):
            assert event.get("student_count", 0) > 0

    completions = res["outcomes"]["student_completions"]
    assert len(completions) == 6
    comp_sum = sum(c.get("completion_time_s") > 0 for c in completions)
    assert comp_sum == 6


def test_3_arrival_1ms_before_at_after_cutoff():
    """3. Arrival 1 ms before / at / after cutoff — declared ready vs leftover."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 4
    unit["resolved_attendance"] = 4
    unit["members"] = [dict(m) for m in scenario["initial_state"]["students"][0]["members"]]

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_millisecond_cutoff",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c1",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "base"},
                },
                {
                    "cohort_id": "c2_before",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 59.999,
                    "readiness_s": 59.999,
                    "evidence": {"category": "assumed", "note": "1ms before"},
                },
                {
                    "cohort_id": "c3_at",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 60.000,
                    "readiness_s": 60.000,
                    "evidence": {"category": "assumed", "note": "at cutoff"},
                },
                {
                    "cohort_id": "c4_after",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 60.001,
                    "readiness_s": 60.001,
                    "evidence": {"category": "assumed", "note": "1ms after"},
                },
            ]
        },
        "events": [],
    }

    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 60.0
    policy["grouping"]["assembly_wait_anchor"] = "earliest_ready"
    policy["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "split-and-go",
            },
            {
                "trigger": "mixed_readiness",
                "action": "split-and-go",
            },
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    splits = [e for e in res["event_trace"] if e.get("event_type") == "part_split"]
    assert len(splits) == 1
    counts = splits[0]["counts"]
    assert 3 in counts.values()
    assert 1 in counts.values()


def test_4_no_next_vehicle_conserved_unfinished_remainder():
    """4. No next vehicle → conserved unfinished remainder, not teleported."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 6
    unit["resolved_attendance"] = 6
    unit["estimated_attendance"] = 6
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(6)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 6},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(6)
            ],
            "student_count": 6,
        }
    ]

    fleet_id = "fleet_single_bus"
    vehicle_id = "veh_01"
    scenario["initial_state"]["vehicles"] = [
        {
            "id": vehicle_id,
            "type": "bus",
            "fleet_id": fleet_id,
            "capacity_students": 4,
            "available_time_s": 0.0,
            "place_id": "origin",
            "operating_cost_per_hour": 100,
            "usable_doors": 1,
            "return_travel_s": 9999.0,
            "_type_fields": {"alight_s_per_student": 1.0, "board_s_per_student": 1.0},
        }
    ]
    scenario["fleets"] = [
        {
            "id": fleet_id,
            "vehicle_ids": [vehicle_id],
            "boarding_place_id": "origin",
            "alighting_place_id": "entrance",
            "boarding_berth_capacity": 1,
            "dropoff_space_capacity": 50,
            "turnaround_s": 9999.0,
            "dispatch_rule": "board_when_available",
        }
    ]
    scenario["route_stages"] = [
        {
            "id": "board_bus",
            "kind": "batch_service",
            "place_id": "origin",
            "action": "board",
            "fleet_id": fleet_id,
            "duration_s": 10.0,
        },
        {
            "id": "ride_bus",
            "kind": "vehicle_travel",
            "leg_id": "walk_1",
            "duration_s": 20.0,
        },
        {
            "id": "alight_bus",
            "kind": "batch_service",
            "place_id": "entrance",
            "action": "alight",
            "fleet_id": fleet_id,
            "duration_s": 10.0,
        },
        {
            "id": "entrance_service",
            "kind": "queue_service",
            "place_id": "entrance",
            "service_duration_s": 10.0,
            "server_count": 1,
            "queue_discipline": "fcfs",
        },
    ]

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_no_next_bus",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_ontime",
                    "count": 4,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "readiness_s": 0,
                    "evidence": {"category": "assumed", "note": "on time"},
                },
                {
                    "cohort_id": "c_late",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 100,
                    "readiness_s": 100,
                    "evidence": {"category": "assumed", "note": "late"},
                },
            ]
        },
        "events": [],
    }

    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 30
    policy["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "split-and-go",
            },
            {
                "trigger": "mixed_readiness",
                "action": "split-and-go",
            },
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "incomplete"
    assert res["measures"]["completed_students"] == 4
    assert res["measures"]["unfinished_students"] == 2
    assert res["measures"]["accounted_students"] == 6

    unfinished = res["unfinished_demand"]
    assert len(unfinished) == 1
    leftover = unfinished[0]
    assert leftover["place_id"] == "origin"
    assert leftover["student_count"] == 2


def test_5_fifo_order_unchanged_vs_enacted_and_refused_jump():
    """5. FIFO two waiters unchanged without jump event. Enacted jump: later arriver enters first if capacity allows. Refused jump: FIFO stays."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 2
    unit["resolved_attendance"] = 2
    unit["estimated_attendance"] = 2
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(2)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 2},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(2)
            ],
            "student_count": 2,
        }
    ]

    # Walk takes 10s, service takes 50s
    scenario["route_legs"][0]["duration_s"] = 10.0
    scenario["route_stages"][1]["service_duration_s"] = 50.0

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_jump_fifo",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_first",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "first"},
                },
                {
                    "cohort_id": "c_second",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 5.0,
                    "readiness_s": 5.0,
                    "evidence": {"category": "assumed", "note": "second"},
                },
            ]
        },
        "events": [],
    }
    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 2.0
    policy["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {"trigger": "queue_jump", "action": "refuse-queue-jump"},
        ]
    }

    res_fifo = simulate(scenario, policy)
    assert res_fifo["status"] == "completed"
    completions = res_fifo["outcomes"]["student_completions"]
    assert len(completions) == 2
    assert completions[0]["completion_time_s"] < completions[1]["completion_time_s"]

    # B. Enacted queue jump: second arriver jumps ahead of first at entrance
    scenario_jump = copy.deepcopy(scenario)
    scenario_jump["behavior"]["events"] = [
        {
            "event_id": "evt_jump_1",
            "phenomenon": "queue_jump",
            "place_id": "entrance",
            "target": {"cohort_id": "c_second", "place_id": "entrance"},
            "trigger": {"before_stage": "entrance_service"},
            "evidence": {"category": "assumed", "note": "jump"},
        }
    ]
    policy_jump = copy.deepcopy(policy)
    policy_jump["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {"trigger": "queue_jump", "action": "allow-queue-jump", "place_id": "entrance"},
        ]
    }

    res_enacted = simulate(scenario_jump, policy_jump)
    assert res_enacted["status"] == "completed"
    enacted_events = [e for e in res_enacted["event_trace"] if e.get("event_type") == "queue_jump_enacted"]
    assert len(enacted_events) == 1
    assert enacted_events[0]["place_id"] == "entrance"
    assert enacted_events[0]["to_rank"] == 1

    # C. Refused jump: FIFO stays
    policy_refused = copy.deepcopy(policy)
    policy_refused["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {"trigger": "queue_jump", "action": "refuse-queue-jump", "place_id": "entrance"},
        ]
    }
    res_refused = simulate(scenario_jump, policy_refused)
    assert res_refused["status"] == "completed"
    attempt_events = [e for e in res_refused["event_trace"] if e.get("event_type") == "queue_jump_attempt"]
    assert len(attempt_events) == 1
    assert len([e for e in res_refused["event_trace"] if e.get("event_type") == "queue_jump_enacted"]) == 0
    comp_ref = res_refused["outcomes"]["student_completions"]
    assert comp_ref[0]["completion_time_s"] < comp_ref[1]["completion_time_s"]


def test_6_station_staff_intercept_vs_empty_post_miss():
    """6. Station with staff intercepts jumper/leftover; empty post records miss. Do not invent workers."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 2
    unit["resolved_attendance"] = 2
    unit["estimated_attendance"] = 2
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(2)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 2},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(2)
            ],
            "student_count": 2,
        }
    ]

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_station_staff",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c1",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "c1"},
                },
                {
                    "cohort_id": "c2",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 10.0,
                    "readiness_s": 10.0,
                    "evidence": {"category": "assumed", "note": "c2"},
                },
            ]
        },
        "events": [
            {
                "event_id": "evt_jump_test6",
                "phenomenon": "queue_jump",
                "place_id": "entrance",
                "target": {"cohort_id": "c2", "place_id": "entrance"},
                "trigger": {"before_stage": "entrance_service"},
                "evidence": {"category": "assumed", "note": "jump"},
            }
        ],
    }

    # Case A: Post WITH staff stationed at 'entrance'
    scenario_staffed = copy.deepcopy(scenario)
    scenario_staffed["initial_state"]["workers"] = [
        {
            "id": "station_worker_01",
            "role": "station",
            "place_id": "entrance",
            "available_time_s": 0.0,
        }
    ]
    policy_intercept = copy.deepcopy(policy)
    policy_intercept["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {
                "trigger": "queue_jump",
                "action": "intercept-at-station",
                "place_id": "entrance",
                "min_station_staff": 1,
                "fallback": "allow-queue-jump",
            },
        ]
    }
    policy_intercept["grouping"] = {"maximum_assembly_wait_s": 5.0}

    res_staffed = simulate(scenario_staffed, policy_intercept)
    assert res_staffed["status"] == "completed"
    intercepts = [e for e in res_staffed["event_trace"] if e.get("event_type") == "station_intercept"]
    assert len(intercepts) == 1
    assert intercepts[0]["place_id"] == "entrance"
    assert "station_worker_01" in intercepts[0]["worker_ids"]

    # Case B: EMPTY post (no workers at entrance)
    scenario_empty = copy.deepcopy(scenario)
    scenario_empty["initial_state"]["workers"] = []

    res_empty = simulate(scenario_empty, policy_intercept)
    assert res_empty["status"] == "completed"
    misses = [e for e in res_empty["event_trace"] if e.get("event_type") == "station_miss"]
    assert len(misses) == 1
    assert misses[0]["place_id"] == "entrance"
    enacted = [e for e in res_empty["event_trace"] if e.get("event_type") == "queue_jump_enacted"]
    assert len(enacted) == 1


def test_7_empty_path_leftover_walk_occupancy():
    """7. Empty-path leftover after first pulse vacated: walk_occupancy_ahead 0, no shared extra."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 4
    unit["resolved_attendance"] = 4
    unit["members"] = [dict(m) for m in scenario["initial_state"]["students"][0]["members"]]

    # Setup walk leg with shared path resource
    scenario["route_legs"][0]["shared_resource_ids"] = ["shared_path_1"]
    scenario["shared_resources"] = [
        {
            "id": "shared_path_1",
            "kind": "path",
            "capacity_students": 100,
            "operating_limit_students": 5,
            "duration_s": 400.0,
        }
    ]
    scenario["operating_rules"]["walk_occupancy_rule"] = {
        "empty_duration_factor": 1.0,
        "congested_duration_factor": 1.5,
        "congested_at": "operating_limit",
    }

    # Pulse 1 (2 students) at t=0; Leftover (2 students) arrives at t=100 (after pulse 1 arrived at entrance at t=60)
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_empty_path_leftover",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_pulse1",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "pulse 1"},
                },
                {
                    "cohort_id": "c_leftover",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 100.0,
                    "readiness_s": 100.0,
                    "evidence": {"category": "assumed", "note": "leftover"},
                },
            ]
        },
        "events": [],
    }

    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 30.0
    policy["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    departures = [e for e in res["event_trace"] if e.get("event_type") == "departure" and e.get("leg_id") == "walk_1"]
    assert len(departures) == 2

    arrivals = [e for e in res["event_trace"] if e.get("event_type") == "arrival" and e.get("leg_id") == "walk_1"]
    leftover_arrival = [a for a in arrivals if a.get("time_ms", 0) > 80000][0]
    leftover_departure = [d for d in departures if d.get("time_ms", 0) > 80000][0]

    duration_ms = leftover_arrival["time_ms"] - leftover_departure["time_ms"]
    assert duration_ms == 60000, f"Expected 60000ms (empty path free walk), got {duration_ms}ms"


def test_8_packed_path_leftover_congested_factor():
    """8. Packed path leftover: congested factor."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 12
    unit["resolved_attendance"] = 12
    unit["estimated_attendance"] = 12
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(12)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 12},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(12)
            ],
            "student_count": 12,
        }
    ]

    # Make walk leg slow so pulse 1 is still on the path when leftover departs
    scenario["route_legs"][0]["duration_s"] = 100.0
    scenario["route_legs"][0]["shared_resource_ids"] = ["shared_path_1"]
    scenario["shared_resources"] = [
        {
            "id": "shared_path_1",
            "kind": "path",
            "capacity_students": 100,
            "operating_limit_students": 5,
            "duration_s": 50.0,
        }
    ]
    congested_factor = 2.0
    scenario["operating_rules"]["walk_occupancy_rule"] = {
        "empty_duration_factor": 1.0,
        "congested_duration_factor": congested_factor,
        "congested_at": "operating_limit",
    }

    # Pulse 1 has 10 students (>= operating_limit of 5); Leftover has 2 students departing at t=20 while pulse 1 is on path
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_packed_path_leftover",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_pulse1",
                    "count": 10,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "packed pulse"},
                },
                {
                    "cohort_id": "c_leftover",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 20.0,
                    "readiness_s": 20.0,
                    "evidence": {"category": "assumed", "note": "leftover"},
                },
            ]
        },
        "events": [],
    }

    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 10.0
    policy["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    departures = [e for e in res["event_trace"] if e.get("event_type") == "departure" and e.get("leg_id") == "walk_1"]
    arrivals = [e for e in res["event_trace"] if e.get("event_type") == "arrival" and e.get("leg_id") == "walk_1"]
    leftover_dep = [d for d in departures if d.get("time_ms", 0) >= 20000][0]
    leftover_arr = [a for a in arrivals if a.get("affected_part_id") == leftover_dep.get("affected_part_id")][0]

    duration_s = (leftover_arr["time_ms"] - leftover_dep["time_ms"]) / 1000.0
    # Expected congested duration: (100 * 2.0) + (50 * 2.0) = 300.0s
    assert duration_s == 300.0, f"Expected 300.0s congested duration, got {duration_s}s"


def test_9_withdrawal_during_queue_vs_travel_and_prestart():
    """9. Withdrawal during queue vs during travel: travel waits for boundary. Pre-start invalid."""
    # A. Pre-start withdrawal is invalid
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["members"] = [dict(m) for m in scenario["initial_state"]["students"][0]["members"]]
    unit["actual_reporting_s"] = 50.0
    unit["readiness_s"] = 50.0
    scenario["initial_state"]["students"][0]["arrival_s"] = 50.0

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_prestart_withdrawal",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c1",
                    "count": 4,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 50.0, # starts at 50s
                    "readiness_s": 50.0,
                    "evidence": {"category": "assumed", "note": "prestart"},
                }
            ]
        },
        "events": [
            {
                "event_id": "evt_withdraw_prestart",
                "phenomenon": "withdrawal",
                "target": {"cohort_id": "c1"},
                "trigger": {"time_s": 10.0}, # triggers BEFORE start at 50s!
                "evidence": {"category": "assumed", "note": "withdraw"},
            }
        ],
    }
    policy["behavior_response"] = {
        "rules": [{"trigger": "withdrawal", "action": "deny"}]
    }
    with pytest.raises(SimulationError) as exc_info:
        simulate(scenario, policy)
    assert "pre-start withdrawal" in str(exc_info.value)

    # B. Withdrawal during queue: assembly duration of 30s holds students at origin until t=30s.
    # Withdrawal at t=15s executes immediately at origin!
    scenario_queue = copy.deepcopy(scenario)
    scenario_queue["source_units"][0]["actual_reporting_s"] = 0.0
    scenario_queue["source_units"][0]["readiness_s"] = 0.0
    scenario_queue["initial_state"]["students"][0]["arrival_s"] = 0.0
    scenario_queue["behavior"]["source_unit_splits"][unit_id][0]["actual_reporting_s"] = 0.0
    scenario_queue["behavior"]["source_unit_splits"][unit_id][0]["readiness_s"] = 0.0
    scenario_queue["behavior"]["events"] = [
        {
            "event_id": "evt_withdraw_queue",
            "phenomenon": "withdrawal",
            "target": {"cohort_id": "c1"},
            "trigger": {"time_s": 15.0}, # during assembly wait at origin!
            "evidence": {"category": "assumed", "note": "withdraw in queue"},
        }
    ]
    policy_queue = copy.deepcopy(policy)
    policy_queue["grouping"] = {"physical_assembly": {"duration_s": 30.0}}
    res_queue = simulate(scenario_queue, policy_queue)
    assert res_queue["status"] == "completed"
    withdraw_events = [e for e in res_queue["event_trace"] if e.get("event_type") == "withdrawal"]
    assert len(withdraw_events) == 1
    assert withdraw_events[0]["requested_time_s"] == 15.0
    assert withdraw_events[0]["actual_time_s"] == 15.0
    assert res_queue["measures"]["withdrawn_students"] == 4

    # C. Withdrawal during travel: travel waits for destination boundary
    scenario_travel = copy.deepcopy(scenario)
    scenario_travel["source_units"][0]["actual_reporting_s"] = 0.0
    scenario_travel["source_units"][0]["readiness_s"] = 0.0
    scenario_travel["initial_state"]["students"][0]["arrival_s"] = 0.0
    scenario_travel["behavior"]["source_unit_splits"][unit_id][0]["actual_reporting_s"] = 0.0
    scenario_travel["behavior"]["source_unit_splits"][unit_id][0]["readiness_s"] = 0.0
    # Walk stage takes 60s (departure at 0s, arrival at 60s)
    scenario_travel["behavior"]["events"] = [
        {
            "event_id": "evt_withdraw_travel",
            "phenomenon": "withdrawal",
            "target": {"cohort_id": "c1"},
            "trigger": {"time_s": 25.0}, # mid-travel at t=25s!
            "evidence": {"category": "assumed", "note": "withdraw during travel"},
        }
    ]
    res_travel = simulate(scenario_travel, policy)
    assert res_travel["status"] == "completed"
    w_events = [e for e in res_travel["event_trace"] if e.get("event_type") == "withdrawal"]
    assert len(w_events) == 1
    # Requested at 25s, executed at boundary at 60s!
    assert w_events[0]["requested_time_s"] == 25.0
    assert w_events[0]["actual_time_s"] == 60.0
    assert w_events[0]["place_id"] == "entrance" # arrived at entrance boundary before withdrawing
    assert res_travel["measures"]["withdrawn_students"] == 4


def test_10_campus_no_behavior_and_restu_replay_complete():
    """10. Campus no-behavior still completes; occupancy rule still on; Restu replay still completes."""
    # Whole campus origins case
    campus, policy = build_whole_campus_origins_case()
    res_campus = simulate(campus, policy)
    assert res_campus["status"] == "completed"
    assert res_campus["termination_cause"] == "all_completed"

    # Restu 17 Sep replay
    restu, pol_restu = build_restu_17sep_replay()
    res_restu = simulate(restu, pol_restu)
    assert res_restu["status"] == "completed"
    assert res_restu["termination_cause"] == "all_completed"
