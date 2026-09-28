"""Acceptance tests for ticket 02: grouping policy and shared RST buses."""

from __future__ import annotations

import copy

import pytest

from usm_sim import (
    SimulationError,
    allocate_integer_counts,
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    build_rst_shared_fleet_case,
    build_ticket02_bus_case,
    materialize_groups,
    simulate,
)

# Literal names. Do not import the production set, or widening that set
# would keep these asserts green.
_HEADCOUNT_EVENT_TYPES = frozenset(
    {
        "headcount",
        "manual_count",
        "count_start",
        "count_complete",
        "checkpoint_count",
    }
)


def _group_sizes(result: dict) -> list[int]:
    return sorted(group["student_count"] for group in result["grouping"]["groups"])


def _student_keys(result: dict) -> list[str]:
    keys = []
    for group in result["grouping"]["groups"]:
        keys.extend(member["student_key"] for member in group["members"])
    return keys


def _headcount_events(result: dict) -> list[dict]:
    return [
        event
        for event in result["event_trace"]
        if event["event_type"] in _HEADCOUNT_EVENT_TYPES
        or event.get("primary_cause") in _HEADCOUNT_EVENT_TYPES
    ]


def test_demand_fields_stay_separate():
    scenario, policy = build_artificial_120_hostel_case("floor")
    hostel = scenario["hostels"][0]
    for key in (
        "registration",
        "resident_occupancy",
        "expected_event_attendance",
        "resolved_attendance",
    ):
        assert key in hostel
    assert hostel["registration"] == 150
    assert hostel["resident_occupancy"] == 132
    assert hostel["expected_event_attendance"] == 120
    assert hostel["resolved_attendance"] == 120
    assert hostel["registration"] != hostel["resident_occupancy"]
    assert hostel["resident_occupancy"] != hostel["expected_event_attendance"]
    unit = scenario["source_units"][0]
    assert unit["registration"] == 25
    assert unit["resident_occupancy"] == 22
    assert unit["expected_event_attendance"] == 20
    assert unit["resolved_attendance"] == 20
    result = simulate(scenario, policy)
    snap_hostel = result["input_snapshot"]["scenario"]["hostels"][0]
    assert snap_hostel["registration"] == 150
    assert snap_hostel["resident_occupancy"] == 132
    assert snap_hostel["expected_event_attendance"] == 120
    assert snap_hostel["resolved_attendance"] == 120
    assert result["grouping"]["total_resolved_attendance"] == 120


def test_occupancy_allocation_is_integer_and_repeatable():
    first = allocate_integer_counts(100, [("a", 1.0), ("b", 1.0), ("c", 1.0)])
    second = allocate_integer_counts(100, [("c", 1.0), ("a", 1.0), ("b", 1.0)])
    assert first == {"a": 34, "b": 33, "c": 33}
    assert first == second
    assert sum(first.values()) == 100
    leftover = allocate_integer_counts(10, [("x", 1.0), ("y", 1.0), ("z", 1.0)])
    assert leftover == {"x": 4, "y": 3, "z": 3}


def test_unknown_layout_target_size_without_floor_plan():
    scenario, policy = build_artificial_120_hostel_case("target_size")
    scenario["source_units"] = [
        {
            "id": "su_whole",
            "hostel_id": "spec_hostel",
            "layout_status": "estimated",
            "estimated_attendance": 120,
            "resolved_attendance": 120,
            "actual_reporting_s": 0,
            "readiness_s": 0,
            "origin_place_id": "origin",
        }
    ]
    policy["grouping"] = {
        "mode": "from_source_units",
        "basis": "target_size",
        "target_students": 40,
        "split_policy": "permit_supervised_split",
        "mixing_policy": "same_hostel",
        "adaptation_rule": {"type": "fixed"},
        "regroup_policy": {"required": False},
    }
    result = simulate(scenario, policy)
    assert result["grouping"]["layout_status"] == "estimated"
    assert _group_sizes(result) == [40, 40, 40]
    assert result["grouping"]["total_resolved_attendance"] == 120
    assert all(group["layout_status"] == "estimated" for group in result["grouping"]["groups"])


def test_spec_120_floor_wing_and_floor_wing_grouping():
    expected = {
        "floor": [40, 40, 40],
        "wing": [60, 60],
        "floor_wing": [20, 20, 20, 20, 20, 20],
        "hostel": [120],
        "building": [120],
    }
    key_sets = {}
    for basis, sizes in expected.items():
        scenario, policy = build_artificial_120_hostel_case(basis)
        result = simulate(scenario, policy)
        assert result["status"] == "completed"
        assert result["grouping"]["total_resolved_attendance"] == 120
        assert _group_sizes(result) == sizes
        keys = _student_keys(result)
        assert len(keys) == 120
        assert len(set(keys)) == 120
        key_sets[basis] = set(keys)
        assert result["measures"]["completed_students"] == 120
    assert key_sets["floor"] == key_sets["wing"] == key_sets["floor_wing"]


