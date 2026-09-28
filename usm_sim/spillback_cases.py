"""Controlled ticket-06 cases: finite space, reports, holds, and changing conditions."""

from __future__ import annotations

from usm_sim.constants import FORMAT_VERSION, TIMEZONE_NAME


def _record(field: str, value, unit: str = "mixed") -> dict:
    return {
        "field": field,
        "value": value,
        "unit": unit,
        "date": "2026-01-01",
        "method": "ticket 06 controlled case",
        "confidence": "assumed",
        "observation_ref": "spec.md#10-queues-finite-space-and-arriving-vehicles",
        "category": "assumed",
    }


def _members(prefix: str, n: int, source_unit_id: str = "su_a") -> list[dict]:
    return [
        {
            "student_key": f"{prefix}{index:02d}",
            "queue_tie_key": f"{index:02d}",
            "source_unit_id": source_unit_id,
            "hostel_id": "synthetic",
        }
        for index in range(n)
    ]


def _unbounded(place_id: str, lat: float, lon: float, meaning: str, extra: dict | None = None) -> dict:
    place = {
        "id": place_id,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "meaning": meaning,
        "capacity_constraint": "unbounded",
        "capacity_note": "explicit unbounded ticket-06 fixture",
        "capacity_from_gps_scatter": False,
    }
    if extra:
        place.update(extra)
    return place


def constrained_place(
    place_id: str,
    lat: float,
    lon: float,
    meaning: str,
    *,
    physical: int,
    operating: int,
    preceding: str | None,
    service_rule: dict | None = None,
    extra: dict | None = None,
) -> dict:
    place = {
        "id": place_id,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "meaning": meaning,
        "capacity_constraint": "finite",
        "constrained": True,
        "capacity_students": physical,
        "physical_capacity_students": physical,
        "operating_limit_students": operating,
        "preceding_place_id": preceding,
        "queue_discipline": "fcfs",
        "priority_rule": "arrival_order",
        "service_rule": service_rule or {"kind": "none"},
        "capacity_from_gps_scatter": False,
        "estimated_capacity_students": physical,
    }
    if extra:
        place.update(extra)
    return place


def _unit(unit_id: str, n: int, hostel_id: str = "synthetic") -> dict:
    return {
        "id": unit_id,
        "hostel_id": hostel_id,
        "estimated_attendance": n,
        "resolved_attendance": n,
        "actual_reporting_s": 0,
        "readiness_s": 0,
    }


def _part(
    part_id: str,
    group_id: str,
    unit_id: str,
    place_id: str,
    members: list[dict],
    extra: dict | None = None,
) -> dict:
    row = {
        "part_id": part_id,
        "group_id": group_id,
        "source_unit_id": unit_id,
        "place_id": place_id,
        "hostel_id": "synthetic",
        "hostel_composition": {"synthetic": len(members)},
        "members": members,
    }
    if extra:
        row.update(extra)
    return row


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
    vehicles: list[dict] | None = None,
    calendars: list[dict] | None = None,
    fleets: list[dict] | None = None,
    workers: list[dict] | None = None,
    queues: list[dict] | None = None,
    extra_scenario: dict | None = None,
    extra_policy: dict | None = None,
    deadline_s: float = 10000,
    simulation_end_s: float = 10000,
    max_events_per_run: int = 100000,
    operating_extra: dict | None = None,
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
        "data_version": "ticket-06-v1",
        "scenario_id": scenario_id,
        "uncertainty_case_id": f"{scenario_id}_base",
        "event_date": "2026-01-01",
        "start_time_local": "00:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": deadline_s,
        "simulation_end_s": simulation_end_s,
        "max_events_per_run": max_events_per_run,
        "source_units": source_units,
        "places": places,
        "route_legs": legs,
        "route_stages": stages,
        "calendars": list(calendars or []),
        "initial_state": {
            "students": students,
            "queues": list(queues or []),
            "workers": list(workers or []),
            "vehicles": list(vehicles or []),
            "hall_occupancy_students": 0,
        },
        "operating_rules": operating,
        "measured_facts": [],
        "uncertain_assumptions": [
            {"id": "ticket06_fixture", "category": "assumed"}
        ],
        "decisions": [{"id": "ticket06_policy", "category": "decision"}],
        "source_records": [
            _record("scenario_id", scenario_id),
        ],
        "background_demand": {
            "pedestrians": 0,
            "road_crossings": 0,
            "other_arrivals": 0,
            "visible_assumption": True,
            "assumption_id": "zero_background_demand",
        },
    }
    if fleets:
        scenario["fleets"] = fleets
    if extra_scenario:
        scenario.update(extra_scenario)
    policy = {
        "policy_id": policy_id,
        "policy_version": "1",
        "required_endpoint": endpoint,
        "release_rule": {"type": "immediate"},
        "vehicle_dispatch_rule": {"type": "none"},
        "destination_rule": {"type": "complete_after_stages"},
        "random_seed": 0,
        "coordination_delay_s": 0,
        "destination_space_rule": "allow_approach_wait",
    }
    if extra_policy:
        policy.update(extra_policy)
    return scenario, policy


