"""Acceptance tests for ticket 03: required manual checks."""

from __future__ import annotations

import copy
import math

import pytest

from usm_sim import (
    COUNT_METHODS,
    EVENT_TYPES,
    FORBIDDEN_MODES,
    STAGE_KINDS,
    SimulationError,
    simulate,
)
from usm_sim.counting import (
    build_bus_checkpoint_case,
    build_bus_mismatch_case,
    build_column_space_case,
    build_group_formation_case,
    build_mismatch_case,
    build_occupancy_attendance_case,
    build_passthrough_queue_case,
    build_split_after_count_case,
    build_two_origin_checkpoint_bypass_case,
    build_walking_checkpoint_case,
    column_count_duration_s,
    count_action_events,
    groups_from_source_units,
    grouping_module,
    join_preserve_links,
    source_units_from_layout,
    split_preserve_links,
)
from usm_sim.scenarios import build_artificial_single_server_case, build_restu_17sep_replay


def _types(result: dict) -> list[str]:
    return [event["event_type"] for event in result["event_trace"]]


def test_policy_cannot_empty_or_drop_required_checkpoints():
    scenario, policy = build_walking_checkpoint_case()
    empty = copy.deepcopy(policy)
    empty["counting"] = {"assignments": {}}
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, empty)
    assert caught.value.category == "fixed_rule_violation"

    dropped = copy.deepcopy(policy)
    dropped["counting"]["required_checkpoints"] = []
    with pytest.raises(SimulationError) as caught_list:
        simulate(scenario, dropped)
    assert caught_list.value.category == "fixed_rule_violation"

    missing = copy.deepcopy(policy)
    missing["counting"]["assignments"] = {}
    missing["required_checkpoints"] = []
    with pytest.raises(SimulationError) as caught_top:
        simulate(scenario, missing)
    assert caught_top.value.category == "fixed_rule_violation"

    omit = copy.deepcopy(policy)
    del omit["counting"]["assignments"]["cp_origin"]
    with pytest.raises(SimulationError) as caught_omit:
        simulate(scenario, omit)
    assert caught_omit.value.category == "fixed_rule_violation"

    elsewhere = copy.deepcopy(policy)
    elsewhere["counting"]["assignments"]["cp_origin"]["location_id"] = "not_permitted"
    with pytest.raises(SimulationError) as caught_loc:
        simulate(scenario, elsewhere)
    assert caught_loc.value.category == "fixed_rule_violation"


def test_walking_and_bus_fixtures_satisfy_required_coverage():
    walk_scenario, walk_policy = build_walking_checkpoint_case()
    walk = simulate(walk_scenario, walk_policy)
    assert walk["status"] == "completed"
    assert walk["checkpoint_coverage"]["required"] == ["cp_origin"]
    assert walk["checkpoint_coverage"]["missing"] == []
    assert walk["checkpoint_coverage"]["satisfied"] == ["cp_origin"]
    assert walk["measures"]["headcount_actions"] >= 1
    assert any(row["checkpoint_id"] == "cp_origin" for row in walk["count_outcomes"])

    bus_scenario, bus_policy = build_bus_checkpoint_case()
    bus = simulate(bus_scenario, bus_policy)
    assert bus["status"] == "completed"
    assert bus["checkpoint_coverage"]["required"] == ["cp_board"]
    assert bus["checkpoint_coverage"]["missing"] == []
    assert bus["checkpoint_coverage"]["satisfied"] == ["cp_board"]
    assert any(row["checkpoint_id"] == "cp_board" for row in bus["count_outcomes"])
    assert any(event["event_type"] == "worker_reserved" for event in bus["event_trace"])


