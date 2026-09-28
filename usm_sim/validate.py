"""Reject incomplete or forbidden Simulate inputs. Do not invent defaults."""

from __future__ import annotations

from typing import Any, Mapping

from usm_sim.constants import (
    CONDITION_KINDS,
    COUNT_METHODS,
    DESTINATION_SPACE_RULES,
    FORBIDDEN_MODES,
    GROUPING_BASES,
    GROUPING_MODES,
    STAGE_KINDS,
    TIMEZONE_NAME,
)
from usm_sim.errors import SimulationError
from usm_sim.grouping import _validate_grouping_fields
from usm_sim.workers import staffing_floor_violations

SCENARIO_REQUIRED = (
    "format_version",
    "data_version",
    "scenario_id",
    "event_date",
    "start_time_local",
    "timezone",
    "deadline_s",
    "simulation_end_s",
    "max_events_per_run",
    "source_units",
    "places",
    "route_legs",
    "route_stages",
    "initial_state",
    "operating_rules",
    "calendars",
    "source_records",
    "measured_facts",
    "uncertain_assumptions",
    "decisions",
)

INITIAL_STATE_REQUIRED = (
    "students",
    "queues",
    "workers",
    "vehicles",
    "hall_occupancy_students",
)

SOURCE_UNIT_REQUIRED = (
    "id",
    "hostel_id",
    "estimated_attendance",
    "resolved_attendance",
    "actual_reporting_s",
    "readiness_s",
)

PLACE_REQUIRED = ("id", "latitude_deg", "longitude_deg")

LEG_REQUIRED = ("id", "from_place_id", "to_place_id", "duration_s")

STAGE_REQUIRED = ("id", "kind")

POLICY_REQUIRED = ("policy_id", "required_endpoint")

SOURCE_RECORD_REQUIRED = (
    "field",
    "value",
    "unit",
    "date",
    "method",
    "confidence",
    "observation_ref",
    "category",
)

HOSTEL_DEMAND_REQUIRED = (
    "id",
    "resident_occupancy",
    "expected_event_attendance",
    "resolved_attendance",
)

VEHICLE_TYPE_REQUIRED = (
    "id",
    "capacity_students",
    "usable_doors",
    "boarding_setup_s",
    "boarding_s_per_passenger_per_door",
    "alighting_setup_s",
    "alighting_s_per_passenger_per_door",
)

FLEET_REQUIRED = (
    "id",
    "vehicle_ids",
    "boarding_place_id",
    "alighting_place_id",
    "boarding_berth_capacity",
    "dropoff_space_capacity",
)


def _as_mapping(value: Any, field: str) -> dict:
    if value is None:
        raise SimulationError(
            "missing_input",
            f"Missing critical input: {field}",
            field=field,
        )
    if not isinstance(value, Mapping):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be an object",
            field=field,
        )
    return dict(value)


def _require_keys(data: Mapping, keys: tuple[str, ...], prefix: str) -> None:
    for key in keys:
        field = f"{prefix}.{key}" if prefix else key
        if key not in data or data[key] is None or data[key] == "":
            raise SimulationError(
                "missing_input",
                f"Missing critical input: {field}",
                field=field,
            )


def _require_nonneg_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be a nonnegative integer",
            field=field,
        )
    if value < 0:
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be a nonnegative integer",
            field=field,
        )
    return value


def _require_nonneg_number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be a nonnegative number of seconds",
            field=field,
        )
    if value < 0:
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be a nonnegative number of seconds",
            field=field,
        )
    return value


def _scan_forbidden(value: Any, field: str) -> None:
    if isinstance(value, str):
        if value in FORBIDDEN_MODES:
            raise SimulationError(
                "unsupported_policy",
                f"Forbidden process or route mode {value!r} is not in this model",
                field=field,
            )
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{field}.{key}" if field else str(key)
            if key in FORBIDDEN_MODES and item:
                raise SimulationError(
                    "unsupported_policy",
                    f"Forbidden process {key!r} is not in this model",
                    field=child,
                )
            _scan_forbidden(item, child)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_forbidden(item, f"{field}[{index}]")


