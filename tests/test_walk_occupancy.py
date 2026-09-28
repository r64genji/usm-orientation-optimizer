"""Occupancy-dependent walk clocks on campus ops physics."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from usm_sim import (
    build_artificial_single_server_case,
    build_restu_17sep_replay,
    build_whole_campus_origins_case,
    simulate,
)
from usm_sim.campus import FREE_WALK_M_S, SHARED_PATH_JALAN_UNIVERSITI_EAST, SLOWER_WALK_M_S

REPO_ROOT = Path(__file__).resolve().parent.parent
CONGESTED_FACTOR = FREE_WALK_M_S / SLOWER_WALK_M_S
UNIQUE_S = 100.0
EXTRA_S = 400.0


def _members(prefix: str, n: int, unit_id: str, hostel_id: str) -> list[dict]:
    return [
        {
            "student_key": f"{prefix}{index:03d}",
            "queue_tie_key": f"{index:03d}",
            "source_unit_id": unit_id,
            "hostel_id": hostel_id,
        }
        for index in range(n)
    ]


def _two_group_walk_case(
    *,
    count_a: int,
    count_b: int,
    ready_b_s: float,
    occupancy_rule: dict | None,
    extra_s: float = EXTRA_S,
    capacity: int = 200,
    operating_limit: int = 60,
) -> tuple[dict, dict]:
    members_a = _members("a", count_a, "su_a", "hostel_a")
    members_b = _members("b", count_b, "su_b", "hostel_b")
    scenario, policy = build_artificial_single_server_case()
    scenario = copy.deepcopy(scenario)
    policy = copy.deepcopy(policy)
    scenario["scenario_id"] = "walk_occupancy_two_group"
    scenario["source_units"] = [
        {
            "id": "su_a",
            "hostel_id": "hostel_a",
            "estimated_attendance": count_a,
            "resolved_attendance": count_a,
            "actual_reporting_s": 0,
            "readiness_s": 0,
        },
        {
            "id": "su_b",
            "hostel_id": "hostel_b",
            "estimated_attendance": count_b,
            "resolved_attendance": count_b,
            "actual_reporting_s": ready_b_s,
            "readiness_s": ready_b_s,
        },
    ]
    scenario["places"] = [
        {
            "id": "origin_a",
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "meaning": "origin a",
            "capacity_constraint": "unbounded",
        },
        {
            "id": "origin_b",
            "latitude_deg": 0.0,
            "longitude_deg": 0.01,
            "meaning": "origin b",
            "capacity_constraint": "unbounded",
        },
        {
            "id": "dest",
            "latitude_deg": 0.001,
            "longitude_deg": 0.0,
            "meaning": "dest",
            "capacity_constraint": "unbounded",
        },
    ]
    scenario["route_legs"] = [
        {
            "id": "walk_a",
            "from_place_id": "origin_a",
            "to_place_id": "dest",
            "duration_s": UNIQUE_S,
            "mode": "walk",
            "shared_resource_ids": [SHARED_PATH_JALAN_UNIVERSITI_EAST],
        },
        {
            "id": "walk_b",
            "from_place_id": "origin_b",
            "to_place_id": "dest",
            "duration_s": UNIQUE_S,
            "mode": "walk",
            "shared_resource_ids": [SHARED_PATH_JALAN_UNIVERSITI_EAST],
        },
    ]
    scenario["route_stages"] = [
        {"id": "walk_a", "kind": "travel", "leg_id": "walk_a"},
        {"id": "walk_b", "kind": "travel", "leg_id": "walk_b"},
    ]
    scenario["routes"] = {"hostel_a": ["walk_a"], "hostel_b": ["walk_b"]}
    scenario["shared_resources"] = [
        {
            "id": SHARED_PATH_JALAN_UNIVERSITI_EAST,
            "kind": "path",
            "capacity_students": capacity,
            "operating_limit_students": operating_limit,
            "duration_s": extra_s,
        }
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_a",
            "group_id": "g_a",
            "source_unit_id": "su_a",
            "place_id": "origin_a",
            "hostel_id": "hostel_a",
            "hostel_composition": {"hostel_a": count_a},
            "members": members_a,
        },
        {
            "part_id": "part_b",
            "group_id": "g_b",
            "source_unit_id": "su_b",
            "place_id": "origin_b",
            "hostel_id": "hostel_b",
            "hostel_composition": {"hostel_b": count_b},
            "members": members_b,
        },
    ]
    scenario["initial_state"]["workers"] = []
    scenario["initial_state"]["vehicles"] = []
    scenario["calendars"] = []
    scenario["operating_rules"]["required_endpoint"] = "stage_complete"
    if occupancy_rule is None:
        scenario["operating_rules"].pop("walk_occupancy_rule", None)
    else:
        scenario["operating_rules"]["walk_occupancy_rule"] = occupancy_rule
    scenario["simulation_end_s"] = 20000
    scenario["deadline_s"] = 20000
    policy["grouping"] = {"mode": "explicit_parts"}
    policy["required_endpoint"] = "stage_complete"
    policy["random_seed"] = 0
    return scenario, policy


def _campus_rule() -> dict:
    return {
        "type": "two_band",
        "empty_means": "other_students_on_path",
        "empty_duration_factor": 1.0,
        "congested_duration_factor": CONGESTED_FACTOR,
        "congested_at": "operating_limit",
        "shared_extra_when": "occupancy_ahead_gt_0",
        "source": "assumed",
        "note": "empty=FREE_WALK_M_S; congested=SLOWER_WALK_M_S; not GPS",
    }


def _depart(result: dict, part_id: str) -> dict:
    for event in result["event_trace"]:
        if event["event_type"] == "departure" and event.get("affected_part_id") == part_id:
            return event
    raise AssertionError(f"no departure for {part_id}")


def _arrive(result: dict, part_id: str) -> dict:
    for event in result["event_trace"]:
        if event["event_type"] == "arrival" and event.get("affected_part_id") == part_id:
            return event
    raise AssertionError(f"no arrival for {part_id}")


def test_campus_declares_occupancy_rule_restu_does_not():
    campus, _ = build_whole_campus_origins_case()
    restu, _ = build_restu_17sep_replay(REPO_ROOT)
    campus_rule = campus["operating_rules"].get("walk_occupancy_rule")
    assert campus_rule is not None
    assert campus_rule["type"] == "two_band"
    assert campus_rule["empty_duration_factor"] == 1.0
    assert campus_rule["congested_duration_factor"] == CONGESTED_FACTOR
    assert restu["operating_rules"].get("walk_occupancy_rule") is None


def test_empty_path_does_not_add_shared_extra():
    scenario, policy = _two_group_walk_case(
        count_a=8,
        count_b=8,
        ready_b_s=UNIQUE_S,
        occupancy_rule=_campus_rule(),
    )
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    first = _depart(result, "part_a")
    leftover = _depart(result, "part_b")
    assert first["walk_occupancy_ahead"] == 0
    assert leftover["walk_occupancy_ahead"] == 0
    assert first["walk_shared_extra_s"] == 0
    assert leftover["walk_shared_extra_s"] == 0
    assert first["walk_duration_s"] == UNIQUE_S
    assert leftover["walk_duration_s"] == UNIQUE_S
    assert _arrive(result, "part_a")["time_ms"] == 100000
    assert leftover["time_ms"] == 100000
    assert _arrive(result, "part_b")["time_ms"] == 200000


def test_overlap_below_limit_adds_shared_extra_at_empty_factor():
    scenario, policy = _two_group_walk_case(
        count_a=8,
        count_b=8,
        ready_b_s=10,
        occupancy_rule=_campus_rule(),
    )
    result = simulate(scenario, policy)
    leftover = _depart(result, "part_b")
    assert leftover["walk_occupancy_ahead"] == 8
    assert leftover["walk_occupancy_factor"] == 1.0
    assert leftover["walk_shared_extra_s"] == EXTRA_S
    assert leftover["walk_duration_s"] == UNIQUE_S + EXTRA_S
    assert leftover["time_ms"] == 10000
    assert _arrive(result, "part_b")["time_ms"] == 510000


def test_packed_path_uses_congested_factor_on_unique_and_extra():
    scenario, policy = _two_group_walk_case(
        count_a=60,
        count_b=8,
        ready_b_s=10,
        occupancy_rule=_campus_rule(),
    )
    result = simulate(scenario, policy)
    leftover = _depart(result, "part_b")
    expected = (UNIQUE_S + EXTRA_S) * CONGESTED_FACTOR
    assert leftover["walk_occupancy_ahead"] == 60
    assert leftover["walk_occupancy_factor"] == CONGESTED_FACTOR
    assert leftover["walk_duration_s"] == pytest.approx(expected)
    assert _arrive(result, "part_b")["time_ms"] == 10000 + int(round(expected * 1000))


def test_no_rule_still_always_adds_shared_extra():
    scenario, policy = _two_group_walk_case(
        count_a=8,
        count_b=8,
        ready_b_s=UNIQUE_S,
        occupancy_rule=None,
    )
    result = simulate(scenario, policy)
    first = _depart(result, "part_a")
    leftover = _depart(result, "part_b")
    assert "walk_occupancy_ahead" not in first
    assert _arrive(result, "part_a")["time_ms"] == int((UNIQUE_S + EXTRA_S) * 1000)
    assert leftover["time_ms"] == 100000
    assert _arrive(result, "part_b")["time_ms"] == 100000 + int((UNIQUE_S + EXTRA_S) * 1000)


def test_packed_shared_extra_change_moves_overlapping_walker():
    base, policy = _two_group_walk_case(
        count_a=60,
        count_b=8,
        ready_b_s=10,
        occupancy_rule=_campus_rule(),
        extra_s=EXTRA_S,
    )
    changed = copy.deepcopy(base)
    changed["shared_resources"][0]["duration_s"] = EXTRA_S + 180
    result_a = simulate(base, policy)
    result_b = simulate(changed, policy)
    arrive_a = _arrive(result_a, "part_b")["time_ms"]
    arrive_b = _arrive(result_b, "part_b")["time_ms"]
    assert arrive_b - arrive_a == int(round(180 * CONGESTED_FACTOR * 1000))


def test_restu_replay_clocks_unchanged_without_occupancy_rule():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    first = simulate(scenario, policy)
    second = simulate(scenario, policy)
    assert scenario["operating_rules"].get("walk_occupancy_rule") is None
    first_times = [
        (event["event_type"], event.get("place_id"), event["time_ms"])
        for event in first["event_trace"]
        if event["event_type"] in {"departure", "arrival", "hall_area_arrival"}
    ]
    second_times = [
        (event["event_type"], event.get("place_id"), event["time_ms"])
        for event in second["event_trace"]
        if event["event_type"] in {"departure", "arrival", "hall_area_arrival"}
    ]
    assert first_times == second_times
    assert first["status"] == second["status"] == "completed"


def test_occupancy_walk_is_deterministic():
    scenario, policy = _two_group_walk_case(
        count_a=60,
        count_b=8,
        ready_b_s=10,
        occupancy_rule=_campus_rule(),
    )
    policy["random_seed"] = 0
    a = simulate(scenario, policy)
    b = simulate(scenario, policy)
    assert [event["time_ms"] for event in a["event_trace"]] == [
        event["time_ms"] for event in b["event_trace"]
    ]
