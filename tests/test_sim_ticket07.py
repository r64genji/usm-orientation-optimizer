"""Acceptance tests for ticket 07: delay attribution and operational measures."""

from __future__ import annotations

import copy

import pytest

from usm_sim import (
    build_artificial_single_server_case,
    build_full_destination_arriving_bus_case,
    build_operating_limit_event_case,
    build_restu_17sep_replay,
    simulate,
)
from usm_sim.counting import build_walking_checkpoint_case
from usm_sim.metrics import DELAY_EXPLANATION_KEYS
from usm_sim.metrics_cases import (
    build_assembly_then_hold_case,
    build_early_arrival_idle_case,
    build_origin_hold_unfinished_case,
    build_outdoor_wait_case,
    build_p95_student_weighted_case,
    build_reporting_window_case,
    build_starvation_not_student_wait_case,
    build_two_hostel_wait_case,
    build_vehicle_busy_held_idle_case,
)
from usm_sim.workers import build_combined_escort_count_case

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _hostel(result: dict, hostel_id: str) -> dict:
    return next(row for row in result["measures"]["by_hostel"] if row["hostel_id"] == hostel_id)


def test_four_student_example_keeps_partial_lateness_and_queue_wait():
    scenario, policy = build_artificial_single_server_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    times = [row["completion_time_s"] for row in result["outcomes"]["student_completions"]]
    assert times == [70, 80, 90, 100]
    late = [row for row in result["outcomes"]["student_completions"] if row["late_s"] > 0]
    assert len(late) == 1
    assert late[0]["late_s"] == pytest.approx(5.0)
    assert result["measures"]["late_students"] == 1
    assert result["measures"]["total_lateness_s"] == pytest.approx(5.0)
    assert result["measures"]["max_lateness_s"] == pytest.approx(5.0)
    assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(60.0)
    assert result["measures"]["total_service_student_s"] == pytest.approx(40.0)
    assert result["measures"]["required_stationary_service_student_s"] == pytest.approx(40.0)
    assert result["measures"]["p95_wait_s"] == pytest.approx(30.0)
    assert result["measures"]["p95_weighting"] == "student_count"
    assert result["measures"]["total_required_journey_student_s"] == pytest.approx(340.0)
    assert result["measures"]["wait_denominator_students"] == 4
    assert result["measures"]["unfinished_students"] == 0
    assert result["measures"]["early_arrival_idle_student_s"] == pytest.approx(0.0)
    assert result["measures"]["reporting_late_students"] == 0
    assert result["measures"]["reporting_lateness_student_s"] == pytest.approx(0.0)
    assert result["measures"]["non_attendance_students"] == 0
    assert result["measures"]["unfinished_leftover_students"] == 0
    assert result["measures"]["assembly_leftover_students"] == 0
    assert result["measures"]["assembly_leftover_events"] == 0
    assert result["measures"]["catch_up_walk_students"] == 0
    assert result["measures"]["catch_up_time_saved_student_s"] == pytest.approx(0.0)


def test_internal_subdivisions_do_not_change_four_student_example():
    grouped_scenario, grouped_policy = build_artificial_single_server_case()
    grouped = simulate(grouped_scenario, grouped_policy)
    split_scenario, split_policy = build_artificial_single_server_case()
    seed = split_scenario["initial_state"]["students"][0]
    members = list(seed["members"])
    split_scenario["initial_state"]["students"] = [
        {
            **seed,
            "part_id": f"part_{member['student_key']}",
            "members": [member],
            "hostel_composition": {seed["hostel_id"]: 1},
        }
        for member in members
    ]
    split = simulate(split_scenario, split_policy)
    limit = split["measures"]["numerical_rounding_limit_s"]
    assert split["status"] == "completed"
    assert [row["completion_time_s"] for row in split["outcomes"]["student_completions"]] == [
        70,
        80,
        90,
        100,
    ]
    assert split["measures"]["total_queue_waiting_student_s"] == pytest.approx(
        grouped["measures"]["total_queue_waiting_student_s"], abs=limit
    )
    assert split["measures"]["late_students"] == grouped["measures"]["late_students"]
    assert split["measures"]["total_lateness_s"] == pytest.approx(
        grouped["measures"]["total_lateness_s"], abs=limit
    )
    assert split["measures"]["p95_wait_s"] == pytest.approx(
        grouped["measures"]["p95_wait_s"], abs=limit
    )


