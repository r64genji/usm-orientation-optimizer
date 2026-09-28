"""Acceptance tests for ticket 06: finite space, spillback, reports, and holds."""

from __future__ import annotations

from pathlib import Path

import pytest

from usm_sim import (
    SimulationError,
    build_blocked_walk_case,
    build_changing_conditions_case,
    build_deadlock_with_valid_wait_case,
    build_delayed_report_case,
    build_door_reopen_case,
    build_full_destination_arriving_bus_case,
    build_hold_resume_case,
    build_initial_inflight_and_background_case,
    build_no_waiting_space_case,
    build_operating_limit_event_case,
    build_partial_service_flow_case,
    build_reserve_before_departure_case,
    build_restu_17sep_replay,
    build_shared_congestion_bus_case,
    build_shared_congestion_walk_case,
    build_time_limit_incomplete_case,
    simulate,
)
from usm_sim.spillback_cases import (
    constrained_place,
    _unbounded,
    _shell,
    _members,
    _part,
    _unit,
)
from usm_sim.accuracy import first_match

REPO_ROOT = Path(__file__).resolve().parent.parent


def _occ(result: dict, place_id: str) -> dict:
    return next(row for row in result["place_occupancy"] if row["place_id"] == place_id)


def _peak(result: dict, place_id: str) -> int:
    peak = 0
    running = 0
    for row in result["occupancy_history"]:
        if row.get("place_id") != place_id:
            continue
        if row.get("direction") == "in":
            running += int(row.get("student_count") or 0)
        else:
            running -= int(row.get("student_count") or 0)
        peak = max(peak, running)
    return peak


def test_constrained_location_fields_are_present():
    scenario, policy = build_blocked_walk_case()
    places = {row["id"]: row for row in scenario["places"]}
    hall = places["hall"]
    assert hall["constrained"] is True
    assert hall["physical_capacity_students"] == 4
    assert hall["operating_limit_students"] <= hall["physical_capacity_students"]
    assert hall["preceding_place_id"] == "path_hold"
    assert hall["queue_discipline"] == "fcfs"
    assert hall["priority_rule"] == "arrival_order"
    assert hall["service_rule"]
    path = places["path_hold"]
    assert path["physical_capacity_students"] == 8
    assert policy["destination_space_rule"] == "allow_approach_wait"
    assert policy["coordination_delay_s"] == 0
    result = simulate(scenario, policy)
    assert result["status"] in {"completed", "incomplete", "infeasible"}


def test_rst_recorded_places_are_separate_and_capacities_are_not_gps():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    places = {row["id"]: row for row in scenario["places"]}
    for place_id in (
        "restu_gathering",
        "rst_bus_wait",
        "dtsp_alighting_area",
        "dtsp_exterior_gathering",
        "rst_rain_shelter",
    ):
        assert place_id in places
        place = places[place_id]
        assert place["capacity_from_gps_scatter"] is False
        assert place.get("estimated_capacity_students")
        if place.get("gps_observation"):
            assert "storage-capacity" in place["gps_observation"]["note"].lower() or (
                "not an area" in place["gps_observation"]["note"].lower()
            )
            assert place["estimated_capacity_students"] != place["gps_observation"].get(
                "sample_count"
            )
    assert "rst_rain_bus_wait" not in places
    repeats = places["rst_bus_wait"]["repeat_observations"]
    assert any(row["id"] == "rst_rain_bus_wait" for row in repeats)
    exterior_ids = [row["id"] for row in scenario["places"] if "exterior" in row["id"]]
    assert exterior_ids == ["dtsp_exterior_gathering"]
    result = simulate(scenario, policy)
    assert result["status"] == "completed"


