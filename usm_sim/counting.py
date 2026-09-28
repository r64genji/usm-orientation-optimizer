"""Manual checks: pass-through and column counting, records, and fixtures.

Forming a group or an internal calculation part does not create a count.
A checkpoint pass is one exposure. Recounts are extra passes with retry limits.
"""

from __future__ import annotations

import importlib.util
import math
from typing import Any, Iterable, Mapping

from usm_sim.constants import COUNT_METHODS, FORMAT_VERSION, TIMEZONE_NAME


COUNT_ACTION_EVENTS = frozenset(
    {
        "count_start",
        "count_complete",
        "recount_start",
        "recount_complete",
    }
)


def grouping_module():
    """Return usm_sim.grouping if ticket 02 landed in this tree, else None."""
    if importlib.util.find_spec("usm_sim.grouping") is None:
        return None
    return importlib.import_module("usm_sim.grouping")


def bound_parallel_columns(
    *,
    student_count: int,
    requested_columns: int,
    space_columns: int,
    available_workers: int,
    workers_per_column: int,
) -> int:
    """Space and workers cap parallel columns. Unlimited columns are not instant."""
    if student_count <= 0:
        return 0
    requested = max(1, int(requested_columns))
    space = max(0, int(space_columns))
    workers = max(0, int(available_workers))
    per_col = max(1, int(workers_per_column))
    worker_cols = workers // per_col
    n = min(requested, student_count)
    if space > 0:
        n = min(n, space)
    if worker_cols > 0:
        n = min(n, worker_cols)
    return max(1, n)


def column_count_duration_s(
    *,
    student_count: int,
    setup_s: float,
    cadence_s_per_person: float,
    aggregation_s: float,
    requested_columns: int,
    space_columns: int,
    available_workers: int,
    workers_per_column: int,
) -> dict[str, float | int]:
    """Setup + longest-column cadence + aggregation. Never zero from extra columns."""
    n_columns = bound_parallel_columns(
        student_count=student_count,
        requested_columns=requested_columns,
        space_columns=space_columns,
        available_workers=available_workers,
        workers_per_column=workers_per_column,
    )
    if student_count <= 0 or n_columns <= 0:
        return {
            "duration_s": 0.0,
            "n_columns": 0,
            "longest_column": 0,
            "workers_required": 0,
        }
    longest = int(math.ceil(student_count / n_columns))
    duration_s = float(setup_s) + float(longest) * float(cadence_s_per_person) + float(aggregation_s)
    if duration_s <= 0:
        # Cadence, setup, and aggregation may all be zero in a degenerate input.
        # Unlimited columns still cannot collapse a real count to "no time"
        # when at least one student is present: keep a one-cadence floor only
        # when the caller asked for a positive cadence. Otherwise honour zeros.
        duration_s = float(setup_s) + float(cadence_s_per_person) + float(aggregation_s)
    workers_required = n_columns * max(1, int(workers_per_column))
    return {
        "duration_s": duration_s,
        "n_columns": n_columns,
        "longest_column": longest,
        "workers_required": workers_required,
    }


def passthrough_person_duration_s(
    flow_s_per_person: float, count_rate_s_per_person: float
) -> float:
    """Apply the slower of flow and count to the same serial service, once."""
    return max(float(flow_s_per_person), float(count_rate_s_per_person))


def passthrough_batch_duration_s(
    flow_total_s: float, student_count: int, count_rate_s_per_person: float
) -> float:
    """Batch boarding/alighting: count rate may stretch the same service, not add another."""
    count_total = float(count_rate_s_per_person) * max(0, int(student_count))
    return max(float(flow_total_s), count_total)


def draw_observed_count(
    rng,
    expected: int,
    assumption: Mapping[str, Any] | None,
    attempt_index: int,
    *,
    student_count: int | None = None,
) -> tuple[int, bool]:
    """One draw per real checkpoint pass (attempt_index 0 is the first pass)."""
    assumed = dict(assumption or {})
    schedule = assumed.get("mismatch_schedule")
    if schedule is not None:
        if not schedule:
            mismatch = False
        elif attempt_index < len(schedule):
            mismatch = bool(schedule[attempt_index])
        else:
            mismatch = bool(schedule[-1])
    else:
        p = float(assumed.get("p_mismatch") or 0.0)
        rel = assumed.get("relationship_to_load")
        if rel and rel not in {"none", None, "independent"}:
            if rel == "linear_with_load" and student_count is not None:
                ref = float(assumed.get("load_ref_students") or 1)
                p = p * (float(student_count) / ref)
        mismatch = bool(rng.random() < p) if p > 0 else False
    if not mismatch:
        return int(expected), False
    delta = int(assumed.get("observed_delta") or 1)
    return int(expected) + delta, True


def split_preserve_links(part: Mapping[str, Any], child_ids: Iterable[str]) -> list[dict]:
    """Split a movement part. Prior count records and checkpoint coverage stay on each child."""
    links = list(part.get("count_record_ids") or [])
    coverage = list(part.get("covered_checkpoint_ids") or [])
    children: list[dict] = []
    for child_id in child_ids:
        child = dict(part)
        child["part_id"] = child_id
        child["parent_part_id"] = part.get("part_id")
        child["count_record_ids"] = list(links)
        child["covered_checkpoint_ids"] = list(coverage)
        children.append(child)
    return children