def validate_inputs(scenario: Mapping, policy: Mapping) -> tuple[dict, dict]:
    scenario_d = _as_mapping(scenario, "scenario")
    policy_d = _as_mapping(policy, "policy")
    _require_keys(scenario_d, SCENARIO_REQUIRED, "scenario")
    _require_keys(policy_d, POLICY_REQUIRED, "policy")
    if is_operational_profile(scenario_d):
        validate_operational_profile(scenario_d, policy_d)
    _scan_forbidden(scenario_d, "scenario")
    _scan_forbidden(policy_d, "policy")

    if scenario_d["timezone"] != TIMEZONE_NAME:
        raise SimulationError(
            "invalid_value_or_unit",
            f"timezone must be {TIMEZONE_NAME}",
            field="scenario.timezone",
        )

    _require_nonneg_number(scenario_d["deadline_s"], "scenario.deadline_s")
    _require_nonneg_number(scenario_d["simulation_end_s"], "scenario.simulation_end_s")
    max_events = _require_nonneg_int(
        scenario_d["max_events_per_run"], "scenario.max_events_per_run"
    )
    if max_events < 1:
        raise SimulationError(
            "invalid_value_or_unit",
            "max_events_per_run must be at least 1",
            field="scenario.max_events_per_run",
        )

    source_units = scenario_d["source_units"]
    if not isinstance(source_units, list) or not source_units:
        raise SimulationError(
            "missing_input",
            "scenario.source_units must list at least one source unit",
            field="scenario.source_units",
        )
    unit_ids: set[str] = set()
    for index, raw_unit in enumerate(source_units):
        unit = _as_mapping(raw_unit, f"scenario.source_units[{index}]")
        _require_keys(unit, SOURCE_UNIT_REQUIRED, f"scenario.source_units[{index}]")
        if unit["id"] in unit_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate source unit id {unit['id']!r}",
                field=f"scenario.source_units[{index}].id",
            )
        unit_ids.add(unit["id"])
        _require_nonneg_int(
            unit["estimated_attendance"],
            f"scenario.source_units[{index}].estimated_attendance",
        )
        _require_nonneg_int(
            unit["resolved_attendance"],
            f"scenario.source_units[{index}].resolved_attendance",
        )
        _require_nonneg_number(
            unit["actual_reporting_s"],
            f"scenario.source_units[{index}].actual_reporting_s",
        )
        _require_nonneg_number(
            unit["readiness_s"],
            f"scenario.source_units[{index}].readiness_s",
        )
        if unit.get("required_reporting_s") is not None:
            _require_nonneg_number(
                unit["required_reporting_s"],
                f"scenario.source_units[{index}].required_reporting_s",
            )
        if unit.get("availability_s") is not None:
            _require_nonneg_number(
                unit["availability_s"],
                f"scenario.source_units[{index}].availability_s",
            )
        source_units[index] = unit

    hostel_ids = _validate_hostels(scenario_d, source_units)

    places = scenario_d["places"]
    if not isinstance(places, list) or not places:
        raise SimulationError(
            "missing_input",
            "scenario.places must list at least one place",
            field="scenario.places",
        )
    place_ids: set[str] = set()
    for index, raw_place in enumerate(places):
        place = _as_mapping(raw_place, f"scenario.places[{index}]")
        _require_keys(place, PLACE_REQUIRED, f"scenario.places[{index}]")
        if place["id"] in place_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate place id {place['id']!r}",
                field=f"scenario.places[{index}].id",
            )
        if place.get("capacity_from_gps_scatter"):
            raise SimulationError(
                "invalid_value_or_unit",
                "GPS scatter cannot set storage capacity",
                field=f"scenario.places[{index}].capacity_from_gps_scatter",
            )
        unbounded = place.get("capacity_constraint") == "unbounded"
        if not unbounded and place.get("capacity_students") is None:
            raise SimulationError(
                "missing_input",
                "place needs capacity_students or an explicit unbounded capacity_constraint",
                field=f"scenario.places[{index}].capacity_students",
            )
        if not unbounded:
            _require_nonneg_int(
                place["capacity_students"],
                f"scenario.places[{index}].capacity_students",
            )
        physical = place.get("physical_capacity_students", place.get("capacity_students"))
        operating = place.get("operating_limit_students")
        if operating is not None:
            _require_nonneg_int(
                operating, f"scenario.places[{index}].operating_limit_students"
            )
            if physical is not None and int(operating) > int(physical):
                raise SimulationError(
                    "invalid_value_or_unit",
                    "operating limit cannot exceed physical capacity",
                    field=f"scenario.places[{index}].operating_limit_students",
                )
        if place.get("physical_capacity_vehicles") is not None:
            _require_nonneg_int(
                place["physical_capacity_vehicles"],
                f"scenario.places[{index}].physical_capacity_vehicles",
            )
        if place.get("constrained"):
            if physical is None:
                raise SimulationError(
                    "missing_input",
                    "constrained place needs physical capacity",
                    field=f"scenario.places[{index}].physical_capacity_students",
                )
            if operating is None:
                raise SimulationError(
                    "missing_input",
                    "constrained place needs operating_limit_students",
                    field=f"scenario.places[{index}].operating_limit_students",
                )
            if "preceding_place_id" not in place:
                raise SimulationError(
                    "missing_input",
                    "constrained place needs preceding_place_id",
                    field=f"scenario.places[{index}].preceding_place_id",
                )
            if not place.get("queue_discipline") and not place.get("priority_rule"):
                raise SimulationError(
                    "missing_input",
                    "constrained place needs queue_discipline or priority_rule",
                    field=f"scenario.places[{index}].priority_rule",
                )
            if place.get("service_rule") is None:
                raise SimulationError(
                    "missing_input",
                    "constrained place needs service_rule",
                    field=f"scenario.places[{index}].service_rule",
                )
        place_ids.add(place["id"])
        places[index] = place
    for index, place in enumerate(places):
        preceding = place.get("preceding_place_id")
        if preceding and preceding not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"place {place['id']!r} preceding_place_id {preceding!r} is unknown",
                field=f"scenario.places[{index}].preceding_place_id",
            )
        queue_place = place.get("vehicle_queue_place_id")
        if queue_place and queue_place not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"place {place['id']!r} vehicle_queue_place_id {queue_place!r} is unknown",
                field=f"scenario.places[{index}].vehicle_queue_place_id",
            )

    legs = scenario_d["route_legs"]
    if not isinstance(legs, list) or not legs:
        raise SimulationError(
            "missing_input",
            "scenario.route_legs must list at least one leg",
            field="scenario.route_legs",
        )
    leg_ids: set[str] = set()
    for index, raw_leg in enumerate(legs):
        leg = _as_mapping(raw_leg, f"scenario.route_legs[{index}]")
        _require_keys(leg, LEG_REQUIRED, f"scenario.route_legs[{index}]")
        if leg["id"] in leg_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate route leg id {leg['id']!r}",
                field=f"scenario.route_legs[{index}].id",
            )
        for ref_field in ("from_place_id", "to_place_id"):
            if leg[ref_field] not in place_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"route leg {leg['id']!r} references unknown place {leg[ref_field]!r}",
                    field=f"scenario.route_legs[{index}].{ref_field}",
                )
        _require_nonneg_number(leg["duration_s"], f"scenario.route_legs[{index}].duration_s")
        if leg.get("flow_limit_students") is not None:
            _require_nonneg_int(
                leg["flow_limit_students"],
                f"scenario.route_legs[{index}].flow_limit_students",
            )
        if leg.get("mode") in FORBIDDEN_MODES:
            raise SimulationError(
                "unsupported_policy",
                f"route leg mode {leg['mode']!r} is not in this model",
                field=f"scenario.route_legs[{index}].mode",
            )
        leg_ids.add(leg["id"])
        legs[index] = leg

    raw_calendars = scenario_d["calendars"]
    if not isinstance(raw_calendars, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.calendars must be a list (empty is an explicit assumption)",
            field="scenario.calendars",
        )
    calendar_ids: set[str] = set()
    for index, raw_calendar in enumerate(raw_calendars):
        calendar = _as_mapping(raw_calendar, f"scenario.calendars[{index}]")
        _require_keys(calendar, ("id", "open_time_s"), f"scenario.calendars[{index}]")
        if calendar["id"] in calendar_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate calendar id {calendar['id']!r}",
                field=f"scenario.calendars[{index}].id",
            )
        _require_nonneg_number(
            calendar["open_time_s"],
            f"scenario.calendars[{index}].open_time_s",
        )
        if calendar.get("close_time_s") is not None:
            _require_nonneg_number(
                calendar["close_time_s"],
                f"scenario.calendars[{index}].close_time_s",
            )
        calendar_ids.add(calendar["id"])
        raw_calendars[index] = calendar

    stages = scenario_d["route_stages"]
    if not isinstance(stages, list) or not stages:
        raise SimulationError(
            "missing_input",
            "scenario.route_stages must list at least one stage",
            field="scenario.route_stages",
        )
    stage_ids: set[str] = set()
    for index, raw_stage in enumerate(stages):
        stage = _as_mapping(raw_stage, f"scenario.route_stages[{index}]")
        _require_keys(stage, STAGE_REQUIRED, f"scenario.route_stages[{index}]")
        kind = stage["kind"]
        if kind in FORBIDDEN_MODES:
            raise SimulationError(
                "unsupported_policy",
                f"stage kind {kind!r} is not in this model",
                field=f"scenario.route_stages[{index}].kind",
            )
        if kind not in STAGE_KINDS:
            raise SimulationError(
                "invalid_value_or_unit",
                f"unsupported stage kind {kind!r}",
                field=f"scenario.route_stages[{index}].kind",
            )
        if kind in {"travel", "vehicle_travel"}:
            if not stage.get("leg_id"):
                raise SimulationError(
                    "missing_input",
                    f"travel stage {stage['id']!r} needs leg_id",
                    field=f"scenario.route_stages[{index}].leg_id",
                )
            if stage["leg_id"] not in leg_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"stage {stage['id']!r} references unknown leg {stage['leg_id']!r}",
                    field=f"scenario.route_stages[{index}].leg_id",
                )
        if kind in {"hold", "queue_service", "batch_service", "manual_count"}:
            if not stage.get("place_id"):
                raise SimulationError(
                    "missing_input",
                    f"stage {stage['id']!r} needs place_id",
                    field=f"scenario.route_stages[{index}].place_id",
                )
            if stage["place_id"] not in place_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"stage {stage['id']!r} references unknown place {stage['place_id']!r}",
                    field=f"scenario.route_stages[{index}].place_id",
                )
        if kind == "manual_count":
            if not stage.get("checkpoint_id"):
                raise SimulationError(
                    "missing_input",
                    f"manual_count stage {stage['id']!r} needs checkpoint_id",
                    field=f"scenario.route_stages[{index}].checkpoint_id",
                )
        if kind == "hold":
            until = stage.get("until")
            if not isinstance(until, dict) or not until:
                raise SimulationError(
                    "missing_input",
                    f"hold stage {stage['id']!r} needs until",
                    field=f"scenario.route_stages[{index}].until",
                )
            if "duration_s" in until:
                _require_nonneg_number(
                    until["duration_s"],
                    f"scenario.route_stages[{index}].until.duration_s",
                )
            if "calendar_id" in until:
                calendar_id = until["calendar_id"]
                if calendar_id not in calendar_ids:
                    raise SimulationError(
                        "unknown_reference",
                        f"hold stage {stage['id']!r} references unknown calendar {calendar_id!r}",
                        field=f"scenario.route_stages[{index}].until.calendar_id",
                    )
        if kind == "queue_service":
            if "service_duration_s" not in stage or stage["service_duration_s"] is None:
                raise SimulationError(
                    "missing_input",
                    f"queue_service stage {stage['id']!r} needs service_duration_s",
                    field=f"scenario.route_stages[{index}].service_duration_s",
                )
            _require_nonneg_number(
                stage["service_duration_s"],
                f"scenario.route_stages[{index}].service_duration_s",
            )
            if "server_count" not in stage or stage["server_count"] is None:
                raise SimulationError(
                    "missing_input",
                    f"queue_service stage {stage['id']!r} needs server_count",
                    field=f"scenario.route_stages[{index}].server_count",
                )
            _require_nonneg_int(
                stage["server_count"],
                f"scenario.route_stages[{index}].server_count",
            )
        if kind == "batch_service":
            has_resource = bool(stage.get("resource_id"))
            has_fleet = bool(stage.get("fleet_id"))
            if has_resource and has_fleet:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"batch_service stage {stage['id']!r} cannot set both resource_id and fleet_id",
                    field=f"scenario.route_stages[{index}].resource_id",
                )
            if not has_resource and not has_fleet:
                raise SimulationError(
                    "missing_input",
                    f"batch_service stage {stage['id']!r} needs resource_id or fleet_id",
                    field=f"scenario.route_stages[{index}].resource_id",
                )
            duration_rule = stage.get("duration_rule")
            if duration_rule not in (None, "fixed", "load_dependent"):
                raise SimulationError(
                    "unsupported_policy",
                    f"unsupported duration_rule {duration_rule!r}",
                    field=f"scenario.route_stages[{index}].duration_rule",
                )
            if duration_rule == "load_dependent":
                if stage.get("duration_s") not in (None, ""):
                    _require_nonneg_number(
                        stage["duration_s"],
                        f"scenario.route_stages[{index}].duration_s",
                    )
            else:
                if stage.get("duration_s") is None:
                    raise SimulationError(
                        "missing_input",
                        f"batch_service stage {stage['id']!r} needs duration_s",
                        field=f"scenario.route_stages[{index}].duration_s",
                    )
                _require_nonneg_number(
                    stage["duration_s"],
                    f"scenario.route_stages[{index}].duration_s",
                )
        if stage["id"] in stage_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate stage id {stage['id']!r}",
                field=f"scenario.route_stages[{index}].id",
            )
        stage_ids.add(stage["id"])
        stages[index] = stage

    initial = _as_mapping(scenario_d["initial_state"], "scenario.initial_state")
    _require_keys(initial, INITIAL_STATE_REQUIRED, "scenario.initial_state")
    if not isinstance(initial["students"], list) or not initial["students"]:
        raise SimulationError(
            "missing_input",
            "initial_state.students must list at least one movement part",
            field="scenario.initial_state.students",
        )
    if not isinstance(initial["queues"], list):
        raise SimulationError(
            "invalid_value_or_unit",
            "initial_state.queues must be a list (empty is an explicit assumption)",
            field="scenario.initial_state.queues",
        )
    if not isinstance(initial["workers"], list):
        raise SimulationError(
            "invalid_value_or_unit",
            "initial_state.workers must be a list",
            field="scenario.initial_state.workers",
        )
    if not isinstance(initial["vehicles"], list):
        raise SimulationError(
            "invalid_value_or_unit",
            "initial_state.vehicles must be a list",
            field="scenario.initial_state.vehicles",
        )
    _require_nonneg_int(
        initial["hall_occupancy_students"],
        "scenario.initial_state.hall_occupancy_students",
    )

    part_ids: set[str] = set()
    global_member_keys: set[str] = set()
    members_by_unit: dict[str, int] = {}
    for index, raw_part in enumerate(initial["students"]):
        part = _as_mapping(raw_part, f"scenario.initial_state.students[{index}]")
        for key in ("part_id", "group_id", "source_unit_id", "place_id", "members"):
            if key not in part or part[key] is None or part[key] == "":
                raise SimulationError(
                    "missing_input",
                    f"Missing critical input: scenario.initial_state.students[{index}].{key}",
                    field=f"scenario.initial_state.students[{index}].{key}",
                )
        if part["part_id"] in part_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate part id {part['part_id']!r}",
                field=f"scenario.initial_state.students[{index}].part_id",
            )
        part_ids.add(part["part_id"])
        if part["source_unit_id"] not in unit_ids:
            raise SimulationError(
                "unknown_reference",
                f"movement part references unknown source unit {part['source_unit_id']!r}",
                field=f"scenario.initial_state.students[{index}].source_unit_id",
            )
        if part["place_id"] not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"movement part references unknown place {part['place_id']!r}",
                field=f"scenario.initial_state.students[{index}].place_id",
            )
        members = part["members"]
        if not isinstance(members, list) or not members:
            raise SimulationError(
                "missing_input",
                "each movement part needs an explicit members list",
                field=f"scenario.initial_state.students[{index}].members",
            )
        seen_keys: set[str] = set()
        for member_index, raw_member in enumerate(members):
            member = _as_mapping(
                raw_member,
                f"scenario.initial_state.students[{index}].members[{member_index}]",
            )
            if not member.get("student_key"):
                raise SimulationError(
                    "missing_input",
                    "member is missing student_key",
                    field=(
                        f"scenario.initial_state.students[{index}]"
                        f".members[{member_index}].student_key"
                    ),
                )
            if "queue_tie_key" not in member or member["queue_tie_key"] in (None, ""):
                raise SimulationError(
                    "missing_input",
                    "member is missing queue_tie_key",
                    field=(
                        f"scenario.initial_state.students[{index}]"
                        f".members[{member_index}].queue_tie_key"
                    ),
                )
            if member["student_key"] in seen_keys:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"duplicate student_key {member['student_key']!r}",
                    field=(
                        f"scenario.initial_state.students[{index}]"
                        f".members[{member_index}].student_key"
                    ),
                )
            if member["student_key"] in global_member_keys:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"overlapping members across parts for {member['student_key']!r}",
                    field=(
                        f"scenario.initial_state.students[{index}]"
                        f".members[{member_index}].student_key"
                    ),
                )
            seen_keys.add(member["student_key"])
            global_member_keys.add(member["student_key"])
            unit_id = member.get("source_unit_id") or part["source_unit_id"]
            members_by_unit[unit_id] = members_by_unit.get(unit_id, 0) + 1
            members[member_index] = member
        part["members"] = members
        initial["students"][index] = part
    for unit in source_units:
        expected = int(unit.get("resolved_attendance") or 0)
        got = int(members_by_unit.get(unit["id"]) or 0)
        if got < expected:
            raise SimulationError(
                "invalid_value_or_unit",
                (
                    f"source unit {unit['id']!r} has {expected} attending students "
                    f"but only {got} members in movement parts"
                ),
                field=f"scenario.source_units.{unit['id']}.resolved_attendance",
            )

    vehicle_ids: set[str] = set()
    for index, raw_vehicle in enumerate(initial["vehicles"]):
        vehicle = _as_mapping(raw_vehicle, f"scenario.initial_state.vehicles[{index}]")
        for key in ("id", "type", "place_id", "available_time_s", "capacity_students"):
            if key not in vehicle or vehicle[key] is None or vehicle[key] == "":
                raise SimulationError(
                    "missing_input",
                    f"Missing critical input: scenario.initial_state.vehicles[{index}].{key}",
                    field=f"scenario.initial_state.vehicles[{index}].{key}",
                )
        if vehicle["place_id"] not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"vehicle references unknown place {vehicle['place_id']!r}",
                field=f"scenario.initial_state.vehicles[{index}].place_id",
            )
        _require_nonneg_number(
            vehicle["available_time_s"],
            f"scenario.initial_state.vehicles[{index}].available_time_s",
        )
        _require_nonneg_int(
            vehicle["capacity_students"],
            f"scenario.initial_state.vehicles[{index}].capacity_students",
        )
        vehicle_ids.add(vehicle["id"])
        initial["vehicles"][index] = vehicle

    vehicle_types = _validate_vehicle_types(scenario_d)
    _bind_vehicles_to_types(initial["vehicles"], vehicle_types)
    fleet_ids = _validate_fleets(scenario_d, vehicle_ids, place_ids)
    cohort_ids = {u.get("cohort_id") for u in scenario_d.get("source_units", []) if u.get("cohort_id")}
    _validate_routes(scenario_d, stage_ids, hostel_ids, cohort_ids=cohort_ids)
    _validate_carpark_tiers(scenario_d)

    for index, stage in enumerate(stages):
        if stage["kind"] == "batch_service":
            resource_id = stage.get("resource_id")
            fleet_id = stage.get("fleet_id")
            if resource_id and resource_id not in vehicle_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"batch_service stage {stage['id']!r} references unknown resource {resource_id!r}",
                    field=f"scenario.route_stages[{index}].resource_id",
                )
            if fleet_id and fleet_id not in fleet_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"batch_service stage {stage['id']!r} references unknown fleet {fleet_id!r}",
                    field=f"scenario.route_stages[{index}].fleet_id",
                )
            if stage.get("duration_rule") == "load_dependent":
                _require_load_dependent_fields(
                    initial["vehicles"],
                    vehicle_types,
                    fleet_id,
                    resource_id,
                    scenario_d.get("fleets") or [],
                )
        if stage["kind"] == "hold":
            until = stage.get("until") or {}
            resource_id = until.get("resource_available")
            if resource_id and resource_id not in vehicle_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"hold stage {stage['id']!r} references unknown resource {resource_id!r}",
                    field=f"scenario.route_stages[{index}].until.resource_available",
                )
            fleet_id = until.get("fleet_available")
            if fleet_id and fleet_id not in fleet_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"hold stage {stage['id']!r} references unknown fleet {fleet_id!r}",
                    field=f"scenario.route_stages[{index}].until.fleet_available",
                )

    source_records = scenario_d["source_records"]
    if not isinstance(source_records, list) or not source_records:
        raise SimulationError(
            "missing_input",
            "scenario.source_records must list provenance for source-derived values",
            field="scenario.source_records",
        )
    for index, raw_record in enumerate(source_records):
        record = _as_mapping(raw_record, f"scenario.source_records[{index}]")
        _require_keys(record, SOURCE_RECORD_REQUIRED, f"scenario.source_records[{index}]")
        if record["category"] not in {"measured", "estimated", "assumed", "decision"}:
            raise SimulationError(
                "invalid_value_or_unit",
                "source record category must be measured, estimated, assumed, or decision",
                field=f"scenario.source_records[{index}].category",
            )
        source_records[index] = record

    for field in ("measured_facts", "uncertain_assumptions", "decisions"):
        if not isinstance(scenario_d[field], list):
            raise SimulationError(
                "invalid_value_or_unit",
                f"{field} must be a list",
                field=f"scenario.{field}",
            )

    operating = _as_mapping(scenario_d["operating_rules"], "scenario.operating_rules")
    if "required_endpoint" not in operating or not operating["required_endpoint"]:
        raise SimulationError(
            "missing_input",
            "operating_rules.required_endpoint is required",
            field="scenario.operating_rules.required_endpoint",
        )
    if operating["required_endpoint"] != policy_d["required_endpoint"]:
        raise SimulationError(
            "fixed_rule_violation",
            "policy.required_endpoint cannot override scenario.operating_rules.required_endpoint",
            field="policy.required_endpoint",
        )
    if operating.get("direct_walk_permitted"):
        raise SimulationError(
            "unsupported_policy",
            "direct walking off the fixed RST route is not in this model",
            field="scenario.operating_rules.direct_walk_permitted",
        )
    walk_rule = operating.get("walk_occupancy_rule")
    if walk_rule is not None:
        rule = _as_mapping(walk_rule, "scenario.operating_rules.walk_occupancy_rule")
        if rule.get("type") not in (None, "two_band"):
            raise SimulationError(
                "unsupported_policy",
                f"unsupported walk_occupancy_rule.type {rule.get('type')!r}",
                field="scenario.operating_rules.walk_occupancy_rule.type",
            )
        for field in ("empty_duration_factor", "congested_duration_factor"):
            if rule.get(field) is not None:
                _require_nonneg_number(rule[field], f"operating_rules.walk_occupancy_rule.{field}")
        empty_factor = float(rule.get("empty_duration_factor") or 1.0)
        congested_factor = float(rule.get("congested_duration_factor") or 1.0)
        if empty_factor <= 0 or congested_factor <= 0:
            raise SimulationError(
                "invalid_value_or_unit",
                "walk occupancy duration factors must be positive",
                field="scenario.operating_rules.walk_occupancy_rule",
            )
        operating["walk_occupancy_rule"] = rule
    scenario_d["operating_rules"] = operating
    scenario_d["initial_state"] = initial

    grouping = policy_d.get("grouping") or {}
    if isinstance(grouping, Mapping):
        mode = grouping.get("mode")
        if mode is not None and mode not in GROUPING_MODES:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported grouping mode {mode!r}",
                field="policy.grouping.mode",
            )
        if grouping.get("basis"):
            _validate_grouping_fields(dict(grouping))
            _require_layout_for_basis(source_units, grouping)
            _validate_physical_assembly(grouping, place_ids, initial)

    _validate_counting(scenario_d, policy_d, place_ids, stage_ids)
    _validate_shared_resources(scenario_d)
    _validate_walking_routes(scenario_d, hostel_ids, leg_ids)
    _validate_destination(scenario_d, place_ids)
    _validate_background_demand(scenario_d)
    _validate_workers(scenario_d, policy_d, place_ids)
    _validate_space_policy(policy_d)
    _validate_external_conditions(scenario_d, place_ids, leg_ids)
    _validate_reporting(scenario_d, policy_d)
    has_legacy = any(
        (unit.get("late_assembly_s") not in (None, 0))
        or (unit.get("non_attendance") not in (None, 0))
        or (unit.get("withdrawn") not in (None, 0))
        for unit in source_units
    )
    walk_rule = (
        scenario_d.get("operating_rules", {}).get("walk_occupancy_rule")
        or scenario_d.get("walk_occupancy_rule")
    )
    if scenario_d.get("behavior") or has_legacy or walk_rule:
        from usm_sim.behavior import validate_behavior_spec
        validate_behavior_spec(scenario_d)
    if scenario_d.get("_behavior_prepared"):
        from usm_sim.behavior import verify_behavior_conservation
        verify_behavior_conservation(scenario_d)
    if is_operational_profile(scenario_d):
        validate_operational_profile(scenario_d, policy_d)
    return scenario_d, policy_d