def test_policy_selects_grouping_fields_and_overrides():
    scenario, policy = build_rst_shared_fleet_case()
    policy["grouping"] = {
        "mode": "from_source_units",
        "basis": "mixed",
        "mixed_default": "hostel",
        "scope_overrides": {"restu": "floor", "saujana": "hostel"},
        "units_per_group": 1,
        "min_students": 1,
        "max_students": 80,
        "maximum_assembly_wait_s": 0,
        "split_policy": "permit_supervised_split",
        "mixing_policy": "same_hostel",
        "regroup_policy": {"required": False, "place_id": "dtsp_alighting_area"},
        "adaptation_rule": {"type": "fixed"},
        "escorts_per_group": 1,
    }
    result = simulate(scenario, policy)
    grouping = result["input_snapshot"]["policy"]["grouping"]
    assert grouping["basis"] == "mixed"
    assert grouping["scope_overrides"]["restu"] == "floor"
    assert grouping["units_per_group"] == 1
    assert grouping["split_policy"] == "permit_supervised_split"
    assert grouping["mixing_policy"] == "same_hostel"
    assert grouping["adaptation_rule"]["type"] == "fixed"
    assert result["status"] == "completed"


def test_changing_grouping_does_not_change_attendance_or_limits():
    floor_scenario, floor_policy = build_artificial_120_hostel_case("floor")
    wing_scenario, wing_policy = build_artificial_120_hostel_case("wing")
    floor = simulate(floor_scenario, floor_policy)
    wing = simulate(wing_scenario, wing_policy)
    assert floor["grouping"]["total_resolved_attendance"] == wing["grouping"]["total_resolved_attendance"] == 120
    assert floor_scenario["source_units"][0]["resolved_attendance"] == 20
    assert wing_scenario["source_units"][0]["resolved_attendance"] == 20
    assert floor_scenario["places"][0]["capacity_constraint"] == wing_scenario["places"][0]["capacity_constraint"]
    assert floor_scenario["source_units"][0]["actual_reporting_s"] == wing_scenario["source_units"][0]["actual_reporting_s"]
    assert floor_scenario["operating_rules"]["required_endpoint"] == wing_scenario["operating_rules"]["required_endpoint"]


def test_creating_groups_adds_no_headcount_or_workers():
    scenario, policy = build_artificial_120_hostel_case("floor")
    workers_before = copy.deepcopy(scenario["initial_state"]["workers"])
    result = simulate(scenario, policy)
    assert result["grouping"]["headcounts_added"] == 0
    assert result["grouping"]["worker_assignments_added"] == 0
    assert result["grouping"]["setup_delay_s"] == 0
    assert _headcount_events(result) == []
    assert result["input_snapshot"]["scenario"]["initial_state"]["workers"] == workers_before
    for group in result["grouping"]["groups"]:
        assert group["headcount_added"] is False
        assert group["workers_assigned_on_create"] == 0
        assert group["setup_delay_s"] == 0
        assert group["count_record_ids"] == []
        assert group["required_supervision"] == {"escorts": 1}


def test_declared_physical_assembly_uses_declared_time_not_auto_workers():
    scenario, policy = build_artificial_120_hostel_case("floor")
    policy["grouping"]["physical_assembly"] = {
        "duration_s": 15,
        "place_id": "origin",
        "worker_count": 2,
    }
    scenario["initial_state"]["workers"] = [
        {"id": "w1", "role": "escort", "place_id": "origin"},
        {"id": "w2", "role": "escort", "place_id": "origin"},
    ]
    result = simulate(scenario, policy)
    times = [row["completion_time_s"] for row in result["outcomes"]["student_completions"]]
    assert times
    assert min(times) == pytest.approx(25.0)
    assert len(result["input_snapshot"]["scenario"]["initial_state"]["workers"]) == 2
    assert _headcount_events(result) == []


def test_exact_target_size_requires_method():
    scenario, policy = build_artificial_120_hostel_case(
        "target_size",
        grouping_updates={
            "target_students": 40,
            "exact_size": True,
            "split_policy": "permit_supervised_split",
        },
    )
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "unresolved_assumption"
    policy["grouping"]["exact_size_method"] = "count_during_boarding"
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert _headcount_events(result) == []