def build_full_destination_arriving_bus_case() -> tuple[dict, dict]:
    """Hall holds 4. Occupants stay. Arriving bus waits in the vehicle queue, aboard."""
    occupants = _members("h", 4, "su_hall")
    riders = _members("b", 4, "su_bus")
    places = [
        _unbounded("origin", 0.0, 0.0, "bus origin"),
        constrained_place(
            "bus_approach",
            0.01,
            0.0,
            "declared vehicle queue",
            physical=0,
            operating=0,
            preceding="origin",
            extra={
                "physical_capacity_vehicles": 2,
                "capacity_vehicles": 2,
                "service_rule": {"kind": "vehicle_queue"},
            },
        ),
        constrained_place(
            "hall",
            0.02,
            0.0,
            "full destination",
            physical=4,
            operating=4,
            preceding="bus_approach",
            extra={"vehicle_queue_place_id": "bus_approach"},
        ),
    ]
    legs = [
        {
            "id": "leg_bus",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 20,
            "mode": "coach",
            "flow_limit_students": 8,
            "shared_resource_ids": [],
        }
    ]
    stages = [
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
    students = [
        _part("part_hall", "g_hall", "su_hall", "hall", occupants),
        _part(
            "part_bus",
            "g_bus",
            "su_bus",
            "origin",
            riders,
            extra={"resource_ids": ["bus_1"]},
        ),
    ]
    vehicles = [
        {
            "id": "bus_1",
            "type": "coach",
            "place_id": "origin",
            "available_time_s": 0,
            "capacity_students": 40,
            "return_travel_s": 30,
            "turnaround_s": 10,
        }
    ]
    scenario, policy = _shell(
        scenario_id="full_dest_arriving_bus_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=students,
        source_units=[_unit("su_hall", 4), _unit("su_bus", 4)],
        policy_id="allow_approach_wait_v1",
        vehicles=vehicles,
        extra_scenario={
            "routes": {
                "synthetic": ["transit", "alighting"],
            }
        },
        extra_policy={"destination_space_rule": "allow_approach_wait", "coordination_delay_s": 0},
        operating_extra={"required_endpoint": "stage_complete"},
        calendars=[
            {
                "id": "never_open",
                "open_time_s": 99999,
                "place_id": "hall",
            }
        ],
    )
    # Occupants never leave: they hold until a calendar that does not open
    # within simulation_end_s. The arriving bus must wait, not overflow.
    scenario["route_stages"] = [
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
        *stages,
    ]
    scenario["routes"] = {
        "synthetic": ["transit", "alighting"],
    }
    # Give occupants a hostel-specific route that only holds.
    occupants_unit = scenario["source_units"][0]
    occupants_unit["hostel_id"] = "hall_stay"
    riders_unit = scenario["source_units"][1]
    riders_unit["hostel_id"] = "bus_riders"
    scenario["initial_state"]["students"][0]["hostel_id"] = "hall_stay"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"hall_stay": 4}
    scenario["initial_state"]["students"][1]["hostel_id"] = "bus_riders"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"bus_riders": 4}
    scenario["routes"] = {
        "hall_stay": ["hall_hold"],
        "bus_riders": ["transit", "alighting"],
    }
    scenario["simulation_end_s"] = 80
    scenario["deadline_s"] = 80
    return scenario, policy