def test_full_destination_arriving_bus_waits_in_declared_queue_or_aboard():
    scenario, policy = build_full_destination_arriving_bus_case()
    result = simulate(scenario, policy)
    hall = _occ(result, "hall")
    assert hall["occupancy_students"] <= 4
    assert _peak(result, "hall") <= 4
    assert result["occupancy_integrity"]["physical_excess_events"] == []
    assert not any(
        event["event_type"] == "vehicle_return_complete" for event in result["event_trace"]
    )
    blocked = [
        event
        for event in result["event_trace"]
        if event["event_type"] in {"physical_block", "hold_start"}
        and event.get("passengers_aboard")
        or (
            event["event_type"] == "physical_block"
            and event.get("place_id") == "bus_approach"
        )
    ]
    assert blocked
    bus_part = next(
        row
        for row in result["unfinished_demand"]
        if row["part_id"] == "part_bus" or "bus" in (row.get("group_id") or "")
    )
    assert bus_part["student_count"] == 4
    assert bus_part["place_id"] == "bus_approach"
    holds = [row for row in result["active_holds"] if row.get("aboard") or row["place_id"] == "bus_approach"]
    assert holds
    assert all(row.get("aboard") for row in holds if row["part_id"] == "part_bus")
    resource = next(row for row in result["resource_summaries"] if row["resource_id"] == "bus_1")
    assert resource["busy"] is True
    wait_class = result["measures"]["waiting_student_s_by_class"]
    assert wait_class.get("physical_blocking", 0) > 0


def test_blocked_walk_occupies_preceding_hold():
    scenario, policy = build_blocked_walk_case()
    result = simulate(scenario, policy)
    assert _peak(result, "hall") <= 4
    assert _occ(result, "path_hold")["occupancy_students"] == 4
    assert _peak(result, "path_hold") <= 8
    walk = next(row for row in result["unfinished_demand"] if row["part_id"] == "part_walk")
    assert walk["place_id"] == "path_hold"
    assert any(
        event["event_type"] == "physical_block" and event.get("place_id") == "path_hold"
        for event in result["event_trace"]
    )
    assert result["measures"]["waiting_student_s_by_class"].get("physical_blocking", 0) > 0
    escort_events = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "worker_reserved" and event.get("affected_part_id") == "part_walk"
    ]
    assert escort_events
    walk_holds = [row for row in result["active_holds"] if row["part_id"] == "part_walk"]
    assert walk_holds


def test_delayed_report_does_not_use_undelivered_information():
    scenario, policy = build_delayed_report_case(delay_s=30)
    result = simulate(scenario, policy)
    assert policy["coordination_delay_s"] == 30
    b_depart = next(
        (
            event
            for event in result["event_trace"]
            if event["event_type"] == "departure" and event.get("affected_part_id") == "part_b"
        ),
        None,
    )
    assert b_depart is not None
    assert b_depart["time_ms"] == pytest.approx(20000, abs=1)
    delivered = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "report_delivered" and event.get("place_id") == "hall"
    ]
    assert delivered
    first_full = next(
        event for event in delivered if int(event.get("occupancy_students") or 0) >= 4
    )
    assert first_full["delivery_ms"] >= first_full["observation_ms"] + 30000
    assert b_depart["time_ms"] < first_full["time_ms"]
    c_depart = next(
        (
            event
            for event in result["event_trace"]
            if event["event_type"] == "departure" and event.get("affected_part_id") == "part_c"
        ),
        None,
    )
    assert c_depart is None
    assert any(
        event["event_type"] == "policy_hold" for event in result["event_trace"]
    )
    assert _peak(result, "hall") <= 4
    b_unfinished = next(
        row for row in result["unfinished_demand"] if row["part_id"] == "part_b"
    )
    assert b_unfinished["place_id"] == "approach"