def join_preserve_links(parts: Iterable[Mapping[str, Any]]) -> dict:
    """Join parts. Union of count-record links and required coverage is kept."""
    part_list = [dict(p) for p in parts]
    if not part_list:
        return {"count_record_ids": [], "covered_checkpoint_ids": [], "student_count": 0}
    ids: list[str] = []
    coverage: list[str] = []
    source_units: list[str] = []
    for part in part_list:
        for record_id in part.get("count_record_ids") or []:
            if record_id not in ids:
                ids.append(record_id)
        for checkpoint_id in part.get("covered_checkpoint_ids") or []:
            if checkpoint_id not in coverage:
                coverage.append(checkpoint_id)
        unit = part.get("source_unit_id")
        if unit and unit not in source_units:
            source_units.append(unit)
    joined = dict(part_list[0])
    parent = part_list[0].get("parent_part_id") or part_list[0].get("part_id")
    joined["part_id"] = parent
    joined["parent_part_id"] = None
    joined["count_record_ids"] = ids
    joined["covered_checkpoint_ids"] = coverage
    joined["student_count"] = sum(int(p.get("student_count") or 0) for p in part_list)
    if source_units:
        joined["source_unit_ids"] = source_units
    return joined


def coverage_report(required_ids: Iterable[str], records: Iterable[Mapping[str, Any]]) -> dict:
    required = list(required_ids)
    performed = {row["checkpoint_id"] for row in records if row.get("checkpoint_id")}
    agreed = {
        row["checkpoint_id"]
        for row in records
        if row.get("outcome") in {"agreed", "attendance_gap"}
    }
    unresolved = {
        row["checkpoint_id"]
        for row in records
        if row.get("outcome") == "unresolved"
    }
    return {
        "required": required,
        "satisfied": [cid for cid in required if cid in agreed],
        "missing": [cid for cid in required if cid not in performed],
        "unresolved": [cid for cid in required if cid in unresolved],
        "performed": [cid for cid in required if cid in performed],
    }


def checkpoint_applies_to_part(
    checkpoint: Mapping[str, Any],
    part: Any,
    scenario: Mapping[str, Any],
) -> bool:
    required_for = list(checkpoint.get("required_for") or [])
    if not required_for:
        return True
    hostel_id = getattr(part, "hostel_id", None)
    if isinstance(part, Mapping):
        hostel_id = part.get("hostel_id") or hostel_id
    operating = scenario.get("operating_rules") or {}
    route_class = operating.get("route_class")
    source_unit_id = getattr(part, "source_unit_id", None)
    if isinstance(part, Mapping):
        source_unit_id = part.get("source_unit_id") or source_unit_id
    tokens = {str(item) for item in required_for}
    return any(
        token in tokens
        for token in (hostel_id, route_class, source_unit_id)
        if token
    )


def required_checkpoints_for_part(
    scenario: Mapping[str, Any],
    part: Any,
) -> list[str]:
    required = required_checkpoint_ids(scenario)
    checkpoints = {
        row["id"]: row for row in scenario.get("checkpoints") or [] if row.get("id")
    }
    applicable: list[str] = []
    for checkpoint_id in required:
        checkpoint = checkpoints.get(checkpoint_id) or {"id": checkpoint_id}
        if checkpoint_applies_to_part(checkpoint, part, scenario):
            applicable.append(checkpoint_id)
    return applicable


def accumulate_group_counts(records: Iterable[Mapping[str, Any]]) -> list[dict]:
    """Sum expected/observed over physical parts, still keyed by parent group."""
    grouped: dict[str, dict] = {}
    for row in records:
        group_id = row.get("group_id") or ""
        bucket = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "count_record_ids": [],
                "source_unit_ids": [],
                "accumulated_expected": 0,
                "accumulated_observed": 0,
                "checkpoint_ids": [],
            },
        )
        record_id = row.get("count_record_id") or row.get("id")
        if record_id and record_id not in bucket["count_record_ids"]:
            bucket["count_record_ids"].append(record_id)
            if row.get("attempt", 1) == 1:
                bucket["accumulated_expected"] += int(row.get("expected_count") or 0)
                bucket["accumulated_observed"] += int(row.get("observed_count") or 0)
        for unit in row.get("source_unit_ids") or []:
            if unit not in bucket["source_unit_ids"]:
                bucket["source_unit_ids"].append(unit)
        checkpoint_id = row.get("checkpoint_id")
        if checkpoint_id and checkpoint_id not in bucket["checkpoint_ids"]:
            bucket["checkpoint_ids"].append(checkpoint_id)
    return [grouped[key] for key in sorted(grouped)]


def count_action_events(trace: Iterable[Mapping[str, Any]]) -> list[dict]:
    return [dict(event) for event in trace if event.get("event_type") in COUNT_ACTION_EVENTS]


def required_checkpoint_ids(scenario: Mapping[str, Any]) -> list[str]:
    rules = scenario.get("operating_rules") or {}
    return list(rules.get("required_checkpoints") or [])


def permitted_counting_locations(scenario: Mapping[str, Any]) -> list[str]:
    rules = scenario.get("operating_rules") or {}
    return list(rules.get("permitted_counting_locations") or [])


def assignment_for(checkpoint: Mapping[str, Any], policy: Mapping[str, Any]) -> dict:
    counting = policy.get("counting") or {}
    assignments = counting.get("assignments") or {}
    raw = assignments.get(checkpoint["id"]) or {}
    return dict(raw)


