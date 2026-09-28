"""Controlled ticket-07 cases for delay attribution and operational measures."""

from __future__ import annotations

from usm_sim.constants import FORMAT_VERSION, TIMEZONE_NAME


def _record(field: str, value, unit: str = "mixed") -> dict:
    return {
        "field": field,
        "value": value,
        "unit": unit,
        "date": "2026-01-01",
        "method": "ticket 07 controlled case",
        "confidence": "assumed",
        "observation_ref": "spec.md#16-required-measures",
        "category": "assumed",
    }


def _members(prefix: str, n: int, source_unit_id: str, hostel_id: str) -> list[dict]:
    return [
        {
            "student_key": f"{prefix}{index:02d}",
            "queue_tie_key": f"{index:02d}",
            "source_unit_id": source_unit_id,
            "hostel_id": hostel_id,
        }
        for index in range(n)
    ]


def _place(
    place_id: str,
    lat: float,
    lon: float,
    meaning: str,
    *,
    outdoor_class: str = "indoor",
    extra: dict | None = None,
) -> dict:
    place = {
        "id": place_id,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "meaning": meaning,
        "capacity_constraint": "unbounded",
        "capacity_note": "explicit unbounded ticket-07 fixture",
        "capacity_from_gps_scatter": False,
        "outdoor_class": outdoor_class,
    }
    if extra:
        place.update(extra)
    return place


def _unit(
    unit_id: str,
    n: int,
    hostel_id: str,
    *,
    actual_reporting_s: float = 0,
    required_reporting_s: float | None = None,
    readiness_s: float = 0,
    availability_s: float = 0,
) -> dict:
    row = {
        "id": unit_id,
        "hostel_id": hostel_id,
        "estimated_attendance": n,
        "resolved_attendance": n,
        "actual_reporting_s": actual_reporting_s,
        "readiness_s": readiness_s,
        "availability_s": availability_s,
    }
    if required_reporting_s is not None:
        row["required_reporting_s"] = required_reporting_s
    return row


def _part(
    part_id: str,
    group_id: str,
    unit_id: str,
    place_id: str,
    members: list[dict],
    hostel_id: str,
) -> dict:
    return {
        "part_id": part_id,
        "group_id": group_id,
        "source_unit_id": unit_id,
        "place_id": place_id,
        "hostel_id": hostel_id,
        "hostel_composition": {hostel_id: len(members)},
        "members": members,
    }


def _shell(
    *,
    scenario_id: str,
    places: list[dict],
    legs: list[dict],
    stages: list[dict],
    students: list[dict],
    source_units: list[dict],
    policy_id: str,
    endpoint: str = "stage_complete",
    deadline_s: float = 10000,
    simulation_end_s: float = 10000,
    calendars: list[dict] | None = None,
    vehicles: list[dict] | None = None,
    workers: list[dict] | None = None,
    fleets: list[dict] | None = None,
    operating_extra: dict | None = None,
    extra_scenario: dict | None = None,
    extra_policy: dict | None = None,
    routes: dict | None = None,
) -> tuple[dict, dict]:
    operating = {
        "required_endpoint": endpoint,
        "direct_walk_permitted": False,
        "bag_check": False,
        "security_service": False,
        "mechanical_clicker": False,
        "qr_scan": False,
        "seating_modeled": False,
    }
    if operating_extra:
        operating.update(operating_extra)
    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": f"ticket-07-{scenario_id}",
        "scenario_id": scenario_id,
        "uncertainty_case_id": f"{scenario_id}_base",
        "event_date": "2026-01-01",
        "start_time_local": "00:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": deadline_s,
        "simulation_end_s": simulation_end_s,
        "max_events_per_run": 100000,
        "source_units": source_units,
        "places": places,
        "route_legs": legs,
        "route_stages": stages,
        "calendars": list(calendars or []),
        "initial_state": {
            "students": students,
            "queues": [],
            "workers": list(workers or []),
            "vehicles": list(vehicles or []),
            "hall_occupancy_students": 0,
        },
        "operating_rules": operating,
        "measured_facts": [],
        "uncertain_assumptions": [{"id": "ticket07_fixture", "category": "assumed"}],
        "decisions": [{"id": "ticket07_policy", "category": "decision"}],
        "source_records": [_record("scenario_id", scenario_id)],
    }
    if fleets:
        scenario["fleets"] = fleets
    if routes:
        scenario["routes"] = routes
    if extra_scenario:
        scenario.update(extra_scenario)
    policy = {
        "policy_id": policy_id,
        "policy_version": "1",
        "grouping": {"mode": "explicit_parts"},
        "required_endpoint": endpoint,
        "release_rule": {"type": "immediate"},
        "vehicle_dispatch_rule": {"type": "none"},
        "destination_rule": {"type": "complete_after_stages"},
        "random_seed": 0,
        "numerical_rounding_limit_s": 0.001,
    }
    if extra_policy:
        policy.update(extra_policy)
    return scenario, policy