def test_sixty_versus_fifty_requires_split_or_infeasible():
    blocked_scenario, blocked_policy = build_ticket02_bus_case(
        grouping_basis="wing",
        split_policy="forbid",
        bus_capacity=50,
        n_buses=1,
        include_cycle=True,
    )
    blocked = simulate(blocked_scenario, blocked_policy)
    assert blocked["status"] == "infeasible"
    assert blocked["violations"]

    split_scenario, split_policy = build_ticket02_bus_case(
        grouping_basis="wing",
        split_policy="permit_supervised_split",
        bus_capacity=50,
        n_buses=1,
        include_cycle=True,
    )
    split = simulate(split_scenario, split_policy)
    assert split["status"] == "completed"
    assert any(event["event_type"] == "part_split" for event in split["event_trace"])
    assert _headcount_events(split) == []
    split_parts = [
        event
        for event in split["event_trace"]
        if event["event_type"] == "part_split" or "~split" in str(event.get("affected_part_id"))
    ]
    group_ids = {group["group_id"] for group in split["grouping"]["groups"]}
    assert len(group_ids) == 2
    for event in split["event_trace"]:
        if event.get("affected_part_id") and "~split" in str(event["affected_part_id"]):
            assert event["affected_group_id"] in group_ids
    completions = split["outcomes"]["student_completions"]
    assert len(completions) == 120
    for row in completions:
        assert row["group_id"] in group_ids


def test_split_retains_lineage_and_hostel_counts():
    scenario, policy = build_ticket02_bus_case(
        grouping_basis="wing",
        split_policy="permit_supervised_split",
        bus_capacity=50,
        n_buses=1,
    )
    result = simulate(scenario, policy)
    split_events = [event for event in result["event_trace"] if event["event_type"] == "part_split"]
    assert split_events
    board_events = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "batch_start" and event.get("primary_cause") == "board"
    ]
    assert board_events
    for event in board_events:
        assert event["hostel_composition"]
        assert sum(event["hostel_composition"].values()) == event["student_count"]
        assert event["student_count"] <= 50


def test_mixed_hostel_load_keeps_separate_counts():
    scenario, policy = build_rst_shared_fleet_case(n_buses=2, bus_capacity=40)
    policy["grouping"]["mixing_policy"] = "permit_mixed_hostels"
    policy["grouping"]["basis"] = "target_size"
    policy["grouping"]["target_students"] = 30
    policy["grouping"]["split_policy"] = "permit_supervised_split"
    policy["grouping"]["regroup_policy"] = {
        "required": True,
        "place_id": "dtsp_alighting_area",
        "duration_s": 0,
        "worker_count": 0,
    }
    result = simulate(scenario, policy)
    mixed = [
        group
        for group in result["grouping"]["groups"]
        if len(group["hostel_composition"]) > 1
    ]
    assert mixed
    for group in mixed:
        assert set(group["hostel_composition"]) <= {"restu", "saujana", "tekun"}
        assert sum(group["hostel_composition"].values()) == group["student_count"]
    assert result["grouping"]["regroup_policy"]["required"] is True


def test_rst_hostels_share_fleet_with_separate_approaches():
    scenario, policy = build_rst_shared_fleet_case(n_buses=1, bus_capacity=40)
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert scenario["operating_rules"]["route_id"] == "rst_fixed_bus_chain"
    assert scenario["operating_rules"]["direct_walk_permitted"] is False
    approach_legs = {
        event["leg_id"]
        for event in result["event_trace"]
        if event["event_type"] == "departure" and event.get("leg_id", "").startswith("leg_approach_")
    }
    assert approach_legs == {"leg_approach_restu", "leg_approach_saujana", "leg_approach_tekun"}
    boarded_resources = {
        tuple(event["resource_ids"])
        for event in result["event_trace"]
        if event["event_type"] == "batch_start" and event.get("primary_cause") == "board"
    }
    assert boarded_resources
    for resource_ids in boarded_resources:
        assert resource_ids[0].startswith("coach_")
    hostels = {group["hostel_id"] for group in result["grouping"]["groups"]}
    assert hostels == {"restu", "saujana", "tekun"}