def build_blocked_walk_case() -> tuple[dict, dict]:
    """Destination holds 4. Walkers occupy the preceding hold, which has capacity."""
    stay = _members("h", 4, "su_hall")
    walkers = _members("w", 4, "su_walk")
    places = [
        _unbounded("origin", 0.0, 0.0, "walk origin"),
        constrained_place(
            "path_hold",
            0.005,
            0.0,
            "preceding path hold",
            physical=8,
            operating=6,
            preceding="origin",
            extra={"service_rule": {"kind": "hold"}},
        ),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "full hall",
            physical=4,
            operating=4,
            preceding="path_hold",
        ),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 10,
            "mode": "walk",
            "flow_limit_students": 4,
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "leg_walk"},
        {
            "id": "hall_service",
            "kind": "queue_service",
            "place_id": "hall",
            "service_duration_s": 5,
            "server_count": 1,
            "queue_discipline": "fcfs",
        },
    ]
    scenario, policy = _shell(
        scenario_id="blocked_walk_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_hall", "g_hall", "su_hall", "hall", stay),
            _part("part_walk", "g_walk", "su_walk", "origin", walkers),
        ],
        source_units=[_unit("su_hall", 4), _unit("su_walk", 4)],
        policy_id="blocked_walk_policy_v1",
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
        simulation_end_s=80,
        deadline_s=80,
        workers=[
            {
                "id": "escort_1",
                "role": "escort",
                "place_id": "origin",
                "available_time_s": 0,
            }
        ],
        operating_extra={
            "require_escorts": True,
            "min_escorts_per_group": 1,
        },
    )
    scenario["initial_state"]["students"][0]["hostel_id"] = "hall_stay"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"hall_stay": 4}
    scenario["initial_state"]["students"][0]["required_supervision"] = {"escorts": 0}
    scenario["initial_state"]["students"][1]["hostel_id"] = "walkers"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"walkers": 4}
    scenario["initial_state"]["students"][1]["required_supervision"] = {"escorts": 1}
    scenario["source_units"][0]["hostel_id"] = "hall_stay"
    scenario["source_units"][1]["hostel_id"] = "walkers"
    scenario["route_stages"] = [
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
        *stages,
    ]
    scenario["routes"] = {
        "hall_stay": ["hall_hold"],
        "walkers": ["walk", "hall_service"],
    }
    return scenario, policy


def build_delayed_report_case(*, delay_s: float = 30.0) -> tuple[dict, dict]:
    """Group B may depart before the full-destination report is delivered."""
    first = _members("a", 4, "su_a")
    second = _members("b", 4, "su_b")
    third = _members("c", 4, "su_c")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "approach",
            0.005,
            0.0,
            "declared approach",
            physical=8,
            operating=8,
            preceding="origin",
        ),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "destination",
            physical=4,
            operating=4,
            preceding="approach",
            service_rule={"kind": "queue", "service_duration_s": 1, "server_count": 1},
        ),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 10,
            "mode": "walk",
            "flow_limit_students": 12,
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "leg_walk"},
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
    ]
    students = [
        _part("part_a", "g_a", "su_a", "origin", first, extra={"readiness_s": 0}),
        _part("part_b", "g_b", "su_b", "origin", second),
        _part("part_c", "g_c", "su_c", "origin", third),
    ]
    scenario, policy = _shell(
        scenario_id="delayed_report_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=students,
        source_units=[_unit("su_a", 4), _unit("su_b", 4), _unit("su_c", 4)],
        policy_id="delayed_report_policy_v1",
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        extra_policy={
            "coordination_delay_s": delay_s,
            "destination_space_rule": "allow_approach_wait",
            "space_control": {
                "destination_place_id": "hall",
                "hold_threshold_students": 4,
                "resume_threshold_students": 0,
                "min_hold_duration_s": 5,
            },
        },
        simulation_end_s=200,
        deadline_s=200,
    )
    for index, (hostel, ready) in enumerate(
        (("group_a", 0), ("group_b", 20), ("group_c", 50))
    ):
        scenario["source_units"][index]["hostel_id"] = hostel
        scenario["source_units"][index]["readiness_s"] = ready
        scenario["source_units"][index]["actual_reporting_s"] = ready
        scenario["initial_state"]["students"][index]["hostel_id"] = hostel
        scenario["initial_state"]["students"][index]["hostel_composition"] = {hostel: 4}
    scenario["routes"] = {
        "group_a": ["walk", "hall_hold"],
        "group_b": ["walk", "hall_hold"],
        "group_c": ["walk", "hall_hold"],
    }
    return scenario, policy


