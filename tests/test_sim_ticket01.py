"""Acceptance tests for ticket 01: public Simulate, hand case, Restu replay."""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from usm_sim import (
    EVENT_TYPES,
    FORBIDDEN_MODES,
    RESTU_STAGE_ORDER,
    STAGE_KINDS,
    SimulationError,
    build_artificial_single_server_case,
    build_restu_17sep_replay,
    simulate,
)
from usm_sim.accuracy import first_match

REPO_ROOT = Path(__file__).resolve().parent.parent
KL = ZoneInfo("Asia/Kuala_Lumpur")
RESTU_START = datetime(2026, 9, 17, 6, 47, 12, tzinfo=KL)


def _restu_offset_s(hour: int, minute: int, second: int = 0) -> float:
    stamp = datetime(2026, 9, 17, hour, minute, second, tzinfo=KL)
    return (stamp - RESTU_START).total_seconds()


def _stage_sequence(trace: list[dict]) -> list[str]:
    ordered: list[str] = []
    for event in trace:
        stage_id = event.get("stage_id")
        if stage_id and (not ordered or ordered[-1] != stage_id):
            ordered.append(stage_id)
    return ordered


def test_public_simulate_accepts_resolved_scenario_and_policy():
    scenario, policy = build_artificial_single_server_case()
    result = simulate(scenario, policy)
    assert result["status"] in {"completed", "infeasible", "incomplete"}
    assert result["input_snapshot"]["scenario"]["scenario_id"] == scenario["scenario_id"]
    assert result["input_snapshot"]["policy"]["policy_id"] == policy["policy_id"]
    assert "event_trace" in result
    assert "measures" in result
    assert "outcomes" in result
    assert "limits_reached" in result
    assert "violations" in result
    assert result["versions"]["format_version"] == scenario["format_version"]
    assert result["versions"]["data_version"] == scenario["data_version"]


def test_missing_critical_input_fails_clearly():
    scenario, policy = build_artificial_single_server_case()
    del scenario["deadline_s"]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "missing_input"
    assert caught.value.field == "scenario.deadline_s"
    payload = caught.value.as_dict()
    assert payload["error"] is True
    assert payload["category"] == "missing_input"

    scenario, policy = build_artificial_single_server_case()
    with pytest.raises(SimulationError) as caught_none:
        simulate(None, policy)
    assert caught_none.value.category == "missing_input"

    scenario, policy = build_artificial_single_server_case()
    del scenario["initial_state"]["queues"]
    with pytest.raises(SimulationError) as caught_queues:
        simulate(scenario, policy)
    assert caught_queues.value.category == "missing_input"


def test_determinism_identical_inputs_identical_results():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    first = simulate(scenario, policy)
    second = simulate(scenario, policy)
    assert first["status"] == second["status"]
    assert first["event_trace"] == second["event_trace"]
    assert first["measures"] == second["measures"]
    assert first["outcomes"] == second["outcomes"]
    assert first["result_id"] == second["result_id"]


def test_artificial_hand_calculated_queue_and_partial_lateness():
    """Hand calculation from spec section 21.

    Four students arrive together at t=60 s. One server, 10 s per student,
    starts immediately. Completions 70, 80, 90, 100 s. Queue waiting
    0+10+20+30 = 60 student-seconds. Deadline 95 s: only the last student
    is late, by 5 s.
    """
    scenario, policy = build_artificial_single_server_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"

    completions = result["outcomes"]["student_completions"]
    times = [row["completion_time_s"] for row in completions]
    assert times == [70, 80, 90, 100]
    late = [row for row in completions if row["late_s"] > 0]
    assert len(late) == 1
    assert late[0]["student_key"] == "s4"
    assert late[0]["late_s"] == pytest.approx(5.0)
    assert result["measures"]["late_students"] == 1
    assert result["measures"]["total_lateness_s"] == pytest.approx(5.0)
    assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(60.0)
    assert result["measures"]["total_service_student_s"] == pytest.approx(40.0)

    at_70 = [event for event in result["event_trace"] if event["time_ms"] == 70000]
    types_at_70 = [event["event_type"] for event in at_70]
    assert "service_complete" in types_at_70
    assert "service_start" in types_at_70
    assert types_at_70.index("service_complete") < types_at_70.index("service_start")

    reversed_members, policy = build_artificial_single_server_case()
    reversed_members["initial_state"]["students"][0]["members"] = list(
        reversed(reversed_members["initial_state"]["students"][0]["members"])
    )
    reversed_result = simulate(reversed_members, policy)
    reversed_times = [
        row["completion_time_s"]
        for row in reversed_result["outcomes"]["student_completions"]
    ]
    reversed_keys = [
        row["student_key"]
        for row in reversed_result["outcomes"]["student_completions"]
    ]
    assert reversed_times == [70, 80, 90, 100]
    assert reversed_keys == ["s1", "s2", "s3", "s4"]