def test_p95_is_weighted_by_student_count_not_groups():
    scenario, policy = build_p95_student_weighted_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["completed_students"] == 100
    assert result["measures"]["p95_weighting"] == "student_count"
    assert result["measures"]["p95_wait_s"] == pytest.approx(0.0)
    assert result["measures"]["mean_wait_s"] == pytest.approx(1.0)
    assert result["measures"]["total_student_waiting_student_s"] == pytest.approx(100.0)
    group_waits = sorted(row["total_waiting_student_s"] for row in result["outcomes"]["per_group"])
    assert group_waits[0] == pytest.approx(0.0)
    assert group_waits[-1] == pytest.approx(100.0)


def test_unfinished_students_stay_in_wait_average():
    scenario, policy = build_artificial_single_server_case()
    scenario["simulation_end_s"] = 85
    result = simulate(scenario, policy)
    assert result["status"] == "incomplete"
    assert result["measures"]["completed_students"] == 2
    assert result["measures"]["unfinished_students"] == 2
    assert result["measures"]["wait_denominator_students"] == 4
    assert result["measures"]["unfinished_in_wait_denominator"] == 2
    assert result["measures"]["mean_wait_s"] == pytest.approx(13.75)
    completed_only = (
        result["measures"]["total_student_waiting_student_s"]
        / result["measures"]["completed_students"]
    )
    assert result["measures"]["mean_wait_s"] != pytest.approx(completed_only)

    held_scenario, held_policy = build_origin_hold_unfinished_case()
    held = simulate(held_scenario, held_policy)
    assert held["status"] == "incomplete"
    assert held["measures"]["unfinished_students"] == 4
    assert held["measures"]["wait_denominator_students"] == 4
    assert held["measures"]["mean_wait_s"] == pytest.approx(40.0)
    assert held["measures"]["total_student_waiting_student_s"] == pytest.approx(160.0)


def test_hostel_split_of_waiting_and_worst_hostel():
    scenario, policy = build_two_hostel_wait_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    a = _hostel(result, "hostel_a")
    b = _hostel(result, "hostel_b")
    assert a["mean_wait_s"] == pytest.approx(10.0)
    assert b["mean_wait_s"] == pytest.approx(50.0)
    assert result["measures"]["max_hostel_mean_wait_s"] == pytest.approx(50.0)
    assert result["measures"]["worst_hostel_id"] == "hostel_b"
    assert result["measures"]["by_campus"]["mean_wait_s"] == pytest.approx(30.0)
    fairness = result["measures"]["fairness"]
    assert fairness["limit_configured"] is False
    assert fairness["evaluated"] is False
    disadvantaged = {row["hostel_id"] for row in fairness["disadvantaged_hostels"]}
    assert "hostel_b" in disadvantaged

    limited_policy = copy.deepcopy(policy)
    limited_policy["fairness_limit"] = {"max_hostel_increase_vs_campus_s": 15}
    limited = simulate(scenario, limited_policy)
    assert limited["measures"]["fairness"]["limit_configured"] is True
    assert limited["measures"]["fairness"]["evaluated"] is True
    assert limited["measures"]["fairness"]["passed"] is False
    assert limited["measures"]["fairness"]["limit_s"] == pytest.approx(15.0)


def test_worker_overlap_is_not_double_counted():
    scenario, policy = build_combined_escort_count_case(permitted=True)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    measures = result["measures"]
    reserved = measures["worker_reserved_s"]
    escort = measures["worker_escort_s"]
    count = measures["worker_count_s"]
    assert reserved > 0
    assert escort > 0
    assert count > 0
    assert reserved == pytest.approx(min(reserved, escort + count))
    assert escort + count > reserved
    assert measures["worker_overlap_double_counted"] is False
    combined = [row for row in result["worker_assignments"] if row.get("combined")]
    assert combined
    union_ms = 0
    by_worker: dict[str, list[tuple[int, int]]] = {}
    for row in result["worker_assignments"]:
        by_worker.setdefault(row["worker_id"], []).append((row["start_ms"], row["end_ms"] or 0))
    for intervals in by_worker.values():
        ordered = sorted(intervals)
        start, end = ordered[0]
        for next_start, next_end in ordered[1:]:
            if next_start <= end:
                end = max(end, next_end)
            else:
                union_ms += max(0, end - start)
                start, end = next_start, next_end
        union_ms += max(0, end - start)
    assert reserved == pytest.approx(union_ms / 1000.0)