def checkpoints_attached_to_stage(scenario: Mapping[str, Any], stage_id: str) -> list[dict]:
    found = []
    for raw in scenario.get("checkpoints") or []:
        if raw.get("attach_to_stage_id") == stage_id or raw.get("stage_id") == stage_id:
            found.append(dict(raw))
    return found


def reconciliation_status(required_ids: Iterable[str], records: Iterable[Mapping[str, Any]]) -> str:
    required = list(required_ids)
    rows = list(records)
    if not required and not rows:
        return "not_required"
    if any(row.get("outcome") == "unresolved" for row in rows):
        return "unresolved"
    report = coverage_report(required, rows)
    if report["missing"]:
        return "incomplete"
    return "agreed"


# --- group formation from explicit source units (no count actions) ---

SPEC_LAYOUT_UNITS = [
    {"id": "f1_east", "floor": 1, "wing": "east", "n": 20},
    {"id": "f1_west", "floor": 1, "wing": "west", "n": 20},
    {"id": "f2_east", "floor": 2, "wing": "east", "n": 20},
    {"id": "f2_west", "floor": 2, "wing": "west", "n": 20},
    {"id": "f3_east", "floor": 3, "wing": "east", "n": 20},
    {"id": "f3_west", "floor": 3, "wing": "west", "n": 20},
]


def source_units_from_layout(
    layout: Iterable[Mapping[str, Any]] | None = None,
    *,
    hostel_id: str = "synthetic",
) -> list[dict]:
    units = []
    for raw in layout or SPEC_LAYOUT_UNITS:
        n = int(raw["n"])
        units.append(
            {
                "id": raw["id"],
                "hostel_id": hostel_id,
                "floor": raw["floor"],
                "wing": raw["wing"],
                "estimated_occupancy": n,
                "estimated_attendance": n,
                "resolved_attendance": n,
                "actual_reporting_s": 0,
                "readiness_s": 0,
                "layout_link": "estimated_floor_wing",
                "layout_estimated": True,
            }
        )
    return units


def _members_for_unit(unit_id: str, n: int) -> list[dict]:
    return [
        {"student_key": f"{unit_id}_{index:04d}", "queue_tie_key": f"{unit_id}_{index:04d}"}
        for index in range(n)
    ]


def groups_from_source_units(
    source_units: Iterable[Mapping[str, Any]],
    basis: str,
    *,
    hostel_id: str = "synthetic",
) -> list[dict]:
    """Build operational groups from disjoint source units.

    Creating these groups adds no count action, worker interval, or setup time.
    """
    buckets: dict[str, list[Mapping[str, Any]]] = {}
    for unit in source_units:
        if basis == "floor":
            key = f"floor_{unit['floor']}"
        elif basis == "wing":
            key = f"wing_{unit['wing']}"
        elif basis in {"floor_wing", "floor-and-wing"}:
            key = f"fw_{unit['floor']}_{unit['wing']}"
        elif basis == "hostel":
            key = f"hostel_{unit.get('hostel_id') or hostel_id}"
        else:
            raise ValueError(f"unsupported grouping basis {basis!r}")
        buckets.setdefault(key, []).append(unit)

    parts: list[dict] = []
    for group_id, units in buckets.items():
        members: list[dict] = []
        source_ids: list[str] = []
        occupancy = 0
        attendance = 0
        for unit in units:
            n = int(unit["resolved_attendance"])
            members.extend(_members_for_unit(unit["id"], n))
            source_ids.append(unit["id"])
            occupancy += int(unit.get("estimated_occupancy") or unit.get("estimated_attendance") or n)
            attendance += n
        lead = units[0]
        parts.append(
            {
                "part_id": f"part_{group_id}",
                "group_id": f"g_{group_id}",
                "source_unit_id": lead["id"],
                "source_unit_ids": source_ids,
                "place_id": "origin",
                "hostel_id": lead.get("hostel_id") or hostel_id,
                "hostel_composition": {lead.get("hostel_id") or hostel_id: len(members)},
                "members": members,
                "student_count": len(members),
                "estimated_occupancy": occupancy,
                "actual_attendance": attendance,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
                "grouping_basis": basis,
            }
        )
    parts.sort(key=lambda row: row["group_id"])
    return parts


# --- scenario shells for ticket 03 fixtures ---


def _record(field: str, value, unit: str, category: str = "assumed") -> dict:
    return {
        "field": field,
        "value": value,
        "unit": unit,
        "date": "2026-01-01",
        "method": "ticket-03 counting fixture",
        "confidence": "high",
        "observation_ref": "spec.md#13-manual-checks",
        "category": category,
    }


def _unbounded(place_id: str, lat: float, lon: float, meaning: str) -> dict:
    return {
        "id": place_id,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "meaning": meaning,
        "capacity_constraint": "unbounded",
        "capacity_note": "explicit unbounded counting fixture",
        "capacity_from_gps_scatter": False,
    }


def _workers(n: int, place_id: str, prefix: str = "counter") -> list[dict]:
    return [
        {
            "id": f"{prefix}_{index}",
            "role": "count",
            "place_id": place_id,
            "available_time_s": 0,
        }
        for index in range(n)
    ]


