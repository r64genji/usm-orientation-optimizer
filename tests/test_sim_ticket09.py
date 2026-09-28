"""Acceptance tests for ticket 09: public Check a proposal."""

from __future__ import annotations

import copy
import inspect
import math
import pytest
import usm_sim.proposals as proposals
from usm_sim import (
    SimulationError,
    build_artificial_120_hostel_case,
    build_rst_shared_fleet_case,
    check_proposal,
    simulate,
)
from usm_sim.counting import build_walking_checkpoint_case
from usm_sim.workers import build_zero_workers_case


def _permitted() -> dict:
    return {
        "grouping_bases": [
            "hostel",
            "building",
            "floor",
            "wing",
            "floor_wing",
            "target_size",
            "mixed",
        ],
        "allowed_values": {
            "grouping.split_policy": [
                "forbid",
                "keep_units_whole",
                "permit_supervised_split",
            ],
            "grouping.mixing_policy": [
                "same_group_only",
                "same_hostel",
                "permit_mixed_hostels",
            ],
        },
        "numerical_bounds": {
            "grouping.units_per_group": {"lower": 1, "upper": 12, "unit": "units"},
            "grouping.target_students": {"lower": 1, "upper": 120, "unit": "students"},
            "grouping.maximum_assembly_wait_s": {"lower": 0, "upper": 1800, "unit": "s"},
            "release_rule.interval_s": {"lower": 0, "upper": 600, "unit": "s"},
        },
    }


def _layout(scenario: dict) -> dict:
    return {
        "layout_status": "estimated",
        "source_units": [
            {
                "id": unit["id"],
                "building_id": unit.get("building_id"),
                "floor_id": unit.get("floor_id"),
                "wing_id": unit.get("wing_id"),
                "layout_status": unit.get("layout_status") or "estimated",
            }
            for unit in scenario.get("source_units") or []
        ],
    }


def _as_proposal(policy: dict, **updates) -> dict:
    grouping = copy.deepcopy(policy.get("grouping") or {})
    regroup = copy.deepcopy(grouping.get("regroup_policy") or {"required": False})
    counting = copy.deepcopy(policy.get("counting") or {})
    if not isinstance(counting, dict):
        counting = {}
    counting.setdefault("assignments", {})
    if counting.get("assignments"):
        methods = [
            row.get("method")
            for row in counting["assignments"].values()
            if isinstance(row, dict) and row.get("method")
        ]
        counting.setdefault("placement", "assigned")
        counting.setdefault("method", methods[0] if methods else None)
    else:
        counting.setdefault("placement", "none")
        counting.setdefault("method", None)
    proposal = {
        "proposal_id": policy.get("policy_id") or "human_proposal",
        "grouping": grouping,
        "regroup_policy": regroup,
        "release_rule": copy.deepcopy(
            policy.get("release_rule") or {"type": "immediate"}
        ),
        "counting": counting,
        "worker_allocation": {"assignments": [], "count": 0},
        "vehicle_dispatch_rule": copy.deepcopy(
            policy.get("vehicle_dispatch_rule") or {"type": "none"}
        ),
        "destination_rule": copy.deepcopy(
            policy.get("destination_rule") or {"type": "complete_after_stages"}
        ),
        "fixed_choices": {
            "required_endpoint": policy.get("required_endpoint"),
        },
        "tunable": {
            "grouping.basis": {
                "allowed": [
                    "hostel",
                    "building",
                    "floor",
                    "wing",
                    "floor_wing",
                    "target_size",
                    "mixed",
                ]
            },
            "grouping.units_per_group": {"lower": 1, "upper": 6, "unit": "units"},
            "grouping.maximum_assembly_wait_s": {"lower": 0, "upper": 600, "unit": "s"},
            "release_rule.interval_s": {"lower": 0, "upper": 300, "unit": "s"},
        },
        "assumptions": [
            {
                "id": "human_written",
                "category": "assumed",
                "note": "hand-written operating proposal",
            }
        ],
    }
    for key, value in updates.items():
        proposal[key] = value
    return proposal


def _reject_category(result: dict) -> str:
    assert result["accepted"] is False
    assert result["error"] is True
    assert result["category"]
    assert result["errors"]
    assert result["errors"][0]["category"] == result["category"]
    assert result.get("field") or result["errors"][0].get("field")
    return result["category"]


def test_valid_floor_proposal_returns_search_space():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert result["accepted"] is True
    assert result["policy"]["grouping"]["basis"] == "floor"
    space = result["search_space"]
    assert "floor" in space["allowed_values"]["grouping.basis"]
    assert space["numerical_bounds"]["grouping.units_per_group"]["lower"] <= space[
        "numerical_bounds"
    ]["grouping.units_per_group"]["upper"]
    assert space["fixed_decisions"]
    assert result["versions"]["format_version"] == scenario["format_version"]
    assert result["versions"]["data_version"] == scenario["data_version"]
    assert result["source_scenario"]["scenario_id"] == scenario["scenario_id"]
    assert result["layout_status"] == "estimated"
    assert result["grouping"]["headcounts_added"] == 0
    assert result["grouping"]["total_resolved_attendance"] == 120
    sizes = sorted(group["student_count"] for group in result["grouping"]["groups"])
    assert sizes == [40, 40, 40]
    for group in result["grouping"]["groups"]:
        assert group["layout_status"] == "estimated"
        assert group["count_record_ids"] == []
        assert group["headcount_added"] is False