OPERATIONAL_SCENARIO_IDS = frozenset({
    "whole_campus_full_cohort_2026",
    "whole-campus-full-cohort",
})
OPERATIONAL_FLEET_TOTAL = 8
OPERATIONAL_FLEET_COACH = 5
OPERATIONAL_FLEET_ELECTRIC = 3
OPERATIONAL_USABLE_DOORS = 1


def is_operational_profile(scenario: Mapping) -> bool:
    if not isinstance(scenario, Mapping):
        return False
    if scenario.get("profile") == "operational":
        return True
    if scenario.get("operational_profile") is True:
        return True
    if scenario.get("profile_id") == "operational":
        return True
    operating = scenario.get("operating_rules")
    if isinstance(operating, Mapping) and operating.get("profile") == "operational":
        return True
    metadata = scenario.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("profile") == "operational":
        return True
    if scenario.get("scenario_id") in OPERATIONAL_SCENARIO_IDS:
        return True
    return False


def validate_operational_profile(scenario_d: dict, policy_d: dict | None = None) -> None:
    vehicles = (scenario_d.get("initial_state") or {}).get("vehicles") or []
    if len(vehicles) != OPERATIONAL_FLEET_TOTAL:
        raise SimulationError(
            "fixed_rule_violation",
            f"operational campus fleet is locked at {OPERATIONAL_FLEET_TOTAL} buses (found {len(vehicles)})",
            field="scenario.initial_state.vehicles",
        )

    coaches = [v for v in vehicles if v.get("type") == "coach"]
    electrics = [v for v in vehicles if v.get("type") == "electric"]
    if len(coaches) != OPERATIONAL_FLEET_COACH or len(electrics) != OPERATIONAL_FLEET_ELECTRIC:
        raise SimulationError(
            "fixed_rule_violation",
            f"operational campus fleet mix is locked at {OPERATIONAL_FLEET_COACH} coaches and {OPERATIONAL_FLEET_ELECTRIC} electric buses (found {len(coaches)} coach, {len(electrics)} electric)",
            field="scenario.initial_state.vehicles",
        )

    for index, v in enumerate(vehicles):
        vtype = v.get("type")
        if vtype not in {"coach", "electric"}:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational vehicle {v.get('id')!r} has invalid type {vtype!r}; must be 'coach' or 'electric'",
                field=f"scenario.initial_state.vehicles[{index}].type",
            )
        doors = v.get("usable_doors")
        if doors is not None and doors != OPERATIONAL_USABLE_DOORS:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational vehicle {v.get('id')!r} has {doors} usable doors; exactly {OPERATIONAL_USABLE_DOORS} door per bus is required",
                field=f"scenario.initial_state.vehicles[{index}].usable_doors",
            )
        tf = v.get("_type_fields") or {}
        tf_doors = tf.get("usable_doors")
        if tf_doors is not None and tf_doors != OPERATIONAL_USABLE_DOORS:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational vehicle {v.get('id')!r} type has {tf_doors} usable doors; exactly {OPERATIONAL_USABLE_DOORS} door per bus is required",
                field=f"scenario.initial_state.vehicles[{index}].usable_doors",
            )

    for index, vt in enumerate(scenario_d.get("vehicle_types") or []):
        doors = vt.get("usable_doors")
        if doors is not None and doors != OPERATIONAL_USABLE_DOORS:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational vehicle type {vt.get('id')!r} has {doors} usable doors; exactly {OPERATIONAL_USABLE_DOORS} door per bus is required",
                field=f"scenario.vehicle_types[{index}].usable_doors",
            )

    dest = scenario_d.get("destination")
    if dest:
        if dest.get("bag_check"):
            raise SimulationError(
                "fixed_rule_violation",
                "operational DTSP destination cannot have bag_check; zero door screening required",
                field="scenario.destination.bag_check",
            )
        if dest.get("security_service"):
            raise SimulationError(
                "fixed_rule_violation",
                "operational DTSP destination cannot have security_service; zero door screening required",
                field="scenario.destination.security_service",
            )
        for dwell_key in ("screening_dwell_s", "screening_dwell", "screening_s_per_person", "check_dwell_s"):
            val = dest.get(dwell_key)
            if val is not None and val > 0:
                raise SimulationError(
                    "fixed_rule_violation",
                    f"operational DTSP destination must have zero screening dwell ({dwell_key}={val})",
                    field=f"scenario.destination.{dwell_key}",
                )
        for index, door in enumerate(dest.get("doors") or []):
            if door.get("bag_check"):
                raise SimulationError(
                    "fixed_rule_violation",
                    f"operational DTSP door {door.get('id')!r} cannot have bag_check",
                    field=f"scenario.destination.doors[{index}].bag_check",
                )
            if door.get("security_service"):
                raise SimulationError(
                    "fixed_rule_violation",
                    f"operational DTSP door {door.get('id')!r} cannot have security_service",
                    field=f"scenario.destination.doors[{index}].security_service",
                )
            for dwell_key in ("screening_dwell_s", "screening_dwell", "screening_s_per_person", "check_dwell_s"):
                val = door.get(dwell_key)
                if val is not None and val > 0:
                    raise SimulationError(
                        "fixed_rule_violation",
                        f"operational DTSP door {door.get('id')!r} must have zero screening dwell ({dwell_key}={val})",
                        field=f"scenario.destination.doors[{index}].{dwell_key}",
                    )

    operating = scenario_d.get("operating_rules") or {}
    if operating.get("bag_check"):
        raise SimulationError(
            "fixed_rule_violation",
            "operational operating_rules cannot have bag_check",
            field="scenario.operating_rules.bag_check",
        )
    if operating.get("security_service"):
        raise SimulationError(
            "fixed_rule_violation",
            "operational operating_rules cannot have security_service",
            field="scenario.operating_rules.security_service",
        )

    if policy_d:
        if policy_d.get("bag_check"):
            raise SimulationError(
                "fixed_rule_violation",
                "operational policy cannot enable bag_check at DTSP",
                field="policy.bag_check",
            )
        if policy_d.get("security_service"):
            raise SimulationError(
                "fixed_rule_violation",
                "operational policy cannot enable security_service at DTSP",
                field="policy.security_service",
            )
        dest_rule = policy_d.get("destination_rule") or {}
        if isinstance(dest_rule, Mapping):
            if dest_rule.get("bag_check") or dest_rule.get("security_service"):
                raise SimulationError(
                    "fixed_rule_violation",
                    "operational policy destination_rule cannot enable door checks at DTSP",
                    field="policy.destination_rule",
                )
            for dwell_key in ("screening_dwell_s", "screening_dwell", "screening_s_per_person", "check_dwell_s"):
                val = dest_rule.get(dwell_key)
                if val is not None and val > 0:
                    raise SimulationError(
                        "fixed_rule_violation",
                        f"operational policy destination_rule must have zero screening dwell ({dwell_key}={val})",
                        field=f"policy.destination_rule.{dwell_key}",
                    )
        counting = policy_d.get("counting") or {}
        assignments = counting.get("assignments") or {}
        if isinstance(assignments, Mapping):
            for cid, assign in assignments.items():
                if not isinstance(assign, Mapping):
                    continue
                loc = assign.get("location_id")
                if loc in {"dtsp_door_a", "dtsp_door_b", "dtsp_door_c", "dtsp_door_d", "door_a", "door_b", "door_c", "door_d", "dtsp_hall_reference"}:
                    raise SimulationError(
                        "fixed_rule_violation",
                        f"operational policy cannot assign counting or screening at DTSP entrance door {loc!r}; headcounts must occur at upstream stations",
                        field=f"policy.counting.assignments.{cid}.location_id",
                    )