def test_forming_or_splitting_groups_adds_zero_count_actions():
    floor_scenario, floor_policy = build_group_formation_case("floor")
    floor = simulate(floor_scenario, floor_policy)
    assert floor["status"] == "completed"
    assert floor["measures"]["headcount_actions"] == 0
    assert floor["count_outcomes"] == []
    assert count_action_events(floor["event_trace"]) == []
    floor_groups = floor["outcomes"]["per_group"]
    assert len(floor_groups) == 3
    assert sum(row["completed_students"] for row in floor_groups) == 120

    wing_scenario, wing_policy = build_group_formation_case("wing")
    wing = simulate(wing_scenario, wing_policy)
    assert wing["measures"]["headcount_actions"] == 0
    assert len(wing["outcomes"]["per_group"]) == 2
    assert sum(row["completed_students"] for row in wing["outcomes"]["per_group"]) == 120

    fw_scenario, fw_policy = build_group_formation_case("floor_wing")
    fw = simulate(fw_scenario, fw_policy)
    assert fw["measures"]["headcount_actions"] == 0
    assert len(fw["outcomes"]["per_group"]) == 6

    units = source_units_from_layout()
    formed = groups_from_source_units(units, "floor")
    assert all(part["count_record_ids"] == [] for part in formed)
    children = split_preserve_links(formed[0], ["a", "b"])
    assert all(child["count_record_ids"] == [] for child in children)

    grouping = grouping_module()
    if grouping is not None:
        form = (
            getattr(grouping, "form_groups", None)
            or getattr(grouping, "apply_grouping", None)
            or getattr(grouping, "groups_for_basis", None)
        )
        if form is not None:
            again = form(units, "wing")
            for part in again:
                assert not part.get("count_record_ids")


def test_passthrough_reserves_worker_and_does_not_add_a_queue_when_flow_allows():
    scenario, policy = build_passthrough_queue_case(count_rate_s_per_person=5.0)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    times = [row["completion_time_s"] for row in result["outcomes"]["student_completions"]]
    assert times == [70, 80, 90, 100]
    assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(60.0)
    assert result["measures"]["total_service_student_s"] == pytest.approx(40.0)
    assert result["measures"]["headcount_actions"] == 1
    assert "waiting_for_counter" not in result["measures"]["waiting_student_s_by_cause"]
    types = _types(result)
    assert types.count("count_start") == 1
    assert "worker_reserved" in types
    assert "worker_released" in types
    assert all(row["added_student_queue"] is False for row in result["count_outcomes"])
    reserved = next(event for event in result["event_trace"] if event["event_type"] == "worker_reserved")
    released = next(event for event in result["event_trace"] if event["event_type"] == "worker_released")
    assert reserved["time_ms"] == 60000
    assert released["time_ms"] == 100000


def test_passthrough_flow_limit_applies_once_not_twice():
    scenario, policy = build_passthrough_queue_case(count_rate_s_per_person=20.0)
    result = simulate(scenario, policy)
    times = [row["completion_time_s"] for row in result["outcomes"]["student_completions"]]
    assert times == [80, 100, 120, 140]
    assert result["measures"]["total_service_student_s"] == pytest.approx(80.0)
    assert result["measures"]["headcount_actions"] == 1
    assert result["count_outcomes"][0]["added_student_queue"] is False

    bus_scenario, bus_policy = build_bus_checkpoint_case(
        count_rate_s_per_person=3.0,
        board_duration_s=10.0,
        student_count=10,
    )
    bus = simulate(bus_scenario, bus_policy)
    start = next(event for event in bus["event_trace"] if event["event_type"] == "batch_start")
    end = next(event for event in bus["event_trace"] if event["event_type"] == "batch_complete")
    board_s = (end["time_ms"] - start["time_ms"]) / 1000.0
    assert board_s == pytest.approx(30.0)
    assert board_s != pytest.approx(40.0)


def test_column_parallelism_bounded_by_space_and_workers():
    expected = column_count_duration_s(
        student_count=20,
        setup_s=5,
        cadence_s_per_person=1,
        aggregation_s=5,
        requested_columns=100,
        space_columns=2,
        available_workers=8,
        workers_per_column=1,
    )
    assert expected["n_columns"] == 2
    assert expected["longest_column"] == 10
    assert expected["duration_s"] == pytest.approx(20.0)

    scenario, policy = build_column_space_case(
        requested_columns=100,
        space_columns=2,
        worker_count=8,
    )
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    row = result["count_outcomes"][0]
    assert row["n_columns"] == 2
    assert row["longest_column"] == 10
    assert row["duration_s"] == pytest.approx(20.0)
    start = next(event for event in result["event_trace"] if event["event_type"] == "count_start")
    end = next(event for event in result["event_trace"] if event["event_type"] == "count_complete")
    assert (end["time_ms"] - start["time_ms"]) / 1000.0 == pytest.approx(20.0)

    unbounded, unbounded_policy = build_column_space_case(
        requested_columns=10_000,
        space_columns=10_000,
        worker_count=20,
    )
    huge = simulate(unbounded, unbounded_policy)
    huge_row = huge["count_outcomes"][0]
    assert huge_row["duration_s"] > 0
    assert huge_row["n_columns"] == 20
    assert huge_row["longest_column"] == 1
    instant = column_count_duration_s(
        student_count=20,
        setup_s=5,
        cadence_s_per_person=1,
        aggregation_s=5,
        requested_columns=10_000,
        space_columns=10_000,
        available_workers=20,
        workers_per_column=1,
    )
    assert instant["duration_s"] == pytest.approx(11.0)