def test_valid_wing_proposal_uses_same_disjoint_units():
    scenario, policy = build_artificial_120_hostel_case("wing")
    proposal = _as_proposal(policy)
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert result["accepted"] is True
    assert result["policy"]["grouping"]["basis"] == "wing"
    sizes = sorted(group["student_count"] for group in result["grouping"]["groups"])
    assert sizes == [60, 60]
    keys = [
        member["student_key"]
        for group in result["grouping"]["groups"]
        for member in group["members"]
    ]
    assert len(keys) == 120
    assert len(set(keys)) == 120
    assert result["grouping"]["headcounts_added"] == 0


def test_valid_mixed_origin_specific_proposal():
    scenario, policy = build_rst_shared_fleet_case()
    policy["grouping"] = {
        "mode": "from_source_units",
        "basis": "mixed",
        "mixed_default": "hostel",
        "scope_overrides": {"restu": "floor", "saujana": "hostel", "tekun": "wing"},
        "split_policy": "permit_supervised_split",
        "mixing_policy": "same_hostel",
        "adaptation_rule": {"type": "fixed"},
        "regroup_policy": {"required": False, "place_id": "dtsp_alighting_area"},
        "escorts_per_group": 1,
    }
    proposal = _as_proposal(policy)
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert result["accepted"] is True
    assert result["policy"]["grouping"]["basis"] == "mixed"
    assert result["policy"]["grouping"]["scope_overrides"]["restu"] == "floor"
    assert result["source_scenario"]["scenario_id"] == scenario["scenario_id"]
    assert scenario["operating_rules"]["route_id"] == "rst_fixed_bus_chain"
    assert result["search_space"]["fixed_decisions"]["route_id"] == "rst_fixed_bus_chain"
    assert result["grouping"]["headcounts_added"] == 0


def test_proposal_cannot_change_occupancy():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["fixed_choices"]["resident_occupancy"] = 1
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "fixed_rule_violation"
    assert "occupancy" in result["message"].lower() or "resident_occupancy" in (
        result.get("field") or ""
    )

    copied = _as_proposal(policy)
    copied["source_units"] = copy.deepcopy(scenario["source_units"])
    copied["source_units"][0]["resident_occupancy"] = 1
    nested = check_proposal(copied, scenario, _layout(scenario), _permitted())
    assert _reject_category(nested) == "fixed_rule_violation"


def test_proposal_cannot_remove_a_checkpoint():
    scenario, policy = build_walking_checkpoint_case()
    proposal = _as_proposal(policy)
    proposal["counting"]["required_checkpoints"] = []
    proposal["counting"]["assignments"] = {}
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "fixed_rule_violation"
    assert "checkpoint" in result["message"].lower()


def test_control_rule_cannot_use_future_or_hidden_information():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["release_rule"] = {
        "type": "when_ready",
        "information_source": "hidden_attendance",
    }
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unsupported_policy"
    assert result.get("field")

    future = _as_proposal(policy)
    future["release_rule"] = {
        "type": "scheduled",
        "uses_future": True,
        "information_source": "actual_future_events",
    }
    future_result = check_proposal(future, scenario, _layout(scenario), _permitted())
    assert _reject_category(future_result) == "unsupported_policy"


def test_workers_cannot_move_without_travel():
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenario["initial_state"]["workers"] = [
        {"id": "w1", "role": "escort", "place_id": "dest", "available_time_s": 0}
    ]
    proposal = _as_proposal(policy)
    proposal["worker_allocation"] = {
        "count": 1,
        "assignments": [
            {
                "worker_id": "w1",
                "from_place_id": "dest",
                "place_id": "origin",
                "skip_travel": True,
            }
        ],
    }
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "fixed_rule_violation"
    assert "travel" in result["message"].lower()