def test_restu_replay_preserves_stage_order_and_places():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"

    places = {place["id"]: place for place in scenario["places"]}
    assert places["restu_gathering"]["latitude_deg"] == pytest.approx(5.357387, abs=1e-6)
    assert places["restu_gathering"]["longitude_deg"] == pytest.approx(100.290251, abs=1e-6)
    assert places["rst_bus_wait"]["latitude_deg"] == pytest.approx(5.356036, abs=1e-6)
    assert places["rst_boarding_approach"]["latitude_deg"] == pytest.approx(5.356012, abs=1e-6)
    assert places["dtsp_alighting_area"]["latitude_deg"] == pytest.approx(5.357215, abs=1e-6)
    assert places["dtsp_exterior_gathering"]["latitude_deg"] == pytest.approx(5.357153, abs=1e-6)
    assert places["dtsp_hall_reference"]["latitude_deg"] == pytest.approx(5.35695, abs=1e-5)
    coords = [
        (place["latitude_deg"], place["longitude_deg"]) for place in scenario["places"]
    ]
    assert len(set(coords)) == len(coords)

    for place_id in (
        "restu_gathering",
        "rst_bus_wait",
        "rst_boarding_approach",
        "dtsp_alighting_area",
        "dtsp_exterior_gathering",
    ):
        place = places[place_id]
        assert place.get("gps_observation")
        assert place["capacity_from_gps_scatter"] is False
        assert place["capacity_constraint"] == "unbounded"
        note = place["gps_observation"]["note"].lower()
        assert "not an area" in note or "storage-capacity" in note

    sequence = _stage_sequence(result["event_trace"])
    positions = []
    for stage_id in RESTU_STAGE_ORDER:
        assert stage_id in sequence, f"missing stage {stage_id} in {sequence}"
        positions.append(sequence.index(stage_id))
    assert positions == sorted(positions)

    gathering_hold_s = None
    for delay in result["delay_explanations"]:
        if delay["cause"] == "waiting_for_release" and delay["place_id"] == "restu_gathering":
            gathering_hold_s = delay["duration_s"]
            break
    assert gathering_hold_s is not None
    assert gathering_hold_s == pytest.approx(_restu_offset_s(7, 33), abs=1)
    assert 40 * 60 <= gathering_hold_s <= 50 * 60
    assert scenario["operating_rules"]["pre_release_classification"] == "required_gathering"
    assert result["resource_summaries"]
    assert result["resource_summaries"][0]["resource_id"] == "coach_1"