def test_delay_explanations_have_required_keys():
    scenario, policy = build_artificial_single_server_case()
    result = simulate(scenario, policy)
    assert result["delay_explanations"]
    for row in result["delay_explanations"]:
        for key in DELAY_EXPLANATION_KEYS:
            assert key in row
        assert row["primary_cause"]
        assert row["cause"] == row["primary_cause"]
        assert row["duration_s"] > 0
        assert row["affected_count"] >= 1
        assert row["place_id"] or row["resource_id"]
        assert isinstance(row["related_event_ids"], list)
    assert result["event_trace"]
    assert result.get("event_trace_retained") is True


def test_required_origin_waiting_survives_assembly_and_is_not_free_time():
    scenario, policy = build_assembly_then_hold_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    unit = result["outcomes"]["source_units"][0]
    assert unit["assembly_start_s"] == pytest.approx(0.0)
    assert unit["assembly_finish_s"] == pytest.approx(10.0)
    assert unit["release_s"] == pytest.approx(40.0)
    assert result["measures"]["assembly_student_s"] == pytest.approx(30.0)
    assert result["measures"]["total_student_waiting_student_s"] == pytest.approx(90.0)
    assert result["measures"]["free_time_before_reporting_student_s"] == pytest.approx(0.0)
    assert result["measures"]["post_completion_stationary_student_s"] == pytest.approx(0.0)
    assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(0.0)
    assert result["measures"]["worker_reserved_s"] == pytest.approx(20.0)
    assert result["worker_assignments"]


def test_reporting_choice_keeps_availability_window_and_response_rule():
    scenario, policy = build_reporting_window_case(reporting_time_s=30)
    result = simulate(scenario, policy)
    assumptions = result["reporting_assumptions"]
    assert assumptions["exogenous_availability_retained"] is True
    assert assumptions["required_reporting_is_search_choice"] is True
    assert assumptions["reporting_window"] == {"earliest_s": 0.0, "latest_s": 60.0}
    assert assumptions["attendance_response_rule"]["type"] == "fixed"
    assert assumptions["availability_s_by_unit"]["su_origin"] == pytest.approx(0.0)
    assert result["measures"]["free_time_before_reporting_student_s"] == pytest.approx(60.0)
    assert result["measures"]["earlier_reporting_burden_student_s"] == pytest.approx(60.0)
    journeys = [row["required_journey_s"] for row in result["outcomes"]["student_completions"]]
    assert journeys == [pytest.approx(10.0), pytest.approx(10.0)]

    early_policy = copy.deepcopy(policy)
    early_policy["reporting_time_s"] = 0
    early = simulate(scenario, early_policy)
    assert early["reporting_assumptions"]["reporting_window"] == assumptions["reporting_window"]
    assert early["reporting_assumptions"]["attendance_response_rule"]["type"] == "fixed"
    assert early["reporting_assumptions"]["availability_s_by_unit"] == assumptions["availability_s_by_unit"]
    assert early["measures"]["earlier_reporting_burden_student_s"] > result["measures"][
        "earlier_reporting_burden_student_s"
    ]
    early_journeys = [row["required_journey_s"] for row in early["outcomes"]["student_completions"]]
    assert early_journeys == journeys