def _validate_hostels(scenario_d: dict, source_units: list) -> set[str]:
    raw_hostels = scenario_d.get("hostels")
    if raw_hostels is None:
        return {unit["hostel_id"] for unit in source_units}
    if not isinstance(raw_hostels, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.hostels must be a list",
            field="scenario.hostels",
        )
    hostel_ids: set[str] = set()
    for index, raw_hostel in enumerate(raw_hostels):
        hostel = _as_mapping(raw_hostel, f"scenario.hostels[{index}]")
        _require_keys(hostel, HOSTEL_DEMAND_REQUIRED, f"scenario.hostels[{index}]")
        if "registration" not in hostel:
            raise SimulationError(
                "missing_input",
                f"Missing critical input: scenario.hostels[{index}].registration",
                field=f"scenario.hostels[{index}].registration",
            )
        if hostel["id"] in hostel_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate hostel id {hostel['id']!r}",
                field=f"scenario.hostels[{index}].id",
            )
        for field_name in (
            "resident_occupancy",
            "expected_event_attendance",
            "resolved_attendance",
        ):
            _require_nonneg_int(hostel[field_name], f"scenario.hostels[{index}].{field_name}")
        registration = hostel["registration"]
        if registration is not None:
            _require_nonneg_int(registration, f"scenario.hostels[{index}].registration")
        if hostel.get("bed_capacity") is not None:
            _require_nonneg_int(
                hostel["bed_capacity"],
                f"scenario.hostels[{index}].bed_capacity",
            )
        if "initial_route" in hostel:
            _require_keys(
                hostel,
                ("latitude_deg", "longitude_deg", "origin_place_id", "initial_route"),
                f"scenario.hostels[{index}]",
            )
            if hostel["initial_route"] not in {"rst_bus", "walk"}:
                raise SimulationError(
                    "invalid_value_or_unit",
                    "initial_route must be rst_bus or walk",
                    field=f"scenario.hostels[{index}].initial_route",
                )
        for estimate_key in (
            "bed_capacity_estimate",
            "resident_occupancy_estimate",
            "expected_event_attendance_estimate",
        ):
            if hostel.get(estimate_key):
                _validate_bound_estimate(
                    hostel[estimate_key],
                    f"scenario.hostels[{index}].{estimate_key}",
                )
        demand_values = [
            hostel.get("registration"),
            hostel.get("bed_capacity"),
            hostel.get("resident_occupancy"),
            hostel.get("expected_event_attendance"),
            hostel.get("resolved_attendance"),
        ]
        present = [value for value in demand_values if isinstance(value, int)]
        if len(present) >= 2 and len(set(present)) == 1:
            raise SimulationError(
                "invalid_value_or_unit",
                "hostel demand fields must not be silently treated as the same number",
                field=f"scenario.hostels[{index}]",
            )
        hostel_ids.add(hostel["id"])
        raw_hostels[index] = hostel
    scenario_d["hostels"] = raw_hostels
    return hostel_ids