def test_reopening_after_hold_resumes_releases():
    scenario, policy = build_hold_resume_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["completed_students"] == 8
    assert any(event["event_type"] == "policy_hold" for event in result["event_trace"])
    assert any(event["event_type"] == "policy_resume" for event in result["event_trace"])
    b_depart = next(
        event
        for event in result["event_trace"]
        if event["event_type"] == "departure" and event.get("affected_part_id") == "part_b"
    )
    hold = next(
        event for event in result["event_trace"] if event["event_type"] == "policy_hold"
    )
    resume = next(
        event for event in result["event_trace"] if event["event_type"] == "policy_resume"
    )
    assert resume["time_ms"] >= hold["time_ms"] + 4000
    assert b_depart["time_ms"] >= resume["time_ms"]
    door_scenario, door_policy = build_door_reopen_case()
    door = simulate(door_scenario, door_policy)
    assert door["status"] == "completed"
    depart = next(
        event for event in door["event_trace"] if event["event_type"] == "departure"
    )
    assert depart["time_ms"] >= 12000


def test_shared_arrivals_move_congestion_and_more_buses_do_not_enlarge_the_hall():
    walk_scenario, walk_policy = build_shared_congestion_walk_case()
    walk = simulate(walk_scenario, walk_policy)
    assert _peak(walk, "hall") <= 4
    assert _occ(walk, "shared_path")["occupancy_students"] >= 4
    one_scenario, one_policy = build_shared_congestion_bus_case(n_buses=1)
    two_scenario, two_policy = build_shared_congestion_bus_case(n_buses=2)
    one = simulate(one_scenario, one_policy)
    two = simulate(two_scenario, two_policy)
    assert _peak(one, "hall") <= 4
    assert _peak(two, "hall") <= 4
    two_hall = _occ(two, "hall")["occupancy_students"]
    one_hall = _occ(one, "hall")["occupancy_students"]
    assert two_hall == one_hall
    two_approach = _occ(two, "bus_approach")["occupancy_vehicles"]
    one_approach = _occ(one, "bus_approach")["occupancy_vehicles"]
    assert two_approach >= one_approach
    assert two["measures"]["waiting_student_s_by_class"].get("physical_blocking", 0) >= one[
        "measures"
    ]["waiting_student_s_by_class"].get("physical_blocking", 0)


def test_no_physical_waiting_space_is_infeasible():
    scenario, policy = build_no_waiting_space_case()
    result = simulate(scenario, policy)
    assert result["status"] == "infeasible"
    assert result["termination_cause"] == "no_waiting_space"
    assert any(row.get("type") == "no_waiting_space" for row in result["violations"])
    assert _peak(result, "hall") <= 2
    assert any(event["event_type"] == "denied_entry" for event in result["event_trace"])
    wait_class = result["measures"]["waiting_student_s_by_class"]
    assert wait_class.get("denied_entry", 0) > 0


def test_deadlock_with_unfinished_students_is_incomplete():
    scenario, policy = build_deadlock_with_valid_wait_case()
    result = simulate(scenario, policy)
    assert result["status"] == "incomplete"
    assert result["status"] != "completed"
    assert result["termination_cause"] == "deadlock"
    assert result["measures"]["unfinished_students"] == 8
    assert _peak(result, "hall") <= 4
    assert _occ(result, "path_hold")["occupancy_students"] == 4


def test_time_limit_is_incomplete_with_unfinished_demand():
    scenario, policy = build_time_limit_incomplete_case()
    result = simulate(scenario, policy)
    assert result["status"] == "incomplete"
    assert result["termination_cause"] == "simulation_end_s"
    assert result["unfinished_demand"]
    assert result["measures"]["unfinished_students"] == 4


def test_partial_service_records_in_out_and_travel_time_is_not_flow_limit():
    scenario, policy = build_partial_service_flow_case()
    leg = scenario["route_legs"][0]
    assert leg["duration_s"] == 60
    assert leg["flow_limit_students"] == 2
    assert leg["duration_s"] != leg["flow_limit_students"]
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    ins = [row for row in result["occupancy_history"] if row["place_id"] == "entrance" and row["direction"] == "in"]
    outs = [row for row in result["occupancy_history"] if row["place_id"] == "entrance" and row["direction"] == "out"]
    assert ins
    assert outs
    assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(60.0)
    times = [row["completion_time_s"] for row in result["outcomes"]["student_completions"]]
    assert times == [70, 80, 90, 100]