def test_restu_eligible_timing_errors_and_coach_ride():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    trace = result["event_trace"]

    bus_queue = first_match(trace, {"event_type": "arrival", "place_id": "rst_bus_wait"})
    bus_depart = first_match(trace, {"event_type": "departure", "leg_id": "leg_coach_transit"})
    dtsp_arrive = first_match(trace, {"event_type": "arrival", "place_id": "dtsp_alighting_area"})
    hall_arrive = first_match(trace, {"event_type": "hall_area_arrival"})
    assert bus_queue is not None
    assert bus_depart is not None
    assert dtsp_arrive is not None
    assert hall_arrive is not None

    def error_s(event: dict, observed_s: float) -> float:
        return abs(event["time_ms"] / 1000.0 - observed_s)

    assert error_s(bus_queue, _restu_offset_s(7, 49)) <= 600
    assert error_s(bus_depart, _restu_offset_s(7, 58)) <= 600
    assert error_s(dtsp_arrive, _restu_offset_s(8, 1, 30)) <= 600
    assert error_s(hall_arrive, _restu_offset_s(8, 35)) <= 600

    coach_s = (dtsp_arrive["time_ms"] - bus_depart["time_ms"]) / 1000.0
    assert 120 <= coach_s <= 270

    hold_start = first_match(trace, {"event_type": "arrival", "place_id": "dtsp_exterior_gathering"})
    hold_end = first_match(trace, {"event_type": "calendar_open", "calendar_id": "hall_open"})
    assert hold_start is not None
    assert hold_end is not None
    hold_s = (hold_end["time_ms"] - hold_start["time_ms"]) / 1000.0
    assert abs(hold_s - 31 * 60) <= 600

    journey_s = hall_arrive["time_ms"] / 1000.0
    observed_journey_s = _restu_offset_s(8, 35)
    assert abs(journey_s - observed_journey_s) <= 600

    predicted = [
        check
        for check in result["accuracy_checks"]
        if check["role"] == "predicted" or check["id"] in {"coach_ride", "exterior_hold_duration"}
    ]
    assert predicted
    assert all(check.get("passed") for check in predicted)


def test_imposed_timestamps_are_inputs_not_predicted_successes():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    release = first_match(
        result["event_trace"],
        {"event_type": "calendar_open", "calendar_id": "restu_release"},
    )
    hall_open = first_match(
        result["event_trace"],
        {"event_type": "calendar_open", "calendar_id": "hall_open"},
    )
    assert release is not None
    assert hall_open is not None
    assert release.get("imposed_input") is True
    assert hall_open.get("imposed_input") is True

    imposed_checks = [
        check for check in result["accuracy_checks"] if check.get("imposed_input")
    ]
    assert {check["id"] for check in imposed_checks} >= {"supervised_release", "hall_open"}
    for check in imposed_checks:
        assert check["counted_as_predicted_success"] is False
        assert check["role"] == "imposed_input"


def test_hall_area_arrival_is_not_seated_completion():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    types = [event["event_type"] for event in result["event_trace"]]
    assert "hall_area_arrival" in types
    assert "seated_completion" not in types
    assert "entrance_completion" not in types
    for row in result["outcomes"]["student_completions"]:
        assert row["endpoint"] == "hall_area_arrival"
        assert row["endpoint"] != "seated_completion"
    seated_checks = [
        check for check in result["accuracy_checks"] if "seated" in check["id"]
    ]
    assert seated_checks == []


def test_time_and_event_limits_are_incomplete_not_success():
    scenario, policy = build_artificial_single_server_case()
    scenario["simulation_end_s"] = 50
    time_limited = simulate(scenario, policy)
    assert time_limited["status"] == "incomplete"
    assert time_limited["status"] != "completed"
    assert "simulation_end_s" in time_limited["limits_reached"]
    assert time_limited["measures"]["unfinished_students"] == 4
    assert time_limited["unfinished_demand"]

    scenario, policy = build_artificial_single_server_case()
    scenario["max_events_per_run"] = 1
    event_limited = simulate(scenario, policy)
    assert event_limited["status"] == "incomplete"
    assert event_limited["status"] != "completed"
    assert "max_events_per_run" in event_limited["limits_reached"]
    assert event_limited["measures"]["unfinished_students"] == 4


