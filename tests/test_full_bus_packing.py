"""Tests for full vehicle capacity bus packing from continuous queue and continuous streaming."""

from __future__ import annotations

import copy
from usm_sim import (
    build_ticket02_bus_case,
    build_whole_campus_full_cohort_case,
    simulate,
)


def test_continuous_queue_full_packing_80_coaches_40_electric():
    """Shuttle buses pack from the continuous queue to full capacity (80 on coaches, 40 on electric)."""
    scenario, policy = build_whole_campus_full_cohort_case()
    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    assert res["measures"]["completed_students"] == 3543

    events = res["event_trace"]
    board_events = [
        e for e in events
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    ]
    coaches = [
        e for e in board_events
        if any(rid.startswith("coach_") for rid in e.get("resource_ids", []))
    ]
    electrics = [
        e for e in board_events
        if any(rid.startswith("electric_") for rid in e.get("resource_ids", []))
    ]

    # Coaches pack to full 80 capacity from smaller 20-student parts
    coaches_80 = [e for e in coaches if e["student_count"] == 80]
    assert len(coaches_80) > 0, "Expected coaches to pack to 80 students"
    # Electric buses pack to full 40 capacity from smaller 20-student parts
    electrics_40 = [e for e in electrics if e["student_count"] == 40]
    assert len(electrics_40) > 0, "Expected electric buses to pack to 40 students"

    # All electric dispatches are at full 40-student capacity
    assert all(e["student_count"] == 40 for e in electrics)


def test_boarding_and_alighting_dwells_180s():
    """Full vehicle loads observe the required 180s boarding and 180s alighting dwells."""
    scenario, policy = build_whole_campus_full_cohort_case()
    res = simulate(scenario, policy)
    events = res["event_trace"]

    # Verify boarding dwell duration = 180,000 ms (180s)
    board_starts = {
        e["time_ms"]: e for e in events
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    }
    board_completes = [
        e for e in events
        if e.get("event_type") == "batch_complete" and e.get("primary_cause") == "board"
    ]
    assert len(board_completes) > 0
    for bc in board_completes:
        expected_start = bc["time_ms"] - 180000
        assert expected_start in board_starts, f"Expected board_start 180s prior at {expected_start}"

    # Verify alighting dwell duration = 180,000 ms (180s)
    alight_starts = {
        e["time_ms"]: e for e in events
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "alight"
    }
    alight_completes = [
        e for e in events
        if e.get("event_type") == "batch_complete" and e.get("primary_cause") == "alight"
    ]
    assert len(alight_completes) > 0
    for ac in alight_completes:
        expected_start = ac["time_ms"] - 180000
        assert expected_start in alight_starts, f"Expected alight_start 180s prior at {expected_start}"


def test_dtsp_alighting_area_unloads_full_combined_passenger_count():
    """DTSP alighting area unloads the full combined passenger count (e.g. 80 on coaches, 40 on electric)."""
    scenario, policy = build_whole_campus_full_cohort_case()
    res = simulate(scenario, policy)
    events = res["event_trace"]

    alight_events = [
        e for e in events
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "alight"
    ]
    alight_counts = {e["student_count"] for e in alight_events}
    assert 80 in alight_counts, "Expected full 80-passenger coach alighting"
    assert 40 in alight_counts, "Expected full 40-passenger electric bus alighting"


def test_partial_part_splitting_packs_bus_and_leaves_remainder_front_of_queue():
    """When a waiting part exceeds remaining vehicle capacity, it splits and packs the bus, leaving remainder at front."""
    scenario, policy = build_ticket02_bus_case(
        grouping_basis="wing",
        split_policy="permit_supervised_split",
        bus_capacity=50,
        n_buses=1,
        include_cycle=True,
    )
    # 2 wings of 60 students each = 120 students total.
    # Bus capacity 50:
    # Trip 1: Wing 1 splits into 50 (boards) and 10 (remainder at front of queue).
    # Trip 2: Remainder (10) packs with 40 from Wing 2 = 50 students! Leaving 20 remainder.
    # Trip 3: Remainder (20) boards.
    # Total: exactly 3 trips [50, 50, 20] instead of 4 uncombined trips [50, 10, 50, 10].
    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    board_events = [
        e for e in res["event_trace"]
        if e.get("event_type") == "batch_start" and e.get("primary_cause") == "board"
    ]
    counts = [e["student_count"] for e in board_events]
    assert counts == [50, 50, 20], f"Expected packed trips [50, 50, 20], got {counts}"

    # Verify Trip 2 combined remainder of Wing 1 (10) with Wing 2 (40)
    # and that they cleanly unpack upon alighting at dest into 10 and 40
    dest_departures = [
        e for e in res["event_trace"]
        if e.get("event_type") == "departure" and e.get("place_id") == "dest"
    ]
    dep_tuples = [(d["student_count"], d["affected_group_id"]) for d in dest_departures]
    assert (10, "g_wing_spec_hostel_east") in dep_tuples, "Expected 10 east students to alight and depart dest"
    assert (40, "g_wing_spec_hostel_west") in dep_tuples, "Expected 40 west students to alight and depart dest"
    assert (20, "g_wing_spec_hostel_west") in dep_tuples, "Expected 20 west students on trip 3 to alight and depart dest"


def test_continuous_pipeline_dud_across_overpass_to_berth_columns():
    """Walking from DUD across overpass to berth queue is a continuous pipeline without bottlenecks."""
    scenario, policy = build_whole_campus_full_cohort_case()
    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    # Verify no physical capacity violations anywhere in the simulation
    cap_violations = [
        v for v in res.get("violations", [])
        if v.get("type") == "physical_capacity"
    ]
    assert cap_violations == []

    # Verify all 2,162 bus students arrive at rst_bus_wait and board
    events = res["event_trace"]
    wait_arrivals = [
        e for e in events
        if e.get("event_type") == "arrival" and e.get("place_id") == "rst_bus_wait"
    ]
    total_wait_students = sum(e.get("student_count", 0) for e in wait_arrivals)
    assert total_wait_students == 2162, f"Expected 2162 bus students to reach rst_bus_wait, got {total_wait_students}"