def test_operating_limit_is_an_event_not_a_physical_failure():
    scenario, policy = build_operating_limit_event_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert any(
        event["event_type"] == "operating_limit_exceeded" for event in result["event_trace"]
    )
    assert _peak(result, "yard") == 6
    assert _peak(result, "yard") <= 10
    assert not any(row.get("type") == "physical_capacity" for row in result["violations"])


def test_reserve_before_departure_does_not_leave_without_a_slot():
    scenario, policy = build_reserve_before_departure_case()
    result = simulate(scenario, policy)
    assert policy["destination_space_rule"] == "reserve_before_departure"
    b_depart = next(
        (
            event
            for event in result["event_trace"]
            if event["event_type"] == "departure" and event.get("affected_part_id") == "part_b"
        ),
        None,
    )
    assert b_depart is None
    assert _peak(result, "hall") <= 4
    b_left = next(row for row in result["unfinished_demand"] if row["part_id"] == "part_b")
    assert b_left["place_id"] == "origin"


def test_wait_classes_are_distinct():
    scenario, policy = build_blocked_walk_case()
    result = simulate(scenario, policy)
    classes = result["measures"]["waiting_student_s_by_class"]
    for name in (
        "queue_waiting",
        "intentional_hold",
        "physical_blocking",
        "resource_waiting",
        "denied_entry",
    ):
        assert name in classes
    assert classes.get("physical_blocking", 0) > 0
    assert classes.get("intentional_hold", 0) > 0
    assert any(event["event_type"] == "physical_block" for event in result["event_trace"])


def test_changing_conditions_are_shared_and_forecast_is_separate():
    scenario, policy = build_changing_conditions_case()
    rain = scenario["external_conditions"][0]
    assert rain["forecast"]["kind"] == "clear"
    assert rain["effects"]["walking_rate_factor"] == 0.5
    assert rain["shared"] is True
    result = simulate(scenario, policy)
    kinds = {event["event_type"] for event in result["event_trace"]}
    assert "condition_change" in kinds
    rain_event = next(
        event
        for event in result["event_trace"]
        if event["event_type"] == "condition_change" and event.get("condition_kind") == "rain"
    )
    assert rain_event.get("forecast")["kind"] == "clear"
    arrivals = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "arrival" and event.get("place_id") == "hall"
    ]
    assert len(arrivals) >= 1
    reports = [row for row in result["reports"] if row.get("kind") == "condition"]
    assert reports
    assert reports[0]["delivery_ms"] >= reports[0]["observation_ms"] + 10000


def test_initial_inflight_queues_and_background_are_explicit():
    scenario, policy = build_initial_inflight_and_background_case()
    moving = scenario["initial_state"]["students"][0]
    assert moving["status"] == "travelling"
    assert moving["leg_id"] == "leg_walk"
    assert moving["arrival_s"] == 12
    assert scenario["initial_state"]["queues"][0]["student_count"] == 3
    assert scenario["background_demand"]["occupancy_by_place"]["hall"] == 3
    result = simulate(scenario, policy)
    arrive = next(
        event
        for event in result["event_trace"]
        if event["event_type"] == "arrival" and event.get("affected_part_id") == "part_move"
    )
    assert arrive["time_ms"] == pytest.approx(12000, abs=1)
    assert _occ(result, "hall")["occupancy_students"] == 3
    assert _peak(result, "hall") == 5
    assert result["background_demand"]["pedestrians"] == 3


def test_operating_limit_above_physical_is_rejected():
    scenario, policy = build_operating_limit_event_case()
    scenario["places"][1]["operating_limit_students"] = 99
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "invalid_value_or_unit"


def test_space_rule_requires_explicit_coordination_delay():
    scenario, policy = build_blocked_walk_case()
    del policy["coordination_delay_s"]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.field == "policy.coordination_delay_s"