def build_hold_resume_case() -> tuple[dict, dict]:
    """Occupancy hold, then service frees the hall, then releases resume."""
    first = _members("a", 4, "su_a")
    second = _members("b", 4, "su_b")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "approach",
            0.005,
            0.0,
            "approach",
            physical=8,
            operating=8,
            preceding="origin",
        ),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "hall",
            physical=4,
            operating=3,
            preceding="approach",
            service_rule={"kind": "queue", "service_duration_s": 2, "server_count": 1},
        ),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 5,
            "mode": "walk",
            "flow_limit_students": 8,
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "leg_walk"},
        {
            "id": "hall_service",
            "kind": "queue_service",
            "place_id": "hall",
            "service_duration_s": 2,
            "server_count": 1,
            "queue_discipline": "fcfs",
        },
    ]
    scenario, policy = _shell(
        scenario_id="hold_resume_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_a", "g_a", "su_a", "origin", first),
            _part("part_b", "g_b", "su_b", "origin", second),
        ],
        source_units=[_unit("su_a", 4), _unit("su_b", 4)],
        policy_id="hold_resume_policy_v1",
        extra_policy={
            "coordination_delay_s": 0,
            "destination_space_rule": "allow_approach_wait",
            "space_control": {
                "destination_place_id": "hall",
                "hold_threshold_students": 4,
                "resume_threshold_students": 0,
                "min_hold_duration_s": 4,
            },
        },
    )
    scenario["source_units"][0]["hostel_id"] = "group_a"
    scenario["source_units"][0]["readiness_s"] = 0
    scenario["source_units"][1]["hostel_id"] = "group_b"
    scenario["source_units"][1]["readiness_s"] = 6
    scenario["source_units"][1]["actual_reporting_s"] = 6
    scenario["initial_state"]["students"][0]["hostel_id"] = "group_a"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"group_a": 4}
    scenario["initial_state"]["students"][1]["hostel_id"] = "group_b"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"group_b": 4}
    scenario["routes"] = {
        "group_a": ["walk", "hall_service"],
        "group_b": ["walk", "hall_service"],
    }
    return scenario, policy


def build_shared_congestion_walk_case() -> tuple[dict, dict]:
    """Two walking groups. First fills the hall. Second waits on the shared path."""
    a = _members("a", 4, "su_a")
    b = _members("b", 4, "su_b")
    places = [
        _unbounded("origin_a", 0.0, 0.0, "origin a"),
        _unbounded("origin_b", 0.0, 0.01, "origin b"),
        constrained_place(
            "shared_path",
            0.005,
            0.005,
            "shared path hold",
            physical=8,
            operating=8,
            preceding="origin_a",
        ),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "small hall",
            physical=4,
            operating=4,
            preceding="shared_path",
        ),
    ]
    places[2]["preceding_place_id"] = "origin_a"
    legs = [
        {
            "id": "leg_a",
            "from_place_id": "origin_a",
            "to_place_id": "hall",
            "duration_s": 8,
            "mode": "walk",
            "flow_limit_students": 8,
            "shared_resource_ids": ["path_shared"],
        },
        {
            "id": "leg_b",
            "from_place_id": "origin_b",
            "to_place_id": "hall",
            "duration_s": 12,
            "mode": "walk",
            "flow_limit_students": 8,
            "shared_resource_ids": ["path_shared"],
        },
    ]
    stages = [
        {"id": "walk_a", "kind": "travel", "leg_id": "leg_a"},
        {"id": "walk_b", "kind": "travel", "leg_id": "leg_b"},
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
    ]
    scenario, policy = _shell(
        scenario_id="shared_congestion_walk_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_a", "g_a", "su_a", "origin_a", a),
            _part("part_b", "g_b", "su_b", "origin_b", b),
        ],
        source_units=[_unit("su_a", 4, "hostel_a"), _unit("su_b", 4, "hostel_b")],
        policy_id="shared_walk_policy_v1",
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        extra_scenario={
            "shared_resources": [
                {
                    "id": "path_shared",
                    "kind": "path",
                    "capacity_students": 8,
                    "operating_limit_students": 8,
                    "duration_s": 0,
                }
            ],
            "routes": {
                "hostel_a": ["walk_a", "hall_hold"],
                "hostel_b": ["walk_b", "hall_hold"],
            },
        },
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
        simulation_end_s=80,
        deadline_s=80,
    )
    scenario["initial_state"]["students"][0]["hostel_id"] = "hostel_a"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"hostel_a": 4}
    scenario["initial_state"]["students"][1]["hostel_id"] = "hostel_b"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"hostel_b": 4}
    return scenario, policy