def test_occupancy_attendance_expected_observed_stay_distinct():
    scenario, policy = build_occupancy_attendance_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    row = result["count_outcomes"][0]
    assert row["estimated_occupancy"] == 12
    assert row["actual_attendance"] == 8
    assert row["expected_count"] == 8
    assert row["observed_count"] == 8
    assert row["is_count_error"] is False
    assert row["outcome"] in {"agreed", "attendance_gap"}
    assert len({row["estimated_occupancy"], row["actual_attendance"]}) == 2
    types = _types(result)
    assert "count_disagreement" not in types
    assert result["measures"]["recounts"] == 0


def test_seeded_mismatch_triggers_recount_then_unresolved_is_not_completed():
    scenario, policy = build_mismatch_case(seed=42, p_mismatch=1.0, max_retries=1)
    first = simulate(scenario, policy)
    second = simulate(copy.deepcopy(scenario), copy.deepcopy(policy))
    assert first["event_trace"] == second["event_trace"]
    assert first["status"] != "completed"
    assert first["status"] == "infeasible"
    assert first["termination_cause"] == "unresolved_count"
    types = _types(first)
    assert "count_disagreement" in types
    assert "recount_start" in types
    assert "count_unresolved" in types
    assert types.count("recount_start") == 1
    unresolved = [row for row in first["count_outcomes"] if row["outcome"] == "unresolved"]
    assert unresolved
    assert unresolved[-1]["retries"] == 1
    assert first["reconciliation_status"] == "unresolved"
    assert first["unfinished_demand"]
    assert first["measures"]["unfinished_students"] == 6

    limited = build_mismatch_case(seed=7, p_mismatch=1.0, max_retries=2)
    third = simulate(*limited)
    assert _types(third).count("recount_start") == 2
    assert third["status"] != "completed"

    recovered_scenario, recovered_policy = build_mismatch_case(
        seed=1,
        p_mismatch=1.0,
        max_retries=1,
        mismatch_schedule=[True, False],
    )
    recovered = simulate(recovered_scenario, recovered_policy)
    assert recovered["status"] == "completed"
    assert "recount_start" in _types(recovered)
    assert "count_unresolved" not in _types(recovered)


def test_bus_recount_keeps_vehicle_held():
    scenario, policy = build_bus_mismatch_case(seed=3, max_retries=1)
    result = simulate(scenario, policy)
    assert result["status"] != "completed"
    bus = next(row for row in result["resource_summaries"] if row["resource_id"] == "bus_1")
    assert bus["busy"] is True
    assert result["unfinished_demand"]
    assert any(row["status"] == "count_blocked" for row in result["unfinished_demand"])


def test_splits_and_joins_keep_count_record_links():
    linked = {"part_id": "p0", "group_id": "g", "count_record_ids": ["cnt_0001"], "covered_checkpoint_ids": ["cp_origin"], "student_count": 4}
    children = split_preserve_links(linked, ["p0_a", "p0_b"])
    assert children[0]["count_record_ids"] == ["cnt_0001"]
    assert children[1]["covered_checkpoint_ids"] == ["cp_origin"]
    joined = join_preserve_links(children)
    assert joined["count_record_ids"] == ["cnt_0001"]
    assert joined["covered_checkpoint_ids"] == ["cp_origin"]

    scenario, policy = build_split_after_count_case()
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    record_ids = {row["count_record_id"] for row in result["count_outcomes"]}
    assert record_ids
    for row in result["outcomes"]["student_completions"]:
        assert row["count_record_ids"]
        assert set(row["count_record_ids"]) <= record_ids
        assert "cp_origin" in row["covered_checkpoint_ids"]
    totals = result["group_count_totals"]
    assert totals
    assert totals[0]["count_record_ids"]