def test_coach_properties_are_not_copied_to_electric():
    scenario, policy = build_ticket02_bus_case(
        grouping_basis="floor_wing",
        split_policy="forbid",
        bus_capacity=20,
        n_buses=1,
    )
    scenario["initial_state"]["vehicles"].append(
        {
            "id": "electric_1",
            "type": "electric",
            "place_id": "origin",
            "available_time_s": 0,
            "capacity_students": 20,
            "calendar_id": "fleet_service",
        }
    )
    scenario["fleets"][0]["vehicle_ids"].append("electric_1")
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "unknown_reference"
    assert "electric" in caught.value.message

    electric_type = {
        "id": "electric",
        "capacity_students": 30,
        "seated_capacity_students": 20,
        "usable_doors": 2,
        "boarding_setup_s": 2,
        "boarding_s_per_passenger_per_door": 0.5,
        "alighting_setup_s": 2,
        "alighting_s_per_passenger_per_door": 0.2,
        "return_travel_s": 25,
        "turnaround_s": 8,
    }
    scenario, policy = build_ticket02_bus_case(
        grouping_basis="floor_wing",
        split_policy="forbid",
        bus_capacity=20,
        n_buses=1,
        extra_vehicle_types=[electric_type],
        extra_vehicles=[
            {
                "id": "electric_1",
                "type": "electric",
                "place_id": "origin",
                "available_time_s": 10,
                "capacity_students": 20,
                "calendar_id": "fleet_service",
            }
        ],
    )
    result = simulate(scenario, policy)
    kinds = {row["kind"] for row in result["resource_summaries"]}
    assert "coach" in kinds
    assert "electric" in kinds
    electric = next(row for row in result["resource_summaries"] if row["kind"] == "electric")
    coach = next(row for row in result["resource_summaries"] if row["kind"] == "coach")
    assert electric["capacity_students"] == 20
    assert coach["capacity_students"] == 20
    assert electric["resource_id"] != coach["resource_id"]


def test_boarding_time_depends_on_load_not_universal_105s():
    scenario, policy = build_ticket02_bus_case(
        grouping_basis="floor_wing",
        split_policy="forbid",
        bus_capacity=20,
        n_buses=2,
        boarding_berth_capacity=2,
        dropoff_space_capacity=2,
    )
    result = simulate(scenario, policy)
    board = next(
        event
        for event in result["event_trace"]
        if event["event_type"] == "batch_start" and event.get("primary_cause") == "board"
    )
    complete = next(
        event
        for event in result["event_trace"]
        if event["event_type"] == "batch_complete"
        and event.get("affected_part_id") == board["affected_part_id"]
        and event.get("primary_cause") == "board"
    )
    duration_s = (complete["time_ms"] - board["time_ms"]) / 1000.0
    assert duration_s == pytest.approx(45.0)
    assert duration_s != pytest.approx(105.0)


def test_bus_stays_unavailable_for_full_cycle():
    scenario, policy = build_ticket02_bus_case(
        grouping_basis="floor_wing",
        split_policy="forbid",
        bus_capacity=20,
        n_buses=1,
        include_cycle=True,
        boarding_berth_capacity=1,
        dropoff_space_capacity=1,
    )
    result = simulate(scenario, policy)
    boards = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "batch_start" and event.get("primary_cause") == "board"
    ]
    boards.sort(key=lambda event: event["time_ms"])
    assert len(boards) >= 2
    first = boards[0]["time_ms"]
    second = boards[1]["time_ms"]
    min_cycle_s = 45 + 20 + 15 + 30 + 10
    assert (second - first) / 1000.0 >= min_cycle_s - 0.001
    types = {event["event_type"] for event in result["event_trace"]}
    assert "vehicle_return_complete" in types
    assert "vehicle_turnaround_complete" in types


def test_berth_and_outage_restrict_fleet_use():
    outage_scenario, outage_policy = build_ticket02_bus_case(
        grouping_basis="floor_wing",
        split_policy="forbid",
        bus_capacity=20,
        n_buses=1,
        boarding_berth_capacity=1,
        dropoff_space_capacity=1,
        include_cycle=True,
        outages=[{"start_s": 0, "end_s": 40}],
    )
    outage_result = simulate(outage_scenario, outage_policy)
    first_board = next(
        event
        for event in outage_result["event_trace"]
        if event["event_type"] == "batch_start" and event.get("primary_cause") == "board"
    )
    assert first_board["time_ms"] >= 40000

    berth_scenario, berth_policy = build_ticket02_bus_case(
        grouping_basis="floor_wing",
        split_policy="forbid",
        bus_capacity=20,
        n_buses=2,
        boarding_berth_capacity=1,
        dropoff_space_capacity=1,
        include_cycle=True,
    )
    berth_result = simulate(berth_scenario, berth_policy)
    boards = [
        event
        for event in berth_result["event_trace"]
        if event["event_type"] == "batch_start" and event.get("primary_cause") == "board"
    ]
    overlapping = 0
    for left in boards:
        for right in boards:
            if left["event_id"] >= right["event_id"]:
                continue
            left_end = left["time_ms"] + 45000
            if left["time_ms"] < right["time_ms"] < left_end:
                overlapping += 1
    assert overlapping == 0