def build_shared_congestion_bus_case(*, n_buses: int = 1) -> tuple[dict, dict]:
    """Buses dump into the same small hall. Extra buses do not enlarge the hall."""
    groups = []
    units = []
    students = []
    vehicles = []
    for index in range(n_buses):
        unit_id = f"su_{index}"
        members = _members(f"b{index}", 4, unit_id)
        units.append(_unit(unit_id, 4, f"hostel_{index}"))
        students.append(
            _part(
                f"part_{index}",
                f"g_{index}",
                unit_id,
                "origin",
                members,
            )
        )
        vehicles.append(
            {
                "id": f"bus_{index}",
                "type": "coach",
                "place_id": "origin",
                "available_time_s": 0,
                "capacity_students": 40,
                "return_travel_s": 20,
                "turnaround_s": 5,
            }
        )
        groups.append(index)
    places = [
        _unbounded("origin", 0.0, 0.0, "bus origin"),
        constrained_place(
            "bus_approach",
            0.008,
            0.0,
            "vehicle queue",
            physical=0,
            operating=0,
            preceding="origin",
            extra={
                "physical_capacity_vehicles": 4,
                "capacity_vehicles": 4,
                "service_rule": {"kind": "vehicle_queue"},
            },
        ),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "small hall",
            physical=4,
            operating=4,
            preceding="bus_approach",
            extra={"vehicle_queue_place_id": "bus_approach"},
        ),
    ]
    legs = [
        {
            "id": "leg_bus",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 8,
            "mode": "coach",
            "flow_limit_students": 16,
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "transit", "kind": "vehicle_travel", "leg_id": "leg_bus"},
        {
            "id": "alighting",
            "kind": "batch_service",
            "place_id": "hall",
            "fleet_id": "fleet_1",
            "action": "alight",
            "duration_s": 4,
        },
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
    ]
    routes = {f"hostel_{index}": ["transit", "alighting", "hall_hold"] for index in groups}
    for index, row in enumerate(students):
        row["hostel_id"] = f"hostel_{index}"
        row["hostel_composition"] = {f"hostel_{index}": 4}
        row["resource_ids"] = [f"bus_{index}"]
    scenario, policy = _shell(
        scenario_id=f"shared_congestion_bus_{n_buses}_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=students,
        source_units=units,
        policy_id=f"shared_bus_{n_buses}_v1",
        vehicles=vehicles,
        fleets=[
            {
                "id": "fleet_1",
                "vehicle_ids": [f"bus_{index}" for index in groups],
                "boarding_place_id": "origin",
                "alighting_place_id": "hall",
                "boarding_berth_capacity": n_buses,
                "dropoff_space_capacity": 1,
            }
        ],
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        extra_scenario={"routes": routes},
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
        simulation_end_s=80,
        deadline_s=80,
    )
    return scenario, policy


def build_no_waiting_space_case() -> tuple[dict, dict]:
    """Full destination and no physical wait slot. Infeasible, no imaginary overflow."""
    stay = _members("h", 2, "su_hall")
    walkers = _members("w", 4, "su_walk")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "tiny hall",
            physical=2,
            operating=2,
            preceding=None,
        ),
    ]
    # preceding None: nowhere to wait
    places[1]["preceding_place_id"] = None
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 5,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "leg_walk"},
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
    ]
    scenario, policy = _shell(
        scenario_id="no_waiting_space_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_hall", "g_hall", "su_hall", "hall", stay),
            _part("part_walk", "g_walk", "su_walk", "origin", walkers),
        ],
        source_units=[_unit("su_hall", 2, "hall_stay"), _unit("su_walk", 4, "walkers")],
        policy_id="no_space_policy_v1",
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
        simulation_end_s=40,
        deadline_s=40,
    )
    scenario["initial_state"]["students"][0]["hostel_id"] = "hall_stay"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"hall_stay": 2}
    scenario["initial_state"]["students"][1]["hostel_id"] = "walkers"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"walkers": 4}
    scenario["routes"] = {
        "hall_stay": ["hall_hold"],
        "walkers": ["walk", "hall_hold"],
    }
    return scenario, policy