def _validate_bound_estimate(raw: Mapping, field: str) -> None:
    estimate = _as_mapping(raw, field)
    for key in ("lower", "base", "upper"):
        if key not in estimate or estimate[key] is None:
            raise SimulationError(
                "missing_input",
                f"Missing critical input: {field}.{key}",
                field=f"{field}.{key}",
            )
        _require_nonneg_int(estimate[key], f"{field}.{key}")
    if estimate["lower"] > estimate["base"] or estimate["base"] > estimate["upper"]:
        raise SimulationError(
            "invalid_value_or_unit",
            "lower estimate must not exceed base or upper estimate",
            field=field,
        )


def _validate_vehicle_types(scenario_d: dict) -> dict[str, dict]:
    raw_types = scenario_d.get("vehicle_types")
    if raw_types is None:
        return {}
    if not isinstance(raw_types, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.vehicle_types must be a list",
            field="scenario.vehicle_types",
        )
    types: dict[str, dict] = {}
    for index, raw_type in enumerate(raw_types):
        vtype = _as_mapping(raw_type, f"scenario.vehicle_types[{index}]")
        _require_keys(vtype, VEHICLE_TYPE_REQUIRED, f"scenario.vehicle_types[{index}]")
        if vtype["id"] in types:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate vehicle type {vtype['id']!r}",
                field=f"scenario.vehicle_types[{index}].id",
            )
        _require_nonneg_int(
            vtype["capacity_students"],
            f"scenario.vehicle_types[{index}].capacity_students",
        )
        _require_nonneg_int(
            vtype["usable_doors"],
            f"scenario.vehicle_types[{index}].usable_doors",
        )
        if int(vtype["usable_doors"]) < 1:
            raise SimulationError(
                "invalid_value_or_unit",
                "usable_doors must be at least 1",
                field=f"scenario.vehicle_types[{index}].usable_doors",
            )
        for field_name in (
            "boarding_setup_s",
            "boarding_s_per_passenger_per_door",
            "alighting_setup_s",
            "alighting_s_per_passenger_per_door",
            "return_travel_s",
            "turnaround_s",
        ):
            if field_name in vtype and vtype[field_name] is not None:
                _require_nonneg_number(
                    vtype[field_name],
                    f"scenario.vehicle_types[{index}].{field_name}",
                )
        if vtype.get("seated_capacity_students") is not None:
            _require_nonneg_int(
                vtype["seated_capacity_students"],
                f"scenario.vehicle_types[{index}].seated_capacity_students",
            )
        types[vtype["id"]] = vtype
        raw_types[index] = vtype
    scenario_d["vehicle_types"] = raw_types
    return types


def _bind_vehicles_to_types(vehicles: list, vehicle_types: dict[str, dict]) -> None:
    if not vehicle_types:
        return
    for index, vehicle in enumerate(vehicles):
        type_id = vehicle["type"]
        vtype = vehicle_types.get(type_id)
        if vtype is None:
            raise SimulationError(
                "unknown_reference",
                f"vehicle {vehicle['id']!r} has unknown type {type_id!r}",
                field=f"scenario.initial_state.vehicles[{index}].type",
            )
        if int(vehicle["capacity_students"]) > int(vtype["capacity_students"]):
            raise SimulationError(
                "fixed_rule_violation",
                f"vehicle {vehicle['id']!r} capacity exceeds type {type_id!r}",
                field=f"scenario.initial_state.vehicles[{index}].capacity_students",
            )
        vehicle["_type_fields"] = {
            "usable_doors": vtype["usable_doors"],
            "boarding_setup_s": vtype["boarding_setup_s"],
            "boarding_s_per_passenger_per_door": vtype["boarding_s_per_passenger_per_door"],
            "alighting_setup_s": vtype["alighting_setup_s"],
            "alighting_s_per_passenger_per_door": vtype["alighting_s_per_passenger_per_door"],
            "return_travel_s": vtype.get("return_travel_s"),
            "turnaround_s": vtype.get("turnaround_s"),
            "seated_capacity_students": vtype.get("seated_capacity_students"),
            "type_capacity_students": vtype["capacity_students"],
        }


def _validate_fleets(scenario_d: dict, vehicle_ids: set[str], place_ids: set[str]) -> set[str]:
    raw_fleets = scenario_d.get("fleets")
    if raw_fleets is None:
        return set()
    if not isinstance(raw_fleets, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.fleets must be a list",
            field="scenario.fleets",
        )
    fleet_ids: set[str] = set()
    for index, raw_fleet in enumerate(raw_fleets):
        fleet = _as_mapping(raw_fleet, f"scenario.fleets[{index}]")
        _require_keys(fleet, FLEET_REQUIRED, f"scenario.fleets[{index}]")
        if fleet["id"] in fleet_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate fleet id {fleet['id']!r}",
                field=f"scenario.fleets[{index}].id",
            )
        vehicle_list = fleet["vehicle_ids"]
        if not isinstance(vehicle_list, list) or not vehicle_list:
            raise SimulationError(
                "missing_input",
                f"fleet {fleet['id']!r} needs vehicle_ids",
                field=f"scenario.fleets[{index}].vehicle_ids",
            )
        for vehicle_id in vehicle_list:
            if vehicle_id not in vehicle_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"fleet {fleet['id']!r} references unknown vehicle {vehicle_id!r}",
                    field=f"scenario.fleets[{index}].vehicle_ids",
                )
        for place_field in ("boarding_place_id", "alighting_place_id"):
            if fleet[place_field] not in place_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"fleet {fleet['id']!r} references unknown place {fleet[place_field]!r}",
                    field=f"scenario.fleets[{index}].{place_field}",
                )
        _require_nonneg_int(
            fleet["boarding_berth_capacity"],
            f"scenario.fleets[{index}].boarding_berth_capacity",
        )
        _require_nonneg_int(
            fleet["dropoff_space_capacity"],
            f"scenario.fleets[{index}].dropoff_space_capacity",
        )
        if fleet["boarding_place_id"] != fleet["alighting_place_id"]:
            vehicles_by_id = {
                v["id"]: v
                for v in scenario_d.get("initial_state", {}).get("vehicles", [])
                if isinstance(v, Mapping) and "id" in v
            }
            for vehicle_id in vehicle_list:
                v = vehicles_by_id.get(vehicle_id)
                if v:
                    ret_s = v.get("return_travel_s")
                    if ret_s is None and "_type_fields" in v:
                        ret_s = v["_type_fields"].get("return_travel_s")
                    if ret_s is None:
                        raise SimulationError(
                            "missing_input",
                            (
                                f"Fleet {fleet['id']!r} operates between different places "
                                f"({fleet['boarding_place_id']!r} and {fleet['alighting_place_id']!r}) "
                                f"but vehicle {vehicle_id!r} is missing return_travel_s"
                            ),
                            field=f"scenario.fleets[{index}].return_travel_s",
                        )
                    if ret_s <= 0:
                        raise SimulationError(
                            "invalid_value_or_unit",
                            (
                                f"Fleet {fleet['id']!r} operates between different places "
                                f"({fleet['boarding_place_id']!r} and {fleet['alighting_place_id']!r}) "
                                f"so vehicle {vehicle_id!r} return_travel_s cannot be 0 s"
                            ),
                            field=f"scenario.fleets[{index}].return_travel_s",
                        )
        fleet_ids.add(fleet["id"])
        raw_fleets[index] = fleet
    scenario_d["fleets"] = raw_fleets
    return fleet_ids


