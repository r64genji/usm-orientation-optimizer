"""Tests for continuous file streaming, multi-berth boarding with PPSL accounting,
strict 3,000 DTSP seating with G03 overflow, and 09:00 deadline alignment.
"""

from __future__ import annotations

import copy
import pytest

pytestmark = pytest.mark.slow
from usm_sim import (
    build_whole_campus_full_cohort_case,
    simulate,
)
from usm_sim.engine import Engine


def test_continuous_streaming_gathering_paths_40_and_80_students():
    """Gathering exit paths allow 40 and 80-student groups to stream through without capacity violations."""
    scenario, policy = build_whole_campus_full_cohort_case()

    # Verify shared resource definitions on exit paths
    shared_map = {r["id"]: r for r in scenario["shared_resources"]}
    for pid in (
        "path_carpark_single_file",
        "path_north_plaza_single_file",
        "path_south_plaza_single_file",
    ):
        assert pid in shared_map
        assert shared_map[pid].get("continuous_streaming") is True
        assert shared_map[pid].get("capacity_students") is None

    # Test with 40-student groups
    policy_40 = copy.deepcopy(policy)
    policy_40["grouping"]["target_students"] = 40
    res_40 = simulate(copy.deepcopy(scenario), policy_40)
    assert res_40["status"] == "completed"
    cap_violations_40 = [
        v for v in res_40.get("violations", []) if v.get("type") == "physical_capacity"
    ]
    assert cap_violations_40 == []
    assert res_40["measures"]["completed_students"] == 3543

    # Test with 80-student groups
    policy_80 = copy.deepcopy(policy)
    policy_80["grouping"]["target_students"] = 80
    res_80 = simulate(copy.deepcopy(scenario), policy_80)
    assert res_80["status"] == "completed"
    cap_violations_80 = [
        v for v in res_80.get("violations", []) if v.get("type") == "physical_capacity"
    ]
    assert cap_violations_80 == []
    assert res_80["measures"]["completed_students"] == 3543


def test_exit_path_timing_not_zero_when_clear():
    """Exit path crossing is not 0 seconds when the path is clear."""
    scenario, policy = build_whole_campus_full_cohort_case()
    engine = Engine(scenario, policy)

    leg_carpark = engine.legs["leg_hall_approach"]
    duration_s, occupancy_ahead, factor, extra_applied = engine._leg_timing(leg_carpark)
    assert occupancy_ahead == 0
    assert duration_s == 40.0
    assert duration_s > 0.0

    leg_north = engine.legs["leg_hall_approach_north"]
    dur_north, occ_north, _, _ = engine._leg_timing(leg_north)
    assert occ_north == 0
    assert dur_north == 30.0

    leg_south = engine.legs["leg_hall_approach_south"]
    dur_south, occ_south, _, _ = engine._leg_timing(leg_south)
    assert occ_south == 0
    assert dur_south == 30.0


def test_configurable_simultaneous_bus_boarding_berths():
    """Policy can configure simultaneous boarding berths from 1 to 4 with concurrent boarding."""
    scenario, base_policy = build_whole_campus_full_cohort_case()

    # Test 1 berth (default)
    pol_1 = copy.deepcopy(base_policy)
    pol_1["vehicle_dispatch_rule"]["simultaneous_boarding_berths"] = 1
    res_1 = simulate(copy.deepcopy(scenario), pol_1)
    assert res_1["status"] == "completed"
    boards_1 = [
        e for e in res_1["event_trace"]
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    ]
    # Check max concurrent boards at any instant
    board_intervals_1 = [
        (e["time_ms"], e["time_ms"] + 180000) for e in boards_1
    ]
    max_overlap_1 = 0
    for t, _ in board_intervals_1:
        overlap = sum(1 for start, end in board_intervals_1 if start <= t < end)
        max_overlap_1 = max(max_overlap_1, overlap)
    assert max_overlap_1 == 1

    # Test 2 berths
    pol_2 = copy.deepcopy(base_policy)
    pol_2["vehicle_dispatch_rule"]["simultaneous_boarding_berths"] = 2
    res_2 = simulate(copy.deepcopy(scenario), pol_2)
    assert res_2["status"] == "completed"
    boards_2 = [
        e for e in res_2["event_trace"]
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    ]
    board_intervals_2 = [
        (e["time_ms"], e["time_ms"] + 180000) for e in boards_2
    ]
    max_overlap_2 = 0
    for t, _ in board_intervals_2:
        overlap = sum(1 for start, end in board_intervals_2 if start <= t < end)
        max_overlap_2 = max(max_overlap_2, overlap)
    assert max_overlap_2 == 2

    # Test 4 berths
    pol_4 = copy.deepcopy(base_policy)
    pol_4["vehicle_dispatch_rule"]["simultaneous_boarding_berths"] = 4
    res_4 = simulate(copy.deepcopy(scenario), pol_4)
    assert res_4["status"] == "completed"
    boards_4 = [
        e for e in res_4["event_trace"]
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    ]
    board_intervals_4 = [
        (e["time_ms"], e["time_ms"] + 180000) for e in boards_4
    ]
    max_overlap_4 = 0
    for t, _ in board_intervals_4:
        overlap = sum(1 for start, end in board_intervals_4 if start <= t < end)
        max_overlap_4 = max(max_overlap_4, overlap)
    assert max_overlap_4 >= 3