def build_deadlock_with_valid_wait_case() -> tuple[dict, dict]:
    """Hall never opens. Waiters occupy the preceding hold. Incomplete deadlock."""
    stay = _members("h", 4, "su_hall")
    walkers = _members("w", 4, "su_walk")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "path_hold",
            0.005,
            0.0,
            "preceding hold",
            physical=8,
            operating=8,
            preceding="origin",
        ),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "hall",
            physical=4,
            operating=4,
            preceding="path_hold",
        ),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 5,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "leg_walk"},
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
    ]
    scenario, policy = _shell(
        scenario_id="deadlock_valid_wait_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_hall", "g_hall", "su_hall", "hall", stay),
            _part("part_walk", "g_walk", "su_walk", "origin", walkers),
        ],
        source_units=[_unit("su_hall", 4, "hall_stay"), _unit("su_walk", 4, "walkers")],
        policy_id="deadlock_policy_v1",
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
        simulation_end_s=10000,
        deadline_s=10000,
    )
    scenario["initial_state"]["students"][0]["hostel_id"] = "hall_stay"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"hall_stay": 4}
    scenario["initial_state"]["students"][1]["hostel_id"] = "walkers"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"walkers": 4}
    scenario["routes"] = {
        "hall_stay": ["hall_hold"],
        "walkers": ["walk", "hall_hold"],
    }
    return scenario, policy


def build_partial_service_flow_case() -> tuple[dict, dict]:
    """Four students, one server, 10 s each. Travel time is not the flow limit."""
    members = _members("s", 4, "su_origin")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "entrance",
            0.001,
            0.0,
            "entrance",
            physical=8,
            operating=6,
            preceding="origin",
            service_rule={"kind": "queue", "service_duration_s": 10, "server_count": 1},
        ),
    ]
    legs = [
        {
            "id": "walk_1",
            "from_place_id": "origin",
            "to_place_id": "entrance",
            "duration_s": 60,
            "mode": "walk",
            "flow_limit_students": 2,
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
        {
            "id": "entrance_service",
            "kind": "queue_service",
            "place_id": "entrance",
            "service_duration_s": 10,
            "server_count": 1,
            "queue_discipline": "fcfs",
        },
    ]
    return _shell(
        scenario_id="partial_service_flow_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[_part("part_origin", "g_walk", "su_origin", "origin", members)],
        source_units=[_unit("su_origin", 4)],
        policy_id="partial_service_policy_v1",
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
        deadline_s=95,
        simulation_end_s=1000,
    )


def build_operating_limit_event_case() -> tuple[dict, dict]:
    members = _members("s", 6, "su_origin")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "yard",
            0.001,
            0.0,
            "yard",
            physical=10,
            operating=5,
            preceding="origin",
        ),
    ]
    legs = [
        {
            "id": "walk_1",
            "from_place_id": "origin",
            "to_place_id": "yard",
            "duration_s": 5,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
    ]
    return _shell(
        scenario_id="operating_limit_event_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[_part("part_origin", "g_walk", "su_origin", "origin", members)],
        source_units=[_unit("su_origin", 6)],
        policy_id="operating_limit_policy_v1",
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
    )


def build_reserve_before_departure_case() -> tuple[dict, dict]:
    first = _members("a", 4, "su_a")
    second = _members("b", 4, "su_b")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "hall",
            physical=4,
            operating=4,
            preceding="origin",
        ),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 5,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {"id": "walk", "kind": "travel", "leg_id": "leg_walk"},
        {
            "id": "hall_hold",
            "kind": "hold",
            "place_id": "hall",
            "until": {"calendar_id": "never_open"},
        },
    ]
    scenario, policy = _shell(
        scenario_id="reserve_before_departure_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_a", "g_a", "su_a", "origin", first),
            _part("part_b", "g_b", "su_b", "origin", second),
        ],
        source_units=[_unit("su_a", 4, "group_a"), _unit("su_b", 4, "group_b")],
        policy_id="reserve_before_v1",
        calendars=[{"id": "never_open", "open_time_s": 99999, "place_id": "hall"}],
        extra_policy={
            "coordination_delay_s": 0,
            "destination_space_rule": "reserve_before_departure",
        },
        simulation_end_s=40,
        deadline_s=40,
    )
    scenario["source_units"][0]["readiness_s"] = 0
    scenario["source_units"][1]["readiness_s"] = 1
    scenario["source_units"][1]["actual_reporting_s"] = 1
    scenario["initial_state"]["students"][0]["hostel_id"] = "group_a"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"group_a": 4}
    scenario["initial_state"]["students"][1]["hostel_id"] = "group_b"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"group_b": 4}
    scenario["routes"] = {
        "group_a": ["walk", "hall_hold"],
        "group_b": ["walk", "hall_hold"],
    }
    return scenario, policy


