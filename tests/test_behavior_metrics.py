"""Acceptance tests for BV-06: behavior outcome metrics compilation.

Covers:
1. 2 no-show + 3 late: non_attendance_students=2, reporting_late_students=3, attending=8
2. Enacted jump increments attempt and enacted; refused jump increments attempt only
3. Staffed post intercept > 0, empty post miss > 0, no invented workers
4. Empty-path leftover: catch_up_time_saved_student_s > 0 vs congested twin; never negative
5. Unique leftover count does not double on two cutoff events for same members
6. Campus no-behavior: new measures are 0 (or absent-as-zero), occupancy still on, ticket07 wait meanings unchanged
7. Unfinished leftover from no-next-vehicle counted unfinished, not hall-late with invented arrival
"""

from __future__ import annotations

import copy
import pytest

from usm_sim import (
    build_artificial_single_server_case,
    build_whole_campus_origins_case,
    simulate,
)
from tests.test_behavior_engine import _valid_all_families_dict


def test_1_two_noshow_three_late_metrics():
    """1. 2 no-show + 3 late: non_attendance_students=2, reporting_late_students=3, attending=8."""
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

    m = res["measures"]
    assert m["non_attendance_students"] == 2
    assert m["reporting_late_students"] == 3
    assert m["attending_students"] == 8
    assert m["reporting_lateness_student_s"] == pytest.approx(360.0)

    # Source unit record matches
    su_rec = res["outcomes"]["source_units"][0]
    assert su_rec["non_attendance_students"] == 2
    assert su_rec["reporting_late_students"] == 3
    assert su_rec["reporting_lateness_student_s"] == pytest.approx(360.0)


def test_2_jump_increments_attempt_and_enacted():
    """2. Enacted jump increments attempt and enacted; refused jump increments attempt only."""
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
        "events": [
            {
                "event_id": "evt_jump_1",
                "phenomenon": "queue_jump",
                "place_id": "entrance",
                "target": {"cohort_id": "c_second", "place_id": "entrance"},
                "trigger": {"before_stage": "entrance_service"},
                "evidence": {"category": "assumed", "note": "jump"},
            }
        ],
    }
    policy["grouping"] = {"maximum_assembly_wait_s": 2.0}

    # A. Enacted jump: increments attempt and enacted
    policy_enacted = copy.deepcopy(policy)
    policy_enacted["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {"trigger": "queue_jump", "action": "allow-queue-jump", "place_id": "entrance"},
        ]
    }
    res_enacted = simulate(scenario, policy_enacted)
    assert res_enacted["status"] == "completed"
    assert res_enacted["measures"]["queue_jump_attempt_students"] == 1
    assert res_enacted["measures"]["queue_jump_enacted_students"] == 1

    # B. Refused jump: increments attempt only
    policy_refused = copy.deepcopy(policy)
    policy_refused["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {"trigger": "queue_jump", "action": "refuse-queue-jump", "place_id": "entrance"},
        ]
    }
    res_refused = simulate(scenario, policy_refused)
    assert res_refused["status"] == "completed"
    assert res_refused["measures"]["queue_jump_attempt_students"] == 1
    assert res_refused["measures"]["queue_jump_enacted_students"] == 0