def test_internal_subdivision_does_not_multiply_count_actions():
    scenario, policy = build_passthrough_queue_case(
        count_rate_s_per_person=5.0,
        student_count=8,
    )
    result = simulate(scenario, policy)
    assert result["measures"]["headcount_actions"] == 1
    assert _types(result).count("count_start") == 1
    assert len(result["count_outcomes"]) == 1
    assert result["count_outcomes"][0]["exposure_unit"] == "checkpoint_pass"
    assert result["count_outcomes"][0]["relationship_to_load"] == "none"


def test_ticket01_restu_and_hand_case_still_pass():
    from pathlib import Path

    hand_scenario, hand_policy = build_artificial_single_server_case()
    hand = simulate(hand_scenario, hand_policy)
    assert hand["status"] == "completed"
    times = [row["completion_time_s"] for row in hand["outcomes"]["student_completions"]]
    assert times == [70, 80, 90, 100]
    assert hand["measures"]["headcount_actions"] == 0

    restu_scenario, restu_policy = build_restu_17sep_replay(Path(__file__).resolve().parent.parent)
    restu = simulate(restu_scenario, restu_policy)
    assert restu["status"] == "completed"
    assert restu["measures"]["headcount_actions"] == 0
    assert count_action_events(restu["event_trace"]) == []


def test_required_checkpoint_is_per_part_not_one_global_record():
    scenario, policy = build_two_origin_checkpoint_bypass_case()
    result = simulate(scenario, policy)
    assert any(row.get("checkpoint_id") == "cp_gate" for row in result["count_outcomes"])
    assert result["status"] != "completed"
    assert result["termination_cause"] == "missing_required_checkpoint" or any(
        row.get("type") == "missing_required_checkpoint" for row in result["violations"]
    )
    uncovered = [
        row
        for row in result["violations"]
        if row.get("type") == "missing_required_checkpoint"
    ]
    assert uncovered
    parts = uncovered[0].get("parts") or []
    assert any(row.get("part_id") == "part_b" for row in parts)

    split_scenario, split_policy = build_two_origin_checkpoint_bypass_case()
    counted = split_scenario["initial_state"]["students"][0]
    sibling = copy.deepcopy(counted)
    sibling["part_id"] = "part_a_split"
    sibling["parent_part_id"] = counted["part_id"]
    sibling["members"] = [
        {
            "student_key": "a1",
            "queue_tie_key": "01",
            "source_unit_id": "su_a",
            "hostel_id": "hostel_a",
        }
    ]
    counted["hostel_composition"] = {"hostel_a": 1}
    sibling["hostel_composition"] = {"hostel_a": 1}
    split_scenario["source_units"][0]["resolved_attendance"] = 2
    split_scenario["source_units"][0]["estimated_attendance"] = 2
    split_scenario["initial_state"]["students"].insert(1, sibling)
    split_result = simulate(split_scenario, split_policy)
    assert any(row.get("checkpoint_id") == "cp_gate" for row in split_result["count_outcomes"])
    assert split_result["status"] != "completed"
    assert split_result["termination_cause"] == "missing_required_checkpoint" or any(
        row.get("type") == "missing_required_checkpoint" for row in split_result["violations"]
    )
    assert int(split_result["measures"]["completed_students"]) + int(
        split_result["measures"].get("unfinished_students") or 0
    ) + int(split_result["measures"].get("withdrawn_students") or 0) == 3