def build_changing_conditions_case() -> tuple[dict, dict]:
    members_a = _members("a", 2, "su_a")
    members_b = _members("b", 2, "su_b")
    places = [
        _unbounded("origin_a", 0.0, 0.0, "origin a"),
        _unbounded("origin_b", 0.0, 0.02, "origin b"),
        _unbounded("shelter", 0.002, 0.0, "rain shelter"),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "hall",
            physical=20,
            operating=18,
            preceding="origin_a",
        ),
    ]
    legs = [
        {
            "id": "leg_a",
            "from_place_id": "origin_a",
            "to_place_id": "hall",
            "duration_s": 20,
            "mode": "walk",
            "shared_resource_ids": [],
        },
        {
            "id": "leg_b",
            "from_place_id": "origin_b",
            "to_place_id": "hall",
            "duration_s": 20,
            "mode": "walk",
            "shared_resource_ids": [],
        },
        {
            "id": "leg_closed",
            "from_place_id": "origin_a",
            "to_place_id": "hall",
            "duration_s": 8,
            "mode": "walk",
            "shared_resource_ids": [],
        },
    ]
    stages = [
        {"id": "walk_a", "kind": "travel", "leg_id": "leg_a"},
        {"id": "walk_b", "kind": "travel", "leg_id": "leg_b"},
    ]
    scenario, policy = _shell(
        scenario_id="changing_conditions_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part("part_a", "g_a", "su_a", "origin_a", members_a),
            _part("part_b", "g_b", "su_b", "origin_b", members_b),
        ],
        source_units=[_unit("su_a", 2, "hostel_a"), _unit("su_b", 2, "hostel_b")],
        policy_id="conditions_policy_v1",
        vehicles=[
            {
                "id": "bus_out",
                "type": "coach",
                "place_id": "origin_a",
                "available_time_s": 0,
                "capacity_students": 40,
                "outages": [{"start_s": 1, "end_s": 50}],
            }
        ],
        workers=[
            {
                "id": "w1",
                "role": "escort",
                "place_id": "origin_a",
                "available_time_s": 0,
                "work_periods": [{"start_s": 0, "end_s": 8}],
            }
        ],
        calendars=[
            {"id": "door_a", "open_time_s": 0, "close_time_s": 15, "place_id": "hall"},
            {"id": "hall_open", "open_time_s": 40, "place_id": "hall"},
        ],
        extra_scenario={
            "routes": {"hostel_a": ["walk_a"], "hostel_b": ["walk_b"]},
            "external_conditions": [
                {
                    "id": "rain_event",
                    "kind": "rain",
                    "at_s": 5,
                    "shared": True,
                    "affects_leg_ids": ["leg_a", "leg_b"],
                    "effects": {"walking_rate_factor": 0.5, "require_shelter": True},
                    "forecast": {"kind": "clear", "walking_rate_factor": 1.0},
                    "actual": True,
                },
                {
                    "id": "path_closed",
                    "kind": "path_closure",
                    "at_s": 0,
                    "shared": True,
                    "affects_leg_ids": ["leg_closed"],
                    "effects": {"path_closed": True},
                    "forecast": {"path_closed": False},
                    "actual": True,
                },
            ],
        },
        extra_policy={"coordination_delay_s": 10, "destination_space_rule": "allow_approach_wait"},
    )
    scenario["initial_state"]["students"][0]["hostel_id"] = "hostel_a"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"hostel_a": 2}
    scenario["initial_state"]["students"][1]["hostel_id"] = "hostel_b"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"hostel_b": 2}
    scenario["source_units"][1]["readiness_s"] = 6
    scenario["source_units"][1]["actual_reporting_s"] = 6
    return scenario, policy