def test_ppsl_worker_accounting_for_berths():
    """Active boarding berths consume 2 PPSL workers each from the 154-worker budget."""
    scenario, base_policy = build_whole_campus_full_cohort_case()

    # If policy configures 4 berths but restricts assigned workers to 2, only 1 berth can be active
    pol_constrained = copy.deepcopy(base_policy)
    pol_constrained["vehicle_dispatch_rule"]["simultaneous_boarding_berths"] = 4
    pol_constrained["vehicle_dispatch_rule"]["berth_workers"] = 2  # Only 1 berth (2 workers // 2 = 1)
    res_constrained = simulate(copy.deepcopy(scenario), pol_constrained)
    assert res_constrained["status"] == "completed"
    boards = [
        e for e in res_constrained["event_trace"]
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    ]
    intervals = [(e["time_ms"], e["time_ms"] + 180000) for e in boards]
    max_overlap = max(sum(1 for start, end in intervals if start <= t < end) for t, _ in intervals)
    assert max_overlap == 1

    # If 4 workers are assigned, up to 2 berths can board concurrently
    pol_4w = copy.deepcopy(base_policy)
    pol_4w["vehicle_dispatch_rule"]["simultaneous_boarding_berths"] = 4
    pol_4w["vehicle_dispatch_rule"]["berth_workers"] = 4  # 4 // 2 = 2 berths
    res_4w = simulate(copy.deepcopy(scenario), pol_4w)
    assert res_4w["status"] == "completed"
    boards_4w = [
        e for e in res_4w["event_trace"]
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    ]
    intervals_4w = [(e["time_ms"], e["time_ms"] + 180000) for e in boards_4w]
    max_overlap_4w = max(sum(1 for start, end in intervals_4w if start <= t < end) for t, _ in intervals_4w)
    assert max_overlap_4w == 2


def test_strict_3000_dtsp_capacity_and_g03_overflow():
    """DTSP usable seating capacity is strictly 3,000 with Bangunan G03 500-seat overflow."""
    scenario, policy = build_whole_campus_full_cohort_case()
    places = {p["id"]: p for p in scenario["places"]}

    assert places["dtsp_seating"]["capacity_students"] == 3000
    assert places["dtsp_seating"]["operating_limit_students"] == 3000
    assert places["g03_seating"]["capacity_students"] in (500, 600)
    assert places["g03_seating"]["operating_limit_students"] in (500, 600)
    assert scenario["destination"]["overflow_destination"]["available_seats"] in (500, 600)

    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    assert res["measures"]["completed_students"] == 3543

    trace = res["event_trace"]
    dtsp_seated = sum(
        e.get("student_count", 1)
        for e in trace
        if e.get("event_type") == "seated_completion" and e.get("place_id") == "dtsp_seating"
    )
    g03_seated = sum(
        e.get("student_count", 1)
        for e in trace
        if e.get("event_type") == "seated_completion" and e.get("place_id") == "g03_seating"
    )
    assert dtsp_seated == 3000
    assert g03_seated == 543
    assert dtsp_seated + g03_seated == 3543

    # Confirm cohort diverted events were emitted for overflow
    diverted_events = [e for e in trace if e.get("event_type") == "cohort_diverted"]
    assert len(diverted_events) > 0
    for de in diverted_events:
        assert de["from_place_id"] == "dtsp_exterior_gathering"
        assert de["to_place_id"] == "g03_foyer_entrance"


def test_deadline_alignment_to_0900():
    """Full-cohort scenario deadline_s aligns start_time_local to 09:00:00."""
    scenario, _ = build_whole_campus_full_cohort_case()
    assert scenario["start_time_local"] == "06:30:00"
    assert scenario["deadline_s"] == 9000

    # Start: 06:30:00 = 6*3600 + 30*60 = 23,400 seconds
    start_s = 6 * 3600 + 30 * 60
    assert start_s == 23400

    # Deadline: 09:00:00 = 9*3600 = 32,400 seconds
    target_s = 9 * 3600
    assert target_s == 32400

    # Exact alignment
    assert start_s + scenario["deadline_s"] == target_s