def test_fleet_size_bus_wait_comparison_does_not_claim_total_wait_always_falls():
    one_scenario, one_policy = build_ticket02_bus_case(
        grouping_basis="floor",
        split_policy="forbid",
        bus_capacity=40,
        n_buses=1,
        include_cycle=True,
        hall_open_s=10000,
        boarding_berth_capacity=1,
        dropoff_space_capacity=1,
    )
    two_scenario, two_policy = build_ticket02_bus_case(
        grouping_basis="floor",
        split_policy="forbid",
        bus_capacity=40,
        n_buses=2,
        include_cycle=True,
        hall_open_s=10000,
        boarding_berth_capacity=2,
        dropoff_space_capacity=2,
    )
    one = simulate(one_scenario, one_policy)
    two = simulate(two_scenario, two_policy)
    one_bus_wait = one["measures"]["waiting_student_s_by_cause"].get("waiting_for_vehicle", 0.0)
    two_bus_wait = two["measures"]["waiting_student_s_by_cause"].get("waiting_for_vehicle", 0.0)
    assert two_bus_wait < one_bus_wait
    assert one["status"] == "completed"
    assert two["status"] == "completed"


def test_internal_calculation_parts_preserve_physical_outcome():
    whole_scenario, whole_policy = build_artificial_120_hostel_case("floor")
    fine_scenario, fine_policy = build_artificial_120_hostel_case(
        "floor", grouping_updates={"internal_part_size": 1}
    )
    coarse_scenario, coarse_policy = build_artificial_120_hostel_case(
        "floor", grouping_updates={"internal_part_size": 20}
    )
    whole = simulate(whole_scenario, whole_policy)
    fine = simulate(fine_scenario, fine_policy)
    coarse = simulate(coarse_scenario, coarse_policy)
    limit = whole_policy["numerical_rounding_limit_s"]
    for result in (whole, fine, coarse):
        times = [row["completion_time_s"] for row in result["outcomes"]["student_completions"]]
        assert times
        assert max(times) == pytest.approx(10.0, abs=limit)
        assert min(times) == pytest.approx(10.0, abs=limit)
        assert result["measures"]["completed_students"] == 120
        assert result["measures"]["total_queue_waiting_student_s"] == pytest.approx(0.0, abs=limit)
        assert _headcount_events(result) == []


def test_grouping_determinism():
    scenario, policy = build_rst_shared_fleet_case(n_buses=2)
    first = simulate(scenario, policy)
    second = simulate(scenario, policy)
    assert first["status"] == second["status"]
    assert first["event_trace"] == second["event_trace"]
    assert first["measures"] == second["measures"]
    assert first["grouping"]["groups"] == second["grouping"]["groups"]


def test_missing_grouping_and_vehicle_fields_fail_clearly():
    scenario, policy = build_artificial_120_hostel_case("floor")
    policy["grouping"]["basis"] = "not_a_basis"
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "unsupported_policy"

    scenario, policy = build_ticket02_bus_case(n_buses=1, bus_capacity=40)
    del scenario["fleets"][0]["boarding_berth_capacity"]
    with pytest.raises(SimulationError) as caught_berth:
        simulate(scenario, policy)
    assert caught_berth.value.category == "missing_input"

    scenario, policy = build_artificial_120_hostel_case("floor")
    policy["grouping"]["adaptation_rule"] = {"type": "release_ready"}
    with pytest.raises(SimulationError) as caught_adapt:
        simulate(scenario, policy)
    assert caught_adapt.value.category == "missing_input"


def test_occupancy_weight_zero_is_rejected():
    units = [
        {
            "id": "a",
            "hostel_id": "h",
            "layout_status": "estimated",
            "occupancy_weight": 0,
        },
        {
            "id": "b",
            "hostel_id": "h",
            "layout_status": "estimated",
            "occupancy_weight": 1,
        },
    ]
    hostels = [
        {
            "id": "h",
            "expected_event_attendance": 10,
            "resolved_attendance": 10,
        }
    ]
    with pytest.raises(SimulationError) as caught:
        materialize_groups(
            units,
            {"basis": "hostel", "adaptation_rule": {"type": "fixed"}},
            hostels,
        )
    assert caught.value.category == "invalid_value_or_unit"