def build_initial_inflight_and_background_case() -> tuple[dict, dict]:
    stay = _members("m", 2, "su_move")
    waiters = _members("q", 2, "su_queue")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "hall",
            physical=20,
            operating=18,
            preceding="origin",
        ),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 30,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    stages = [{"id": "walk", "kind": "travel", "leg_id": "leg_walk"}]
    scenario, policy = _shell(
        scenario_id="initial_inflight_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[
            _part(
                "part_move",
                "g_move",
                "su_move",
                "origin",
                stay,
                extra={
                    "status": "travelling",
                    "leg_id": "leg_walk",
                    "arrival_s": 12,
                },
            ),
            _part("part_wait", "g_wait", "su_queue", "origin", waiters),
        ],
        source_units=[_unit("su_move", 2, "movers"), _unit("su_queue", 2, "waiters")],
        policy_id="inflight_policy_v1",
        queues=[{"place_id": "hall", "student_count": 3}],
        extra_scenario={
            "background_demand": {
                "pedestrians": 3,
                "road_crossings": 1,
                "other_arrivals": 0,
                "visible_assumption": False,
                "occupancy_by_place": {"hall": 3},
            },
            "routes": {"movers": ["walk"], "waiters": ["walk"]},
        },
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
    )
    scenario["initial_state"]["students"][0]["hostel_id"] = "movers"
    scenario["initial_state"]["students"][0]["hostel_composition"] = {"movers": 2}
    scenario["initial_state"]["students"][1]["hostel_id"] = "waiters"
    scenario["initial_state"]["students"][1]["hostel_composition"] = {"waiters": 2}
    scenario["source_units"][1]["readiness_s"] = 0
    return scenario, policy


def build_time_limit_incomplete_case() -> tuple[dict, dict]:
    members = _members("s", 4, "su_origin")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        _unbounded("hall", 0.01, 0.0, "hall"),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 50,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    stages = [{"id": "walk", "kind": "travel", "leg_id": "leg_walk"}]
    return _shell(
        scenario_id="time_limit_incomplete_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[_part("part_origin", "g_walk", "su_origin", "origin", members)],
        source_units=[_unit("su_origin", 4)],
        policy_id="time_limit_policy_v1",
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
        simulation_end_s=10,
        deadline_s=10,
    )


def build_door_reopen_case() -> tuple[dict, dict]:
    members = _members("s", 2, "su_origin")
    places = [
        _unbounded("origin", 0.0, 0.0, "origin"),
        constrained_place(
            "hall",
            0.01,
            0.0,
            "hall",
            physical=10,
            operating=10,
            preceding="origin",
        ),
    ]
    legs = [
        {
            "id": "leg_walk",
            "from_place_id": "origin",
            "to_place_id": "hall",
            "duration_s": 5,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    stages = [
        {
            "id": "door_hold",
            "kind": "hold",
            "place_id": "origin",
            "until": {"calendar_id": "door_a"},
        },
        {"id": "walk", "kind": "travel", "leg_id": "leg_walk"},
    ]
    return _shell(
        scenario_id="door_reopen_v1",
        places=places,
        legs=legs,
        stages=stages,
        students=[_part("part_origin", "g_walk", "su_origin", "origin", members)],
        source_units=[_unit("su_origin", 2)],
        policy_id="door_reopen_policy_v1",
        calendars=[
            {
                "id": "door_a",
                "open_time_s": 12,
                "close_time_s": 80,
                "place_id": "hall",
            }
        ],
        extra_policy={"coordination_delay_s": 0, "destination_space_rule": "allow_approach_wait"},
    )
