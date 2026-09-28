"""Acceptance tests for ticket 04: finite PPSL staffing and worker travel."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from usm_sim import SimulationError, build_restu_17sep_replay, simulate
from usm_sim.counting import build_walking_checkpoint_case
from usm_sim.scenarios import build_artificial_120_hostel_case
from usm_sim.workers import (
    build_combined_escort_count_case,
    build_contended_assembly_case,
    build_dtsp_restu_return_case,
    build_escort_ratio_grouping_override_case,
    build_exclusive_duty_case,
    build_handover_case,
    build_insufficient_staff_case,
    build_late_calendar_case,
    build_min_station_staff_policy_case,
    build_physical_split_case,
    build_station_queue_case,
    build_zero_workers_case,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAVEL_S = 30.0
WALK_S = 20.0


def _escort_reserved(result: dict) -> list[dict]:
    return [
        event
        for event in result["event_trace"]
        if event["event_type"] == "worker_reserved" and event.get("primary_cause") == "escort"
    ]


def _escort_released(result: dict) -> list[dict]:
    return [
        event
        for event in result["event_trace"]
        if event["event_type"] == "worker_released"
        and event.get("primary_cause") in {"required_endpoint_reached", "handover"}
    ]


def _assignments_for(result: dict, duty: str) -> list[dict]:
    return [
        row
        for row in result.get("worker_assignments") or []
        if duty in (row.get("duties") or [])
    ]


def test_dtsp_finish_cannot_start_at_restu_until_travel_elapses():
    scenario, policy = build_dtsp_restu_return_case(travel_s=TRAVEL_S, walk_s=WALK_S)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    reserved = _escort_reserved(result)
    released = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "worker_released" and event.get("primary_cause") == "required_endpoint_reached"
    ]
    assert reserved
    assert released
    first_end = min(event["time_ms"] for event in released)
    later = [event for event in reserved if event["time_ms"] >= first_end]
    assert later
    travel_ms = int(round(TRAVEL_S * 1000.0))
    assert min(event["time_ms"] for event in later) >= first_end + travel_ms
    assert result["measures"]["worker_travel_s"] >= TRAVEL_S


def test_handover_at_permitted_place():
    scenario, policy = build_handover_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    handovers = [event for event in result["event_trace"] if event["event_type"] == "handover"]
    assert handovers
    event = handovers[0]
    assert event["place_id"] == "transfer"
    assert event.get("released_worker_ids") == ["w_a"]
    assert event.get("worker_ids") == ["w_b"]
    second_walk = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "departure" and event.get("leg_id") == "leg_to_dest"
    ]
    assert second_walk
    assert "w_b" in (second_walk[0].get("escort_ids") or second_walk[0].get("worker_ids") or [])


def test_incompatible_overlapping_duties_are_not_simultaneous():
    scenario, policy = build_exclusive_duty_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    escort_rows = _assignments_for(result, "escort")
    w1_rows = [row for row in escort_rows if row["worker_id"] == "w1"]
    assert len(w1_rows) >= 2
    ordered = sorted(w1_rows, key=lambda row: row["start_ms"])
    for index in range(len(ordered) - 1):
        end_ms = ordered[index]["end_ms"]
        next_start = ordered[index + 1]["start_ms"]
        assert end_ms is not None
        assert next_start >= end_ms
    reserved = _escort_reserved(result)
    assert len(reserved) >= 2
    assert reserved[1]["time_ms"] >= reserved[0]["time_ms"]


def test_physical_split_needs_escorts_internal_part_size_does_not():
    split_scenario, split_policy = build_physical_split_case()
    split = simulate(split_scenario, split_policy)
    assert split["status"] == "completed"
    assert any(event["event_type"] == "part_split" for event in split["event_trace"])
    moves = [
        event
        for event in split["event_trace"]
        if event["event_type"] in {"batch_start", "departure"}
        and event.get("affected_part_id")
        and "~split" in str(event.get("affected_part_id"))
    ]
    assert moves
    parts_seen = {}
    for event in moves:
        part_id = event["affected_part_id"]
        escorts = event.get("escort_ids") or event.get("worker_ids") or []
        parts_seen.setdefault(part_id, escorts)
        assert escorts
    assert len(parts_seen) >= 2
    unique_escorts = set()
    for escorts in parts_seen.values():
        unique_escorts.update(escorts)
    assert len(unique_escorts) >= 2
    first_split_move = min(event["time_ms"] for event in moves)
    second_reserved = [
        event
        for event in split["event_trace"]
        if event["event_type"] == "worker_reserved"
        and event.get("primary_cause") == "escort"
        and event.get("affected_part_id")
        and "~split" in str(event.get("affected_part_id"))
    ]
    assert second_reserved
    assert min(event["time_ms"] for event in second_reserved) <= first_split_move

    internal_scenario, internal_policy = build_physical_split_case(internal_part_size=1)
    internal = simulate(internal_scenario, internal_policy)
    assert internal["status"] == "completed"
    escort_events = _escort_reserved(internal)
    assert len(escort_events) == 1
    used = set()
    for event in escort_events:
        used.update(event.get("worker_ids") or [])
    assert used == {"w1"}


def test_zero_workers_does_not_complete():
    scenario, policy = build_zero_workers_case()
    result = simulate(scenario, policy)
    assert result["status"] in {"incomplete", "infeasible"}
    assert result["status"] != "completed"
    assert result["measures"]["unfinished_students"] > 0
    assert result["outcomes"]["campus"]["unfinished_students"] > 0
    assert result["outcomes"]["campus"]["completed_students"] == 0


def test_insufficient_staff_for_hard_requirement_is_infeasible():
    scenario, policy = build_insufficient_staff_case()
    result = simulate(scenario, policy)
    assert result["status"] == "infeasible"
    assert result["status"] != "completed"
    assert any(row.get("type") == "insufficient_staff" for row in result["violations"])


def test_combined_escort_and_count_charged_once_when_permitted():
    permitted_scenario, permitted_policy = build_combined_escort_count_case(permitted=True)
    permitted = simulate(permitted_scenario, permitted_policy)
    assert permitted["status"] == "completed"
    perm_ids = set()
    for event in permitted["event_trace"]:
        if event["event_type"] in {"worker_reserved", "count_start"}:
            perm_ids.update(event.get("worker_ids") or [])
    assert perm_ids == {"w1"}
    combined_rows = [row for row in permitted["worker_assignments"] if row.get("combined")]
    assert combined_rows
    assert "count" in combined_rows[0]["duties"]
    assert "escort" in combined_rows[0]["duties"]
    span = max(row["end_ms"] or 0 for row in permitted["worker_assignments"]) - min(
        row["start_ms"] for row in permitted["worker_assignments"]
    )
    assert permitted["measures"]["worker_reserved_s"] == pytest.approx(span / 1000.0)
    assert permitted["measures"]["worker_count_s"] > 0
    assert permitted["measures"]["worker_count_s"] <= permitted["measures"]["worker_reserved_s"]
    assert "worker_standby_s" in permitted["measures"]

    separate_scenario, separate_policy = build_combined_escort_count_case(permitted=False)
    separate = simulate(separate_scenario, separate_policy)
    assert separate["status"] == "completed"
    sep_ids = set()
    for event in separate["event_trace"]:
        if event["event_type"] == "worker_reserved":
            sep_ids.update(event.get("worker_ids") or [])
    assert sep_ids == {"w1", "w2"}
    assert separate["measures"]["peak_concurrent_workers"] >= 2


def test_policy_cannot_lower_min_station_staff():
    scenario, policy = build_min_station_staff_policy_case()
    lowered = copy.deepcopy(policy)
    lowered["min_station_staff"] = {"entrance": 1}
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, lowered)
    assert caught.value.category == "fixed_rule_violation"

    nested = copy.deepcopy(policy)
    nested["staffing"] = {"min_station_staff": {"entrance": 0}}
    with pytest.raises(SimulationError) as caught_nested:
        simulate(scenario, nested)
    assert caught_nested.value.category == "fixed_rule_violation"

    ratio = copy.deepcopy(policy)
    ratio["staffing_ratio"] = {"escorts_per_group": 0}
    scenario_ratio = copy.deepcopy(scenario)
    scenario_ratio["operating_rules"]["staffing_ratio"] = {"escorts_per_group": 1}
    with pytest.raises(SimulationError) as caught_ratio:
        simulate(scenario_ratio, ratio)
    assert caught_ratio.value.category == "fixed_rule_violation"


def test_late_calendar_keeps_occupied_workers_reserved():
    scenario, policy = build_late_calendar_case(walk_s=80.0, open_s=40.0)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    reserved = _escort_reserved(result)
    by_worker: dict[str, list[int]] = {}
    for event in reserved:
        for worker_id in event.get("worker_ids") or []:
            by_worker.setdefault(worker_id, []).append(event["time_ms"])
    assert "w_early" in by_worker
    assert "w_late" in by_worker
    late_start = min(by_worker["w_late"])
    assert late_start >= 40000
    early_release = min(
        event["time_ms"]
        for event in result["event_trace"]
        if event["event_type"] == "worker_released"
        and "w_early" in (event.get("worker_ids") or [])
    )
    assert early_release > late_start
    early_rows = [row for row in _assignments_for(result, "escort") if row["worker_id"] == "w_early"]
    assert early_rows
    assert all((row["end_ms"] or 0) > late_start for row in early_rows)
    late_rows = [row for row in result["worker_assignments"] if row["worker_id"] == "w_late"]
    assert late_rows
    assert min(row["start_ms"] for row in late_rows) >= 40000


def test_more_workers_cut_worker_limited_queue():
    few_scenario, few_policy = build_station_queue_case(worker_count=1, min_station_staff=1, server_count=2)
    many_scenario, many_policy = build_station_queue_case(worker_count=2, min_station_staff=1, server_count=2)
    few = simulate(few_scenario, few_policy)
    many = simulate(many_scenario, many_policy)
    assert few["status"] == "completed"
    assert many["status"] == "completed"
    few_queue = few["measures"]["waiting_student_s_by_cause"].get("waiting_for_server", 0.0)
    many_queue = many["measures"]["waiting_student_s_by_cause"].get("waiting_for_server", 0.0)
    assert many_queue < few_queue


def test_forbidden_combined_duty_with_one_worker_is_infeasible():
    scenario, policy = build_combined_escort_count_case(permitted=False)
    scenario["initial_state"]["workers"] = [
        worker for worker in scenario["initial_state"]["workers"] if worker["id"] == "w1"
    ]
    result = simulate(scenario, policy)
    assert result["status"] == "infeasible"
    assert result["status"] != "completed"
    assert result["measures"]["unfinished_students"] > 0
    assert any(row.get("type") == "insufficient_staff" for row in result["violations"])


def test_split_waiting_part_keeps_escort_and_distant_escort_does_not_crash():
    scenario, policy = build_physical_split_case()
    for worker in scenario["initial_state"]["workers"]:
        if worker["id"] == "w2":
            worker["place_id"] = "dest"
    travel = [{"from_place_id": "dest", "to_place_id": "boarding", "duration_s": 50}]
    scenario["worker_travel"] = travel
    scenario["operating_rules"]["worker_travel"] = travel
    result = simulate(scenario, policy)
    assert result["status"] in {"completed", "incomplete", "infeasible"}
    departures = [
        event
        for event in result["event_trace"]
        if event["event_type"] in {"batch_start", "departure"}
        and event.get("affected_part_id")
        and "~split" in str(event.get("affected_part_id"))
    ]
    for event in departures:
        assert event.get("escort_ids") or event.get("worker_ids")


def test_ticket01_restu_still_completes():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["completed_students"] == 40


def test_required_assembly_workers_wait_when_busy_or_late():
    scenario, policy = build_contended_assembly_case()
    result = simulate(scenario, policy)
    starts = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "assembly_start"
    ]
    assert len(starts) == 2
    times = sorted(event["time_ms"] for event in starts)
    assert times[0] == 0
    assert times[1] >= 10000
    assert all(event.get("worker_ids") for event in starts)
    waits = result["measures"]["waiting_student_s_by_cause"].get("waiting_for_worker", 0.0)
    assert waits >= 10.0

    late_scenario, late_policy = build_contended_assembly_case(worker_available_s=60)
    late = simulate(late_scenario, late_policy)
    late_starts = [
        event["time_ms"]
        for event in late["event_trace"]
        if event["event_type"] == "assembly_start"
    ]
    assert late_starts
    assert min(late_starts) >= 60000


def test_assembly_at_a_different_place_requires_worker_travel():
    scenario, policy = build_contended_assembly_case(
        assembly_place_id="yard",
        worker_place_id="origin",
        worker_travel=[
            {"from_place_id": "origin", "to_place_id": "yard", "duration_s": 30}
        ],
    )
    result = simulate(scenario, policy)
    starts = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "assembly_start"
    ]
    assert starts
    assert min(event["time_ms"] for event in starts) >= 30000
    assert any(event.get("place_id") == "yard" for event in starts)


def test_missing_return_travel_edge_is_an_input_error():
    scenario, policy = build_dtsp_restu_return_case(travel_s=TRAVEL_S, walk_s=WALK_S)
    scenario["worker_travel"] = []
    scenario["operating_rules"]["worker_travel"] = []
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "missing_input"
    assert "travel" in caught.value.message.lower()


def test_escort_ratio_overrides_grouping_offer_of_one():
    scenario, policy = build_escort_ratio_grouping_override_case()
    result = simulate(scenario, policy)
    reserved = _escort_reserved(result)
    used = set()
    for event in reserved:
        used.update(event.get("worker_ids") or [])
    assert len(used) >= 5


def test_ticket02_grouping_and_ticket03_counting_still_pass():
    grouped_scenario, grouped_policy = build_artificial_120_hostel_case("floor")
    grouped = simulate(grouped_scenario, grouped_policy)
    assert grouped["status"] == "completed"
    assert grouped["measures"]["completed_students"] == 120
    assert grouped["grouping"]["worker_assignments_added"] == 0

    walk_scenario, walk_policy = build_walking_checkpoint_case()
    walk = simulate(walk_scenario, walk_policy)
    assert walk["status"] == "completed"
    assert walk["checkpoint_coverage"]["missing"] == []
    assert any(event["event_type"] == "worker_reserved" for event in walk["event_trace"])