def test_human_written_proposal_works_without_ai_service(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("proposal check called an AI service")

    monkeypatch.setattr(proposals, "call_ai", boom)
    scenario, _policy = build_artificial_120_hostel_case("floor")
    proposal = {
        "proposal_id": "hand_written_floor_v1",
        "grouping": {
            "mode": "from_source_units",
            "basis": "floor",
            "split_policy": "forbid",
            "mixing_policy": "same_hostel",
            "adaptation_rule": {"type": "fixed"},
            "regroup_policy": {"required": False},
            "escorts_per_group": 1,
        },
        "regroup_policy": {"required": False},
        "release_rule": {
            "type": "immediate",
            "information_source": "delivered_reports",
        },
        "counting": {"placement": "none", "method": None, "assignments": {}},
        "worker_allocation": {"assignments": [], "count": 0},
        "vehicle_dispatch_rule": {"type": "none"},
        "destination_rule": {"type": "complete_after_stages"},
        "fixed_choices": {"required_endpoint": "stage_complete"},
        "tunable": {
            "grouping.basis": {"allowed": ["floor", "wing", "mixed"]},
            "grouping.units_per_group": {"lower": 1, "upper": 6, "unit": "units"},
            "grouping.maximum_assembly_wait_s": {"lower": 0, "upper": 600, "unit": "s"},
        },
        "assumptions": [
            {
                "id": "layout_estimated",
                "category": "assumed",
                "note": "declared estimated floor and wing layout",
            }
        ],
    }
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert result["accepted"] is True
    assert result["policy"]["policy_id"] == "hand_written_floor_v1"
    source = inspect.getsource(proposals)
    for name in ("openai", "anthropic", "litellm", "langchain"):
        assert name not in source.lower()


def test_missing_proposal_is_missing_input():
    scenario, _policy = build_artificial_120_hostel_case("floor")
    result = check_proposal(None, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "missing_input"
    assert result["field"] == "proposal"


def test_unknown_regroup_place_is_unknown_reference():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["regroup_policy"] = {
        "required": True,
        "place_id": "no_such_yard",
        "duration_s": 10,
        "worker_count": 1,
    }
    proposal["grouping"]["regroup_policy"] = proposal["regroup_policy"]
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unknown_reference"


def test_exact_target_size_needs_a_count_method():
    scenario, policy = build_artificial_120_hostel_case(
        "target_size",
        grouping_updates={
            "target_students": 40,
            "exact_size": True,
            "split_policy": "permit_supervised_split",
        },
    )
    proposal = _as_proposal(policy)
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unresolved_assumption"
    proposal["grouping"]["exact_size_method"] = "count_during_boarding"
    accepted = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert accepted["accepted"] is True
    assert accepted["grouping"]["headcounts_added"] == 0


def test_external_condition_assumption_needs_a_labelled_scenario():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["assumptions"] = [
        {
            "id": "surprise_rain",
            "kind": "rain",
            "changes_external_conditions": True,
        }
    ]
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unresolved_assumption"

    labelled = _as_proposal(policy)
    labelled["assumptions"] = [
        {
            "id": "forecast_rain",
            "kind": "rain",
            "changes_external_conditions": True,
            "labelled_scenario_id": "artificial_120_rain_v1",
        }
    ]
    ok = check_proposal(labelled, scenario, _layout(scenario), _permitted())
    assert ok["accepted"] is True
    assert ok["source_scenario"]["scenario_id"] == scenario["scenario_id"]


def test_unordered_range_and_infinite_duration_are_invalid():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["tunable"]["grouping.maximum_assembly_wait_s"] = {
        "lower": 90,
        "upper": 10,
        "unit": "s",
    }
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "invalid_value_or_unit"

    infinite = _as_proposal(policy)
    infinite["regroup_policy"] = {
        "required": True,
        "place_id": "origin",
        "duration_s": math.inf,
        "worker_count": 0,
    }
    infinite["grouping"]["regroup_policy"] = infinite["regroup_policy"]
    inf_result = check_proposal(infinite, scenario, _layout(scenario), _permitted())
    assert _reject_category(inf_result) == "invalid_value_or_unit"


def test_zero_buses_and_workers_are_valid_stress_inputs():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["worker_allocation"] = {"assignments": [], "count": 0}
    proposal["vehicle_dispatch_rule"] = {"type": "shared_fleet", "bus_count": 0}
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert result["accepted"] is True

    zero_scenario, zero_policy = build_zero_workers_case()
    zero_proposal = _as_proposal(zero_policy)
    zero_proposal["grouping"] = {
        "mode": "explicit_parts",
        "regroup_policy": {"required": False},
    }
    zero_result = check_proposal(
        zero_proposal, zero_scenario, _layout(zero_scenario), _permitted()
    )
    assert zero_result["accepted"] is True


def test_busy_worker_is_not_a_static_impossibility():
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenario["initial_state"]["workers"] = [
        {"id": "w_busy", "role": "escort", "place_id": "origin", "available_time_s": 400}
    ]
    proposal = _as_proposal(policy)
    proposal["worker_allocation"] = {
        "count": 1,
        "assignments": [
            {"worker_id": "w_busy", "place_id": "origin", "duty": "escort"}
        ],
    }
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert result["accepted"] is True
    assert result.get("category") != "impossible_static_requirement"


def test_fixed_rst_route_cannot_be_replaced_with_direct_walk():
    scenario, policy = build_rst_shared_fleet_case()
    proposal = _as_proposal(policy)
    proposal["fixed_choices"]["direct_walk_permitted"] = True
    proposal["direct_walk_permitted"] = True
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) in {"fixed_rule_violation", "unsupported_policy"}


def test_no_waiting_space_for_required_regroup_is_impossible():
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenario["places"].append(
        {
            "id": "full_yard",
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "meaning": "declared full regroup yard",
            "constrained": True,
            "physical_capacity_students": 0,
            "capacity_students": 0,
            "operating_limit_students": 0,
            "preceding_place_id": "origin",
            "queue_discipline": "fcfs",
            "service_rule": "none",
            "capacity_from_gps_scatter": False,
        }
    )
    proposal = _as_proposal(policy)
    proposal["regroup_policy"] = {
        "required": True,
        "place_id": "full_yard",
        "duration_s": 15,
        "worker_count": 0,
    }
    proposal["grouping"]["regroup_policy"] = proposal["regroup_policy"]
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "impossible_static_requirement"


def test_checked_floor_policy_still_simulates():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    checked = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert checked["accepted"] is True
    simulated = simulate(scenario, checked["policy"])
    assert simulated["status"] == "completed"
    assert simulated["measures"]["completed_students"] == 120
    assert simulated["grouping"]["headcounts_added"] == 0


def test_check_proposal_does_not_raise_for_structured_errors():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    del proposal["grouping"]
    try:
        result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    except SimulationError as error:
        raise AssertionError("Check must return structured errors") from error
    assert _reject_category(result) == "missing_input"
    assert result["field"] == "proposal.grouping"


def test_occupancy_cannot_hide_inside_grouping_or_capacity_tunable():
    scenario, policy = build_artificial_120_hostel_case("floor")
    occupancy = _as_proposal(policy)
    occupancy["grouping"]["resident_occupancy"] = 1
    result = check_proposal(occupancy, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "fixed_rule_violation"

    capacity = _as_proposal(policy)
    capacity["tunable"]["capacity_students"] = {
        "lower": 1,
        "upper": 10,
        "unit": "students",
    }
    capacity_result = check_proposal(
        capacity, scenario, _layout(scenario), _permitted()
    )
    assert _reject_category(capacity_result) == "fixed_rule_violation"


def test_unknown_information_source_is_unsupported():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["release_rule"] = {
        "type": "when_ready",
        "information_source": "queue_oracle",
    }
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unsupported_policy"


def test_incompatible_or_missing_bound_units_are_invalid():
    scenario, policy = build_artificial_120_hostel_case("floor")
    minutes = _as_proposal(policy)
    minutes["tunable"]["grouping.maximum_assembly_wait_s"] = {
        "lower": 0,
        "upper": 10,
        "unit": "min",
    }
    result = check_proposal(minutes, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "invalid_value_or_unit"

    missing = _as_proposal(policy)
    missing["tunable"]["grouping.maximum_assembly_wait_s"] = {
        "lower": 0,
        "upper": 10,
    }
    missing_result = check_proposal(
        missing, scenario, _layout(scenario), _permitted()
    )
    assert _reject_category(missing_result) == "invalid_value_or_unit"


def test_proposal_operating_rules_cannot_drop_checkpoints():
    scenario, policy = build_walking_checkpoint_case()
    proposal = _as_proposal(policy)
    proposal["operating_rules"] = {"required_checkpoints": []}
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "fixed_rule_violation"


def test_target_size_proposal_is_valid_when_size_is_declared():
    scenario, policy = build_artificial_120_hostel_case(
        "target_size",
        grouping_updates={
            "target_students": 40,
            "split_policy": "permit_supervised_split",
        },
    )
    proposal = _as_proposal(policy)
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert result["accepted"] is True
    assert result["policy"]["grouping"]["basis"] == "target_size"


def test_students_per_escort_is_honored_when_grouping_offers_one():
    from usm_sim.workers import build_escort_ratio_grouping_override_case

    scenario, policy = build_escort_ratio_grouping_override_case()
    result = simulate(scenario, policy)
    reserved = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "worker_reserved" and event.get("primary_cause") == "escort"
    ]
    used = set()
    for event in reserved:
        used.update(event.get("worker_ids") or [])
    assert len(used) >= 5
    assert result["status"] == "completed"


def test_checked_proposal_matches_raw_policy_on_holds_workers_dispatch():
    from usm_sim import build_rst_shared_fleet_case
    scenario, raw_policy = build_rst_shared_fleet_case(n_buses=2, bus_capacity=40)
    raw_policy["destination_space_rule"] = "reserve_before_departure"
    raw_policy["coordination_delay_s"] = 0.0
    raw_policy["space_control"] = {
        "destination_place_id": "hall",
        "hold_threshold_students": 40,
        "resume_threshold_students": 0,
    }
    raw_policy["vehicle_dispatch_rule"] = {"type": "shared_fleet", "fleet_id": "rst_fleet", "bus_count": 1}
    
    proposal = _as_proposal(raw_policy)
    proposal["space_control"] = raw_policy["space_control"]
    proposal["destination_space_rule"] = raw_policy["destination_space_rule"]
    proposal["coordination_delay_s"] = raw_policy["coordination_delay_s"]
    proposal["vehicle_dispatch_rule"] = raw_policy["vehicle_dispatch_rule"]
    
    checked = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert checked["accepted"] is True
    assert checked["policy"]["destination_space_rule"] == "reserve_before_departure"
    assert checked["policy"]["space_control"] == raw_policy["space_control"]
    assert checked["policy"]["vehicle_dispatch_rule"] == raw_policy["vehicle_dispatch_rule"]
    
    res_raw = simulate(scenario, raw_policy)
    res_checked = simulate(scenario, checked["policy"])
    
    assert res_raw["status"] == res_checked["status"]
    assert res_raw["measures"]["total_student_waiting_student_s"] == res_checked["measures"]["total_student_waiting_student_s"]
    assert len(res_raw["event_trace"]) == len(res_checked["event_trace"])


def test_queue_based_release_requires_space_control_or_destination_space():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["release_rule"] = {"type": "queue_based"}
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unsupported_policy"


def test_late_unit_with_two_assembly_wait_limits():
    scenario, policy = build_artificial_120_hostel_case(
        "floor",
        grouping_updates={
            "units_per_group": 2,
        },
    )
    # Make one unit late: ready at 300s, other ready at 0s
    scenario["source_units"][0]["actual_reporting_s"] = 0
    scenario["source_units"][0]["readiness_s"] = 0
    scenario["source_units"][1]["actual_reporting_s"] = 300
    scenario["source_units"][1]["readiness_s"] = 300
    
    # With large wait limit (600s): waits for late unit
    policy_wait = copy.deepcopy(policy)
    policy_wait["grouping"]["maximum_assembly_wait_s"] = 600
    res_wait = simulate(scenario, policy_wait)
    
    # With small wait limit (100s): early unit departs, late unit departs later
    policy_nowait = copy.deepcopy(policy)
    policy_nowait["grouping"]["maximum_assembly_wait_s"] = 100
    res_nowait = simulate(scenario, policy_nowait)
    
    # Traces must differ because early unit is not held back
    assert res_wait["measures"]["total_student_waiting_student_s"] != res_nowait["measures"]["total_student_waiting_student_s"]
    trace_wait = [e["time_ms"] for e in res_wait["event_trace"] if e["event_type"] == "departure"]
    trace_nowait = [e["time_ms"] for e in res_nowait["event_trace"] if e["event_type"] == "departure"]
    assert trace_wait != trace_nowait


def test_regrouping_with_busy_worker_and_duration_charged():
    scenario, policy = build_rst_shared_fleet_case(n_buses=2)
    scenario["initial_state"]["workers"] = [{"id": f"w_regroup_{i}", "role": "escort", "place_id": "dtsp_alighting_area", "count": 1} for i in range(3)]
    policy["grouping"]["regroup_policy"] = {
        "required": True,
        "place_id": "dtsp_alighting_area",
        "duration_s": 30.0,
        "worker_count": 1,
    }
    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    starts = [
        e
        for e in res["event_trace"]
        if e["event_type"] == "hold_start" and e.get("primary_cause") == "waiting_for_regroup"
    ]
    ends = [
        e
        for e in res["event_trace"]
        if e["event_type"] == "hold_end" and e.get("primary_cause") == "group_assembled"
    ]
    assert starts and ends
    by_part_start = {e["affected_part_id"]: e["time_ms"] for e in starts}
    durs = [
        (e["time_ms"] - by_part_start[e["affected_part_id"]]) / 1000.0
        for e in ends
        if e.get("affected_part_id") in by_part_start
    ]
    assert durs
    assert any(abs(d - 30.0) < 0.01 for d in durs)
    reserved = [
        e for e in res["event_trace"] if e.get("primary_cause") == "regrouping" and e["event_type"] == "worker_reserved"
    ]
    assert reserved

    busy_sc = copy.deepcopy(scenario)
    busy_sc["initial_state"]["workers"] = [
        {"id": "w_only", "role": "escort", "place_id": "dtsp_alighting_area", "count": 1, "available_time_s": 200}
    ]
    busy = simulate(busy_sc, policy)
    idle_sc = copy.deepcopy(busy_sc)
    idle_sc["initial_state"]["workers"][0]["available_time_s"] = 0
    idle = simulate(idle_sc, policy)
    busy_end = next(
        e["time_ms"]
        for e in busy["event_trace"]
        if e["event_type"] == "hold_end" and e.get("primary_cause") == "group_assembled"
    )
    idle_end = next(
        e["time_ms"]
        for e in idle["event_trace"]
        if e["event_type"] == "hold_end" and e.get("primary_cause") == "group_assembled"
    )
    assert busy_end > idle_end


def test_layout_assumptions_preserved_on_policy_and_simulate_succeeds():
    scenario, policy = build_artificial_120_hostel_case("floor")
    # Remove floor_id from all source units in scenario
    for unit in scenario["source_units"]:
        unit["floor_id"] = None
    
    # Supplying floor labels only through layout_assumptions
    layout = {
        "layout_status": "estimated",
        "source_units": [
            {"id": unit["id"], "floor_id": unit["id"].split("_")[1][1:], "building_id": unit.get("building_id")}
            for unit in scenario["source_units"]
        ],
    }
    proposal = _as_proposal(policy)
    checked = check_proposal(proposal, scenario, layout, _permitted())
    assert checked["accepted"] is True
    assert "layout_assumptions" in checked["policy"]
    
    # Simulating with scenario (which still lacks floor_id) and checked policy succeeds!
    res = simulate(scenario, checked["policy"])
    assert res["status"] == "completed"


def test_adaptation_release_ready_has_a_handler_at_permitted_place():
    scenario, policy = build_artificial_120_hostel_case(
        "floor",
        grouping_updates={"units_per_group": 2},
    )
    scenario["source_units"][0]["actual_reporting_s"] = 0
    scenario["source_units"][0]["readiness_s"] = 0
    scenario["source_units"][1]["actual_reporting_s"] = 300
    scenario["source_units"][1]["readiness_s"] = 300
    fixed = copy.deepcopy(policy)
    fixed["grouping"]["adaptation_rule"] = {"type": "fixed"}
    ready = copy.deepcopy(policy)
    ready["grouping"]["adaptation_rule"] = {
        "type": "release_ready",
        "permitted_place_id": "origin",
    }
    res_fixed = simulate(scenario, fixed)
    res_ready = simulate(scenario, ready)
    assert res_fixed["status"] == "completed"
    assert res_ready["status"] == "completed"
    assert (
        res_fixed["measures"]["total_student_waiting_student_s"]
        != res_ready["measures"]["total_student_waiting_student_s"]
    )
    proposal = _as_proposal(ready)
    proposal["adaptation_rule"] = ready["grouping"]["adaptation_rule"]
    checked = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert checked["accepted"] is True
    assert checked["policy"]["grouping"]["adaptation_rule"]["type"] == "release_ready"


def test_unsupported_destination_rule_types_are_rejected():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _as_proposal(policy)
    proposal["destination_rule"] = {"type": "immediate"}
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unsupported_policy"
    proposal["destination_rule"] = {"type": "service_then_complete"}
    result = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert _reject_category(result) == "unsupported_policy"


def test_destination_rule_wait_for_opening_changes_the_trace():
    scenario, policy = build_artificial_120_hostel_case("hostel")
    scenario["calendars"] = [
        {"id": "gate_open", "kind": "opening", "place_id": "dest", "open_time_s": 50}
    ]
    waiting = copy.deepcopy(policy)
    waiting["destination_rule"] = {"type": "wait_for_imposed_opening", "calendar_id": "gate_open"}
    done = copy.deepcopy(policy)
    done["destination_rule"] = {"type": "complete_after_stages"}
    res_wait = simulate(scenario, waiting)
    res_done = simulate(scenario, done)
    assert res_wait["status"] == "completed"
    assert res_done["status"] == "completed"
    wait_times = [row["completion_time_s"] for row in res_wait["outcomes"]["student_completions"]]
    done_times = [row["completion_time_s"] for row in res_done["outcomes"]["student_completions"]]
    assert wait_times != done_times
    assert min(wait_times) >= 50
    assert max(done_times) < 50


def test_destination_space_rule_reserve_changes_the_trace():
    from usm_sim.spillback_cases import (
        constrained_place,
        _unbounded,
        _shell,
        _members,
        _part,
        _unit,
    )

    places = [
        _unbounded("o1", 0.0, 0.0, "o1"),
        _unbounded("o2", 0.0, 0.1, "o2"),
        constrained_place("hall", 0.01, 0.0, "hall", physical=4, operating=4, preceding=None),
    ]
    legs = [
        {"id": "l1", "from_place_id": "o1", "to_place_id": "hall", "duration_s": 10, "mode": "walk", "shared_resource_ids": []},
        {"id": "l2", "from_place_id": "o2", "to_place_id": "hall", "duration_s": 10, "mode": "walk", "shared_resource_ids": []},
    ]
    stages = [
        {"id": "w1", "kind": "travel", "leg_id": "l1"},
        {"id": "w2", "kind": "travel", "leg_id": "l2"},
    ]
    scenario, policy = _shell(
        scenario_id="reserve_vs_allow_f08",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("pa", "ga", "sua", "o1", _members("a", 4, "sua")),
            _part("pb", "gb", "sub", "o2", _members("b", 4, "sub")),
        ],
        source_units=[_unit("sua", 4, "h1"), _unit("sub", 4, "h2")],
        policy_id="p",
        extra_policy={"coordination_delay_s": 0},
    )
    scenario["routes"] = {"h1": ["w1"], "h2": ["w2"]}
    scenario["source_units"][0]["hostel_id"] = "h1"
    scenario["source_units"][1]["hostel_id"] = "h2"
    scenario["initial_state"]["students"][0]["hostel_id"] = "h1"
    scenario["initial_state"]["students"][1]["hostel_id"] = "h2"
    allow = copy.deepcopy(policy)
    allow["destination_space_rule"] = "allow_approach_wait"
    reserve = copy.deepcopy(policy)
    reserve["destination_space_rule"] = "reserve_before_departure"
    res_allow = simulate(scenario, allow)
    res_reserve = simulate(scenario, reserve)
    assert [e["time_ms"] for e in res_allow["event_trace"] if e["event_type"] == "departure"] != [
        e["time_ms"] for e in res_reserve["event_trace"] if e["event_type"] == "departure"
    ]


def test_checked_worker_assignment_appears_on_simulated_workers():
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenario["initial_state"]["workers"] = [
        {"id": "w1", "role": "escort", "place_id": "origin", "available_time_s": 0, "count": 1},
        {"id": "w2", "role": "escort", "place_id": "origin", "available_time_s": 0, "count": 1},
    ]
    scenario["worker_travel"] = [{"from_place_id": "origin", "to_place_id": "dest", "duration_s": 25}]
    proposal = _as_proposal(policy)
    proposal["worker_allocation"] = {
        "count": 1,
        "assignments": [
            {
                "worker_id": "w1",
                "from_place_id": "origin",
                "place_id": "dest",
                "travel_s": 25,
                "role": "station",
                "available_from_s": 5,
            }
        ],
    }
    checked = check_proposal(proposal, scenario, _layout(scenario), _permitted())
    assert checked["accepted"] is True
    result = simulate(scenario, checked["policy"])
    w1 = next(row for row in result["worker_summaries"] if row["worker_id"] == "w1")
    assert w1["place_id"] == "dest"
    assert w1["role"] == "station"


def test_worker_assignment_without_travel_does_not_teleport():
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenario["initial_state"]["workers"] = [
        {"id": "w1", "role": "escort", "place_id": "origin", "count": 1}
    ]
    policy["worker_allocation"] = {
        "assignments": [
            {"worker_id": "w1", "from_place_id": "origin", "place_id": "dest"}
        ]
    }
    result = simulate(scenario, policy)
    w1 = next(row for row in result["worker_summaries"] if row["worker_id"] == "w1")
    assert w1["place_id"] == "origin"

def test_operational_case_enforces_locked_fleet_size():
    from usm_sim.campus import build_whole_campus_full_cohort_case

    scenario, policy = build_whole_campus_full_cohort_case()
    assert len(scenario["initial_state"]["vehicles"]) == 8

    # Fleet size 7 rejected
    sc_7 = copy.deepcopy(scenario)
    sc_7["initial_state"]["vehicles"].pop()
    with pytest.raises(SimulationError) as err_7:
        simulate(sc_7, policy)
    assert err_7.value.category == "fixed_rule_violation"
    assert "locked at 8 buses" in err_7.value.message

    # Fleet size 9 rejected
    sc_9 = copy.deepcopy(scenario)
    sc_9["initial_state"]["vehicles"].append(copy.deepcopy(sc_9["initial_state"]["vehicles"][0]))
    sc_9["initial_state"]["vehicles"][-1]["id"] = "extra_coach"
    with pytest.raises(SimulationError) as err_9:
        simulate(sc_9, policy)
    assert err_9.value.category == "fixed_rule_violation"
    assert "locked at 8 buses" in err_9.value.message

    # Fleet size 0 rejected for operational case
    sc_0 = copy.deepcopy(scenario)
    sc_0["initial_state"]["vehicles"] = []
    with pytest.raises(SimulationError) as err_0:
        simulate(sc_0, policy)
    assert err_0.value.category == "fixed_rule_violation"


def test_operational_case_enforces_locked_fleet_mix():
    from usm_sim.campus import build_whole_campus_full_cohort_case

    scenario, policy = build_whole_campus_full_cohort_case()

    # 6 coaches + 2 electric rejected
    sc_6_2 = copy.deepcopy(scenario)
    for v in sc_6_2["initial_state"]["vehicles"]:
        if v["id"] == "electric_1":
            v["type"] = "coach"
            break
    with pytest.raises(SimulationError) as err_mix:
        simulate(sc_6_2, policy)
    assert err_mix.value.category == "fixed_rule_violation"
    assert "5 coaches and 3 electric buses" in err_mix.value.message

    # Invalid vehicle type rejected
    sc_inv = copy.deepcopy(scenario)
    sc_inv["initial_state"]["vehicles"][0]["type"] = "minivan"
    with pytest.raises(SimulationError) as err_type:
        simulate(sc_inv, policy)
    assert err_type.value.category in {"fixed_rule_violation", "unknown_reference"}


def test_operational_case_enforces_single_usable_door_per_bus():
    from usm_sim.campus import build_whole_campus_full_cohort_case

    scenario, policy = build_whole_campus_full_cohort_case()

    # Vehicle type with 2 usable doors rejected
    sc_doors_vt = copy.deepcopy(scenario)
    for vt in sc_doors_vt["vehicle_types"]:
        if vt["id"] == "coach":
            vt["usable_doors"] = 2
    with pytest.raises(SimulationError) as err_doors:
        simulate(sc_doors_vt, policy)
    assert err_doors.value.category == "fixed_rule_violation"
    assert "usable doors" in err_doors.value.message

    # Vehicle instance with 2 usable doors rejected
    sc_doors_v = copy.deepcopy(scenario)
    sc_doors_v["initial_state"]["vehicles"][0]["usable_doors"] = 2
    with pytest.raises(SimulationError) as err_v_doors:
        simulate(sc_doors_v, policy)
    assert err_v_doors.value.category == "fixed_rule_violation"
    assert "usable doors" in err_v_doors.value.message


def test_operational_case_rejects_door_checks_and_screening_at_dtsp():
    from usm_sim.campus import build_whole_campus_full_cohort_case

    scenario, policy = build_whole_campus_full_cohort_case()

    # bag_check on destination rejected
    sc_bag = copy.deepcopy(scenario)
    sc_bag["destination"]["bag_check"] = True
    with pytest.raises(SimulationError) as err_bag:
        simulate(sc_bag, policy)
    assert err_bag.value.category == "fixed_rule_violation"
    assert "bag_check" in err_bag.value.message

    # security_service on destination rejected
    sc_sec = copy.deepcopy(scenario)
    sc_sec["destination"]["security_service"] = True
    with pytest.raises(SimulationError) as err_sec:
        simulate(sc_sec, policy)
    assert err_sec.value.category == "fixed_rule_violation"
    assert "security_service" in err_sec.value.message

    # screening dwell on destination rejected
    sc_dwell = copy.deepcopy(scenario)
    sc_dwell["destination"]["screening_dwell_s"] = 15.0
    with pytest.raises(SimulationError) as err_dwell:
        simulate(sc_dwell, policy)
    assert err_dwell.value.category == "fixed_rule_violation"
    assert "screening dwell" in err_dwell.value.message

    # door bag_check rejected
    sc_door_bag = copy.deepcopy(scenario)
    sc_door_bag["destination"]["doors"][0]["bag_check"] = True
    with pytest.raises(SimulationError) as err_dbag:
        simulate(sc_door_bag, policy)
    assert err_dbag.value.category == "fixed_rule_violation"

    # door screening dwell rejected
    sc_door_dwell = copy.deepcopy(scenario)
    sc_door_dwell["destination"]["doors"][0]["screening_dwell_s"] = 10.0
    with pytest.raises(SimulationError) as err_ddwell:
        simulate(sc_door_dwell, policy)
    assert err_ddwell.value.category == "fixed_rule_violation"
def test_operational_proposal_rejects_fleet_and_door_check_modifications():
    from usm_sim.campus import build_whole_campus_full_cohort_case

    scenario, policy = build_whole_campus_full_cohort_case()

    # Proposal altering bus count
    p_count = _as_proposal(policy)
    p_count["vehicle_dispatch_rule"] = {"type": "shared_fleet", "bus_count": 6}
    res_count = check_proposal(p_count, scenario, _layout(scenario), _permitted())
    assert _reject_category(res_count) == "fixed_rule_violation"
    assert "locked at 8 buses" in res_count["message"]

    # Proposal tuning fleet size
    p_tune = _as_proposal(policy)
    p_tune["tunable"] = {"fleet.n_buses": {"allowed": [6, 8, 10]}}
    res_tune = check_proposal(p_tune, scenario, _layout(scenario), _permitted())
    assert _reject_category(res_tune) == "fixed_rule_violation"

    # Proposal introducing bag check at destination
    p_bag = _as_proposal(policy)
    p_bag["destination_rule"] = {"bag_check": True}
    res_bag = check_proposal(p_bag, scenario, _layout(scenario), _permitted())
    assert _reject_category(res_bag) == "fixed_rule_violation"

    # Proposal introducing screening dwell at destination
    p_dwell = _as_proposal(policy)
    p_dwell["destination_rule"] = {"screening_dwell_s": 20}
    res_dwell = check_proposal(p_dwell, scenario, _layout(scenario), _permitted())
    assert _reject_category(res_dwell) == "fixed_rule_violation"

    # Proposal placing counting assignment at DTSP entrance door
    p_door_cnt = _as_proposal(policy)
    p_door_cnt["counting"] = {
        "assignments": {
            "chk_door": {
                "checkpoint_id": "chk_door",
                "location_id": "dtsp_door_a",
                "method": "visual",
            }
        }
    }
    res_door_cnt = check_proposal(p_door_cnt, scenario, _layout(scenario), _permitted())
    assert _reject_category(res_door_cnt) == "fixed_rule_violation"
    assert "DTSP entrance door" in res_door_cnt["message"]