def build_p95_student_weighted_case() -> tuple[dict, dict]:
    """99 students wait 0 s. One student waits 100 s. Student-weighted P95 is 0."""
    many = _members("a", 99, "su_a", "hostel_a")
    one = _members("b", 1, "su_b", "hostel_b")
    places = [
        _place("origin_a", 0.0, 0.0, "hostel A origin", outdoor_class="exposed"),
        _place("origin_b", 0.0, 0.001, "hostel B origin", outdoor_class="exposed"),
        _place("dest", 0.001, 0.0, "shared destination", outdoor_class="indoor"),
    ]
    legs = [
        {
            "id": "walk_a",
            "from_place_id": "origin_a",
            "to_place_id": "dest",
            "duration_s": 0,
            "mode": "walk",
            "shared_resource_ids": [],
        },
        {
            "id": "walk_b",
            "from_place_id": "origin_b",
            "to_place_id": "dest",
            "duration_s": 0,
            "mode": "walk",
            "shared_resource_ids": [],
        },
    ]
    stages = [
        {"id": "hold_b", "kind": "hold", "place_id": "origin_b", "until": {"calendar_id": "late_release"}},
        {"id": "walk", "kind": "travel", "leg_id": "walk_a"},
    ]
    return _shell(
        scenario_id="p95_student_weighted_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_a", "g_a", "su_a", "origin_a", many, "hostel_a"),
            _part("part_b", "g_b", "su_b", "origin_b", one, "hostel_b"),
        ],
        source_units=[
            _unit("su_a", 99, "hostel_a"),
            _unit("su_b", 1, "hostel_b"),
        ],
        policy_id="p95_policy_v1",
        calendars=[{"id": "late_release", "open_time_s": 100, "place_id": "origin_b"}],
        routes={
            "hostel_a": ["walk"],
            "hostel_b": ["hold_b", "walk_b"],
        },
        extra_scenario={
            "route_stages": [
                {"id": "hold_b", "kind": "hold", "place_id": "origin_b", "until": {"calendar_id": "late_release"}},
                {"id": "walk", "kind": "travel", "leg_id": "walk_a"},
                {"id": "walk_b", "kind": "travel", "leg_id": "walk_b"},
            ]
        },
        deadline_s=1000,
        simulation_end_s=1000,
    )


def build_two_hostel_wait_case() -> tuple[dict, dict]:
    """Hostel A waits 10 s. Hostel B waits 50 s. Worst hostel is B."""
    a = _members("a", 4, "su_a", "hostel_a")
    b = _members("b", 4, "su_b", "hostel_b")
    places = [
        _place("origin_a", 0.0, 0.0, "hostel A yard", outdoor_class="exposed"),
        _place("origin_b", 0.0, 0.001, "hostel B yard", outdoor_class="shaded"),
        _place("dest", 0.001, 0.0, "hall", outdoor_class="indoor"),
    ]
    return _shell(
        scenario_id="two_hostel_wait_v1",
        places=places,
        legs=[
            {
                "id": "walk_a",
                "from_place_id": "origin_a",
                "to_place_id": "dest",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "walk_b",
                "from_place_id": "origin_b",
                "to_place_id": "dest",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            },
        ],
        stages=[
            {"id": "hold_a", "kind": "hold", "place_id": "origin_a", "until": {"calendar_id": "rel_a"}},
            {"id": "hold_b", "kind": "hold", "place_id": "origin_b", "until": {"calendar_id": "rel_b"}},
            {"id": "walk_a", "kind": "travel", "leg_id": "walk_a"},
            {"id": "walk_b", "kind": "travel", "leg_id": "walk_b"},
        ],
        students=[
            _part("part_a", "g_a", "su_a", "origin_a", a, "hostel_a"),
            _part("part_b", "g_b", "su_b", "origin_b", b, "hostel_b"),
        ],
        source_units=[_unit("su_a", 4, "hostel_a"), _unit("su_b", 4, "hostel_b")],
        policy_id="two_hostel_wait_policy_v1",
        calendars=[
            {"id": "rel_a", "open_time_s": 10, "place_id": "origin_a"},
            {"id": "rel_b", "open_time_s": 50, "place_id": "origin_b"},
        ],
        routes={
            "hostel_a": ["hold_a", "walk_a"],
            "hostel_b": ["hold_b", "walk_b"],
        },
        deadline_s=1000,
        simulation_end_s=1000,
        extra_scenario={
            "route_stages": [
                {"id": "hold_a", "kind": "hold", "place_id": "origin_a", "until": {"calendar_id": "rel_a"}},
                {"id": "hold_b", "kind": "hold", "place_id": "origin_b", "until": {"calendar_id": "rel_b"}},
                {"id": "walk_a", "kind": "travel", "leg_id": "walk_a"},
                {"id": "walk_b", "kind": "travel", "leg_id": "walk_b"},
            ]
        },
    )