def test_equal_share_when_all_occupancy_weights_omitted():
    units = [
        {"id": "a", "hostel_id": "h", "layout_status": "estimated"},
        {"id": "b", "hostel_id": "h", "layout_status": "estimated"},
    ]
    hostels = [
        {
            "id": "h",
            "expected_event_attendance": 10,
            "resolved_attendance": 10,
        }
    ]
    summary = materialize_groups(
        units,
        {"basis": "hostel", "adaptation_rule": {"type": "fixed"}},
        hostels,
    )
    counts = {unit["id"]: unit["resolved_attendance"] for unit in summary["source_units"]}
    assert counts == {"a": 5, "b": 5}
    assert summary["total_resolved_attendance"] == 10


def test_overlapping_layout_units_are_rejected():
    units = [
        {
            "id": "u1",
            "hostel_id": "h",
            "floor_id": "1",
            "wing_id": "east",
            "layout_status": "estimated",
            "estimated_attendance": 5,
            "resolved_attendance": 5,
        },
        {
            "id": "u2",
            "hostel_id": "h",
            "floor_id": "1",
            "wing_id": "east",
            "layout_status": "estimated",
            "estimated_attendance": 5,
            "resolved_attendance": 5,
        },
    ]
    with pytest.raises(SimulationError) as caught:
        materialize_groups(
            units,
            {"basis": "floor_wing", "adaptation_rule": {"type": "fixed"}},
        )
    assert caught.value.category == "invalid_value_or_unit"


def test_min_students_cannot_exceed_max_students():
    scenario, policy = build_artificial_120_hostel_case(
        "floor",
        grouping_updates={
            "min_students": 80,
            "max_students": 10,
            "split_policy": "permit_supervised_split",
        },
    )
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "invalid_value_or_unit"


def test_internal_part_size_does_not_change_bus_outcome():
    whole_scenario, whole_policy = build_ticket02_bus_case(
        grouping_basis="floor",
        split_policy="forbid",
        bus_capacity=40,
        n_buses=1,
        include_cycle=True,
    )
    fine_scenario, fine_policy = build_ticket02_bus_case(
        grouping_basis="floor",
        split_policy="forbid",
        bus_capacity=40,
        n_buses=1,
        include_cycle=True,
        grouping_updates={"internal_part_size": 1},
    )
    whole = simulate(whole_scenario, whole_policy)
    fine = simulate(fine_scenario, fine_policy)
    limit = whole_policy["numerical_rounding_limit_s"]
    whole_times = [row["completion_time_s"] for row in whole["outcomes"]["student_completions"]]
    fine_times = [row["completion_time_s"] for row in fine["outcomes"]["student_completions"]]
    assert whole["status"] == fine["status"] == "completed"
    assert max(whole_times) == pytest.approx(max(fine_times), abs=limit)
    assert whole["measures"]["waiting_student_s_by_cause"].get(
        "waiting_for_vehicle", 0.0
    ) == pytest.approx(
        fine["measures"]["waiting_student_s_by_cause"].get("waiting_for_vehicle", 0.0),
        abs=limit,
    )
    assert _headcount_events(whole) == []
    assert _headcount_events(fine) == []


def test_physical_assembly_needs_declared_workers():
    scenario, policy = build_artificial_120_hostel_case("floor")
    policy["grouping"]["physical_assembly"] = {
        "duration_s": 15,
        "place_id": "origin",
        "worker_count": 2,
    }
    scenario["initial_state"]["workers"] = []
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "impossible_static_requirement"


def test_zero_dropoff_space_is_infeasible():
    scenario, policy = build_ticket02_bus_case(
        grouping_basis="floor_wing",
        split_policy="forbid",
        bus_capacity=20,
        n_buses=1,
        include_cycle=True,
        dropoff_space_capacity=0,
    )
    result = simulate(scenario, policy)
    assert result["status"] == "infeasible"
    assert any(row.get("resource") == "dropoff_space" for row in result["violations"])


def test_required_regroup_needs_place():
    scenario, policy = build_artificial_120_hostel_case("floor")
    policy["grouping"]["regroup_policy"] = {"required": True}
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "missing_input"


def test_materialize_helper_accepts_any_hostel_id():
    units = [
        {
            "id": "su_a",
            "hostel_id": "indah_kembara",
            "floor_id": "1",
            "wing_id": "east",
            "layout_status": "estimated",
            "estimated_attendance": 10,
            "resolved_attendance": 10,
        },
        {
            "id": "su_b",
            "hostel_id": "fajar_harapan",
            "floor_id": "1",
            "wing_id": "west",
            "layout_status": "estimated",
            "estimated_attendance": 10,
            "resolved_attendance": 10,
        },
    ]
    summary = materialize_groups(
        units,
        {"basis": "hostel", "adaptation_rule": {"type": "fixed"}},
    )
    hostels = {group["hostel_id"] for group in summary["groups"]}
    assert hostels == {"indah_kembara", "fajar_harapan"}
    assert summary["total_resolved_attendance"] == 20
    assert summary["headcounts_added"] == 0