def test_3_staffed_post_intercept_empty_post_miss():
    """3. Staffed post intercept > 0, empty post miss > 0, no invented workers."""
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
                {"cohort_id": "c1", "count": 1, "attendance_state": "attending", "reporting_mode": "absolute", "actual_reporting_s": 0.0, "readiness_s": 0.0, "evidence": {"category": "assumed", "note": "c1"}},
                {"cohort_id": "c2", "count": 1, "attendance_state": "attending", "reporting_mode": "absolute", "actual_reporting_s": 10.0, "readiness_s": 10.0, "evidence": {"category": "assumed", "note": "c2"}},
            ]
        },
        "events": [
            {
                "event_id": "evt_jump_test3",
                "phenomenon": "queue_jump",
                "place_id": "entrance",
                "target": {"cohort_id": "c2", "place_id": "entrance"},
                "trigger": {"before_stage": "entrance_service"},
                "evidence": {"category": "assumed", "note": "jump"},
            }
        ],
    }

    # Case A: Post with staff stationed at 'entrance'
    scenario_staffed = copy.deepcopy(scenario)
    scenario_staffed["initial_state"]["workers"] = [
        {"id": "station_worker_01", "role": "station", "place_id": "entrance", "available_time_s": 0.0}
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
    assert res_staffed["measures"]["station_intercept_students"] > 0
    assert res_staffed["measures"]["station_miss_students"] == 0
    assert res_staffed["measures"]["station_intercept_students_by_place"]["entrance"] == 1
    # No invented workers: intercepts record only the declared station worker
    intercepts = [e for e in res_staffed["event_trace"] if e.get("event_type") == "station_intercept"]
    assert len(intercepts) == 1
    assert intercepts[0]["worker_ids"] == ["station_worker_01"]

    # Case B: Empty post (no workers at entrance)
    scenario_empty = copy.deepcopy(scenario)
    scenario_empty["initial_state"]["workers"] = []

    res_empty = simulate(scenario_empty, policy_intercept)
    assert res_empty["status"] == "completed"
    assert res_empty["measures"]["station_intercept_students"] == 0
    assert res_empty["measures"]["station_miss_students"] > 0
    assert res_empty["measures"]["station_miss_students_by_place"]["entrance"] == 1
    # No invented workers: empty post records empty worker_ids
    misses = [e for e in res_empty["event_trace"] if e.get("event_type") == "station_miss"]
    assert len(misses) == 1
    assert misses[0]["worker_ids"] == []


def test_4_catch_up_time_saved_empty_vs_congested_twin():
    """4. Empty-path leftover: catch_up_time_saved_student_s > 0 vs congested twin; never negative."""
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 4
    unit["resolved_attendance"] = 4
    unit["members"] = [dict(m) for m in scenario["initial_state"]["students"][0]["members"]]

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

    # Pulse 1 (2 students) at t=0; Leftover (2 students) arrives at t=100 (after pulse 1 vacated at t=60)
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
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "readiness_s": 0,
                    "evidence": {"category": "assumed", "note": "pulse 1"},
                },
                {
                    "cohort_id": "c_leftover",
                    "count": 2,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 100,
                    "readiness_s": 100,
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

    # A. Empty-path leftover run: Leftover departs on empty path, saving time vs congested twin
    res_empty = simulate(scenario, policy)
    assert res_empty["status"] == "completed"
    assert res_empty["measures"]["catch_up_time_saved_student_s"] > 0
    assert res_empty["measures"]["catch_up_walk_students"] == 2
    assert res_empty["measures"]["catch_up_time_saved_student_s"] == pytest.approx(1260.0)

    # B. Congested twin run: 12 students where Leftover departs while pulse 1 occupies the path
    scenario_congested, policy_congested = build_artificial_single_server_case()
    unit8 = scenario_congested["source_units"][0]
    unit8_id = unit8["id"]
    unit8["declared_population"] = 12
    unit8["resolved_attendance"] = 12
    unit8["estimated_attendance"] = 12
    unit8["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit8_id, "hostel_id": "synthetic"}
        for i in range(12)
    ]
    scenario_congested["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit8_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 12},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit8_id, "hostel_id": "synthetic"}
                for i in range(12)
            ],
            "student_count": 12,
        }
    ]
    scenario_congested["route_legs"][0]["duration_s"] = 100.0
    scenario_congested["route_legs"][0]["shared_resource_ids"] = ["shared_path_1"]
    scenario_congested["shared_resources"] = [
        {
            "id": "shared_path_1",
            "kind": "path",
            "capacity_students": 100,
            "operating_limit_students": 5,
            "duration_s": 50.0,
        }
    ]
    scenario_congested["operating_rules"]["walk_occupancy_rule"] = {
        "empty_duration_factor": 1.0,
        "congested_duration_factor": 2.0,
        "congested_at": "operating_limit",
    }
    scenario_congested["behavior"] = {
        "version": "1.0",
        "case_id": "case_packed_path_leftover",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            unit8_id: [
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
    policy_congested["grouping"] = {"maximum_assembly_wait_s": 10.0}
    policy_congested["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
        ]
    }
    res_congested = simulate(scenario_congested, policy_congested)
    assert res_congested["status"] == "completed"
    # Leftover departed on congested path -> 0 time saved
    assert res_congested["measures"]["catch_up_time_saved_student_s"] == 0.0
    assert res_congested["measures"]["catch_up_walk_students"] == 0
    # In both runs, catch up time saved is never negative
    assert res_empty["measures"]["catch_up_time_saved_student_s"] >= 0.0
    assert res_congested["measures"]["catch_up_time_saved_student_s"] >= 0.0


def test_5_unique_assembly_leftover_does_not_double_on_repeat_cutoffs():
    """5. Unique leftover count does not double on two cutoff events for same members."""
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
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    m = res["measures"]
    assert m["assembly_leftover_events"] == 2
    # 4 unique members (s2, s3, s4, s5), not 6 (does not double)
    assert m["assembly_leftover_students"] == 4

    su_rec = res["outcomes"]["source_units"][0]
    assert su_rec["assembly_leftover_events"] == 2
    assert su_rec["assembly_leftover_students"] == 4


def test_6_campus_no_behavior_measures_zero_occupancy_on():
    """6. Campus no-behavior: new measures are 0 (or absent-as-zero), occupancy still on, ticket07 wait meanings unchanged."""
    campus, policy = build_whole_campus_origins_case()
    res = simulate(campus, policy)
    assert res["status"] == "completed"

    m = res["measures"]
    # All new behavior measures are 0 or 0.0
    behavior_keys = [
        "reporting_late_students",
        "reporting_lateness_student_s",
        "assembly_leftover_students",
        "assembly_leftover_events",
        "missed_pulse_students",
        "deviation_attempt_students",
        "path_skip_students",
        "hall_area_late_students",
        "hall_area_lateness_student_s",
        "unfinished_leftover_students",
        "non_attendance_students",
        "withdrawn_students",
        "catch_up_walk_students",
        "catch_up_time_saved_student_s",
        "queue_jump_attempt_students",
        "queue_jump_enacted_students",
        "station_intercept_students",
        "station_miss_students",
        "unsupervised_flow_students",
    ]
    for key in behavior_keys:
        assert m[key] == 0 or m[key] == 0.0, f"Expected {key} to be 0/0.0, got {m[key]}"

    # Occupancy rule is still declared on
    assert bool(campus.get("operating_rules", {}).get("walk_occupancy_rule")) is True

    # Ticket07 wait meanings are unchanged
    assert m["completed_students"] == 64
    assert m["total_student_waiting_student_s"] > 0
    assert m["mean_wait_s"] > 0
    assert m["p95_wait_s"] >= 0
    assert m["wait_denominator_students"] == 64
    assert m["unfinished_students"] == 0


def test_7_unfinished_leftover_from_no_next_vehicle_not_hall_late():
    """7. Unfinished leftover from no-next-vehicle counted unfinished, not hall-late with invented arrival."""
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
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
        ]
    }

    res = simulate(scenario, policy)
    assert res["status"] == "incomplete"

    m = res["measures"]
    # 2 unfinished students counted as unfinished_leftover_students
    assert m["unfinished_leftover_students"] == 2
    assert m["unfinished_students"] == 2

    # Not counted as hall-late with invented arrival
    assert m["hall_area_late_students"] == 0
    assert m["hall_area_lateness_student_s"] == 0.0

    su_rec = res["outcomes"]["source_units"][0]
    assert su_rec["unfinished_leftover_students"] == 2
    assert su_rec["unfinished_students"] == 2
    assert su_rec["hall_area_late_students"] == 0
    assert su_rec["hall_area_lateness_student_s"] == 0.0