def build_origin_hold_unfinished_case() -> tuple[dict, dict]:
    """Four students wait at origin. Time ends before release. They stay in the average."""
    members = _members("s", 4, "su_origin", "hostel_a")
    return _shell(
        scenario_id="origin_hold_unfinished_v1",
        places=[
            _place("origin", 0.0, 0.0, "hostel gathering", outdoor_class="exposed"),
            _place("dest", 0.001, 0.0, "hall", outdoor_class="indoor"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 10,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {
                "id": "gather",
                "kind": "hold",
                "place_id": "origin",
                "until": {"calendar_id": "never"},
            },
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
        ],
        students=[_part("part_origin", "g_origin", "su_origin", "origin", members, "hostel_a")],
        source_units=[_unit("su_origin", 4, "hostel_a")],
        policy_id="origin_hold_unfinished_policy_v1",
        calendars=[{"id": "never", "open_time_s": 99999, "place_id": "origin"}],
        deadline_s=40,
        simulation_end_s=40,
        operating_extra={"pre_release_classification": "required_gathering"},
    )


def build_reporting_window_case(*, reporting_time_s: float = 30) -> tuple[dict, dict]:
    """Reporting time is a search choice. Availability and the window stay fixed."""
    members = _members("s", 2, "su_origin", "hostel_a")
    scenario, policy = _shell(
        scenario_id="reporting_window_v1",
        places=[
            _place("origin", 0.0, 0.0, "hostel gathering", outdoor_class="exposed"),
            _place("dest", 0.001, 0.0, "hall", outdoor_class="indoor"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 10,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
        students=[_part("part_origin", "g_origin", "su_origin", "origin", members, "hostel_a")],
        source_units=[
            _unit(
                "su_origin",
                2,
                "hostel_a",
                actual_reporting_s=30,
                availability_s=0,
            )
        ],
        policy_id="reporting_window_policy_v1",
        deadline_s=95,
        simulation_end_s=1000,
        operating_extra={
            "reporting_window": {"earliest_s": 0, "latest_s": 60},
            "attendance_response_rule": {"type": "fixed"},
        },
        extra_policy={
            "reporting_time_s": reporting_time_s,
            "reporting_window": {"earliest_s": 0, "latest_s": 60},
            "attendance_response_rule": {"type": "fixed"},
        },
    )
    return scenario, policy


def build_assembly_then_hold_case() -> tuple[dict, dict]:
    """Assembly then a hostel hold. Finishing assembly does not clear origin wait."""
    members = _members("s", 3, "su_origin", "hostel_a")
    scenario, policy = _shell(
        scenario_id="assembly_then_hold_v1",
        places=[
            _place("origin", 0.0, 0.0, "hostel gathering", outdoor_class="sheltered"),
            _place("dest", 0.001, 0.0, "hall", outdoor_class="indoor"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {
                "id": "gather",
                "kind": "hold",
                "place_id": "origin",
                "until": {"calendar_id": "release"},
            },
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
        ],
        students=[_part("part_origin", "g_origin", "su_origin", "origin", members, "hostel_a")],
        source_units=[_unit("su_origin", 3, "hostel_a")],
        policy_id="assembly_then_hold_policy_v1",
        calendars=[{"id": "release", "open_time_s": 40, "place_id": "origin"}],
        workers=[
            {"id": "w1", "role": "escort", "place_id": "origin"},
            {"id": "w2", "role": "escort", "place_id": "origin"},
        ],
        extra_policy={
            "grouping": {
                "mode": "explicit_parts",
                "physical_assembly": {
                    "duration_s": 10,
                    "place_id": "origin",
                    "worker_count": 2,
                },
            }
        },
        deadline_s=1000,
        simulation_end_s=1000,
        operating_extra={"pre_release_classification": "required_gathering"},
    )
    return scenario, policy


def build_outdoor_wait_case() -> tuple[dict, dict]:
    """Exposed, shaded, and sheltered waits are separate student-time totals."""
    exposed = _members("e", 2, "su_e", "hostel_e")
    shaded = _members("h", 2, "su_h", "hostel_h")
    sheltered = _members("s", 2, "su_s", "hostel_s")
    return _shell(
        scenario_id="outdoor_wait_v1",
        places=[
            _place("yard", 0.0, 0.0, "exposed yard", outdoor_class="exposed"),
            _place("tree", 0.0, 0.001, "shaded tree line", outdoor_class="shaded"),
            _place("shelter", 0.0, 0.002, "rain shelter", outdoor_class="sheltered"),
            _place("hall", 0.001, 0.0, "indoor hall", outdoor_class="indoor"),
        ],
        legs=[
            {
                "id": "from_yard",
                "from_place_id": "yard",
                "to_place_id": "hall",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "from_tree",
                "from_place_id": "tree",
                "to_place_id": "hall",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "from_shelter",
                "from_place_id": "shelter",
                "to_place_id": "hall",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            },
        ],
        stages=[],
        students=[
            _part("part_e", "g_e", "su_e", "yard", exposed, "hostel_e"),
            _part("part_h", "g_h", "su_h", "tree", shaded, "hostel_h"),
            _part("part_s", "g_s", "su_s", "shelter", sheltered, "hostel_s"),
        ],
        source_units=[
            _unit("su_e", 2, "hostel_e"),
            _unit("su_h", 2, "hostel_h"),
            _unit("su_s", 2, "hostel_s"),
        ],
        policy_id="outdoor_wait_policy_v1",
        calendars=[
            {"id": "rel_e", "open_time_s": 10, "place_id": "yard"},
            {"id": "rel_h", "open_time_s": 10, "place_id": "tree"},
            {"id": "rel_s", "open_time_s": 10, "place_id": "shelter"},
        ],
        routes={
            "hostel_e": ["hold_e", "walk_e"],
            "hostel_h": ["hold_h", "walk_h"],
            "hostel_s": ["hold_s", "walk_s"],
        },
        extra_scenario={
            "route_stages": [
                {"id": "hold_e", "kind": "hold", "place_id": "yard", "until": {"calendar_id": "rel_e"}},
                {"id": "hold_h", "kind": "hold", "place_id": "tree", "until": {"calendar_id": "rel_h"}},
                {"id": "hold_s", "kind": "hold", "place_id": "shelter", "until": {"calendar_id": "rel_s"}},
                {"id": "walk_e", "kind": "travel", "leg_id": "from_yard"},
                {"id": "walk_h", "kind": "travel", "leg_id": "from_tree"},
                {"id": "walk_s", "kind": "travel", "leg_id": "from_shelter"},
            ]
        },
        deadline_s=1000,
        simulation_end_s=1000,
    )


def build_vehicle_busy_held_idle_case() -> tuple[dict, dict]:
    """One bus boards, travels, waits to alight, then sits idle."""
    riders = _members("b", 2, "su_bus", "hostel_a")
    blockers = _members("h", 4, "su_hall", "hall_stay")
    places = [
        _place("origin", 0.0, 0.0, "bus origin", outdoor_class="exposed"),
        _place(
            "approach",
            0.01,
            0.0,
            "vehicle queue",
            outdoor_class="exposed",
            extra={
                "capacity_constraint": "finite",
                "constrained": True,
                "physical_capacity_students": 0,
                "physical_capacity_vehicles": 2,
                "capacity_students": 0,
                "capacity_vehicles": 2,
                "operating_limit_students": 0,
                "preceding_place_id": "origin",
                "queue_discipline": "fcfs",
                "priority_rule": "arrival_order",
                "service_rule": {"kind": "vehicle_queue"},
            },
        ),
        _place(
            "hall",
            0.02,
            0.0,
            "full hall",
            outdoor_class="indoor",
            extra={
                "capacity_constraint": "finite",
                "constrained": True,
                "physical_capacity_students": 4,
                "capacity_students": 4,
                "operating_limit_students": 4,
                "preceding_place_id": "approach",
                "vehicle_queue_place_id": "approach",
                "queue_discipline": "fcfs",
                "priority_rule": "arrival_order",
                "service_rule": {"kind": "none"},
            },
        ),
    ]
    return _shell(
        scenario_id="vehicle_busy_held_idle_v1",
        places=places,
        legs=[
            {
                "id": "leg_bus",
                "from_place_id": "origin",
                "to_place_id": "hall",
                "duration_s": 20,
                "mode": "coach",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {"id": "transit", "kind": "vehicle_travel", "leg_id": "leg_bus", "resource_id": "bus_1"},
            {
                "id": "alighting",
                "kind": "batch_service",
                "place_id": "hall",
                "resource_id": "bus_1",
                "action": "alight",
                "duration_s": 5,
            },
        ],
        students=[
            _part("part_hall", "g_hall", "su_hall", "hall", blockers, "hall_stay"),
            _part("part_bus", "g_bus", "su_bus", "origin", riders, "hostel_a"),
        ],
        source_units=[_unit("su_hall", 4, "hall_stay"), _unit("su_bus", 2, "hostel_a")],
        policy_id="vehicle_held_policy_v1",
        vehicles=[
            {
                "id": "bus_1",
                "type": "coach",
                "place_id": "origin",
                "available_time_s": 0,
                "capacity_students": 40,
                "return_travel_s": 30,
                "turnaround_s": 10,
            }
        ],
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        routes={
            "hall_stay": ["hall_hold"],
            "hostel_a": ["transit", "alighting"],
        },
        extra_scenario={
            "route_stages": [
                {
                    "id": "hall_hold",
                    "kind": "hold",
                    "place_id": "hall",
                    "until": {"calendar_id": "never_open"},
                },
                {"id": "transit", "kind": "vehicle_travel", "leg_id": "leg_bus", "resource_id": "bus_1"},
                {
                    "id": "alighting",
                    "kind": "batch_service",
                    "place_id": "hall",
                    "resource_id": "bus_1",
                    "action": "alight",
                    "duration_s": 5,
                },
            ]
        },
        extra_policy={"destination_space_rule": "allow_approach_wait", "coordination_delay_s": 0},
        deadline_s=80,
        simulation_end_s=80,
        operating_extra={"required_endpoint": "stage_complete"},
    )


def build_early_arrival_idle_case() -> tuple[dict, dict]:
    """Students hold at the hall before a declared event start. That idle is not queue wait."""
    members = _members("s", 2, "su_hall", "hostel_a")
    return _shell(
        scenario_id="early_arrival_idle_v1",
        places=[
            _place("hall", 0.001, 0.0, "hall foyer", outdoor_class="indoor"),
            _place("origin", 0.0, 0.0, "unused origin", outdoor_class="exposed"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "hall",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {
                "id": "hall_hold",
                "kind": "hold",
                "place_id": "hall",
                "until": {"calendar_id": "hall_open"},
            }
        ],
        students=[_part("part_hall", "g_hall", "su_hall", "hall", members, "hostel_a")],
        source_units=[_unit("su_hall", 2, "hostel_a")],
        policy_id="early_arrival_idle_policy_v1",
        calendars=[{"id": "hall_open", "open_time_s": 40, "place_id": "hall"}],
        deadline_s=100,
        simulation_end_s=100,
        operating_extra={"event_start_s": 30, "required_endpoint": "stage_complete"},
    )


def build_starvation_not_student_wait_case() -> tuple[dict, dict]:
    """One server is idle until students arrive. That idle time is not student waiting."""
    members = _members("s", 1, "su_origin", "hostel_a")
    return _shell(
        scenario_id="starvation_not_wait_v1",
        places=[
            _place("origin", 0.0, 0.0, "origin", outdoor_class="indoor"),
            _place("entrance", 0.001, 0.0, "entrance", outdoor_class="indoor"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "entrance",
                "duration_s": 0,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
            {
                "id": "entrance_service",
                "kind": "queue_service",
                "place_id": "entrance",
                "service_duration_s": 10,
                "server_count": 2,
                "queue_discipline": "fcfs",
            },
        ],
        students=[_part("part_origin", "g_walk", "su_origin", "origin", members, "hostel_a")],
        source_units=[_unit("su_origin", 1, "hostel_a")],
        policy_id="starvation_policy_v1",
        endpoint="service_complete",
        deadline_s=95,
        simulation_end_s=1000,
        extra_policy={"required_endpoint": "service_complete"},
    )