def _accounted(result: dict) -> int:
    measures = result["measures"]
    return (
        int(measures["completed_students"])
        + int(measures.get("withdrawn_students") or 0)
        + int(measures["unfinished_students"])
    )


def _unique_student_keys(result: dict) -> list[str]:
    keys = []
    for group in result["grouping"]["groups"]:
        keys.extend(member["student_key"] for member in group.get("members") or [])
    return keys


def test_units_per_group_one_keeps_all_120_students():
    scenario, policy = build_artificial_120_hostel_case(
        "hostel", grouping_updates={"units_per_group": 1}
    )
    result = simulate(scenario, policy)
    grouped_ids = [group["group_id"] for group in result["grouping"]["groups"]]
    group_keys = _unique_student_keys(result)
    completion_keys = [row["student_key"] for row in result["outcomes"]["student_completions"]]
    engine_parts = [
        event["affected_part_id"]
        for event in result["event_trace"]
        if event.get("event_type") == "part_ready"
    ]
    attending = sum(unit["resolved_attendance"] for unit in scenario["source_units"])
    assert attending == 120
    assert result["status"] == "completed"
    assert len(result["grouping"]["groups"]) == 6
    assert len(set(grouped_ids)) == 6
    assert [group["student_count"] for group in result["grouping"]["groups"]] == [20] * 6
    assert len(engine_parts) == 6
    assert len(set(engine_parts)) == 6
    assert len(group_keys) == 120
    assert len(set(group_keys)) == 120
    assert len(completion_keys) == 120
    assert len(set(completion_keys)) == 120
    assert set(group_keys) == set(completion_keys)
    assert _accounted(result) == 120
    assert result["measures"]["completed_students"] == 120

    floor_scenario, floor_policy = build_artificial_120_hostel_case(
        "floor", grouping_updates={"units_per_group": 1}
    )
    floor = simulate(floor_scenario, floor_policy)
    floor_keys = _unique_student_keys(floor)
    floor_ready = [
        event["affected_part_id"]
        for event in floor["event_trace"]
        if event.get("event_type") == "part_ready"
    ]
    assert floor["status"] == "completed"
    assert len(set(floor_ready)) == 6
    assert len(floor_ready) == 6
    assert len(set(floor_keys)) == 120
    assert _accounted(floor) == 120


def test_max_students_keeps_both_halves_of_a_40_student_group():
    scenario, policy = build_artificial_120_hostel_case(
        "floor",
        grouping_updates={
            "max_students": 20,
            "split_policy": "permit_supervised_split",
        },
    )
    result = simulate(scenario, policy)
    groups = result["grouping"]["groups"]
    keys = _unique_student_keys(result)
    completion_keys = [row["student_key"] for row in result["outcomes"]["student_completions"]]
    ids = [group["group_id"] for group in groups]
    ready = [
        event["affected_part_id"]
        for event in result["event_trace"]
        if event.get("event_type") == "part_ready"
    ]
    assert any(group["student_count"] == 20 for group in groups)
    assert len(ids) == len(set(ids)) == 6
    assert len(ready) == 6
    assert len(set(ready)) == 6
    assert len(keys) == 120
    assert len(set(keys)) == 120
    assert len(set(completion_keys)) == 120
    assert _accounted(result) == 120
    assert result["measures"]["completed_students"] == 120


def test_duplicate_part_ids_are_rejected():
    scenario, policy = build_artificial_120_hostel_case("floor")
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    scenario, policy = build_artificial_single_server_case()
    seed = copy.deepcopy(scenario["initial_state"]["students"][0])
    other = copy.deepcopy(seed)
    scenario["initial_state"]["students"] = [seed, other]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "invalid_value_or_unit"
    assert "part" in caught.value.message.lower() or "part_id" in (caught.value.field or "")


def test_overlapping_members_across_parts_are_rejected():
    scenario, policy = build_artificial_single_server_case()
    seed = copy.deepcopy(scenario["initial_state"]["students"][0])
    other = copy.deepcopy(seed)
    other["part_id"] = "part_overlap"
    other["group_id"] = "g_overlap"
    scenario["initial_state"]["students"] = [seed, other]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "invalid_value_or_unit"
    assert "overlap" in caught.value.message.lower() or "duplicate" in caught.value.message.lower()


def test_missing_source_members_are_rejected():
    scenario, policy = build_artificial_single_server_case()
    part = scenario["initial_state"]["students"][0]
    part["members"] = part["members"][:2]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "invalid_value_or_unit"