def test_model_excludes_clicker_qr_and_face():
    assert COUNT_METHODS == frozenset({"pass_through", "column"})
    assert STAGE_KINDS.isdisjoint(FORBIDDEN_MODES)
    assert EVENT_TYPES.isdisjoint(FORBIDDEN_MODES)
    assert "facial_recognition" in FORBIDDEN_MODES
    assert "mechanical_clicker" in FORBIDDEN_MODES
    assert "qr_scan" in FORBIDDEN_MODES
    assert "personal_student_record" in FORBIDDEN_MODES

    scenario, policy = build_walking_checkpoint_case()
    blocked = copy.deepcopy(policy)
    blocked["counting"]["assignments"]["cp_origin"]["method"] = "facial_recognition"
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, blocked)
    assert caught.value.category in {"unsupported_policy", "fixed_rule_violation"}

    clicker = copy.deepcopy(policy)
    clicker["mechanical_clicker"] = True
    with pytest.raises(SimulationError) as caught_clicker:
        simulate(scenario, clicker)
    assert caught_clicker.value.category == "unsupported_policy"


def test_required_checkpoint_must_be_attached_to_a_stage():
    scenario, policy = build_walking_checkpoint_case()
    scenario["checkpoints"][0].pop("stage_id", None)
    scenario["route_stages"] = [
        stage for stage in scenario["route_stages"] if stage["kind"] != "manual_count"
    ]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "impossible_static_requirement"


def test_passthrough_mismatch_does_not_complete_or_duplicate_students():
    scenario, policy = build_passthrough_queue_case(count_rate_s_per_person=5.0)
    scenario["checkpoints"][0]["max_retries"] = 1
    scenario["count_error_assumptions"] = [
        {
            "id": "visual_checkpoint_pass",
            "exposure_unit": "checkpoint_pass",
            "relationship_to_load": "none",
            "p_mismatch": 1.0,
            "observed_delta": 1,
        }
    ]
    policy["random_seed"] = 1
    result = simulate(scenario, policy)
    assert result["status"] != "completed"
    assert result["status"] == "infeasible"
    assert result["termination_cause"] == "unresolved_count"
    keys = [row["student_key"] for row in result["outcomes"]["student_completions"]]
    assert len(keys) == len(set(keys))
    assert result["outcomes"]["campus"]["completed_students"] == 0
    assert result["measures"]["unfinished_students"] == 4
    assert all(row["status"] == "count_blocked" for row in result["unfinished_demand"])


def test_passthrough_recovered_mismatch_completes_each_student_once():
    scenario, policy = build_passthrough_queue_case(count_rate_s_per_person=5.0)
    scenario["checkpoints"][0]["max_retries"] = 1
    scenario["count_error_assumptions"] = [
        {
            "id": "visual_checkpoint_pass",
            "exposure_unit": "checkpoint_pass",
            "relationship_to_load": "none",
            "p_mismatch": 1.0,
            "observed_delta": 1,
            "mismatch_schedule": [True, False],
        }
    ]
    policy["random_seed"] = 1
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    keys = [row["student_key"] for row in result["outcomes"]["student_completions"]]
    assert sorted(keys) == ["s1", "s2", "s3", "s4"]
    assert result["outcomes"]["campus"]["completed_students"] == 4
    assert "recount_start" in _types(result)
    assert min(row["completion_time_s"] for row in result["outcomes"]["student_completions"]) >= 100


def test_passthrough_without_workers_does_not_complete_the_count():
    scenario, policy = build_passthrough_queue_case(count_rate_s_per_person=5.0)
    scenario["initial_state"]["workers"] = []
    result = simulate(scenario, policy)
    assert result["status"] != "completed"
    assert result["count_outcomes"] == []
    assert result["checkpoint_coverage"]["missing"] == ["cp_entrance"]
    assert "worker_reserved" not in _types(result)

    bus_scenario, bus_policy = build_bus_checkpoint_case()
    bus_scenario["initial_state"]["workers"] = []
    bus = simulate(bus_scenario, bus_policy)
    assert bus["status"] != "completed"
    assert bus["count_outcomes"] == []
    assert bus["checkpoint_coverage"]["missing"] == ["cp_board"]


def test_column_duration_formula_matches_hand_values():
    stats = column_count_duration_s(
        student_count=20,
        setup_s=5,
        cadence_s_per_person=1,
        aggregation_s=5,
        requested_columns=2,
        space_columns=2,
        available_workers=2,
        workers_per_column=1,
    )
    assert stats["n_columns"] == 2
    assert stats["longest_column"] == math.ceil(20 / 2)
    assert stats["duration_s"] == pytest.approx(5 + 10 + 5)