def _error_assumption(
    *,
    p_mismatch: float = 0.0,
    observed_delta: int = 1,
    mismatch_schedule: list[bool] | None = None,
    relationship_to_load: str = "none",
) -> dict:
    row = {
        "id": "visual_checkpoint_pass",
        "exposure_unit": "checkpoint_pass",
        "relationship_to_load": relationship_to_load,
        "p_mismatch": p_mismatch,
        "observed_delta": observed_delta,
    }
    if mismatch_schedule is not None:
        row["mismatch_schedule"] = list(mismatch_schedule)
    return row


def _policy(policy_id: str, required_endpoint: str, counting: dict, seed: int = 0) -> dict:
    return {
        "policy_id": policy_id,
        "policy_version": "1",
        "grouping": {"mode": "explicit_parts"},
        "required_endpoint": required_endpoint,
        "release_rule": {"type": "immediate"},
        "vehicle_dispatch_rule": {"type": "none"},
        "destination_rule": {"type": "service_then_complete"},
        "random_seed": seed,
        "counting": counting,
    }


def _shell(
    *,
    scenario_id: str,
    data_version: str,
    deadline_s: float,
    source_units: list[dict],
    places: list[dict],
    legs: list[dict],
    stages: list[dict],
    students: list[dict],
    workers: list[dict],
    vehicles: list[dict],
    operating_rules: dict,
    checkpoints: list[dict],
    error_assumptions: list[dict],
    source_records: list[dict],
    policy_id: str,
    policy_counting: dict,
    seed: int = 0,
    extra_scenario: dict | None = None,
) -> tuple[dict, dict]:
    endpoint = operating_rules["required_endpoint"]
    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": data_version,
        "scenario_id": scenario_id,
        "uncertainty_case_id": f"{scenario_id}_base",
        "event_date": "2026-01-01",
        "start_time_local": "00:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": deadline_s,
        "simulation_end_s": 10000,
        "max_events_per_run": 100000,
        "source_units": source_units,
        "places": places,
        "route_legs": legs,
        "route_stages": stages,
        "calendars": [],
        "initial_state": {
            "students": students,
            "queues": [],
            "workers": workers,
            "vehicles": vehicles,
            "hall_occupancy_students": 0,
        },
        "operating_rules": operating_rules,
        "checkpoints": checkpoints,
        "count_error_assumptions": error_assumptions,
        "measured_facts": [],
        "uncertain_assumptions": [
            {
                "id": "counting_fixture",
                "category": "assumed",
                "note": "ticket 03 controlled counting case",
            }
        ],
        "decisions": [
            {
                "id": "count_method",
                "category": "decision",
                "note": "policy chooses among permitted methods only",
            }
        ],
        "source_records": source_records,
        "accuracy_references": [],
    }
    if extra_scenario:
        scenario.update(extra_scenario)
    policy = _policy(policy_id, endpoint, policy_counting, seed=seed)
    return scenario, policy


def build_walking_checkpoint_case() -> tuple[dict, dict]:
    """Ticket-01-style walk with a required origin column count."""
    members = [
        {"student_key": "s1", "queue_tie_key": "00"},
        {"student_key": "s2", "queue_tie_key": "01"},
        {"student_key": "s3", "queue_tie_key": "02"},
        {"student_key": "s4", "queue_tie_key": "03"},
    ]
    checkpoint = {
        "id": "cp_origin",
        "location_id": "origin",
        "required": True,
        "required_for": ["walk"],
        "permitted_methods": ["column"],
        "stage_id": "origin_count",
        "max_retries": 0,
        "column": {
            "setup_s": 2,
            "cadence_s_per_person": 1,
            "aggregation_s": 1,
            "space_columns": 2,
            "workers_per_column": 1,
            "requested_columns": 4,
        },
    }
    return _shell(
        scenario_id="walk_required_count_v1",
        data_version="ticket-03-walk-v1",
        deadline_s=200,
        source_units=[
            {
                "id": "su_origin",
                "hostel_id": "synthetic",
                "estimated_occupancy": 4,
                "estimated_attendance": 4,
                "resolved_attendance": 4,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            }
        ],
        places=[
            _unbounded("origin", 0.0, 0.0, "walk origin"),
            _unbounded("dest", 0.001, 0.0, "walk destination"),
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
                "id": "origin_count",
                "kind": "manual_count",
                "place_id": "origin",
                "checkpoint_id": "cp_origin",
                "method": "column",
            },
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
        ],
        students=[
            {
                "part_id": "part_walk",
                "group_id": "g_walk",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 4},
                "members": members,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            }
        ],
        workers=_workers(4, "origin"),
        vehicles=[],
        operating_rules={
            "required_endpoint": "stage_complete",
            "route_class": "walk",
            "required_checkpoints": ["cp_origin"],
            "permitted_counting_locations": ["origin"],
            "permitted_count_methods": ["column"],
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "facial_recognition": False,
            "seating_modeled": False,
        },
        checkpoints=[checkpoint],
        error_assumptions=[_error_assumption()],
        source_records=[
            _record("checkpoints.cp_origin", "origin", "location", "decision"),
            _record("route_legs.walk_1.duration_s", 10, "s"),
        ],
        policy_id="walk_column_v1",
        policy_counting={
            "required_checkpoints": ["cp_origin"],
            "assignments": {
                "cp_origin": {
                    "location_id": "origin",
                    "method": "column",
                    "requested_columns": 4,
                }
            },
        },
    )