def _validate_routes(
    scenario_d: dict,
    stage_ids: set[str],
    hostel_ids: set[str],
    cohort_ids: set[str] | None = None,
) -> None:
    routes = scenario_d.get("routes")
    if routes is None:
        return
    if not isinstance(routes, Mapping):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.routes must be an object keyed by hostel id",
            field="scenario.routes",
        )
    allowed_keys = hostel_ids | (cohort_ids or set())
    for hostel_id, stage_list in routes.items():
        if hostel_id not in allowed_keys:
            raise SimulationError(
                "unknown_reference",
                f"routes references unknown hostel {hostel_id!r}",
                field=f"scenario.routes.{hostel_id}",
            )
        if not isinstance(stage_list, list) or not stage_list:
            raise SimulationError(
                "missing_input",
                f"route for {hostel_id!r} needs a stage list",
                field=f"scenario.routes.{hostel_id}",
            )
        for stage_id in stage_list:
            if stage_id not in stage_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"route for {hostel_id!r} references unknown stage {stage_id!r}",
                    field=f"scenario.routes.{hostel_id}",
                )
    missing = sorted(hostel_ids - set(routes))
    if missing:
        raise SimulationError(
            "missing_input",
            f"missing required route for origin {missing[0]!r}",
            field=f"scenario.routes.{missing[0]}",
        )


def _validate_carpark_tiers(scenario_d: dict) -> None:
    carpark_tiers = scenario_d.get("destination", {}).get("carpark_tiers")
    if not carpark_tiers or not isinstance(carpark_tiers, Mapping):
        return
    cohort_counts: dict[str, int] = {}
    for u in scenario_d.get("source_units", []):
        cid = u.get("cohort_id")
        if cid:
            cohort_counts[cid] = cohort_counts.get(cid, 0) + int(u.get("resolved_attendance") or 0)
    for tier_id, tier in carpark_tiers.items():
        if not isinstance(tier, Mapping):
            continue
        max_cap = tier.get("max")
        if max_cap is not None:
            assigned = tier.get("assigned_cohorts") or []
            total = sum(cohort_counts.get(c, 0) for c in assigned)
            if total > max_cap:
                raise SimulationError(
                    "capacity_violation",
                    f"Carpark tier {tier_id!r} max capacity {max_cap} exceeded by assigned cohorts total {total}",
                    field=f"destination.carpark_tiers.{tier_id}.assigned_cohorts",
                )


def _require_load_dependent_fields(
    vehicles: list,
    vehicle_types: dict[str, dict],
    fleet_id: str | None,
    resource_id: str | None,
    fleets: list,
) -> None:
    fleet_vehicle_ids = None
    if fleet_id:
        for fleet in fleets:
            if fleet.get("id") == fleet_id:
                fleet_vehicle_ids = set(fleet.get("vehicle_ids") or [])
                break
    missing_types: list[str] = []
    seen_types: set[str] = set()
    for vehicle in vehicles:
        if resource_id and vehicle["id"] != resource_id:
            continue
        if fleet_vehicle_ids is not None and vehicle["id"] not in fleet_vehicle_ids:
            continue
        type_id = vehicle["type"]
        if type_id in seen_types:
            continue
        seen_types.add(type_id)
        vtype = vehicle_types.get(type_id)
        if vtype is None:
            missing_types.append(type_id)
    if missing_types:
        raise SimulationError(
            "missing_input",
            "load-dependent boarding needs door rules on each vehicle type; "
            f"missing types: {missing_types}",
            field="scenario.vehicle_types",
        )


def _validate_physical_assembly(
    grouping: Mapping,
    place_ids: set[str],
    initial: Mapping,
) -> None:
    physical = grouping.get("physical_assembly")
    if not physical:
        return
    place_id = physical.get("place_id")
    if place_id not in place_ids:
        raise SimulationError(
            "unknown_reference",
            f"physical assembly references unknown place {place_id!r}",
            field="policy.grouping.physical_assembly.place_id",
        )
    worker_count = physical.get("worker_count")
    workers = initial.get("workers") or []
    if not isinstance(workers, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "initial_state.workers must be a list",
            field="scenario.initial_state.workers",
        )
    if isinstance(worker_count, int) and worker_count > len(workers):
        raise SimulationError(
            "impossible_static_requirement",
            "physical assembly worker_count exceeds declared workers",
            field="policy.grouping.physical_assembly.worker_count",
        )


def _require_layout_for_basis(source_units: list, grouping: Mapping) -> None:
    basis = grouping.get("basis")
    overrides = grouping.get("scope_overrides") or {}
    mixed_default = grouping.get("mixed_default")
    for unit in source_units:
        unit_basis = overrides.get(unit["hostel_id"]) or overrides.get(unit.get("building_id"))
        if unit_basis is None:
            unit_basis = mixed_default if basis == "mixed" else basis
        if unit_basis in {"floor", "floor_wing"} and not unit.get("floor_id"):
            raise SimulationError(
                "missing_input",
                f"source unit {unit['id']!r} needs floor_id for {unit_basis} grouping",
                field=f"source_units.{unit['id']}.floor_id",
            )
        if unit_basis in {"wing", "floor_wing"} and not unit.get("wing_id"):
            raise SimulationError(
                "missing_input",
                f"source unit {unit['id']!r} needs wing_id for {unit_basis} grouping",
                field=f"source_units.{unit['id']}.wing_id",
            )
        if unit_basis == "building" and not unit.get("building_id"):
            raise SimulationError(
                "missing_input",
                f"source unit {unit['id']!r} needs building_id for building grouping",
                field=f"source_units.{unit['id']}.building_id",
            )
        if unit_basis not in GROUPING_BASES and unit_basis is not None:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported grouping basis {unit_basis!r}",
                field="policy.grouping.basis",
            )