def test_each_student_interval_has_one_primary_activity_and_waiting_cause():
    scenario, policy = build_artificial_single_server_case()
    result = simulate(scenario, policy)
    assert result["student_time_intervals"]
    for row in result["student_time_intervals"]:
        assert row["primary_activity"]
        assert isinstance(row.get("secondary_reasons"), list) or row.get("secondary_reasons") == []
        if row["primary_activity"] == "waiting":
            assert row["primary_waiting_cause"]
        else:
            assert row.get("primary_waiting_cause") in {None, ""}
        assert row["duration_s"] >= 0
    waiting = [row for row in result["student_time_intervals"] if row["primary_activity"] == "waiting"]
    service = [row for row in result["student_time_intervals"] if row["primary_activity"] == "service"]
    travel = [row for row in result["student_time_intervals"] if row["primary_activity"] == "travel"]
    assert waiting
    assert service
    assert travel
    wait_s = sum(row["duration_s"] * row["student_count"] for row in waiting)
    assert wait_s == pytest.approx(result["measures"]["total_student_waiting_student_s"])


def _ten_student_origin_case(*, required_reporting_s, readiness_s, actual_reporting_s=0.0, availability_s=0.0):
    scenario, policy = build_artificial_single_server_case()
    members = [
        {
            "student_key": f"s{index:02d}",
            "queue_tie_key": f"{index:02d}",
            "source_unit_id": "su_origin",
            "hostel_id": "synthetic",
        }
        for index in range(10)
    ]
    scenario["source_units"] = [
        {
            "id": "su_origin",
            "hostel_id": "synthetic",
            "estimated_attendance": 10,
            "resolved_attendance": 10,
            "actual_reporting_s": actual_reporting_s,
            "readiness_s": readiness_s,
            "required_reporting_s": required_reporting_s,
            "availability_s": availability_s,
        }
    ]
    scenario["places"] = [
        {
            "id": "origin",
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "meaning": "origin",
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
            "id": "walk_1",
            "from_place_id": "origin",
            "to_place_id": "dest",
            "duration_s": 1,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    scenario["route_stages"] = [{"id": "walk", "kind": "travel", "leg_id": "walk_1"}]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_origin",
            "source_unit_id": "su_origin",
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 10},
            "members": members,
        }
    ]
    scenario["initial_state"]["workers"] = []
    scenario["initial_state"]["vehicles"] = []
    scenario["operating_rules"]["required_endpoint"] = "stage_complete"
    policy["required_endpoint"] = "stage_complete"
    policy["grouping"] = {"mode": "explicit_parts"}
    policy["release_rule"] = {"type": "immediate"}
    return scenario, policy


def test_delayed_release_counts_required_origin_waiting():
    scenario, policy = _ten_student_origin_case(
        required_reporting_s=0,
        readiness_s=0,
        actual_reporting_s=0,
        availability_s=0,
    )
    policy["release_rule"] = {
        "type": "fixed_interval",
        "interval_s": 0,
        "start_s": 600,
    }
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    origin_wait = result["measures"]["waiting_student_s_by_cause"].get(
        "waiting_for_release", 0.0
    )
    assert origin_wait == pytest.approx(6000.0)
    assert result["measures"]["total_student_waiting_student_s"] == pytest.approx(6000.0)


def test_free_prep_origin_time_is_not_required_waiting():
    scenario, policy = _ten_student_origin_case(
        required_reporting_s=600,
        readiness_s=600,
        actual_reporting_s=600,
        availability_s=0,
    )
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    origin_wait = result["measures"]["waiting_student_s_by_cause"].get(
        "waiting_for_release", 0.0
    )
    assert origin_wait == pytest.approx(0.0)
    assert result["measures"]["free_time_before_reporting_student_s"] == pytest.approx(6000.0)


def test_counting_is_separate_from_queue_waiting():
    scenario, policy = build_walking_checkpoint_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["headcount_actions"] >= 1
    assert result["measures"]["counting_student_s"] > 0
    assert result["measures"]["counting_student_s"] <= result["measures"][
        "required_stationary_service_student_s"
    ]
    queue = result["measures"]["total_queue_waiting_student_s"]
    counting = result["measures"]["counting_student_s"]
    assert result["measures"]["total_student_waiting_student_s"] == pytest.approx(
        queue + result["measures"]["total_hold_waiting_student_s"]
    )
    assert counting != pytest.approx(queue) or counting == 0 or queue == 0