def build_bus_checkpoint_case(
    *,
    count_rate_s_per_person: float = 1.0,
    board_duration_s: float = 10.0,
    student_count: int = 10,
) -> tuple[dict, dict]:
    """One-bus chain with pass-through counting on boarding."""
    members = [
        {"student_key": f"b{index:02d}", "queue_tie_key": f"{index:02d}"}
        for index in range(student_count)
    ]
    checkpoint = {
        "id": "cp_board",
        "location_id": "boarding",
        "required": True,
        "required_for": ["bus"],
        "permitted_methods": ["pass_through"],
        "attach_to_stage_id": "boarding",
        "max_retries": 0,
        "pass_through": {
            "count_rate_s_per_person": count_rate_s_per_person,
            "workers_required": 1,
        },
    }
    return _shell(
        scenario_id="bus_required_count_v1",
        data_version="ticket-03-bus-v1",
        deadline_s=500,
        source_units=[
            {
                "id": "su_bus",
                "hostel_id": "synthetic",
                "estimated_occupancy": student_count,
                "estimated_attendance": student_count,
                "resolved_attendance": student_count,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            }
        ],
        places=[
            _unbounded("origin", 0.0, 0.0, "bus origin"),
            _unbounded("boarding", 0.001, 0.0, "boarding berth"),
            _unbounded("dest", 0.002, 0.0, "alighting"),
        ],
        legs=[
            {
                "id": "to_berth",
                "from_place_id": "origin",
                "to_place_id": "boarding",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "bus_ride",
                "from_place_id": "boarding",
                "to_place_id": "dest",
                "duration_s": 20,
                "mode": "coach",
                "shared_resource_ids": ["bus_1"],
            },
        ],
        stages=[
            {
                "id": "wait_bus",
                "kind": "hold",
                "place_id": "origin",
                "until": {"resource_available": "bus_1"},
            },
            {"id": "to_berth", "kind": "travel", "leg_id": "to_berth"},
            {
                "id": "boarding",
                "kind": "batch_service",
                "place_id": "boarding",
                "resource_id": "bus_1",
                "action": "board",
                "duration_s": board_duration_s,
            },
            {
                "id": "ride",
                "kind": "vehicle_travel",
                "leg_id": "bus_ride",
                "resource_id": "bus_1",
            },
            {
                "id": "alighting",
                "kind": "batch_service",
                "place_id": "dest",
                "resource_id": "bus_1",
                "action": "alight",
                "duration_s": 5,
            },
        ],
        students=[
            {
                "part_id": "part_bus",
                "group_id": "g_bus",
                "source_unit_id": "su_bus",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": student_count},
                "members": members,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            }
        ],
        workers=_workers(2, "boarding"),
        vehicles=[
            {
                "id": "bus_1",
                "type": "coach",
                "place_id": "boarding",
                "available_time_s": 0,
                "capacity_students": 80,
            }
        ],
        operating_rules={
            "required_endpoint": "stage_complete",
            "route_class": "bus",
            "required_checkpoints": ["cp_board"],
            "permitted_counting_locations": ["boarding"],
            "permitted_count_methods": ["pass_through"],
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "facial_recognition": False,
            "seating_modeled": False,
        },
        checkpoints=[checkpoint],
        error_assumptions=[_error_assumption()],
        source_records=[
            _record("checkpoints.cp_board", "boarding", "location", "decision"),
            _record("route_stages.boarding.duration_s", board_duration_s, "s"),
        ],
        policy_id="bus_passthrough_v1",
        policy_counting={
            "required_checkpoints": ["cp_board"],
            "assignments": {
                "cp_board": {
                    "location_id": "boarding",
                    "method": "pass_through",
                }
            },
        },
    )


def build_passthrough_queue_case(
    *,
    count_rate_s_per_person: float,
    service_duration_s: float = 10.0,
    student_count: int = 4,
) -> tuple[dict, dict]:
    """Serial entrance with pass-through counting on the same service."""
    members = [
        {"student_key": f"s{index+1}", "queue_tie_key": f"{index:02d}"}
        for index in range(student_count)
    ]
    checkpoint = {
        "id": "cp_entrance",
        "location_id": "entrance",
        "required": True,
        "required_for": ["walk"],
        "permitted_methods": ["pass_through"],
        "attach_to_stage_id": "entrance_service",
        "max_retries": 0,
        "pass_through": {
            "count_rate_s_per_person": count_rate_s_per_person,
            "workers_required": 1,
        },
    }
    return _shell(
        scenario_id="passthrough_queue_v1",
        data_version="ticket-03-passthrough-queue-v1",
        deadline_s=95,
        source_units=[
            {
                "id": "su_origin",
                "hostel_id": "synthetic",
                "estimated_occupancy": student_count,
                "estimated_attendance": student_count,
                "resolved_attendance": student_count,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            }
        ],
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("entrance", 0.001, 0.0, "serial entrance"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "entrance",
                "duration_s": 60,
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
                "service_duration_s": service_duration_s,
                "server_count": 1,
                "queue_discipline": "fcfs",
            },
        ],
        students=[
            {
                "part_id": "part_origin",
                "group_id": "g_walk",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": student_count},
                "members": members,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            }
        ],
        workers=_workers(2, "entrance"),
        vehicles=[],
        operating_rules={
            "required_endpoint": "service_complete",
            "route_class": "walk",
            "required_checkpoints": ["cp_entrance"],
            "permitted_counting_locations": ["entrance"],
            "permitted_count_methods": ["pass_through"],
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "facial_recognition": False,
            "seating_modeled": False,
        },
        checkpoints=[checkpoint],
        error_assumptions=[_error_assumption()],
        source_records=[
            _record("checkpoints.cp_entrance", "entrance", "location", "decision"),
            _record("route_stages.entrance_service.service_duration_s", service_duration_s, "s"),
        ],
        policy_id="passthrough_queue_v1",
        policy_counting={
            "required_checkpoints": ["cp_entrance"],
            "assignments": {
                "cp_entrance": {
                    "location_id": "entrance",
                    "method": "pass_through",
                }
            },
        },
    )