def test_ticket01_restu_still_meets_timing_bounds():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    trace = result["event_trace"]
    from datetime import datetime
    from zoneinfo import ZoneInfo

    kl = ZoneInfo("Asia/Kuala_Lumpur")
    start = datetime(2026, 9, 17, 6, 47, 12, tzinfo=kl)

    def offset(hour, minute, second=0):
        stamp = datetime(2026, 9, 17, hour, minute, second, tzinfo=kl)
        return (stamp - start).total_seconds()

    def error_s(event, observed_s):
        return abs(event["time_ms"] / 1000.0 - observed_s)

    bus_queue = first_match(trace, {"event_type": "arrival", "place_id": "rst_bus_wait"})
    bus_depart = first_match(trace, {"event_type": "departure", "leg_id": "leg_coach_transit"})
    dtsp_arrive = first_match(trace, {"event_type": "arrival", "place_id": "dtsp_alighting_area"})
    hall_arrive = first_match(trace, {"event_type": "hall_area_arrival"})
    assert error_s(bus_queue, offset(7, 49)) <= 600
    assert error_s(bus_depart, offset(7, 58)) <= 600
    assert error_s(dtsp_arrive, offset(8, 1, 30)) <= 600
    assert error_s(hall_arrive, offset(8, 35)) <= 600
    coach_s = (dtsp_arrive["time_ms"] - bus_depart["time_ms"]) / 1000.0
    assert 120 <= coach_s <= 270


def test_serviceable_initial_queue_drains_and_releases_capacity_unlike_permanent_background():
    places = [
        constrained_place("desk", 0.0, 0.0, "desk", physical=10, operating=10, preceding="entry"),
        _unbounded("entry", 0.0, 0.0, "entry"),
    ]
    stages = [
        {"id": "svc", "kind": "queue_service", "place_id": "desk", "server_count": 1, "service_duration_s": 10.0},
    ]
    scenario, policy = _shell(
        scenario_id="serviceable_queue_drain_v1",
        places=places,
        legs=[{"id": "leg_dummy", "from_place_id": "entry", "to_place_id": "desk", "duration_s": 1.0, "mode": "walk"}],
        stages=stages,
        students=[_part("part_p", "g_p", "su_p", "desk", _members("p", 2, "su_p"))],
        source_units=[_unit("su_p", 2, "hostel_p")],
        policy_id="serviceable_queue_policy_v1",
        queues=[{"place_id": "desk", "student_count": 3, "serviceable": True}],
        simulation_end_s=100,
        deadline_s=100,
        operating_extra={"required_endpoint": "stage_complete"},
    )
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["completed_students"] == 2
    assert result["measures"]["accounted_students"] == 2
    trace = result["event_trace"]
    service_completes = [e for e in trace if e["event_type"] == "service_complete" and e["place_id"] == "desk"]
    assert len(service_completes) >= 3
    assert any(e.get("affected_part_id") == "init_q_desk_0" for e in service_completes)
    final_desk_occ = _occ(result, "desk")["occupancy_students"]
    assert final_desk_occ == 0

    # Compare with permanent background occupancy: does not drain!
    scenario_perm, policy_perm = _shell(
        scenario_id="perm_background_v1",
        places=places,
        legs=[{"id": "leg_dummy", "from_place_id": "entry", "to_place_id": "desk", "duration_s": 1.0, "mode": "walk"}],
        stages=stages,
        students=[_part("part_p", "g_p", "su_p", "desk", _members("p", 2, "su_p"))],
        source_units=[_unit("su_p", 2, "hostel_p")],
        policy_id="serviceable_queue_policy_v1",
        queues=[{"place_id": "desk", "student_count": 3, "permanent_background": True}],
        simulation_end_s=100,
        deadline_s=100,
        operating_extra={"required_endpoint": "stage_complete"},
    )
    result_perm = simulate(scenario_perm, policy_perm)
    assert _occ(result_perm, "desk")["occupancy_students"] >= 3