def _validate_counting(
    scenario_d: dict,
    policy_d: dict,
    place_ids: set[str],
    stage_ids: set[str],
) -> None:
    operating = scenario_d["operating_rules"]
    required = list(operating.get("required_checkpoints") or [])
    permitted_locs = list(operating.get("permitted_counting_locations") or [])
    raw_checkpoints = scenario_d.get("checkpoints")
    if raw_checkpoints is None:
        raw_checkpoints = []
        scenario_d["checkpoints"] = raw_checkpoints
    if not isinstance(raw_checkpoints, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.checkpoints must be a list",
            field="scenario.checkpoints",
        )

    checkpoints: dict[str, dict] = {}
    for index, raw in enumerate(raw_checkpoints):
        checkpoint = _as_mapping(raw, f"scenario.checkpoints[{index}]")
        _require_keys(checkpoint, ("id", "location_id"), f"scenario.checkpoints[{index}]")
        if checkpoint["id"] in checkpoints:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate checkpoint id {checkpoint['id']!r}",
                field=f"scenario.checkpoints[{index}].id",
            )
        if checkpoint["location_id"] not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"checkpoint {checkpoint['id']!r} references unknown place {checkpoint['location_id']!r}",
                field=f"scenario.checkpoints[{index}].location_id",
            )
        methods = checkpoint.get("permitted_methods") or []
        if not isinstance(methods, list):
            raise SimulationError(
                "invalid_value_or_unit",
                "permitted_methods must be a list",
                field=f"scenario.checkpoints[{index}].permitted_methods",
            )
        for method in methods:
            if method not in COUNT_METHODS:
                raise SimulationError(
                    "unsupported_policy",
                    f"count method {method!r} is not in this model",
                    field=f"scenario.checkpoints[{index}].permitted_methods",
                )
        attach_id = checkpoint.get("attach_to_stage_id") or checkpoint.get("stage_id")
        if attach_id and attach_id not in stage_ids:
            raise SimulationError(
                "unknown_reference",
                f"checkpoint {checkpoint['id']!r} references unknown stage {attach_id!r}",
                field=f"scenario.checkpoints[{index}].stage_id",
            )
        raw_checkpoints[index] = checkpoint
        checkpoints[checkpoint["id"]] = checkpoint

    attached: set[str] = set()
    for stage in scenario_d["route_stages"]:
        if stage.get("checkpoint_id"):
            attached.add(stage["checkpoint_id"])
    for cid, checkpoint in checkpoints.items():
        attach_id = checkpoint.get("attach_to_stage_id") or checkpoint.get("stage_id")
        if attach_id and attach_id in stage_ids:
            attached.add(cid)

    for cid in required:
        if cid not in checkpoints:
            raise SimulationError(
                "unknown_reference",
                f"required checkpoint {cid!r} is not in scenario.checkpoints",
                field="scenario.operating_rules.required_checkpoints",
            )
        location_id = checkpoints[cid]["location_id"]
        if permitted_locs and location_id not in permitted_locs:
            raise SimulationError(
                "impossible_static_requirement",
                f"required checkpoint {cid!r} location {location_id!r} is not permitted",
                field="scenario.operating_rules.permitted_counting_locations",
            )
        if cid not in attached:
            raise SimulationError(
                "impossible_static_requirement",
                f"required checkpoint {cid!r} is not attached to a route stage",
                field="scenario.operating_rules.required_checkpoints",
            )

    if required and not permitted_locs:
        raise SimulationError(
            "impossible_static_requirement",
            "required checkpoints need permitted counting locations",
            field="scenario.operating_rules.permitted_counting_locations",
        )

    assumptions = scenario_d.get("count_error_assumptions")
    if assumptions is None:
        assumptions = []
        scenario_d["count_error_assumptions"] = assumptions
    if not isinstance(assumptions, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "count_error_assumptions must be a list",
            field="scenario.count_error_assumptions",
        )
    if required:
        if not assumptions:
            raise SimulationError(
                "missing_input",
                "count error assumptions must state an exposure unit",
                field="scenario.count_error_assumptions",
            )
        for index, raw in enumerate(assumptions):
            row = _as_mapping(raw, f"scenario.count_error_assumptions[{index}]")
            if not row.get("exposure_unit"):
                raise SimulationError(
                    "missing_input",
                    "error assumption needs exposure_unit (for example checkpoint_pass)",
                    field=f"scenario.count_error_assumptions[{index}].exposure_unit",
                )
            assumptions[index] = row

    policy_required = policy_d.get("required_checkpoints")
    counting = policy_d.get("counting")
    if counting is None:
        counting = {}
    elif not isinstance(counting, Mapping):
        raise SimulationError(
            "invalid_value_or_unit",
            "policy.counting must be an object",
            field="policy.counting",
        )
        counting = dict(counting)
    else:
        counting = dict(counting)

    if required:
        if policy_required == [] or counting.get("required_checkpoints") == []:
            raise SimulationError(
                "fixed_rule_violation",
                "policy cannot replace required checkpoints with an empty list",
                field="policy.counting.required_checkpoints",
            )
        if policy_required is not None:
            if set(required) - set(policy_required):
                raise SimulationError(
                    "fixed_rule_violation",
                    "policy cannot drop a required checkpoint",
                    field="policy.required_checkpoints",
                )
        copied = counting.get("required_checkpoints")
        if copied is not None and set(required) - set(copied):
            raise SimulationError(
                "fixed_rule_violation",
                "policy cannot drop a required checkpoint",
                field="policy.counting.required_checkpoints",
            )
        assignments = counting.get("assignments")
        if not assignments:
            raise SimulationError(
                "fixed_rule_violation",
                "policy cannot omit or empty required checkpoint assignments",
                field="policy.counting.assignments",
            )
        if not isinstance(assignments, Mapping):
            raise SimulationError(
                "invalid_value_or_unit",
                "policy.counting.assignments must be an object",
                field="policy.counting.assignments",
            )
        for cid in required:
            if cid not in assignments:
                raise SimulationError(
                    "fixed_rule_violation",
                    f"policy dropped required checkpoint {cid!r}",
                    field="policy.counting.assignments",
                )
        for cid, raw_asg in assignments.items():
            asg = _as_mapping(raw_asg, f"policy.counting.assignments.{cid}")
            if cid not in checkpoints:
                raise SimulationError(
                    "unknown_reference",
                    f"policy assignment references unknown checkpoint {cid!r}",
                    field=f"policy.counting.assignments.{cid}",
                )
            location_id = asg.get("location_id") or checkpoints[cid]["location_id"]
            if permitted_locs and location_id not in permitted_locs:
                raise SimulationError(
                    "fixed_rule_violation",
                    f"policy chose counting location {location_id!r} which is not permitted",
                    field=f"policy.counting.assignments.{cid}.location_id",
                )
            method = asg.get("method") or checkpoints[cid].get("permitted_methods", [None])[0]
            permitted_methods = checkpoints[cid].get("permitted_methods") or []
            if method and permitted_methods and method not in permitted_methods:
                raise SimulationError(
                    "fixed_rule_violation",
                    f"policy method {method!r} is not permitted for checkpoint {cid!r}",
                    field=f"policy.counting.assignments.{cid}.method",
                )
            if method and method not in COUNT_METHODS:
                raise SimulationError(
                    "unsupported_policy",
                    f"count method {method!r} is not in this model",
                    field=f"policy.counting.assignments.{cid}.method",
                )
    elif policy_required == [] or (isinstance(counting, Mapping) and counting.get("required_checkpoints") == []):
        # Empty copy of an empty requirement list is allowed.
        pass


WALKING_ROUTE_REQUIRED = (
    "hostel_id",
    "distance_m",
    "duration_s",
    "duration_range_s",
    "source",
    "method",
)

DESTINATION_REQUIRED = (
    "available_seats",
    "seating_rate_s_per_person",
    "doors",
    "exterior_storage_students",
    "foyer_storage_students",
    "initial_occupants",
    "reserved_seating",
)


def _validate_shared_resources(scenario_d: dict) -> None:
    raw = scenario_d.get("shared_resources")
    if raw is None:
        return
    if not isinstance(raw, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.shared_resources must be a list",
            field="scenario.shared_resources",
        )
    seen: set[str] = set()
    for index, item in enumerate(raw):
        resource = _as_mapping(item, f"scenario.shared_resources[{index}]")
        _require_keys(resource, ("id", "kind"), f"scenario.shared_resources[{index}]")
        if resource["id"] in seen:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate shared resource id {resource['id']!r}",
                field=f"scenario.shared_resources[{index}].id",
            )
        seen.add(resource["id"])
        if resource.get("capacity_students") is not None:
            _require_nonneg_int(
                resource["capacity_students"],
                f"scenario.shared_resources[{index}].capacity_students",
            )
        if resource.get("duration_s") is not None:
            _require_nonneg_number(
                resource["duration_s"],
                f"scenario.shared_resources[{index}].duration_s",
            )
        raw[index] = resource
    scenario_d["shared_resources"] = raw


def _validate_walking_routes(
    scenario_d: dict,
    hostel_ids: set[str],
    leg_ids: set[str],
) -> None:
    hostels = scenario_d.get("hostels") or []
    walk_ids = [
        hostel["id"]
        for hostel in hostels
        if isinstance(hostel, Mapping) and hostel.get("initial_route") == "walk"
    ]
    raw = scenario_d.get("walking_routes")
    if raw is None:
        if walk_ids:
            raise SimulationError(
                "missing_input",
                f"missing required walking route data for origin {walk_ids[0]!r}",
                field=f"scenario.walking_routes.{walk_ids[0]}",
            )
        return
    if not isinstance(raw, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.walking_routes must be a list",
            field="scenario.walking_routes",
        )
    by_hostel: set[str] = set()
    for index, item in enumerate(raw):
        route = _as_mapping(item, f"scenario.walking_routes[{index}]")
        _require_keys(route, WALKING_ROUTE_REQUIRED, f"scenario.walking_routes[{index}]")
        if route["hostel_id"] not in hostel_ids:
            raise SimulationError(
                "unknown_reference",
                f"walking route references unknown hostel {route['hostel_id']!r}",
                field=f"scenario.walking_routes[{index}].hostel_id",
            )
        _require_nonneg_number(
            route["distance_m"],
            f"scenario.walking_routes[{index}].distance_m",
        )
        _require_nonneg_number(
            route["duration_s"],
            f"scenario.walking_routes[{index}].duration_s",
        )
        span = route["duration_range_s"]
        if not isinstance(span, (list, tuple)) or len(span) != 2:
            raise SimulationError(
                "invalid_value_or_unit",
                "duration_range_s must be [lower, upper] seconds",
                field=f"scenario.walking_routes[{index}].duration_range_s",
            )
        _require_nonneg_number(span[0], f"scenario.walking_routes[{index}].duration_range_s[0]")
        _require_nonneg_number(span[1], f"scenario.walking_routes[{index}].duration_range_s[1]")
        if float(span[0]) > float(span[1]):
            raise SimulationError(
                "invalid_value_or_unit",
                "duration_range_s lower must not exceed upper",
                field=f"scenario.walking_routes[{index}].duration_range_s",
            )
        if route.get("mode") in {"drive", "driving"}:
            raise SimulationError(
                "unsupported_policy",
                "a driving route is not a walking route",
                field=f"scenario.walking_routes[{index}].mode",
            )
        for leg_id in route.get("leg_ids") or []:
            if leg_id not in leg_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"walking route references unknown leg {leg_id!r}",
                    field=f"scenario.walking_routes[{index}].leg_ids",
                )
        by_hostel.add(route["hostel_id"])
        raw[index] = route
    scenario_d["walking_routes"] = raw
    missing = [hostel_id for hostel_id in walk_ids if hostel_id not in by_hostel]
    if missing:
        raise SimulationError(
            "missing_input",
            f"missing required walking route data for origin {missing[0]!r}",
            field=f"scenario.walking_routes.{missing[0]}",
        )

    routes = scenario_d.get("routes") or {}
    stages = {stage["id"]: stage for stage in scenario_d.get("route_stages") or []}
    legs = {leg["id"]: leg for leg in scenario_d.get("route_legs") or []}
    for hostel in hostels:
        if not isinstance(hostel, Mapping):
            continue
        hostel_id = hostel.get("id")
        stage_list = routes.get(hostel_id) or []
        if hostel.get("initial_route") == "walk":
            for stage_id in stage_list:
                stage = stages.get(stage_id) or {}
                if stage.get("kind") not in {"travel", "vehicle_travel"}:
                    continue
                leg = legs.get(stage.get("leg_id")) or {}
                if leg.get("mode") in {"coach", "drive", "driving"}:
                    raise SimulationError(
                        "unsupported_policy",
                        f"walking origin {hostel_id!r} cannot use a driving or coach leg as its walk",
                        field=f"scenario.routes.{hostel_id}",
                    )


