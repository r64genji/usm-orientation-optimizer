"""Acceptance tests for ticket 05: eight-hostel shared movement system."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from usm_sim import (
    HOSTEL_IDS,
    NORTH_WALK_HOSTEL_IDS,
    RST_HOSTEL_IDS,
    SOUTH_WALK_HOSTEL_IDS,
    WALK_HOSTEL_IDS,
    SimulationError,
    append_origin,
    build_artificial_single_server_case,
    build_restu_17sep_replay,
    build_whole_campus_origins_case,
    effective_seats,
    simulate,
)
from usm_sim.campus import (
    FREE_WALK_M_S,
    SHARED_FOYER_PASSAGE,
    SHARED_PATH_JALAN_UNIVERSITI_EAST,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _by_id(rows: list[dict], key: str = "id") -> dict:
    return {row[key]: row for row in rows}


def _first_arrival(result: dict, place_id: str, hostel_id: str) -> dict | None:
    for event in result["event_trace"]:
        if event["event_type"] != "arrival" or event.get("place_id") != place_id:
            continue
        composition = event.get("hostel_composition") or {}
        if hostel_id in composition:
            return event
    return None


def test_eight_hostels_have_coords_demand_route_and_provenance():
    scenario, policy = build_whole_campus_origins_case()
    hostels = _by_id(scenario["hostels"])
    assert tuple(hostels) == HOSTEL_IDS
    places = _by_id(scenario["places"])
    walking = _by_id(scenario["walking_routes"], "hostel_id")
    for hostel_id, hostel in hostels.items():
        assert hostel["latitude_deg"] is not None
        assert hostel["longitude_deg"] is not None
        origin = hostel["origin_place_id"]
        assert origin in places
        assert places[origin]["latitude_deg"] == pytest.approx(hostel["latitude_deg"])
        assert places[origin]["longitude_deg"] == pytest.approx(hostel["longitude_deg"])
        for field in (
            "registration",
            "bed_capacity",
            "resident_occupancy",
            "expected_event_attendance",
            "resolved_attendance",
        ):
            assert field in hostel
        assert hostel_id in scenario["routes"]
        assert scenario["routes"][hostel_id]
        coord_records = [
            row
            for row in scenario["source_records"]
            if row["field"].startswith(f"hostels.{hostel_id}.")
        ]
        assert coord_records
        for row in coord_records:
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
                assert row[key] not in (None, "") or key == "value"
        if hostel["initial_route"] == "walk":
            route = walking[hostel_id]
            assert route["distance_m"] > 0
            assert route["duration_s"] > 0
            assert len(route["duration_range_s"]) == 2
            assert route["source"]
            assert route["method"] == "map_estimate"
            assert route["not_driving_route"] is True
            assert route["not_restu_congested_speed"] is True
            assert route["walking_speed_m_s"] == FREE_WALK_M_S
            assert "access_limits" in route
            assert "crossings" in route
            assert "shared_sections" in route
    assert hostels["restu"]["registration"] is None
    assert hostels["cahaya_gemilang"]["registration"] is None
    assert hostels["fajar_harapan"]["registration"] is None
    assert hostels["saujana"]["registration"] == 610
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["completed_students"] == 64


def test_demand_fields_are_not_silently_equal():
    scenario, policy = build_whole_campus_origins_case()
    for hostel in scenario["hostels"]:
        numbers = [
            hostel.get("registration"),
            hostel.get("bed_capacity"),
            hostel["resident_occupancy"],
            hostel["expected_event_attendance"],
            hostel["resolved_attendance"],
        ]
        present = [value for value in numbers if isinstance(value, int)]
        assert len(set(present)) == len(present)
        assert hostel["resident_occupancy"] != hostel["expected_event_attendance"]
        assert hostel["expected_event_attendance"] != hostel["resolved_attendance"]
        estimate = hostel.get("resident_occupancy_estimate")
        if estimate:
            assert estimate["lower"] <= estimate["base"] <= estimate["upper"]
        assert hostel["layout_status"] == "estimated"
    for unit in scenario["source_units"]:
        assert unit["layout_status"] == "estimated"
        assert unit["late_assembly_rule"] == "explicit_event"
        assert unit["non_attendance_rule"] == "explicit"
        assert unit["withdrawal_rule"] == "explicit_event"
        assert unit["actual_reporting_s"] == 0
        assert unit["readiness_s"] == 0
    rules = scenario["operating_rules"]
    assert rules["late_assembly"] == "explicit_event"
    assert rules["non_attendance"] == "explicit"
    assert rules["optional_withdrawal"] == "explicit_event"
    result = simulate(scenario, policy)
    snap = result["input_snapshot"]["scenario"]["hostels"]
    assert snap[0]["resident_occupancy"] != snap[0]["resolved_attendance"]


def test_rst_uses_bus_and_other_origins_walk():
    scenario, policy = build_whole_campus_origins_case()
    hostels = _by_id(scenario["hostels"])
    stages = _by_id(scenario["route_stages"])
    legs = _by_id(scenario["route_legs"])
    for hostel_id in RST_HOSTEL_IDS:
        assert hostels[hostel_id]["initial_route"] == "rst_bus"
        kinds = [stages[stage_id]["kind"] for stage_id in scenario["routes"][hostel_id]]
        assert "vehicle_travel" in kinds
        transit = stages["transit"]
        assert legs[transit["leg_id"]]["mode"] == "coach"
    for hostel_id in WALK_HOSTEL_IDS:
        assert hostels[hostel_id]["initial_route"] == "walk"
        for stage_id in scenario["routes"][hostel_id]:
            stage = stages[stage_id]
            if stage["kind"] not in {"travel", "vehicle_travel"}:
                continue
            assert legs[stage["leg_id"]]["mode"] == "walk"
            assert legs[stage["leg_id"]]["mode"] != "coach"
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    bus_depart = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "departure" and event.get("leg_id") == "leg_transit"
    ]
    assert bus_depart
    walk_depart = [
        event
        for event in result["event_trace"]
        if event["event_type"] == "departure"
        and str(event.get("leg_id") or "").startswith("leg_walk_")
    ]
    assert walk_depart


def test_dtsp_gathering_areas_and_route_splits():
    scenario, policy = build_whole_campus_origins_case()
    places = _by_id(scenario["places"])

    # 1. Places exist with required coordinates, capacities, shelter access
    north = places["dtsp_north_plaza"]
    assert north["latitude_deg"] == pytest.approx(5.356518, abs=1e-6)
    assert north["longitude_deg"] == pytest.approx(100.303214, abs=1e-6)
    assert north["capacity_students"] == 1200
    assert north["shelter_access"] is True

    south = places["dtsp_south_plaza"]
    assert south["latitude_deg"] == pytest.approx(5.356118, abs=1e-6)
    assert south["longitude_deg"] == pytest.approx(100.302400, abs=1e-6)
    assert south["capacity_students"] == 1000
    assert south["shelter_access"] is False

    exterior = places["dtsp_exterior_gathering"]
    assert exterior["latitude_deg"] == pytest.approx(5.357153, abs=1e-6)
    assert exterior["longitude_deg"] == pytest.approx(100.301749, abs=1e-6)
    assert exterior["capacity_students"] in {300, 500, 600}
    assert exterior["shelter_access"] is True

    # 2. Route splits
    routes = scenario["routes"]
    stages = _by_id(scenario["route_stages"])
    legs = _by_id(scenario["route_legs"])

    # Bus cohorts: exterior gathering hold -> door A -> foyer -> seating
    for hid in RST_HOSTEL_IDS:
        r_stages = [stages[sid] for sid in routes[hid]]
        stage_places = [s.get("place_id") for s in r_stages]
        assert "dtsp_exterior_gathering" in stage_places
        assert "dtsp_north_plaza" not in stage_places
        assert "dtsp_south_plaza" not in stage_places
        assert "entrance_door_a" in routes[hid]
        assert "entrance_door_b" not in routes[hid]

    # Northern walkers: dtsp_walk_approach -> north plaza hold -> door A -> foyer -> seating
    for hid in NORTH_WALK_HOSTEL_IDS:
        r_stages = [stages[sid] for sid in routes[hid]]
        stage_places = [s.get("place_id") for s in r_stages]
        assert "dtsp_north_plaza" in stage_places
        assert "dtsp_south_plaza" not in stage_places
        assert "dtsp_exterior_gathering" not in stage_places
        assert "entrance_door_a" in routes[hid]
        assert "entrance_door_b" not in routes[hid]

    # Southern walkers: dtsp_walk_approach -> south plaza hold -> door B -> foyer -> seating
    for hid in SOUTH_WALK_HOSTEL_IDS:
        r_stages = [stages[sid] for sid in routes[hid]]
        stage_places = [s.get("place_id") for s in r_stages]
        assert "dtsp_south_plaza" in stage_places
        assert "dtsp_north_plaza" not in stage_places
        assert "dtsp_exterior_gathering" not in stage_places
        assert "entrance_door_b" in routes[hid]
        assert "entrance_door_a" not in routes[hid]

    # All walkers pass through dtsp_walk_approach
    for hid in WALK_HOSTEL_IDS:
        first_leg = legs[stages[routes[hid][0]]["leg_id"]]
        assert first_leg["to_place_id"] == "dtsp_walk_approach"

    # 3. Simulate and verify non-zero occupancies during arrivals
    result = simulate(scenario, policy)
    assert result["status"] == "completed"

    occ_places = {row["place_id"]: row for row in result["place_occupancy"]}
    assert "dtsp_north_plaza" in occ_places
    assert "dtsp_south_plaza" in occ_places
    assert "dtsp_exterior_gathering" in occ_places

    for pid in ("dtsp_north_plaza", "dtsp_south_plaza", "dtsp_exterior_gathering"):
        in_events = [
            row
            for row in result["occupancy_history"]
            if row.get("place_id") == pid and row.get("direction") == "in"
        ]
        assert len(in_events) > 0
        assert sum(int(r.get("student_count") or 0) for r in in_events) > 0


def test_shared_path_resource_change_affects_both_walking_origins():
    scenario, policy = build_whole_campus_origins_case()
    resources = _by_id(scenario["shared_resources"])
    assert SHARED_PATH_JALAN_UNIVERSITI_EAST in resources
    legs = _by_id(scenario["route_legs"])
    assert SHARED_PATH_JALAN_UNIVERSITI_EAST in legs["leg_walk_indah_kembara"]["shared_resource_ids"]
    assert SHARED_PATH_JALAN_UNIVERSITI_EAST in legs["leg_walk_aman_damai"]["shared_resource_ids"]
    result_a = simulate(scenario, policy)
    indah_a = _first_arrival(result_a, "dtsp_walk_approach", "indah_kembara")
    aman_a = _first_arrival(result_a, "dtsp_walk_approach", "aman_damai")
    assert indah_a is not None
    assert aman_a is not None
    assert SHARED_PATH_JALAN_UNIVERSITI_EAST in (indah_a.get("resource_ids") or [])
    assert SHARED_PATH_JALAN_UNIVERSITI_EAST in (aman_a.get("resource_ids") or [])

    changed = copy.deepcopy(scenario)
    path = _by_id(changed["shared_resources"])[SHARED_PATH_JALAN_UNIVERSITI_EAST]
    path["duration_s"] = int(path["duration_s"]) + 180
    result_b = simulate(changed, policy)
    indah_b = _first_arrival(result_b, "dtsp_walk_approach", "indah_kembara")
    aman_b = _first_arrival(result_b, "dtsp_walk_approach", "aman_damai")
    assert indah_b is not None
    assert aman_b is not None
    indah_delta = indah_b["time_ms"] - indah_a["time_ms"]
    aman_delta = aman_b["time_ms"] - aman_a["time_ms"]
    assert {indah_delta, aman_delta} == {0, 180000}


def test_changing_walking_duration_changes_arrival_time():
    scenario, policy = build_whole_campus_origins_case()
    result_a = simulate(scenario, policy)
    arrival_a = _first_arrival(result_a, "dtsp_walk_approach", "cahaya_gemilang")
    assert arrival_a is not None
    changed = copy.deepcopy(scenario)
    for leg in changed["route_legs"]:
        if leg["id"] == "leg_walk_cahaya_gemilang":
            leg["duration_s"] = int(leg["duration_s"]) + 120
    result_b = simulate(changed, policy)
    arrival_b = _first_arrival(result_b, "dtsp_walk_approach", "cahaya_gemilang")
    assert arrival_b is not None
    assert arrival_b["time_ms"] - arrival_a["time_ms"] == pytest.approx(120000, abs=1)


def test_extra_door_does_not_increase_seat_capacity():
    scenario, policy = build_whole_campus_origins_case()
    dest = scenario["destination"]
    seats = effective_seats(dest)
    seating = _by_id(scenario["places"])["dtsp_seating"]
    assert seating["capacity_students"] == seats
    assert SHARED_FOYER_PASSAGE in dest["shared_internal_path_ids"]
    door_count = len(dest["doors"])
    result_a = simulate(scenario, policy)
    assert result_a["destination"]["effective_seats"] == seats
    assert result_a["destination"]["door_count"] == door_count

    extra = copy.deepcopy(scenario)
    extra["places"].append(
        {
            "id": "dtsp_door_c",
            "latitude_deg": 5.35670,
            "longitude_deg": 100.30320,
            "meaning": "extra DTSP door C",
            "capacity_constraint": "unbounded",
            "capacity_note": "extra door does not add seats",
            "capacity_from_gps_scatter": False,
            "shelter_access": None,
            "closures": [],
            "lift_restriction": None,
            "stair_restriction": None,
        }
    )
    extra["destination"]["doors"].append(
        {
            "id": "door_c",
            "place_id": "dtsp_door_c",
            "approach": "extra",
            "entrance_rate_s_per_person": 1.0,
        }
    )
    extra["route_stages"].append(
        {
            "id": "entrance_door_c",
            "kind": "queue_service",
            "place_id": "dtsp_door_c",
            "service_duration_s": 1.0,
            "server_count": 1,
            "queue_discipline": "fcfs",
            "completion_event": "entrance_completion",
        }
    )
    result_b = simulate(extra, policy)
    assert effective_seats(extra["destination"]) == seats
    assert result_b["destination"]["effective_seats"] == seats
    assert result_b["destination"]["door_count"] == door_count + 1
    assert _by_id(extra["places"])["dtsp_seating"]["capacity_students"] == seats
    assert extra["destination"]["shared_internal_path_ids"] == [SHARED_FOYER_PASSAGE]
    assert result_b["destination"]["shared_internal_path_ids"] == [SHARED_FOYER_PASSAGE]


def test_zero_background_demand_is_a_visible_assumption():
    scenario, policy = build_whole_campus_origins_case()
    background = scenario["background_demand"]
    assert background["pedestrians"] == 0
    assert background["road_crossings"] == 0
    assert background["other_arrivals"] == 0
    assert background["visible_assumption"] is True
    result = simulate(scenario, policy)
    assert result["background_demand"]["pedestrians"] == 0
    assumption_ids = {row["id"] for row in result["visible_assumptions"]}
    assert "zero_background_demand" in assumption_ids
    snap_ids = {
        row["id"]
        for row in result["input_snapshot"]["scenario"]["uncertain_assumptions"]
    }
    assert "zero_background_demand" in snap_ids


def test_ninth_origin_is_data_only():
    scenario, policy = build_whole_campus_origins_case()
    hostel = {
        "id": "synthetic_ninth",
        "name": "Synthetic Ninth",
        "latitude_deg": 5.35800,
        "longitude_deg": 100.29800,
        "registration": 90,
        "registration_status": "assumed",
        "bed_capacity": 120,
        "resident_occupancy": 80,
        "expected_event_attendance": 60,
        "resolved_attendance": 4,
        "initial_route": "walk",
        "origin_place_id": "synthetic_ninth_origin",
        "layout_status": "estimated",
    }
    units = [
        {
            "id": "su_synthetic_ninth",
            "hostel_id": "synthetic_ninth",
            "building_id": "synthetic_ninth_block",
            "floor_id": "1",
            "wing_id": "east",
            "layout_status": "estimated",
            "registration": 90,
            "resident_occupancy": 80,
            "expected_event_attendance": 60,
            "estimated_attendance": 60,
            "resolved_attendance": 4,
            "actual_reporting_s": 0,
            "readiness_s": 0,
            "late_assembly_s": 0,
            "non_attendance": 0,
            "withdrawn": 0,
            "late_assembly_rule": "explicit_event",
            "non_attendance_rule": "explicit",
            "withdrawal_rule": "explicit_event",
            "origin_place_id": "synthetic_ninth_origin",
        }
    ]
    place = {
        "id": "synthetic_ninth_origin",
        "latitude_deg": 5.35800,
        "longitude_deg": 100.29800,
        "meaning": "synthetic ninth origin",
        "capacity_constraint": "unbounded",
        "capacity_note": "explicit unbounded synthetic origin",
        "capacity_from_gps_scatter": False,
        "shelter_access": None,
        "closures": [],
        "lift_restriction": None,
        "stair_restriction": None,
    }
    walk_leg = {
        "id": "leg_walk_synthetic_ninth",
        "from_place_id": "synthetic_ninth_origin",
        "to_place_id": "dtsp_walk_approach",
        "duration_s": 90,
        "mode": "walk",
        "distance_m": 117,
        "duration_range_s": [80, 120],
        "access_limits": [],
        "slope": "flat",
        "stairs": False,
        "crossings": [],
        "shared_resource_ids": [],
        "walking_speed_m_s": FREE_WALK_M_S,
        "not_driving_route": True,
        "not_restu_congested_speed": True,
    }
    walk_stage = {
        "id": "walk_synthetic_ninth",
        "kind": "travel",
        "leg_id": "leg_walk_synthetic_ninth",
    }
    walking_route = {
        "hostel_id": "synthetic_ninth",
        "leg_ids": ["leg_walk_synthetic_ninth", "leg_walk_to_exterior"],
        "distance_m": 117,
        "duration_s": 90,
        "duration_range_s": [80, 120],
        "access_limits": [],
        "slope": "flat",
        "stairs": False,
        "crossings": [],
        "shared_sections": [],
        "source": "synthetic data-only origin for ticket 05",
        "method": "assumed",
        "mode": "walk",
        "walking_speed_m_s": FREE_WALK_M_S,
        "not_driving_route": True,
        "not_restu_congested_speed": True,
        "date": "2026-09-19",
        "confidence": "low",
    }
    records = [
        {
            "field": "hostels.synthetic_ninth.latitude_deg",
            "value": 5.35800,
            "unit": "deg",
            "date": "2026-09-19",
            "method": "synthetic origin added as data",
            "confidence": "low",
            "observation_ref": "ticket-05-assumption",
            "category": "assumed",
        }
    ]
    append_origin(
        scenario,
        hostel=hostel,
        source_units=units,
        place=place,
        walk_leg=walk_leg,
        walk_stage=walk_stage,
        walking_route=walking_route,
        source_records=records,
    )
    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    assert result["measures"]["completed_students"] == 68
    hostel_ids = {row["hostel_id"] for row in result["outcomes"]["per_hostel"]}
    assert "synthetic_ninth" in hostel_ids


def test_missing_required_route_fails():
    scenario, policy = build_whole_campus_origins_case()
    del scenario["routes"]["fajar_harapan"]
    with pytest.raises(SimulationError) as caught:
        simulate(scenario, policy)
    assert caught.value.category == "missing_input"
    assert "fajar_harapan" in caught.value.field

    scenario, policy = build_whole_campus_origins_case()
    scenario["walking_routes"] = [
        route
        for route in scenario["walking_routes"]
        if route["hostel_id"] != "aman_damai"
    ]
    with pytest.raises(SimulationError) as caught_walk:
        simulate(scenario, policy)
    assert caught_walk.value.category == "missing_input"


def test_restu_replay_still_meets_targets_and_unmeasured_stay_unverified():
    restu_scenario, restu_policy = build_restu_17sep_replay(REPO_ROOT)
    restu = simulate(restu_scenario, restu_policy)
    predicted = [
        check
        for check in restu["accuracy_checks"]
        if check["role"] == "predicted" or check["id"] in {"coach_ride", "exterior_hold_duration"}
    ]
    assert predicted
    assert all(check.get("passed") for check in predicted)
    coach = next(check for check in restu["accuracy_checks"] if check["id"] == "coach_ride")
    assert 120 <= coach["predicted_s"] <= 270
    for check in predicted:
        if check["id"] == "coach_ride":
            continue
        if check.get("limit_s") == 600:
            assert check["passed"]

    scenario, policy = build_whole_campus_origins_case()
    campus = simulate(scenario, policy)
    unverified = [
        check
        for check in campus["accuracy_checks"]
        if check.get("role") == "unverified" or check.get("label") == "unverified"
    ]
    unverified_hostels = {check["hostel_id"] for check in unverified}
    assert set(WALK_HOSTEL_IDS) <= unverified_hostels
    assert "saujana" in unverified_hostels
    assert "tekun" in unverified_hostels
    for check in unverified:
        assert check["counted_as_predicted_success"] is False
        assert check.get("verified") is False
        assert "Restu replay" in (check.get("note") or "")


def test_each_hostel_can_use_ticket02_grouping_bases():
    scenario, policy = build_whole_campus_origins_case()
    policy["grouping"]["basis"] = "floor"
    floor = simulate(scenario, policy)
    assert floor["status"] == "completed"
    assert floor["grouping"]["total_resolved_attendance"] == 64
    assert floor["grouping"]["layout_status"] == "estimated"
    sizes = sorted(group["student_count"] for group in floor["grouping"]["groups"])
    assert sizes == [4] * 16

    mixed_scenario, mixed_policy = build_whole_campus_origins_case()
    mixed_policy["grouping"] = {
        "mode": "from_source_units",
        "basis": "mixed",
        "mixed_default": "hostel",
        "scope_overrides": {"indah_kembara": "wing", "aman_damai": "floor_wing"},
        "split_policy": "forbid",
        "mixing_policy": "same_hostel",
        "adaptation_rule": {"type": "fixed"},
        "regroup_policy": {"required": False},
        "escorts_per_group": 1,
    }
    mixed = simulate(mixed_scenario, mixed_policy)
    assert mixed["status"] == "completed"
    assert mixed["grouping"]["total_resolved_attendance"] == 64


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


def _shared_path_case(capacity: int) -> tuple[dict, dict]:
    members_a = _members("a", 60, "su_a", "hostel_a")
    members_b = _members("b", 60, "su_b", "hostel_b")
    scenario, policy = build_artificial_single_server_case()
    scenario = copy.deepcopy(scenario)
    policy = copy.deepcopy(policy)
    scenario["scenario_id"] = f"shared_path_cap_{capacity}"
    scenario["source_units"] = [
        {
            "id": "su_a",
            "hostel_id": "hostel_a",
            "estimated_attendance": 60,
            "resolved_attendance": 60,
            "actual_reporting_s": 0,
            "readiness_s": 0,
        },
        {
            "id": "su_b",
            "hostel_id": "hostel_b",
            "estimated_attendance": 60,
            "resolved_attendance": 60,
            "actual_reporting_s": 0,
            "readiness_s": 0,
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
            "duration_s": 100,
            "mode": "walk",
            "shared_resource_ids": [SHARED_PATH_JALAN_UNIVERSITI_EAST],
        },
        {
            "id": "walk_b",
            "from_place_id": "origin_b",
            "to_place_id": "dest",
            "duration_s": 100,
            "mode": "walk",
            "shared_resource_ids": [SHARED_PATH_JALAN_UNIVERSITI_EAST],
        },
    ]
    scenario["route_stages"] = [
        {"id": "walk_a", "kind": "travel", "leg_id": "walk_a"},
        {"id": "walk_b", "kind": "travel", "leg_id": "walk_b"},
    ]
    scenario["routes"] = {
        "hostel_a": ["walk_a"],
        "hostel_b": ["walk_b"],
    }
    scenario["shared_resources"] = [
        {
            "id": SHARED_PATH_JALAN_UNIVERSITI_EAST,
            "kind": "path",
            "capacity_students": capacity,
            "operating_limit_students": min(60, capacity),
            "duration_s": 0,
        }
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_a",
            "group_id": "g_a",
            "source_unit_id": "su_a",
            "place_id": "origin_a",
            "hostel_id": "hostel_a",
            "hostel_composition": {"hostel_a": 60},
            "members": members_a,
        },
        {
            "part_id": "part_b",
            "group_id": "g_b",
            "source_unit_id": "su_b",
            "place_id": "origin_b",
            "hostel_id": "hostel_b",
            "hostel_composition": {"hostel_b": 60},
            "members": members_b,
        },
    ]
    scenario["initial_state"]["workers"] = []
    scenario["initial_state"]["vehicles"] = []
    scenario["calendars"] = []
    scenario["operating_rules"]["required_endpoint"] = "stage_complete"
    scenario["simulation_end_s"] = 5000
    scenario["deadline_s"] = 4000
    policy["grouping"] = {"mode": "explicit_parts"}
    policy["required_endpoint"] = "stage_complete"
    policy["policy_id"] = f"shared_path_cap_{capacity}"
    return scenario, policy


def test_shared_path_capacity_bounds_occupancy_and_changing_it_changes_flow():
    high_scenario, high_policy = _shared_path_case(80)
    high = simulate(high_scenario, high_policy)
    occ = [
        row["occupancy_after"]
        for row in high["occupancy_history"]
        if row.get("place_id") == SHARED_PATH_JALAN_UNIVERSITI_EAST
        or row.get("resource_id") == SHARED_PATH_JALAN_UNIVERSITI_EAST
    ]
    assert occ
    assert max(occ) <= 80
    assert max(occ) < 120
    reconstructed = 0
    peak = 0
    for row in high["occupancy_history"]:
        if row.get("place_id") != SHARED_PATH_JALAN_UNIVERSITI_EAST and row.get(
            "resource_id"
        ) != SHARED_PATH_JALAN_UNIVERSITI_EAST:
            continue
        n = int(row.get("student_count") or 0)
        if row.get("direction") == "in":
            reconstructed += n
        elif row.get("direction") == "out":
            reconstructed -= n
        peak = max(peak, reconstructed)
        assert reconstructed <= 80
        assert int(row.get("occupancy_after") or 0) <= 80
    assert peak <= 80
    assert peak == 60
    waits = [
        event
        for event in high["event_trace"]
        if event.get("primary_cause") == "waiting_for_path"
    ]
    assert waits
    arrivals = [
        event["time_ms"]
        for event in high["event_trace"]
        if event["event_type"] == "arrival"
    ]
    assert arrivals
    assert max(arrivals) - min(arrivals) >= 100000

    low_scenario, low_policy = _shared_path_case(40)
    low = simulate(low_scenario, low_policy)
    low_arrivals = [
        event["time_ms"]
        for event in low["event_trace"]
        if event["event_type"] == "arrival"
    ]
    assert low["status"] != high["status"] or sorted(low_arrivals) != sorted(arrivals)
    low_occ = [
        row["occupancy_after"]
        for row in low["occupancy_history"]
        if row.get("place_id") == SHARED_PATH_JALAN_UNIVERSITI_EAST
        or row.get("resource_id") == SHARED_PATH_JALAN_UNIVERSITI_EAST
    ]
    if low_occ:
        assert max(low_occ) <= 40


def test_delay_classification_does_not_depend_on_literal_ids_restu_release_and_hall_open():
    base_sc, base_pol = build_restu_17sep_replay(REPO_ROOT)
    base_res = simulate(base_sc, base_pol)
    assert base_res["status"] == "completed"
    
    import json
    text = json.dumps(base_sc)
    text = text.replace("restu_release", "renamed_release_cal")
    text = text.replace("hall_open", "renamed_opening_cal")
    renamed_sc = json.loads(text)
    
    pol_text = json.dumps(base_pol)
    pol_text = pol_text.replace("restu_release", "renamed_release_cal")
    pol_text = pol_text.replace("hall_open", "renamed_opening_cal")
    renamed_pol = json.loads(pol_text)
    
    renamed_res = simulate(renamed_sc, renamed_pol)
    assert renamed_res["status"] == "completed"
    
    # Physical measures must match
    assert renamed_res["measures"]["total_required_journey_student_s"] == base_res["measures"]["total_required_journey_student_s"]
    assert renamed_res["measures"]["total_student_waiting_student_s"] == base_res["measures"]["total_student_waiting_student_s"]
    
    # Delay classification categories must match
    assert renamed_res["measures"]["waiting_student_s_by_class"] == base_res["measures"]["waiting_student_s_by_class"]
    assert renamed_res["measures"]["waiting_student_s_by_cause"] == base_res["measures"]["waiting_student_s_by_cause"]