def test_mixed_policy_scope_overrides_to_target_size_packs_only_that_hostel():
    scenario, policy = build_rst_shared_fleet_case(n_buses=2, bus_capacity=40)
    policy["grouping"]["basis"] = "mixed"
    policy["grouping"]["mixed_default"] = "floor"
    policy["grouping"]["scope_overrides"] = {"restu": "target_size"}
    policy["grouping"]["target_students"] = 20
    policy["grouping"]["split_policy"] = "permit_supervised_split"
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    restu_groups = [g for g in result["grouping"]["groups"] if g["hostel_id"] == "restu"]
    other_groups = [g for g in result["grouping"]["groups"] if g["hostel_id"] != "restu"]
    assert all(g["student_count"] <= 20 for g in restu_groups)
    assert any(g["student_count"] == 20 for g in restu_groups)
    # Saujana and Tekun remain grouped by floor
    for g in other_groups:
        assert "floor" in g["group_id"] or g["student_count"] in {12, 20}
    assert result["measures"]["completed_students"] == sum(
        u["resolved_attendance"] for u in scenario["source_units"]
    )


def test_mixed_origin_without_routes_or_permitted_join_is_rejected():
    scenario, policy = build_rst_shared_fleet_case()
    scenario["routes"] = {}  # Remove approaches
    policy["grouping"]["mixing_policy"] = "permit_mixed_hostels"
    policy["grouping"]["basis"] = "target_size"
    policy["grouping"]["target_students"] = 30
    policy["grouping"]["split_policy"] = "permit_supervised_split"
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "unsupported_policy"
    assert "mixed-origin" in caught.value.message.lower()


def test_mixed_origin_with_routes_still_requires_a_physical_join():
    scenario, policy = build_rst_shared_fleet_case()
    policy["grouping"]["mixing_policy"] = "permit_mixed_hostels"
    policy["grouping"]["basis"] = "target_size"
    policy["grouping"]["target_students"] = 30
    policy["grouping"]["split_policy"] = "permit_supervised_split"
    policy["grouping"]["exact_size"] = True
    policy["grouping"]["exact_size_method"] = "count_during_boarding"
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "unsupported_policy"
    assert "mixed-origin" in caught.value.message.lower()


def test_mixed_origin_with_regroup_starts_at_each_origin_place():
    scenario, policy = build_rst_shared_fleet_case()
    policy["grouping"]["mixing_policy"] = "permit_mixed_hostels"
    policy["grouping"]["basis"] = "target_size"
    policy["grouping"]["target_students"] = 30
    policy["grouping"]["split_policy"] = "permit_supervised_split"
    policy["grouping"]["exact_size"] = True
    policy["grouping"]["exact_size_method"] = "count_during_boarding"
    policy["grouping"]["regroup_policy"] = {
        "required": True,
        "place_id": "dtsp_alighting_area",
        "duration_s": 20.0,
        "worker_count": 0,
    }
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    ready = [e for e in result["event_trace"] if e["event_type"] == "part_ready"]
    places = {e.get("place_id") for e in ready}
    assert "restu_origin" in places
    assert "saujana_origin" in places or "tekun_origin" in places
    assert result["measures"]["completed_students"] == 60
    join = [
        e
        for e in result["event_trace"]
        if e.get("primary_cause") in {"waiting_for_regroup", "group_assembled"}
        and e.get("place_id") == "dtsp_alighting_area"
    ]
    assert join


def test_target_size_estimation_different_from_hidden_attendance():
    scenario, policy = build_artificial_120_hostel_case("floor")
    # Modify one source unit: estimated 20, but actual 25
    scenario["source_units"][0]["estimated_attendance"] = 20
    scenario["source_units"][0]["resolved_attendance"] = 25
    scenario["source_units"][1]["estimated_attendance"] = 20
    scenario["source_units"][1]["resolved_attendance"] = 15
    
    policy["grouping"]["basis"] = "target_size"
    policy["grouping"]["target_students"] = 20
    policy["grouping"]["split_policy"] = "keep_units_whole"
    policy["grouping"]["exact_size"] = False
    
    res_est = simulate(scenario, policy)
    # The first group received the whole unit of 25 because planner estimated it as 20
    first_group = res_est["grouping"]["groups"][0]
    assert first_group["student_count"] == 25
    
    # Now with paid exact size count
    policy["grouping"]["exact_size"] = True
    policy["grouping"]["exact_size_method"] = "count_during_boarding"
    policy["grouping"]["split_policy"] = "permit_supervised_split"
    res_exact = simulate(scenario, policy)
    first_exact = res_exact["grouping"]["groups"][0]
    assert first_exact["student_count"] == 20