def _validate_destination(scenario_d: dict, place_ids: set[str]) -> None:
    raw = scenario_d.get("destination")
    if raw is None:
        return
    dest = _as_mapping(raw, "scenario.destination")
    _require_keys(dest, DESTINATION_REQUIRED, "scenario.destination")
    _require_nonneg_int(dest["available_seats"], "scenario.destination.available_seats")
    _require_nonneg_int(
        dest["exterior_storage_students"],
        "scenario.destination.exterior_storage_students",
    )
    _require_nonneg_int(
        dest["foyer_storage_students"],
        "scenario.destination.foyer_storage_students",
    )
    _require_nonneg_int(dest["initial_occupants"], "scenario.destination.initial_occupants")
    _require_nonneg_int(dest["reserved_seating"], "scenario.destination.reserved_seating")
    _require_nonneg_number(
        dest["seating_rate_s_per_person"],
        "scenario.destination.seating_rate_s_per_person",
    )
    if dest["initial_occupants"] + dest["reserved_seating"] > dest["available_seats"]:
        raise SimulationError(
            "invalid_value_or_unit",
            "initial occupants and reserved seating exceed available seats",
            field="scenario.destination.available_seats",
        )
    doors = dest["doors"]
    if not isinstance(doors, list) or not doors:
        raise SimulationError(
            "missing_input",
            "destination.doors must list at least one door",
            field="scenario.destination.doors",
        )
    door_ids: set[str] = set()
    for index, raw_door in enumerate(doors):
        door = _as_mapping(raw_door, f"scenario.destination.doors[{index}]")
        _require_keys(door, ("id", "place_id"), f"scenario.destination.doors[{index}]")
        if door["id"] in door_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate door id {door['id']!r}",
                field=f"scenario.destination.doors[{index}].id",
            )
        door_ids.add(door["id"])
        if door["place_id"] not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"door {door['id']!r} references unknown place {door['place_id']!r}",
                field=f"scenario.destination.doors[{index}].place_id",
            )
        doors[index] = door
    dest["doors"] = doors
    seating_place_id = dest.get("seating_place_id")
    if seating_place_id and seating_place_id not in place_ids:
        raise SimulationError(
            "unknown_reference",
            f"destination seating place {seating_place_id!r} is unknown",
            field="scenario.destination.seating_place_id",
        )
    scenario_d["destination"] = dest


def _validate_background_demand(scenario_d: dict) -> None:
    raw = scenario_d.get("background_demand")
    if raw is None:
        return
    demand = _as_mapping(raw, "scenario.background_demand")
    for key in ("pedestrians", "road_crossings", "other_arrivals"):
        if key not in demand or demand[key] is None:
            raise SimulationError(
                "missing_input",
                f"Missing critical input: scenario.background_demand.{key}",
                field=f"scenario.background_demand.{key}",
            )
        _require_nonneg_int(demand[key], f"scenario.background_demand.{key}")
    scenario_d["background_demand"] = demand


def _validate_workers(scenario_d: dict, policy_d: dict, place_ids: set[str]) -> None:
    initial = scenario_d["initial_state"]
    raw_workers = initial.get("workers") or []
    if not isinstance(raw_workers, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "initial_state.workers must be a list",
            field="scenario.initial_state.workers",
        )
    for index, raw in enumerate(raw_workers):
        worker = _as_mapping(raw, f"scenario.initial_state.workers[{index}]")
        if not worker.get("id"):
            raise SimulationError(
                "missing_input",
                "worker is missing id",
                field=f"scenario.initial_state.workers[{index}].id",
            )
        place_id = worker.get("place_id")
        if place_id and place_id not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"worker {worker['id']!r} references unknown place {place_id!r}",
                field=f"scenario.initial_state.workers[{index}].place_id",
            )
        if "available_time_s" in worker and worker["available_time_s"] is not None:
            _require_nonneg_number(
                worker["available_time_s"],
                f"scenario.initial_state.workers[{index}].available_time_s",
            )
        if "count" in worker and worker["count"] is not None:
            _require_nonneg_int(
                worker["count"],
                f"scenario.initial_state.workers[{index}].count",
            )
        raw_workers[index] = worker

    travel_rows: list = []
    operating = scenario_d["operating_rules"]
    for key in ("worker_travel", "worker_travel_s"):
        for source_name, source in (
            ("scenario", scenario_d),
            ("scenario.operating_rules", operating),
        ):
            raw = source.get(key)
            if raw is None:
                continue
            if not isinstance(raw, list):
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"{key} must be a list",
                    field=f"{source_name}.{key}",
                )
            travel_rows.extend((source_name, key, index, row) for index, row in enumerate(raw))
    for source_name, key, index, raw_row in travel_rows:
        row = _as_mapping(raw_row, f"{source_name}.{key}[{index}]")
        for place_field in ("from_place_id", "to_place_id"):
            place_id = row.get(place_field)
            if place_id and place_id not in place_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"{key} references unknown place {place_id!r}",
                    field=f"{source_name}.{key}[{index}].{place_field}",
                )

    for field, message in staffing_floor_violations(scenario_d, policy_d):
        raise SimulationError("fixed_rule_violation", message, field=field)


def _validate_space_policy(policy_d: dict) -> None:
    rule = policy_d.get("destination_space_rule")
    if rule is not None and rule not in DESTINATION_SPACE_RULES:
        raise SimulationError(
            "unsupported_policy",
            f"unsupported destination_space_rule {rule!r}",
            field="policy.destination_space_rule",
        )
    control = policy_d.get("space_control")
    needs_delay = rule is not None or control not in (None, {})
    if needs_delay:
        if policy_d.get("coordination_delay_s") is None:
            raise SimulationError(
                "missing_input",
                "coordination_delay_s is required when a space rule is set, including 0",
                field="policy.coordination_delay_s",
            )
        _require_nonneg_number(
            policy_d["coordination_delay_s"], "policy.coordination_delay_s"
        )
    if control is None:
        return
    control_d = _as_mapping(control, "policy.space_control")
    hold = control_d.get("hold_threshold_students")
    resume = control_d.get("resume_threshold_students")
    if hold is not None:
        _require_nonneg_int(hold, "policy.space_control.hold_threshold_students")
    if resume is not None:
        _require_nonneg_int(resume, "policy.space_control.resume_threshold_students")
        if hold is not None and int(resume) > int(hold):
            raise SimulationError(
                "invalid_value_or_unit",
                "resume threshold cannot exceed hold threshold",
                field="policy.space_control.resume_threshold_students",
            )
    if control_d.get("min_hold_duration_s") is not None:
        _require_nonneg_number(
            control_d["min_hold_duration_s"],
            "policy.space_control.min_hold_duration_s",
        )
    policy_d["space_control"] = control_d


def _validate_reporting(scenario_d: dict, policy_d: dict) -> None:
    operating = dict(scenario_d.get("operating_rules") or {})
    if operating.get("event_start_s") is not None:
        _require_nonneg_number(operating["event_start_s"], "operating_rules.event_start_s")
    if scenario_d.get("event_start_s") is not None:
        _require_nonneg_number(scenario_d["event_start_s"], "scenario.event_start_s")
    window = operating.get("reporting_window") or policy_d.get("reporting_window")
    window_d = dict(window) if isinstance(window, Mapping) else None
    if window_d is not None:
        _require_nonneg_number(window_d.get("earliest_s") or 0, "reporting_window.earliest_s")
        _require_nonneg_number(window_d.get("latest_s") or 0, "reporting_window.latest_s")
        if float(window_d.get("latest_s") or 0) < float(window_d.get("earliest_s") or 0):
            raise SimulationError(
                "invalid_value_or_unit",
                "reporting_window.latest_s cannot be before earliest_s",
                field="scenario.operating_rules.reporting_window.latest_s",
            )
    choice = policy_d.get("reporting_time_s")
    nested = policy_d.get("reporting") or {}
    if choice is None and isinstance(nested, Mapping):
        choice = nested.get("required_reporting_s") or nested.get("reporting_time_s")
    if choice is not None:
        _require_nonneg_number(choice, "policy.reporting_time_s")
        if window_d is not None:
            earliest = float(window_d.get("earliest_s") or 0)
            latest = float(window_d.get("latest_s") or 0)
            if float(choice) < earliest or float(choice) > latest:
                raise SimulationError(
                    "invalid_value_or_unit",
                    "reporting_time_s is outside the allowed reporting window",
                    field="policy.reporting_time_s",
                )


def _validate_external_conditions(
    scenario_d: dict, place_ids: set[str], leg_ids: set[str]
) -> None:
    raw = scenario_d.get("external_conditions")
    if raw is None:
        return
    if not isinstance(raw, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.external_conditions must be a list",
            field="scenario.external_conditions",
        )
    for index, item in enumerate(raw):
        row = _as_mapping(item, f"scenario.external_conditions[{index}]")
        _require_keys(row, ("id", "kind", "at_s"), f"scenario.external_conditions[{index}]")
        if row["kind"] not in CONDITION_KINDS:
            raise SimulationError(
                "invalid_value_or_unit",
                f"unsupported condition kind {row['kind']!r}",
                field=f"scenario.external_conditions[{index}].kind",
            )
        _require_nonneg_number(row["at_s"], f"scenario.external_conditions[{index}].at_s")
        for leg_id in row.get("affects_leg_ids") or []:
            if leg_id not in leg_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"condition {row['id']!r} references unknown leg {leg_id!r}",
                    field=f"scenario.external_conditions[{index}].affects_leg_ids",
                )
        raw[index] = row
    scenario_d["external_conditions"] = raw