def test_model_excludes_bag_check_clicker_qr_and_direct_walk():
    assert STAGE_KINDS.isdisjoint(FORBIDDEN_MODES)
    assert EVENT_TYPES.isdisjoint(FORBIDDEN_MODES)

    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    rules = scenario["operating_rules"]
    assert rules["bag_check"] is False
    assert rules["security_service"] is False
    assert rules["mechanical_clicker"] is False
    assert rules["qr_scan"] is False
    assert rules["direct_walk_permitted"] is False
    for leg in scenario["route_legs"]:
        assert leg.get("mode") not in FORBIDDEN_MODES

    blocked = copy.deepcopy(policy)
    blocked["route_mode"] = "rst_direct_walk"
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, blocked)
    assert caught.value.category == "unsupported_policy"

    bag_policy = copy.deepcopy(policy)
    bag_policy["bag_check"] = True
    with pytest.raises(SimulationError) as caught_bag:
        simulate(scenario, bag_policy)
    assert caught_bag.value.category == "unsupported_policy"


def test_internal_time_is_integer_ms_and_local_times_use_kl():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    for event in result["event_trace"]:
        assert isinstance(event["time_ms"], int)
        assert event["time_local"].endswith("+08:00")
        assert "event_id" in event
        assert "event_type" in event
        assert "student_count" in event
        assert "hostel_composition" in event
        assert "primary_cause" in event
        assert "related_event_ids" in event


def test_source_records_separate_facts_assumptions_and_decisions():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    simulate(scenario, policy)
    assert scenario["measured_facts"]
    assert scenario["uncertain_assumptions"]
    assert scenario["decisions"]
    categories = {record["category"] for record in scenario["source_records"]}
    assert "measured" in categories
    assert "assumed" in categories
    assert "decision" in categories
    for record in scenario["source_records"]:
        for key in (
            "field",
            "value",
            "unit",
            "date",
            "method",
            "confidence",
            "observation_ref",
            "category",
        ):
            assert record.get(key) not in (None, "")
    all_text = str(scenario)
    assert "student_name" not in all_text
    assert "ic_number" not in all_text
    duration_fields = {record["field"] for record in scenario["source_records"]}
    assert "route_legs.leg_supervised_approach.duration_s" in duration_fields
    assert "route_legs.leg_coach_transit.duration_s" in duration_fields
    assert "route_legs.leg_hall_approach.duration_s" in duration_fields
    assert "route_stages.boarding.duration_s" in duration_fields


def test_zero_servers_deadlock_is_incomplete_not_success():
    scenario, policy = build_artificial_single_server_case()
    scenario["route_stages"][1]["server_count"] = 0
    result = simulate(scenario, policy)
    assert result["status"] == "incomplete"
    assert result["status"] != "completed"
    assert result["termination_cause"] == "deadlock"
    assert result["measures"]["unfinished_students"] == 4
    assert result["unfinished_demand"]
    assert result["active_holds"] == []
    assert result["queue_summaries"][0]["queued_students"] == 4


def test_missing_server_count_and_place_capacity_fail_clearly():
    scenario, policy = build_artificial_single_server_case()
    del scenario["route_stages"][1]["server_count"]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "missing_input"
    assert "server_count" in caught.value.field

    scenario, policy = build_artificial_single_server_case()
    del scenario["places"][0]["capacity_constraint"]
    with pytest.raises(SimulationError) as caught_cap:
        simulate(scenario, policy)
    assert caught_cap.value.category == "missing_input"

    scenario, policy = build_artificial_single_server_case()
    scenario["route_stages"].insert(
        0,
        {
            "id": "blocked",
            "kind": "hold",
            "place_id": "origin",
            "until": {"calendar_id": "does_not_exist"},
        },
    )
    with pytest.raises(SimulationError) as caught_cal:
        simulate(scenario, policy)
    assert caught_cal.value.category == "unknown_reference"


def test_over_capacity_coach_is_infeasible_not_completed():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    scenario["initial_state"]["vehicles"][0]["capacity_students"] = 1
    result = simulate(scenario, policy)
    assert result["status"] == "infeasible"
    assert result["status"] != "completed"
    assert result["violations"]
    assert result["measures"]["unfinished_students"] == 40


def test_restu_replay_requires_gps_file(tmp_path):
    with pytest.raises(SimulationError) as caught:
        build_restu_17sep_replay(tmp_path)
    assert caught.value.category == "missing_input"
    assert "Location.csv" in caught.value.message