def test_early_arrival_idle_is_not_queue_waiting():
    scenario, policy = build_early_arrival_idle_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["early_arrival_idle_student_s"] == pytest.approx(60.0)
    assert result["measures"]["total_hold_waiting_student_s"] == pytest.approx(80.0)
    assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(0.0)
    assert result["measures"]["total_student_waiting_student_s"] == pytest.approx(80.0)

    restu_scenario, restu_policy = build_restu_17sep_replay(REPO_ROOT)
    restu = simulate(restu_scenario, restu_policy)
    assert restu["measures"]["early_arrival_idle_student_s"] == pytest.approx(0.0)
    assert restu["measures"]["total_hold_waiting_student_s"] > 0


def test_unused_service_is_not_student_waiting():
    scenario, policy = build_starvation_not_student_wait_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["unused_service_s"] == pytest.approx(10.0)
    assert result["measures"]["unused_service_is_student_waiting"] is False
    assert result["measures"]["total_student_waiting_student_s"] == pytest.approx(0.0)
    assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(0.0)


def test_outdoor_waiting_classes_are_not_medical_risk():
    scenario, policy = build_outdoor_wait_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    outdoor = result["measures"]["outdoor_waiting"]
    assert outdoor["measured_medical_risk"] is False
    assert outdoor["exposed_student_s"] == pytest.approx(20.0)
    assert outdoor["shaded_student_s"] == pytest.approx(20.0)
    assert outdoor["sheltered_student_s"] == pytest.approx(20.0)


def test_hall_entrance_and_seating_are_distinct_and_unknown_stay_unknown():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    group = result["outcomes"]["groups"][0]
    assert group["hall_area_arrival_s"] is not None
    assert group["entrance_completion_s"] is None
    assert group["seated_completion_s"] is None
    assert "hall_area_arrival_s" in group["supported_completion_points"]
    assert "seated_completion" in group["unknown_completion_points"]
    for row in result["outcomes"]["student_completions"]:
        assert row["endpoint"] == "hall_area_arrival"


def test_source_units_and_groups_record_obligation_times():
    scenario, policy = build_artificial_single_server_case()
    result = simulate(scenario, policy)
    units = result["outcomes"]["source_units"]
    groups = result["outcomes"]["groups"]
    assert units
    assert groups
    unit = units[0]
    for key in (
        "required_reporting_s",
        "actual_reporting_s",
        "readiness_s",
        "assembly_start_s",
        "assembly_finish_s",
        "release_s",
        "stage_arrivals",
        "service_times",
        "status",
        "unfinished_students",
    ):
        assert key in unit
    assert unit["service_times"]
    assert groups[0]["service_times"]


def test_vehicle_totals_include_busy_held_and_idle():
    scenario, policy = build_full_destination_arriving_bus_case()
    result = simulate(scenario, policy)
    vehicles = result["measures"]["vehicles"]
    assert vehicles["held_s"] > 0
    assert vehicles["busy_s"] > 0
    assert "idle_s" in vehicles
    assert vehicles["waiting_to_alight_s"] >= 0
    custom_scenario, custom_policy = build_vehicle_busy_held_idle_case()
    custom = simulate(custom_scenario, custom_policy)
    assert custom["measures"]["vehicles"]["held_s"] > 0
    assert custom["measures"]["vehicles"]["busy_s"] > 0


def test_operating_limit_denied_entry_and_max_queue_are_visible():
    scenario, policy = build_operating_limit_event_case()
    result = simulate(scenario, policy)
    exceedance = result["measures"]["operating_limit_exceedance"]
    assert "duration_s" in exceedance
    assert "max_excess_students" in exceedance
    assert result["measures"]["max_queue_students"] >= 0
    assert "denied_entry_students" in result["measures"]
    assert result["measures"]["unfinished_students"] >= 0


def test_coordination_counts_real_actions():
    scenario, policy = build_walking_checkpoint_case()
    result = simulate(scenario, policy)
    coord = result["measures"]["coordination"]
    assert "policy_decisions" in coord
    assert "reports_requiring_action" in coord
    assert "handovers" in coord
    assert "physical_regrouping_actions" in coord
    assert "active_stations" in coord
    assert "distinct_operating_rules" in coord
    assert result["measures"]["headcount_actions"] == len(result["count_outcomes"])
    recounts = sum(1 for row in result["count_outcomes"] if int(row.get("attempt") or 1) > 1)
    assert result["measures"]["recounts"] == recounts