def build_column_space_case(
    *,
    student_count: int = 20,
    requested_columns: int = 100,
    space_columns: int = 2,
    worker_count: int = 8,
    workers_per_column: int = 1,
    setup_s: float = 5,
    cadence_s_per_person: float = 1,
    aggregation_s: float = 5,
) -> tuple[dict, dict]:
    members = [
        {"student_key": f"c{index:02d}", "queue_tie_key": f"{index:02d}"}
        for index in range(student_count)
    ]
    checkpoint = {
        "id": "cp_column",
        "location_id": "yard",
        "required": True,
        "required_for": ["walk"],
        "permitted_methods": ["column"],
        "stage_id": "yard_count",
        "max_retries": 0,
        "column": {
            "setup_s": setup_s,
            "cadence_s_per_person": cadence_s_per_person,
            "aggregation_s": aggregation_s,
            "space_columns": space_columns,
            "workers_per_column": workers_per_column,
            "requested_columns": requested_columns,
        },
    }
    return _shell(
        scenario_id="column_space_v1",
        data_version="ticket-03-column-v1",
        deadline_s=500,
        source_units=[
            {
                "id": "su_yard",
                "hostel_id": "synthetic",
                "estimated_occupancy": student_count,
                "estimated_attendance": student_count,
                "resolved_attendance": student_count,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            }
        ],
        places=[_unbounded("yard", 0.0, 0.0, "column yard")],
        legs=[
            {
                "id": "stay",
                "from_place_id": "yard",
                "to_place_id": "yard",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {
                "id": "yard_count",
                "kind": "manual_count",
                "place_id": "yard",
                "checkpoint_id": "cp_column",
                "method": "column",
            },
            {"id": "leave", "kind": "travel", "leg_id": "stay"},
        ],
        students=[
            {
                "part_id": "part_yard",
                "group_id": "g_yard",
                "source_unit_id": "su_yard",
                "place_id": "yard",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": student_count},
                "members": members,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            }
        ],
        workers=_workers(worker_count, "yard"),
        vehicles=[],
        operating_rules={
            "required_endpoint": "stage_complete",
            "route_class": "walk",
            "required_checkpoints": ["cp_column"],
            "permitted_counting_locations": ["yard"],
            "permitted_count_methods": ["column"],
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "facial_recognition": False,
            "seating_modeled": False,
        },
        checkpoints=[checkpoint],
        error_assumptions=[_error_assumption()],
        source_records=[_record("checkpoints.cp_column", "yard", "location", "decision")],
        policy_id="column_space_v1",
        policy_counting={
            "required_checkpoints": ["cp_column"],
            "assignments": {
                "cp_column": {
                    "location_id": "yard",
                    "method": "column",
                    "requested_columns": requested_columns,
                }
            },
        },
    )


def build_occupancy_attendance_case() -> tuple[dict, dict]:
    """Occupancy 12, actual attendance 8. Gap is not a counting error."""
    members = [
        {"student_key": f"a{index}", "queue_tie_key": f"{index:02d}"} for index in range(8)
    ]
    checkpoint = {
        "id": "cp_origin",
        "location_id": "origin",
        "required": True,
        "required_for": ["walk"],
        "permitted_methods": ["column"],
        "stage_id": "origin_count",
        "max_retries": 0,
        "expected_source": "actual_attendance",
        "treat_attendance_gap_as_count_error": False,
        "column": {
            "setup_s": 1,
            "cadence_s_per_person": 1,
            "aggregation_s": 1,
            "space_columns": 2,
            "workers_per_column": 1,
            "requested_columns": 2,
        },
    }
    return _shell(
        scenario_id="occupancy_vs_attendance_v1",
        data_version="ticket-03-occupancy-v1",
        deadline_s=200,
        source_units=[
            {
                "id": "su_origin",
                "hostel_id": "synthetic",
                "estimated_occupancy": 12,
                "estimated_attendance": 10,
                "resolved_attendance": 8,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            }
        ],
        places=[_unbounded("origin", 0.0, 0.0, "origin")],
        legs=[
            {
                "id": "stay",
                "from_place_id": "origin",
                "to_place_id": "origin",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {
                "id": "origin_count",
                "kind": "manual_count",
                "place_id": "origin",
                "checkpoint_id": "cp_origin",
                "method": "column",
            },
            {"id": "leave", "kind": "travel", "leg_id": "stay"},
        ],
        students=[
            {
                "part_id": "part_origin",
                "group_id": "g_walk",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 8},
                "members": members,
                "estimated_occupancy": 12,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            }
        ],
        workers=_workers(2, "origin"),
        vehicles=[],
        operating_rules={
            "required_endpoint": "stage_complete",
            "route_class": "walk",
            "required_checkpoints": ["cp_origin"],
            "permitted_counting_locations": ["origin"],
            "permitted_count_methods": ["column"],
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "facial_recognition": False,
            "seating_modeled": False,
            "treat_attendance_gap_as_count_error": False,
        },
        checkpoints=[checkpoint],
        error_assumptions=[_error_assumption(p_mismatch=0.0)],
        source_records=[
            _record("source_units.su_origin.estimated_occupancy", 12, "persons"),
            _record("source_units.su_origin.resolved_attendance", 8, "persons"),
        ],
        policy_id="occupancy_gap_v1",
        policy_counting={
            "required_checkpoints": ["cp_origin"],
            "assignments": {
                "cp_origin": {"location_id": "origin", "method": "column"}
            },
        },
    )


def build_mismatch_case(
    *,
    seed: int = 42,
    p_mismatch: float = 1.0,
    max_retries: int = 1,
    mismatch_schedule: list[bool] | None = None,
) -> tuple[dict, dict]:
    members = [
        {"student_key": f"m{index}", "queue_tie_key": f"{index:02d}"} for index in range(6)
    ]
    checkpoint = {
        "id": "cp_hold",
        "location_id": "yard",
        "required": True,
        "required_for": ["walk"],
        "permitted_methods": ["column"],
        "stage_id": "yard_count",
        "max_retries": max_retries,
        "column": {
            "setup_s": 2,
            "cadence_s_per_person": 1,
            "aggregation_s": 1,
            "space_columns": 2,
            "workers_per_column": 1,
            "requested_columns": 2,
        },
    }
    scenario, policy = _shell(
        scenario_id="seeded_mismatch_v1",
        data_version="ticket-03-mismatch-v1",
        deadline_s=200,
        source_units=[
            {
                "id": "su_yard",
                "hostel_id": "synthetic",
                "estimated_occupancy": 6,
                "estimated_attendance": 6,
                "resolved_attendance": 6,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            }
        ],
        places=[_unbounded("yard", 0.0, 0.0, "yard")],
        legs=[
            {
                "id": "stay",
                "from_place_id": "yard",
                "to_place_id": "yard",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {
                "id": "yard_count",
                "kind": "manual_count",
                "place_id": "yard",
                "checkpoint_id": "cp_hold",
                "method": "column",
            },
            {"id": "leave", "kind": "travel", "leg_id": "stay"},
        ],
        students=[
            {
                "part_id": "part_yard",
                "group_id": "g_yard",
                "source_unit_id": "su_yard",
                "place_id": "yard",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 6},
                "members": members,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            }
        ],
        workers=_workers(2, "yard"),
        vehicles=[],
        operating_rules={
            "required_endpoint": "stage_complete",
            "route_class": "walk",
            "required_checkpoints": ["cp_hold"],
            "permitted_counting_locations": ["yard"],
            "permitted_count_methods": ["column"],
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "facial_recognition": False,
            "seating_modeled": False,
        },
        checkpoints=[checkpoint],
        error_assumptions=[
            _error_assumption(
                p_mismatch=p_mismatch,
                mismatch_schedule=mismatch_schedule,
            )
        ],
        source_records=[_record("count_error_assumptions.p_mismatch", p_mismatch, "probability")],
        policy_id="seeded_mismatch_v1",
        policy_counting={
            "required_checkpoints": ["cp_hold"],
            "assignments": {
                "cp_hold": {"location_id": "yard", "method": "column"}
            },
        },
        seed=seed,
    )
    return scenario, policy


def build_group_formation_case(basis: str) -> tuple[dict, dict]:
    """Floor/wing groups as explicit parts. No required checkpoints."""
    units = source_units_from_layout()
    grouping = grouping_module()
    if grouping is not None:
        form = (
            getattr(grouping, "form_groups", None)
            or getattr(grouping, "apply_grouping", None)
            or getattr(grouping, "groups_for_basis", None)
        )
        if form is not None:
            parts = form(units, basis)
        else:
            parts = groups_from_source_units(units, basis)
    else:
        parts = groups_from_source_units(units, basis)
    for part in parts:
        part.setdefault("place_id", "origin")
        part.setdefault("count_record_ids", [])
        part.setdefault("covered_checkpoint_ids", [])
    operating_rules = {
        "required_endpoint": "stage_complete",
        "route_class": "walk",
        "required_checkpoints": [],
        "permitted_counting_locations": ["origin"],
        "permitted_count_methods": ["column", "pass_through"],
        "direct_walk_permitted": False,
        "bag_check": False,
        "security_service": False,
        "mechanical_clicker": False,
        "qr_scan": False,
        "facial_recognition": False,
        "seating_modeled": False,
    }
    return _shell(
        scenario_id=f"groups_{basis}_v1",
        data_version="ticket-03-groups-v1",
        deadline_s=50,
        source_units=units,
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("dest", 0.001, 0.0, "dest"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
        students=parts,
        workers=[],
        vehicles=[],
        operating_rules=operating_rules,
        checkpoints=[],
        error_assumptions=[],
        source_records=[_record("grouping.basis", basis, "category", "decision")],
        policy_id=f"groups_{basis}_v1",
        policy_counting={"required_checkpoints": [], "assignments": {}},
    )


def build_split_after_count_case() -> tuple[dict, dict]:
    """Column count, then a serial entrance that splits for calculation."""
    scenario, policy = build_walking_checkpoint_case()
    scenario["scenario_id"] = "split_after_count_v1"
    scenario["places"].append(_unbounded("entrance", 0.002, 0.0, "entrance"))
    scenario["route_legs"] = [
        {
            "id": "walk_1",
            "from_place_id": "origin",
            "to_place_id": "entrance",
            "duration_s": 10,
            "mode": "walk",
            "shared_resource_ids": [],
        }
    ]
    scenario["route_stages"] = [
        {
            "id": "origin_count",
            "kind": "manual_count",
            "place_id": "origin",
            "checkpoint_id": "cp_origin",
            "method": "column",
        },
        {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
        {
            "id": "entrance_service",
            "kind": "queue_service",
            "place_id": "entrance",
            "service_duration_s": 1,
            "server_count": 1,
            "queue_discipline": "fcfs",
        },
    ]
    scenario["operating_rules"]["required_endpoint"] = "service_complete"
    policy["required_endpoint"] = "service_complete"
    policy["policy_id"] = "split_after_count_v1"
    return scenario, policy


def build_bus_mismatch_case(*, seed: int = 3, max_retries: int = 1) -> tuple[dict, dict]:
    """Pass-through boarding mismatch holds the bus through recounts."""
    scenario, policy = build_bus_checkpoint_case(
        count_rate_s_per_person=1.0,
        board_duration_s=10.0,
        student_count=8,
    )
    scenario["scenario_id"] = "bus_mismatch_v1"
    scenario["checkpoints"][0]["max_retries"] = max_retries
    scenario["count_error_assumptions"] = [_error_assumption(p_mismatch=1.0)]
    policy["random_seed"] = seed
    policy["policy_id"] = "bus_mismatch_v1"
    return scenario, policy


def build_two_origin_checkpoint_bypass_case() -> tuple[dict, dict]:
    """Two origins share a required checkpoint. One route never visits it."""
    members_a = [
        {
            "student_key": "a0",
            "queue_tie_key": "00",
            "source_unit_id": "su_a",
            "hostel_id": "hostel_a",
        }
    ]
    members_b = [
        {
            "student_key": "b0",
            "queue_tie_key": "00",
            "source_unit_id": "su_b",
            "hostel_id": "hostel_b",
        }
    ]
    checkpoint = {
        "id": "cp_gate",
        "location_id": "origin_a",
        "required": True,
        "permitted_methods": ["column"],
        "stage_id": "count_a",
        "attach_to_stage_id": "count_a",
        "max_retries": 0,
        "column": {
            "setup_s": 1,
            "cadence_s_per_person": 1,
            "aggregation_s": 1,
            "space_columns": 1,
            "workers_per_column": 1,
            "requested_columns": 1,
        },
    }
    return _shell(
        scenario_id="two_origin_checkpoint_bypass_v1",
        data_version="ticket-03-bypass-v1",
        deadline_s=200,
        source_units=[
            {
                "id": "su_a",
                "hostel_id": "hostel_a",
                "estimated_occupancy": 1,
                "estimated_attendance": 1,
                "resolved_attendance": 1,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            },
            {
                "id": "su_b",
                "hostel_id": "hostel_b",
                "estimated_occupancy": 1,
                "estimated_attendance": 1,
                "resolved_attendance": 1,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            },
        ],
        places=[
            _unbounded("origin_a", 0.0, 0.0, "origin a"),
            _unbounded("origin_b", 0.0, 0.01, "origin b"),
            _unbounded("dest", 0.001, 0.0, "shared dest"),
        ],
        legs=[
            {
                "id": "walk_a",
                "from_place_id": "origin_a",
                "to_place_id": "dest",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "walk_b",
                "from_place_id": "origin_b",
                "to_place_id": "dest",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            },
        ],
        stages=[
            {
                "id": "count_a",
                "kind": "manual_count",
                "place_id": "origin_a",
                "checkpoint_id": "cp_gate",
                "method": "column",
            },
            {"id": "walk_a", "kind": "travel", "leg_id": "walk_a"},
            {"id": "walk_b", "kind": "travel", "leg_id": "walk_b"},
        ],
        students=[
            {
                "part_id": "part_a",
                "group_id": "g_a",
                "source_unit_id": "su_a",
                "place_id": "origin_a",
                "hostel_id": "hostel_a",
                "hostel_composition": {"hostel_a": 1},
                "members": members_a,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            },
            {
                "part_id": "part_b",
                "group_id": "g_b",
                "source_unit_id": "su_b",
                "place_id": "origin_b",
                "hostel_id": "hostel_b",
                "hostel_composition": {"hostel_b": 1},
                "members": members_b,
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            },
        ],
        workers=_workers(2, "origin_a"),
        vehicles=[],
        operating_rules={
            "required_endpoint": "stage_complete",
            "required_checkpoints": ["cp_gate"],
            "permitted_counting_locations": ["origin_a", "origin_b"],
            "permitted_count_methods": ["column"],
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "facial_recognition": False,
            "seating_modeled": False,
        },
        checkpoints=[checkpoint],
        error_assumptions=[_error_assumption(p_mismatch=0.0)],
        source_records=[_record("checkpoints.cp_gate", "required", "flag", "decision")],
        policy_id="two_origin_bypass_v1",
        policy_counting={
            "required_checkpoints": ["cp_gate"],
            "assignments": {
                "cp_gate": {
                    "method": "column",
                    "location_id": "origin_a",
                    "requested_columns": 1,
                }
            },
        },
        extra_scenario={
            "routes": {
                "hostel_a": ["count_a", "walk_a"],
                "hostel_b": ["walk_b"],
            }
        },
    )


assert COUNT_METHODS == {"pass_through", "column"}
