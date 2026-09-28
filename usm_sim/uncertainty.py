"""Ticket 08: Shared uncertainty cases, keyed RNG, and robust comparisons."""

from __future__ import annotations

import copy
import hashlib
import math
from typing import Any, Collection, Mapping, Sequence

from usm_sim.behavior import (
    ALL_PHENOMENON_FAMILIES,
    ALLOWED_BEHAVIOR_MODES,
    ALLOWED_EVIDENCE_CATEGORIES,
    prepare_behavior,
    validate_behavior_spec,
    validate_evidence,
    verify_behavior_conservation,
)
from usm_sim.constants import ENGINE_VERSION, FORMAT_VERSION
from usm_sim.errors import SimulationError
from usm_sim.grouping import allocate_integer_counts
from usm_sim.simulate import simulate

UNCERTAINTY_BANDS = ("lower", "base", "upper")
VALID_DATASET_ROLES = ("development", "final_independent", "selection", "calibration")
PROPERTY_CLASSES = ("unknown_fixed", "between_days", "during_day", "search_choice")
VEHICLE_MODES = frozenset({"bus", "coach"})

RANGE_COVERAGE_NOTE = (
    "A range is not a probability distribution. Equal weighting of stress cases "
    "describes benchmark coverage, not the actual chance of those cases occurring."
)

FORBIDDEN_POLICY_INFORMATION = frozenset(
    {
        "future_weather",
        "future_travel_times",
        "future_travel_time",
        "future_state",
        "unreported_bus_failure",
        "hidden_attendance",
        "actual_attendance",
        "oracle_schedule",
        "perfect_foresight",
        "hidden_no_show",
        "hidden_no_shows",
        "no_show_truth",
        "future_arrivals",
        "future_arrival",
        "hidden_behavior",
        "future_behavior",
        "actual_no_shows",
        "hidden_stragglers",
        "actual_behavior",
    }
)

DEFAULT_AGGREGATE_RULE = {
    "typical": "base_case",
    "stress": "worst_case",
    "weights": None,
    "weights_describe": "benchmark_coverage",
    "note": RANGE_COVERAGE_NOTE,
}

# Ticket-12 GPS calibration replays. These are final independent cases and
# cannot be used to select a plan.
GPS_HOLDOUT_SCENARIO_IDS = frozenset(
    {
        "restu_17sep_replay",
        "restu_18sep_rainy_replay",
    }
)

LOADING_DURATION_FIELDS = (
    "boarding_setup_s",
    "boarding_s_per_passenger_per_door",
    "alighting_setup_s",
    "alighting_s_per_passenger_per_door",
)

EMPTY_FAILURE_MEASURES = {
    "max_lateness_s": 0.0,
    "physical_violations": 0,
    "unfinished_students": 0,
    "mean_wait_s": 0.0,
    "total_student_waiting_student_s": 0.0,
    "total_lateness_s": 0.0,
    "late_students": 0,
    "worker_reserved_s": 0.0,
    "worker_duty_s": 0.0,
    "max_hostel_mean_wait_s": 0.0,
    "coordination_effort": 0.0,
}


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def iter_case_identity_values(case: Any) -> list[str]:
    """Collect identifiers that may mark case or GPS-holdout identity."""
    if isinstance(case, (list, tuple)):
        res: list[str] = []
        for item in case:
            res.extend(iter_case_identity_values(item))
        return res
    if isinstance(case, str):
        return [case]
    if not isinstance(case, Mapping):
        return []
    meta = _as_mapping(case.get("case_metadata")) or {}
    operating = _as_mapping(case.get("operating_rules")) or {}
    details = _as_mapping(case.get("case_details")) or {}
    resolved_inputs = _as_mapping(case.get("resolved_inputs")) or {}
    ids = [
        case.get("scenario_id"),
        case.get("case_id"),
        case.get("uncertainty_case_id"),
        case.get("id"),
        case.get("name"),
        case.get("replay_id"),
        case.get("evidence_id"),
        meta.get("case_id"),
        meta.get("scenario_id"),
        meta.get("uncertainty_case_id"),
        meta.get("evidence_id"),
        meta.get("replay_id"),
        operating.get("scenario_id"),
        operating.get("case_id"),
        operating.get("uncertainty_case_id"),
        operating.get("replay_id"),
        details.get("scenario_id"),
        details.get("case_id"),
        details.get("uncertainty_case_id"),
        details.get("replay_id"),
        resolved_inputs.get("scenario_id"),
        resolved_inputs.get("case_id"),
    ]
    # Check any nested string values that might contain holdout identifiers
    for k, v in list(case.items()) + list(meta.items()) + list(operating.items()):
        if isinstance(v, str) and v in GPS_HOLDOUT_SCENARIO_IDS:
            ids.append(v)
    return [str(item) for item in ids if item]


def is_gps_holdout_case(case: Any) -> bool:
    if isinstance(case, str) and case in GPS_HOLDOUT_SCENARIO_IDS:
        return True
    return any(item in GPS_HOLDOUT_SCENARIO_IDS for item in iter_case_identity_values(case))


def infer_dataset_role(
    scenario: Mapping[str, Any] | None = None,
    spec: Mapping[str, Any] | None = None,
) -> str:
    """Preserve holdout / independent identity. Do not default a labelled case to development."""
    spec = spec or {}
    scenario = scenario or {}
    if is_gps_holdout_case(spec) or is_gps_holdout_case(scenario):
        return "final_independent"
    meta_spec = _as_mapping(spec.get("case_metadata")) or {}
    op_spec = _as_mapping(spec.get("operating_rules")) or {}
    meta_sc = _as_mapping(scenario.get("case_metadata")) or {}
    op_sc = _as_mapping(scenario.get("operating_rules")) or {}

    roles = [
        spec.get("dataset_role"),
        meta_spec.get("dataset_role"),
        op_spec.get("dataset_role"),
        meta_sc.get("dataset_role"),
        scenario.get("dataset_role"),
        op_sc.get("dataset_role"),
    ]
    if "final_independent" in roles:
        return "final_independent"
    for r in roles:
        if r:
            return str(r)
    return "development"

def case_weight(scenario: Mapping[str, Any] | None) -> float:
    if not isinstance(scenario, Mapping):
        return 1.0
    meta = _as_mapping(scenario.get("case_metadata")) or {}
    if meta.get("weight") is not None:
        return float(meta["weight"])
    if scenario.get("weight") is not None:
        return float(scenario["weight"])
    return 1.0


def simulate_case_safely(scenario: Mapping[str, Any], policy: Mapping[str, Any]) -> dict:
    """Run simulate(); convert a per-case SimulationError into an infeasible record."""
    try:
        return simulate(scenario, policy)
    except SimulationError as err:
        return {
            "status": "infeasible",
            "termination_cause": err.category,
            "measures": dict(EMPTY_FAILURE_MEASURES),
            "accuracy_checks": [],
            "violations": [],
            "error": err.as_dict(),
            "input_snapshot": {
                "scenario": copy.deepcopy(dict(scenario)),
                "policy": copy.deepcopy(dict(policy)),
            },
        }


def simulation_failure_reasons(
    sim_res: Mapping[str, Any],
    constraints: Mapping[str, Any] | None,
    scenario: Mapping[str, Any],
) -> list[str]:
    """Hard-feasibility reasons for one simulated case. Input errors are failures."""
    measures = sim_res.get("measures") or {}
    reasons = _case_failed(measures, constraints or {}, scenario)
    if sim_res.get("status") != "completed":
        reasons.append(
            f"Simulation status was {sim_res.get('status')} ({sim_res.get('termination_cause')})"
        )
    return reasons


def keyed_random(seed: int | str, *keys: Any) -> float:
    """Return a deterministic float in [0.0, 1.0) keyed by seed and physical identifiers."""
    parts = [str(seed)] + [str(k) for k in keys]
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:14], 16) / float(0xFFFFFFFFFFFFFF)


def keyed_uniform(seed: int | str, low: float, high: float, *keys: Any) -> float:
    """Return a deterministic float in [low, high) keyed by seed and physical identifiers."""
    r = keyed_random(seed, *keys)
    return low + (high - low) * r


def keyed_choice(seed: int | str, seq: Sequence[Any], *keys: Any) -> Any:
    """Deterministically choose an element from seq keyed by seed and physical identifiers."""
    if not seq:
        raise ValueError("Cannot choose from empty sequence")
    r = keyed_random(seed, *keys)
    idx = int(r * len(seq)) % len(seq)
    return seq[idx]


def keyed_int(seed: int | str, low: int, high: int, *keys: Any) -> int:
    """Return a deterministic integer in [low, high] inclusive."""
    r = keyed_random(seed, *keys)
    return low + int(r * (high - low + 1))


def validate_policy_information(policy: Mapping[str, Any]) -> None:
    """Validate that a policy does not read hidden simulator state or future information."""
    found: list[str] = []

    def _scan(obj: Any, prefix: str = "") -> None:
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                cur_path = f"{prefix}.{k}" if prefix else str(k)
                if k in FORBIDDEN_POLICY_INFORMATION:
                    found.append(cur_path)
                _scan(v, cur_path)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                if isinstance(item, str) and item in FORBIDDEN_POLICY_INFORMATION:
                    found.append(f"{prefix}[{item}]")
                elif isinstance(item, Mapping):
                    _scan(item, prefix)

    _scan(policy)

    if found:
        raise SimulationError(
            "unsupported_policy",
            f"Policy attempts to access forbidden hidden/future information: {', '.join(sorted(found))}. "
            "A reactive policy may act only on information already delivered.",
            field=found[0],
        )

def _is_exposed_walking_leg(leg: Mapping[str, Any]) -> bool:
    mode = leg.get("mode")
    if mode in VEHICLE_MODES:
        return bool(leg.get("outdoor") is True or leg.get("exposed") is True)
    if leg.get("outdoor") is False or leg.get("exposed") is False:
        return False
    if leg.get("outdoor") is True or leg.get("exposed") is True:
        return True
    return mode == "walk"


def apply_shared_rain(scenario: dict, rain_factor: float = 1.3) -> list[str]:
    """Apply shared rain to exposed walking legs. Vehicle legs stay dry unless marked exposed."""
    affected: list[str] = []
    for leg in scenario.get("route_legs") or []:
        if not _is_exposed_walking_leg(leg):
            continue
        orig = float(leg.get("duration_s", 0))
        leg["duration_s"] = round(orig * rain_factor, 2)
        leg["rain_affected"] = True
        affected.append(leg["id"])
    return affected


def _scale_leg_durations(scenario: dict, factor: float, modes: Collection[str]) -> list[str]:
    if factor == 1.0:
        return []
    changed: list[str] = []
    allowed = set(modes)
    for leg in scenario.get("route_legs") or []:
        if leg.get("mode") not in allowed:
            continue
        orig = float(leg.get("duration_s", 0))
        leg["duration_s"] = round(orig * factor, 2)
        changed.append(leg["id"])
    return changed


def _demand_factor(spec: Mapping[str, Any], band: str) -> float:
    if spec.get("demand_factor") is not None:
        return float(spec["demand_factor"])
    demand = spec.get("demand", "base")
    if demand in ("low", "lower"):
        return 0.75
    if demand in ("high", "upper"):
        return 1.25
    if band == "lower":
        return 0.75
    if band == "upper":
        return 1.25
    return 1.0


def _scale_count(value: Any, factor: float) -> int:
    return max(0, int(round(float(value or 0) * factor)))


def _attendance_base(row: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        if row.get(key) is not None:
            return int(row[key])
    return 0


def _resize_part_members(part: dict, new_len: int) -> None:
    members = list(part.get("members") or [])
    new_len = max(0, int(new_len))
    if new_len < len(members):
        part["members"] = members[:new_len]
    elif new_len > len(members):
        part_id = part.get("part_id", "part")
        extras = [
            {"student_key": f"{part_id}_extra_{j}", "queue_tie_key": f"{j:02d}"}
            for j in range(len(members), new_len)
        ]
        part["members"] = members + extras
    hostel_id = part.get("hostel_id", "synthetic")
    part["hostel_composition"] = {hostel_id: len(part.get("members") or [])}


def _sync_initial_population(resolved: dict) -> None:
    """Make initial movement-part membership match resolved unit attendance."""
    source_units = resolved.get("source_units") or []
    parts = ((resolved.get("initial_state") or {}).get("students")) or []
    if not parts:
        return
    unit_att = {
        u["id"]: int(u.get("resolved_attendance") or 0)
        for u in source_units
        if u.get("id") is not None
    }
    parts_by_unit: dict[str, list[dict]] = {}
    for part in parts:
        su_id = part.get("source_unit_id")
        if su_id in unit_att:
            parts_by_unit.setdefault(str(su_id), []).append(part)
    for su_id, unit_parts in parts_by_unit.items():
        target = int(unit_att[su_id])
        weights = [
            (str(part.get("part_id") or idx), float(len(part.get("members") or []) or 1.0))
            for idx, part in enumerate(unit_parts)
        ]
        allocated = _allocate_by_weight(target, weights)
        for idx, part in enumerate(unit_parts):
            pid = str(part.get("part_id") or idx)
            _resize_part_members(part, int(allocated.get(pid, 0)))


def _apply_demand_factor(resolved: dict, demand_factor: float) -> None:
    if demand_factor == 1.0:
        return
    hostels = resolved.get("hostels") or []
    source_units = resolved.get("source_units") or []

    if hostels:
        for hostel in hostels:
            hid = hostel.get("id")
            h_units = [u for u in source_units if u.get("hostel_id") == hid]
            if h_units:
                base_att = sum(
                    _attendance_base(u, "resolved_attendance", "estimated_attendance")
                    for u in h_units
                )
            else:
                base_att = _attendance_base(hostel, "resolved_attendance", "expected_event_attendance")

            scaled_hostel = max(1, _scale_count(base_att, demand_factor)) if base_att else 0
            hostel["resolved_attendance"] = scaled_hostel

            if h_units:
                weights = [
                    (
                        u["id"],
                        float(_attendance_base(u, "resolved_attendance", "estimated_attendance") or 1),
                    )
                    for u in h_units
                ]
                allocated = _allocate_by_weight(scaled_hostel, weights)
                for u in h_units:
                    u["resolved_attendance"] = int(allocated.get(u["id"], 0))
    elif source_units:
        base_total = sum(
            _attendance_base(u, "resolved_attendance", "estimated_attendance")
            for u in source_units
        )
        scaled_total = max(1, _scale_count(base_total, demand_factor)) if base_total else 0
        weights = [
            (
                u["id"],
                float(_attendance_base(u, "resolved_attendance", "estimated_attendance") or 1),
            )
            for u in source_units
        ]
        allocated = _allocate_by_weight(scaled_total, weights)
        for u in source_units:
            u["resolved_attendance"] = int(allocated.get(u["id"], 0))


def _allocate_by_weight(total: int, items: list[tuple[str, float]]) -> dict[str, int]:
    if not items:
        return {}
    if total <= 0:
        return {item_id: 0 for item_id, _weight in items}
    positive = [(item_id, weight) for item_id, weight in items if weight > 0]
    assigned = {item_id: 0 for item_id, weight in items if weight <= 0}
    if not positive:
        positive = [(item_id, 1.0) for item_id, _weight in items]
        assigned = {}
    assigned.update(allocate_integer_counts(int(total), positive))
    return assigned


def _sync_source_units_to_hostels(resolved: dict) -> None:
    hostels = {h["id"]: h for h in resolved.get("hostels") or []}
    if not hostels:
        return
    units_by_hostel: dict[str, list[dict]] = {}
    for su in resolved.get("source_units") or []:
        hid = su.get("hostel_id")
        if hid in hostels:
            units_by_hostel.setdefault(hid, []).append(su)
    for hid, units in units_by_hostel.items():
        target = int(hostels[hid].get("resolved_attendance") or 0)
        weights = [
            (u["id"], float(u.get("resolved_attendance") if u.get("resolved_attendance") is not None else (u.get("estimated_attendance") or 1.0)))
            for u in units
        ]
        allocated = _allocate_by_weight(target, weights)
        for unit in units:
            att = int(allocated.get(unit["id"], 0))
            unit["resolved_attendance"] = att


def _constrain_campus_attendance(resolved: dict, total: int) -> None:
    hostels = resolved.get("hostels") or []
    if hostels:
        weights = [
            (h["id"], float(h.get("resolved_attendance") if h.get("resolved_attendance") is not None else (h.get("expected_event_attendance") or 1.0)))
            for h in hostels
        ]
        allocated = _allocate_by_weight(int(total), weights)
        for hostel in hostels:
            att = int(allocated.get(hostel["id"], 0))
            hostel["resolved_attendance"] = att
        _sync_source_units_to_hostels(resolved)
        return
    units = resolved.get("source_units") or []
    if not units:
        return
    weights = [
        (u["id"], float(u.get("resolved_attendance") if u.get("resolved_attendance") is not None else (u.get("estimated_attendance") or 1.0)))
        for u in units
    ]
    allocated = _allocate_by_weight(int(total), weights)
    for unit in units:
        att = int(allocated.get(unit["id"], 0))
        unit["resolved_attendance"] = att


def _infer_property_class(spec: Mapping[str, Any], grouping_basis: str | None, is_rain: bool) -> str:
    declared = spec.get("property_class") or spec.get("uncertainty_class")
    if declared:
        if declared not in PROPERTY_CLASSES:
            raise SimulationError(
                "invalid_value_or_unit",
                f"Unknown property class '{declared}'. Use one of {PROPERTY_CLASSES}.",
                field="property_class",
            )
        return declared
    if grouping_basis or spec.get("grouping_basis"):
        return "search_choice"
    if spec.get("holding_capacity") is not None or spec.get("queue_capacity_factor") is not None:
        return "unknown_fixed"
    if (
        is_rain
        or "coordination_delay_s" in spec
        or "report_delay_s" in spec
        or spec.get("bus_delay_s") is not None
        or spec.get("readiness_delta_s")
    ):
        return "during_day"
    return "between_days"


def _apply_optional_dimensions(resolved: dict, spec: Mapping[str, Any]) -> dict[str, Any]:
    applied: dict[str, Any] = {}
    walking_factor = float(spec.get("walking_factor", 1.0))
    if walking_factor != 1.0:
        applied["walking_legs"] = _scale_leg_durations(resolved, walking_factor, {"walk"})
        applied["walking_factor"] = walking_factor

    bus_travel_factor = spec.get("bus_travel_factor")
    if bus_travel_factor is not None:
        btf = float(bus_travel_factor)
        if btf != 1.0:
            applied["bus_legs"] = _scale_leg_durations(resolved, btf, VEHICLE_MODES)
            applied["bus_travel_factor"] = btf

    bus_loading_factor = spec.get("bus_loading_factor")
    if bus_loading_factor is not None:
        blf = float(bus_loading_factor)
        applied["bus_loading_factor"] = blf
        # Scale boarding duration fields on vehicle types and vehicles
        for vtype in resolved.get("vehicle_types") or []:
            for field in LOADING_DURATION_FIELDS:
                if vtype.get(field) is not None:
                    vtype[field] = round(float(vtype[field]) * blf, 4)
        for veh in (resolved.get("initial_state") or {}).get("vehicles") or []:
            for field in LOADING_DURATION_FIELDS:
                if veh.get(field) is not None:
                    veh[field] = round(float(veh[field]) * blf, 4)
        for stage in resolved.get("route_stages") or []:
            if stage.get("kind") in ("boarding", "alighting") and "duration_s" in stage:
                stage["duration_s"] = round(float(stage["duration_s"]) * blf, 2)

    hall_factor = float(spec.get("hall_service_factor", 1.0))
    if hall_factor != 1.0:
        for stage in resolved.get("route_stages") or []:
            if stage.get("kind") == "queue_service" and "service_duration_s" in stage:
                stage["service_duration_s"] = round(float(stage["service_duration_s"]) * hall_factor, 2)
        applied["hall_service_factor"] = hall_factor
    occupancy_factor = spec.get("occupancy_factor")
    if occupancy_factor is not None:
        occ = float(occupancy_factor)
        for row in list(resolved.get("source_units") or []) + list(resolved.get("hostels") or []):
            if row.get("resident_occupancy"):
                row["resident_occupancy"] = max(0, _scale_count(row["resident_occupancy"], occ))
        applied["occupancy_factor"] = occ
    readiness_delta = spec.get("readiness_delta_s")
    if readiness_delta:
        delta = float(readiness_delta)
        for su in resolved.get("source_units") or []:
            su["readiness_s"] = float(su.get("readiness_s") or 0) + delta
            su["actual_reporting_s"] = float(su.get("actual_reporting_s") or 0) + delta
        applied["readiness_delta_s"] = delta
    report_delay = spec.get("report_delay_s", spec.get("coordination_delay_s"))
    if report_delay is not None:
        resolved.setdefault("operating_rules", {})["coordination_delay_s"] = float(report_delay)
        applied["report_delay_s"] = float(report_delay)
    worker_factor = spec.get("worker_factor")
    if worker_factor is not None:
        workers = list((resolved.get("initial_state") or {}).get("workers") or [])
        keep = max(0, int(round(len(workers) * float(worker_factor))))
        if resolved.get("initial_state") is not None:
            resolved["initial_state"]["workers"] = workers[:keep]
        applied["worker_factor"] = float(worker_factor)
        applied["workers_kept"] = keep
    queue_factor = spec.get("queue_capacity_factor")
    if queue_factor is not None:
        qf = float(queue_factor)
        for place in resolved.get("places") or []:
            for field in (
                "capacity_students",
                "physical_capacity_students",
                "operating_limit_students",
                "estimated_capacity_students",
            ):
                if place.get(field) is not None:
                    place[field] = max(1, _scale_count(place[field], qf))
        applied["queue_capacity_factor"] = qf
        applied["queue_capacity_affects_admitting"] = True
    if spec.get("count_mismatch_p") is not None:
        resolved["count_error_assumptions"] = [
            {
                "id": "uncertainty_count_pass",
                "exposure_unit": "checkpoint_pass",
                "relationship_to_load": "none",
                "p_mismatch": float(spec["count_mismatch_p"]),
                "observed_delta": int(spec.get("count_observed_delta", 1)),
            }
        ]
        applied["count_mismatch_p"] = float(spec["count_mismatch_p"])
    return applied


def _resolve_value_from_band_or_draw(
    raw: Any,
    band_name: str,
    *,
    seed: int | str,
    case_id: str,
    phenomenon: str,
    source_unit_id: str = "",
    cohort_id: str = "",
    event_id: str = "",
    field_name: str = "",
    default_units: str = "count",
) -> tuple[int | float, str, bool]:
    """Resolve a scalar value from a coverage band, keyed draw spec, or fixed value.

    Returns (selected_value, key_string, is_keyed_draw).
    """
    if raw is None:
        key_str = f"{seed}:{case_id}:{phenomenon}:{source_unit_id}:{cohort_id}:{event_id}:{field_name}:none"
        return 0, key_str, False

    if isinstance(raw, bool):
        key_str = f"{seed}:{case_id}:{phenomenon}:{source_unit_id}:{cohort_id}:{event_id}:{field_name}:fixed"
        return raw, key_str, False

    if isinstance(raw, dict):
        # 1. Keyed draw specification
        if any(k in raw for k in ("selection_rule", "rule", "draw")):
            rule = raw.get("selection_rule") or raw.get("rule") or raw.get("draw") or "keyed_int"
            bounds = raw.get("bounds") or raw.get("range")
            if bounds is None:
                if "low" in raw and "high" in raw:
                    bounds = (raw["low"], raw["high"])
                elif "lower" in raw and "upper" in raw:
                    bounds = (raw["lower"], raw["upper"])
            if bounds is None:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"Keyed draw for {field_name} missing bounds",
                    field=field_name,
                )
            if isinstance(bounds, (list, tuple)):
                low, high = bounds[0], bounds[1]
            elif isinstance(bounds, dict):
                low = bounds.get("lower", bounds.get("low", 0))
                high = bounds.get("upper", bounds.get("high", 0))
            else:
                low, high = 0, bounds

            units = raw.get("units", default_units)
            rounding = raw.get("rounding_rule") or raw.get("rounding")
            key_str = f"{seed}:{case_id}:{phenomenon}:{source_unit_id}:{cohort_id}:{event_id}:{field_name}"

            if rule in ("keyed_int", "uniform_int", "integer_uniform"):
                val = keyed_int(
                    seed,
                    int(low),
                    int(high),
                    case_id,
                    phenomenon,
                    source_unit_id,
                    cohort_id,
                    event_id,
                    field_name,
                )
                return int(val), key_str, True
            elif rule in ("keyed_uniform", "uniform"):
                val = keyed_uniform(
                    seed,
                    float(low),
                    float(high),
                    case_id,
                    phenomenon,
                    source_unit_id,
                    cohort_id,
                    event_id,
                    field_name,
                )
                if rounding == "round":
                    val = round(val)
                elif rounding == "floor":
                    val = math.floor(val)
                elif rounding == "ceil":
                    val = math.ceil(val)
                if "student" in str(units).lower() or "count" in str(units).lower() or rounding:
                    return int(val), key_str, True
                return round(val, 2), key_str, True
            else:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"Unknown selection rule {rule!r} for {field_name}",
                    field=field_name,
                )

        # 2. Nested band
        if "band" in raw and isinstance(raw["band"], (dict, list, tuple)):
            return _resolve_value_from_band_or_draw(
                raw["band"],
                band_name,
                seed=seed,
                case_id=case_id,
                phenomenon=phenomenon,
                source_unit_id=source_unit_id,
                cohort_id=cohort_id,
                event_id=event_id,
                field_name=field_name,
                default_units=default_units,
            )

        # 3. Coverage band dict with lower/base/upper
        if any(k in raw for k in ("lower", "base", "upper")):
            val = raw.get(band_name)
            if val is None:
                val = raw.get("base")
            if val is None:
                val = next(iter(raw.values()))
            key_str = f"{seed}:{case_id}:{phenomenon}:{source_unit_id}:{cohort_id}:{event_id}:{field_name}:{band_name}"
            if isinstance(val, (dict, list, tuple)):
                return _resolve_value_from_band_or_draw(
                    val,
                    band_name,
                    seed=seed,
                    case_id=case_id,
                    phenomenon=phenomenon,
                    source_unit_id=source_unit_id,
                    cohort_id=cohort_id,
                    event_id=event_id,
                    field_name=field_name,
                    default_units=default_units,
                )
            return val, key_str, False

    # 4. Coverage band list/tuple of 3 items
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        idx = 0 if band_name == "lower" else (2 if band_name == "upper" else 1)
        key_str = f"{seed}:{case_id}:{phenomenon}:{source_unit_id}:{cohort_id}:{event_id}:{field_name}:{band_name}"
        val = raw[idx]
        if isinstance(val, (dict, list, tuple)):
            return _resolve_value_from_band_or_draw(
                val,
                band_name,
                seed=seed,
                case_id=case_id,
                phenomenon=phenomenon,
                source_unit_id=source_unit_id,
                cohort_id=cohort_id,
                event_id=event_id,
                field_name=field_name,
                default_units=default_units,
            )
        return val, key_str, False

    # 5. List/tuple of 2 items interpreted as bounds for keyed draw
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        key_str = f"{seed}:{case_id}:{phenomenon}:{source_unit_id}:{cohort_id}:{event_id}:{field_name}"
        val = keyed_int(
            seed,
            int(raw[0]),
            int(raw[1]),
            case_id,
            phenomenon,
            source_unit_id,
            cohort_id,
            event_id,
            field_name,
        )
        return int(val), key_str, True

    # 6. Fixed scalar
    key_str = f"{seed}:{case_id}:{phenomenon}:{source_unit_id}:{cohort_id}:{event_id}:{field_name}:fixed"
    return raw, key_str, False


def resolve_behavior_bands(
    resolved: dict,
    spec: Mapping[str, Any] | None = None,
    *,
    seed: int | str,
    case_id: str,
    band: str = "base",
) -> dict[str, Any]:
    """Resolve named behavior coverage bands into concrete counts and offsets.

    Called AFTER demand factor and _sync_initial_population.
    Keyed by seed, case ID, phenomenon, source-unit ID, cohort ID, event ID.
    Does NOT key by policy, group size, part ID, or call order.
    """
    spec = spec or {}
    behavior_input = (
        spec.get("behavior")
        or spec.get("behavior_bands")
        or spec.get("behavior_band")
    )
    if behavior_input is not None:
        if "behavior" in resolved and isinstance(resolved["behavior"], dict) and isinstance(behavior_input, dict):
            base_beh = copy.deepcopy(resolved["behavior"])
            for k, v in behavior_input.items():
                if k == "source_unit_splits" and isinstance(v, dict) and isinstance(base_beh.get("source_unit_splits"), dict):
                    base_beh["source_unit_splits"] = dict(base_beh["source_unit_splits"])
                    base_beh["source_unit_splits"].update(v)
                elif k == "phenomena" and isinstance(v, dict) and isinstance(base_beh.get("phenomena"), dict):
                    base_beh["phenomena"] = dict(base_beh["phenomena"])
                    base_beh["phenomena"].update(v)
                else:
                    base_beh[k] = copy.deepcopy(v)
            behavior_dict = base_beh
        elif isinstance(behavior_input, dict):
            behavior_dict = copy.deepcopy(behavior_input)
        else:
            behavior_dict = behavior_input
    elif "behavior" in resolved and isinstance(resolved["behavior"], dict):
        behavior_dict = copy.deepcopy(resolved["behavior"])
    else:
        # No behavior defined
        return {}

    behavior_dict.setdefault("version", "1.0")
    behavior_dict.setdefault("case_id", str(case_id))
    if behavior_dict.get("mode") not in ALLOWED_BEHAVIOR_MODES:
        behavior_dict["mode"] = "resolved_band"
    behavior_dict.setdefault("events", [])
    behavior_dict.setdefault("source_unit_splits", {})

    declared_phenomena = behavior_dict.setdefault("phenomena", {})
    if not isinstance(declared_phenomena, dict):
        declared_phenomena = {p: {} for p in declared_phenomena}
        behavior_dict["phenomena"] = declared_phenomena

    for fam in ALL_PHENOMENON_FAMILIES:
        if fam not in declared_phenomena and fam not in behavior_dict:
            declared_phenomena[fam] = {}

    raw_bands_record: dict[str, Any] = {}
    selected_values_record: dict[str, Any] = {}
    keys_record: dict[str, str] = {}
    provenance_record: dict[str, Any] = {}
    records_list: list[dict[str, Any]] = []

    source_units = resolved.get("source_units") or []
    splits = behavior_dict.get("source_unit_splits")

    for unit in source_units:
        uid = unit.get("id")
        post_demand_pop = int(unit.get("resolved_attendance") or 0)
        required_reporting_s = unit.get("required_reporting_s", 0)

        unit_cohorts = None
        if isinstance(splits, dict) and uid in splits:
            unit_cohorts = splits[uid]
        elif isinstance(splits, list):
            unit_cohorts = [c for c in splits if c.get("source_unit_id") == uid]
        elif "cohorts" in unit:
            unit_cohorts = unit["cohorts"]

        # If no cohorts defined on splits or unit, check if declared_phenomena has bands
        if unit_cohorts is None or len(unit_cohorts) == 0:
            has_no_show = (
                "no_show" in declared_phenomena
                and any(k in declared_phenomena["no_show"] for k in ("band", "count_band", "count", "selection_rule"))
            )
            has_late = (
                "late_reporting" in declared_phenomena
                and any(k in declared_phenomena["late_reporting"] for k in ("band", "count_band", "count", "selection_rule"))
            )
            if has_no_show or has_late:
                unit_cohorts = []
                if has_no_show:
                    ns_decl = declared_phenomena["no_show"]
                    unit_cohorts.append({
                        "cohort_id": f"{uid}_noshow",
                        "attendance_state": "no_show",
                        "count_band": ns_decl.get("count_band", ns_decl.get("band", ns_decl.get("count"))),
                        "evidence": ns_decl.get("evidence", {"category": "assumed", "note": "declared no_show phenomenon"}),
                    })
                if has_late:
                    late_decl = declared_phenomena["late_reporting"]
                    unit_cohorts.append({
                        "cohort_id": f"{uid}_late",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "count_band": late_decl.get("count_band", late_decl.get("band", late_decl.get("count"))),
                        "late_assembly_band": late_decl.get(
                            "late_assembly_band",
                            late_decl.get("delay_band", late_decl.get("late_assembly_s", 120)),
                        ),
                        "evidence": late_decl.get("evidence", {"category": "assumed", "note": "declared late_reporting phenomenon"}),
                    })
                unit_cohorts.append({
                    "cohort_id": f"{uid}_ontime",
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "allocation_rule": "remainder",
                    "evidence": {"category": "assumed", "note": "on-time remainder cohort"},
                })

        if unit_cohorts is not None:
            remainder_cohort = None
            for cohort in unit_cohorts:
                cid = cohort.get("cohort_id")
                state = cohort.get("attendance_state", "attending")
                phenom = cohort.get("phenomenon")
                if not phenom:
                    if state == "no_show":
                        phenom = "no_show"
                    elif (
                        cohort.get("late_assembly_s") is not None
                        or cohort.get("late_assembly_band") is not None
                        or cohort.get("reporting_mode") == "delay_from_required"
                    ):
                        phenom = "late_reporting"
                    elif cohort.get("readiness_s") is not None or cohort.get("readiness_band") is not None:
                        phenom = "mixed_readiness"
                    else:
                        phenom = "attending"

                ev = cohort.get("evidence")
                if not ev:
                    ev = declared_phenomena.get(phenom, {}).get("evidence") or {
                        "category": "assumed",
                        "note": f"evidence for {cid}",
                    }
                validate_evidence(ev, f"scenario.source_units.{uid}.cohorts.{cid}.evidence")
                cohort["evidence"] = ev

                is_remainder = (
                    cohort.get("allocation_rule") == "remainder"
                    or cohort.get("count") == "remainder"
                    or cohort.get("remainder") is True
                )
                if is_remainder:
                    if remainder_cohort is not None:
                        raise SimulationError(
                            "invalid_value_or_unit",
                            f"Multiple remainder cohorts in unit {uid!r}",
                            field=f"scenario.source_units.{uid}",
                        )
                    remainder_cohort = cohort
                else:
                    raw_count = (
                        cohort.get("count_band")
                        if cohort.get("count_band") is not None
                        else (
                            cohort.get("count")
                            if cohort.get("count") is not None
                            else cohort.get("count_draw")
                        )
                    )
                    if raw_count is None and ("selection_rule" in cohort or "bounds" in cohort):
                        raw_count = cohort
                    if raw_count is None:
                        raw_count = declared_phenomena.get(phenom, {}).get(
                            "count_band", declared_phenomena.get(phenom, {}).get("count")
                        )

                    if raw_count is not None:
                        sel_count, k_str, _ = _resolve_value_from_band_or_draw(
                            raw_count,
                            band,
                            seed=seed,
                            case_id=case_id,
                            phenomenon=phenom,
                            source_unit_id=uid,
                            cohort_id=cid,
                            event_id="none",
                            field_name="count",
                            default_units="students",
                        )
                        cohort["count"] = int(sel_count)
                        item_k = f"{uid}:{cid}:count"
                        raw_bands_record[item_k] = raw_count
                        selected_values_record[item_k] = int(sel_count)
                        keys_record[item_k] = k_str
                        provenance_record[item_k] = ev
                        records_list.append({
                            "id": item_k,
                            "source_unit_id": uid,
                            "cohort_id": cid,
                            "field": "count",
                            "raw_band": raw_count,
                            "selected_value": int(sel_count),
                            "key": k_str,
                            "evidence": ev,
                        })

                # Resolve late_assembly_s / delay
                raw_late = (
                    cohort.get("late_assembly_band")
                    if cohort.get("late_assembly_band") is not None
                    else cohort.get("delay_band")
                )
                if raw_late is None and isinstance(cohort.get("late_assembly_s"), (dict, list, tuple)):
                    raw_late = cohort["late_assembly_s"]
                if raw_late is None:
                    raw_late = declared_phenomena.get(phenom, {}).get("late_assembly_band")

                if raw_late is not None:
                    sel_late, k_late, _ = _resolve_value_from_band_or_draw(
                        raw_late,
                        band,
                        seed=seed,
                        case_id=case_id,
                        phenomenon=phenom,
                        source_unit_id=uid,
                        cohort_id=cid,
                        event_id="none",
                        field_name="late_assembly_s",
                        default_units="seconds",
                    )
                    cohort["late_assembly_s"] = int(sel_late)
                    item_k = f"{uid}:{cid}:late_assembly_s"
                    raw_bands_record[item_k] = raw_late
                    selected_values_record[item_k] = int(sel_late)
                    keys_record[item_k] = k_late
                    provenance_record[item_k] = ev
                    records_list.append({
                        "id": item_k,
                        "source_unit_id": uid,
                        "cohort_id": cid,
                        "field": "late_assembly_s",
                        "raw_band": raw_late,
                        "selected_value": int(sel_late),
                        "key": k_late,
                        "evidence": ev,
                    })

                # Ensure delay and actual reporting are consistent
                if cohort.get("reporting_mode") == "delay_from_required":
                    if "late_assembly_s" in cohort:
                        cohort["actual_reporting_s"] = required_reporting_s + cohort["late_assembly_s"]
                elif cohort.get("reporting_mode") == "absolute":
                    if "actual_reporting_s" in cohort:
                        cohort["late_assembly_s"] = max(0, cohort["actual_reporting_s"] - required_reporting_s)

                # Resolve readiness_s if band
                raw_ready = cohort.get("readiness_band")
                if raw_ready is None and isinstance(cohort.get("readiness_s"), (dict, list, tuple)):
                    raw_ready = cohort["readiness_s"]
                if raw_ready is not None:
                    sel_ready, k_ready, _ = _resolve_value_from_band_or_draw(
                        raw_ready,
                        band,
                        seed=seed,
                        case_id=case_id,
                        phenomenon=phenom,
                        source_unit_id=uid,
                        cohort_id=cid,
                        event_id="none",
                        field_name="readiness_s",
                        default_units="seconds",
                    )
                    cohort["readiness_s"] = int(sel_ready)
                    item_k = f"{uid}:{cid}:readiness_s"
                    raw_bands_record[item_k] = raw_ready
                    selected_values_record[item_k] = int(sel_ready)
                    keys_record[item_k] = k_ready
                    provenance_record[item_k] = ev

            # Check post-demand population and resolve remainder
            if remainder_cohort is not None:
                non_rem_sum = sum(
                    int(c.get("count") or 0) for c in unit_cohorts if c is not remainder_cohort
                )
                rem_count = post_demand_pop - non_rem_sum
                if rem_count < 0:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"Behavior counts total ({non_rem_sum}) exceeds post-demand population ({post_demand_pop}) for unit {uid!r}",
                        field=f"scenario.source_units.{uid}.declared_population",
                    )
                remainder_cohort["count"] = rem_count
                rem_cid = remainder_cohort["cohort_id"]
                item_k = f"{uid}:{rem_cid}:count"
                raw_bands_record[item_k] = "remainder"
                selected_values_record[item_k] = rem_count
                keys_record[item_k] = f"{seed}:{case_id}:{remainder_cohort.get('phenomenon', 'attending')}:{uid}:{rem_cid}:none:count:remainder"
                provenance_record[item_k] = remainder_cohort["evidence"]
                records_list.append({
                    "id": item_k,
                    "source_unit_id": uid,
                    "cohort_id": rem_cid,
                    "field": "count",
                    "raw_band": "remainder",
                    "selected_value": rem_count,
                    "key": keys_record[item_k],
                    "evidence": remainder_cohort["evidence"],
                })
            else:
                total_c_sum = sum(int(c.get("count") or 0) for c in unit_cohorts)
                if total_c_sum > post_demand_pop:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"Behavior counts total ({total_c_sum}) exceeds post-demand population ({post_demand_pop}) for unit {uid!r}",
                        field=f"scenario.source_units.{uid}.declared_population",
                    )

            if isinstance(splits, dict):
                splits[uid] = unit_cohorts
            unit["cohorts"] = unit_cohorts
            unit["declared_population"] = post_demand_pop

    # Resolve events
    events = behavior_dict.get("events") or []
    for event in events:
        eid = event.get("event_id")
        phenom = event.get("phenomenon", "event")
        target = event.get("target")
        ev = event.get("evidence")
        if not ev:
            ev = declared_phenomena.get(phenom, {}).get("evidence") or {
                "category": "assumed",
                "note": f"evidence for event {eid}",
            }
        validate_evidence(ev, f"scenario.behavior.events.{eid}.evidence")
        event["evidence"] = ev

        trigger = event.get("trigger")
        if isinstance(trigger, dict):
            raw_time = trigger.get("time_s_band")
            if raw_time is None and isinstance(trigger.get("time_s"), (dict, list, tuple)):
                raw_time = trigger["time_s"]
            if raw_time is not None:
                sel_time, k_time, _ = _resolve_value_from_band_or_draw(
                    raw_time,
                    band,
                    seed=seed,
                    case_id=case_id,
                    phenomenon=phenom,
                    source_unit_id="",
                    cohort_id=str(target) if isinstance(target, str) else "",
                    event_id=eid,
                    field_name="time_s",
                    default_units="seconds",
                )
                trigger["time_s"] = sel_time
                item_k = f"event:{eid}:time_s"
                raw_bands_record[item_k] = raw_time
                selected_values_record[item_k] = sel_time
                keys_record[item_k] = k_time
                provenance_record[item_k] = ev
                records_list.append({
                    "id": item_k,
                    "event_id": eid,
                    "field": "time_s",
                    "raw_band": raw_time,
                    "selected_value": sel_time,
                    "key": k_time,
                    "evidence": ev,
                })

    resolved["behavior"] = behavior_dict
    prepare_behavior(resolved)
    verify_behavior_conservation(resolved)

    behavior_meta = {
        "seed": seed,
        "case_id": case_id,
        "range_interpretation": "coverage_band",
        "is_probability_distribution": False,
        "raw_bands": raw_bands_record,
        "selected_values": selected_values_record,
        "keys": keys_record,
        "provenance": provenance_record,
        "records": records_list,
    }
    return behavior_meta

def resolve_case(
    scenario: Mapping[str, Any],
    case_spec: Mapping[str, Any] | None = None,
    *,
    seed: int | None = None,
    grouping_basis: str | None = None,
) -> dict:
    """Resolve an uncertainty case on a base scenario.

    Keyed RNG guarantees that the same seed + physical key produces the same draw,
    so changing grouping or internal calculations never resamples weather or attendance.
    """
    resolved = copy.deepcopy(dict(scenario))
    spec = dict(case_spec or {})

    if seed is None:
        seed = int(spec.get("random_seed", spec.get("seed", resolved.get("random_seed", 0))))
    resolved["random_seed"] = seed

    meta_in = _as_mapping(resolved.get("case_metadata")) or {}
    op_in = _as_mapping(resolved.get("operating_rules")) or {}
    spec_meta = _as_mapping(spec.get("case_metadata")) or {}
    spec_op = _as_mapping(spec.get("operating_rules")) or {}

    scenario_id = (
        spec.get("scenario_id")
        or spec_meta.get("scenario_id")
        or spec_op.get("scenario_id")
        or resolved.get("scenario_id")
        or meta_in.get("scenario_id")
        or op_in.get("scenario_id")
    )
    if scenario_id is not None:
        resolved["scenario_id"] = str(scenario_id)

    uncertainty_case_id = (
        spec.get("uncertainty_case_id")
        or spec_meta.get("uncertainty_case_id")
        or spec_op.get("uncertainty_case_id")
        or resolved.get("uncertainty_case_id")
        or meta_in.get("uncertainty_case_id")
        or op_in.get("uncertainty_case_id")
    )

    case_id = (
        spec.get("case_id")
        or spec.get("id")
        or spec_meta.get("case_id")
        or (scenario_id if scenario_id in GPS_HOLDOUT_SCENARIO_IDS else None)
        or uncertainty_case_id
        or resolved.get("case_id")
        or meta_in.get("case_id")
        or "case_base"
    )
    resolved["uncertainty_case_id"] = uncertainty_case_id or case_id

    case_type = spec.get("case_type") or spec.get("kind")
    if not case_type:
        case_type = "stress" if "stress" in str(case_id).lower() else "typical"

    band = spec.get("band", spec.get("uncertainty_band", "base"))
    if band not in UNCERTAINTY_BANDS:
        raise SimulationError(
            "invalid_value_or_unit",
            f"Uncertainty band must be one of {UNCERTAINTY_BANDS}, not '{band}'.",
            field="band",
        )

    dataset_role = infer_dataset_role(resolved, spec)
    resolved["dataset_role"] = dataset_role
    if dataset_role not in VALID_DATASET_ROLES:
        raise SimulationError(
            "invalid_value_or_unit",
            f"dataset_role must be one of {VALID_DATASET_ROLES}, not '{dataset_role}'.",
            field="dataset_role",
        )
    if spec.get("claim_independent_validation"):
        if dataset_role != "final_independent":
            raise SimulationError(
                "fixed_rule_violation",
                f"Case '{case_id}' has dataset_role '{dataset_role}' and cannot claim independent validation. "
                "Only final_independent cases can claim independent validation.",
                field="dataset_role",
            )

    weather_draw = keyed_random(seed, "weather", "campus")
    if "rain" in spec:
        is_rain = bool(spec["rain"])
    elif spec.get("weather") == "rain" or spec.get("weather_condition") == "rain":
        is_rain = True
    elif "rain_probability" in spec:
        is_rain = weather_draw < float(spec["rain_probability"])
    elif case_type == "stress" and ("rain" in str(case_id).lower() or spec.get("stress_kind") == "rain"):
        is_rain = True
    else:
        is_rain = False

    rain_factor = float(spec.get("rain_factor", 1.3))
    affected_legs: list[str] = []
    extra_dims = _apply_optional_dimensions(resolved, spec)
    if is_rain:
        affected_legs = apply_shared_rain(resolved, rain_factor)

    demand = spec.get("demand", "base")
    demand_factor = _demand_factor(spec, band)
    _apply_demand_factor(resolved, demand_factor)

    campus_attendance_total = spec.get("campus_attendance_total")
    if campus_attendance_total is not None:
        _constrain_campus_attendance(resolved, int(campus_attendance_total))
    _sync_initial_population(resolved)

    behavior_meta = resolve_behavior_bands(
        resolved,
        spec,
        seed=seed,
        case_id=str(case_id),
        band=band,
    )

    if spec.get("scenario_type") == "estimated" or spec.get("is_estimated") or resolved.get("scenario_type") == "estimated":
        resolved["scenario_type"] = "estimated"
        resolved["is_estimated"] = True

    if spec.get("accuracy_references"):
        resolved.setdefault("accuracy_references", []).extend(spec["accuracy_references"])

    if "coordination_delay_s" in spec and "report_delay_s" not in spec:
        resolved.setdefault("operating_rules", {})["coordination_delay_s"] = float(spec["coordination_delay_s"])

    grouping_used = grouping_basis or spec.get("grouping_basis")
    property_class = _infer_property_class(spec, grouping_used, is_rain)

    resolved["case_metadata"] = {
        "case_id": case_id,
        "case_type": case_type,
        "property_class": property_class,
        "uncertainty_band": band,
        "dataset_role": dataset_role,
        "random_seed": seed,
        "range_interpretation": "coverage_band",
        "is_probability_distribution": False,
        "weights_describe": "benchmark_coverage",
        "coverage_note": RANGE_COVERAGE_NOTE,
        "format_version": resolved.get("format_version", FORMAT_VERSION),
        "data_version": resolved.get("data_version"),
        "engine_version": ENGINE_VERSION,
        "search_choice_grouping_basis": grouping_used,
        "resolved_weather": {
            "rain": is_rain,
            "draw": weather_draw,
            "key": f"{seed}:weather:campus",
        },
        "shared_conditions": {
            "rain": is_rain,
            "rain_factor": rain_factor if is_rain else 1.0,
            "affected_legs": affected_legs,
        },
        "resolved_inputs": {
            "demand": demand,
            "demand_factor": demand_factor,
            "seed": seed,
            "weather": "rain" if is_rain else "clear",
            "extra_dimensions": extra_dims,
        },
        "source_records": list(resolved.get("source_records") or []),
    }
    if behavior_meta:
        resolved["case_metadata"]["resolved_inputs"]["behavior"] = behavior_meta
        resolved["case_metadata"]["resolved_inputs"]["raw_bands"] = behavior_meta["raw_bands"]
        resolved["case_metadata"]["resolved_inputs"]["selected_values"] = behavior_meta["selected_values"]
        resolved["case_metadata"]["resolved_inputs"]["keys"] = behavior_meta["keys"]
        resolved["case_metadata"]["resolved_inputs"]["provenance"] = behavior_meta["provenance"]
        for rec in behavior_meta.get("records", []):
            ev = rec.get("evidence") or {}
            resolved.setdefault("source_records", []).append({
                "id": rec.get("id"),
                "category": ev.get("category", "assumed"),
                "note": ev.get("note"),
                "ref": ev.get("ref"),
                "key": rec.get("key"),
                "selected_value": rec.get("selected_value"),
            })
        resolved["case_metadata"]["source_records"] = list(resolved.get("source_records") or [])

    if scenario_id is not None:
        resolved["case_metadata"]["scenario_id"] = str(scenario_id)
    if uncertainty_case_id is not None:
        resolved["case_metadata"]["uncertainty_case_id"] = str(uncertainty_case_id)
    for extra_key in ("evidence_id", "replay_id", "evidence_use", "relabelled_from"):
        extra_val = spec_meta.get(extra_key)
        if extra_val is None:
            extra_val = meta_in.get(extra_key)
        if extra_val is not None:
            resolved["case_metadata"][extra_key] = extra_val
    if is_gps_holdout_case(scenario) or is_gps_holdout_case(spec):
        for val in iter_case_identity_values(scenario) + iter_case_identity_values(spec):
            if val in GPS_HOLDOUT_SCENARIO_IDS:
                resolved["case_metadata"]["scenario_id"] = val
                resolved["scenario_id"] = val
                resolved.setdefault("operating_rules", {})["scenario_id"] = val
                break
    return resolved


def _normalize_policies(
    policies: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
) -> dict[str, dict]:
    policy_dict: dict[str, dict] = {}
    if isinstance(policies, Mapping):
        items = list(policies.items())
    else:
        items = [(p.get("policy_id", f"policy_{i}"), p) for i, p in enumerate(policies)]
    for pid, policy in items:
        validate_policy_information(policy)
        p_copy = copy.deepcopy(dict(policy))
        p_copy.setdefault("policy_id", pid)
        policy_dict[str(pid)] = p_copy
    return policy_dict


def _resolve_cases(
    cases: Sequence[Any],
    base_scenario: Mapping[str, Any] | None,
) -> list[dict]:
    resolved_scenarios: list[dict] = []
    seen_ids: dict[str, int] = {}
    for idx, case in enumerate(cases):
        if isinstance(case, tuple) and len(case) == 2:
            sc, spec = case
            resolved = resolve_case(sc, spec)
        elif isinstance(case, Mapping):
            if "route_stages" in case or "places" in case:
                sc_dict = copy.deepcopy(dict(case))
                if "case_metadata" not in sc_dict:
                    sc_dict["case_metadata"] = {
                        "case_id": sc_dict.get("uncertainty_case_id", sc_dict.get("scenario_id", f"case_{idx}")),
                        "case_type": "stress" if "stress" in str(sc_dict.get("scenario_id", "")).lower() else "typical",
                    }
                resolved = sc_dict
            else:
                if base_scenario is None:
                    raise SimulationError(
                        "missing_input",
                        "base_scenario required when cases are case specifications",
                    )
                resolved = resolve_case(base_scenario, case)
        else:
            raise TypeError(f"Unsupported case format: {type(case)}")

        cid = str(resolved.get("case_metadata", {}).get("case_id", f"case_{idx}"))
        if cid in seen_ids:
            seen_ids[cid] += 1
            unique_cid = f"{cid}_{seen_ids[cid]}"
            resolved["case_metadata"]["case_id"] = unique_cid
            resolved["case_metadata"]["original_case_id"] = cid
            resolved["uncertainty_case_id"] = unique_cid
        else:
            seen_ids[cid] = 1
        resolved_scenarios.append(resolved)
    return resolved_scenarios


def _case_failed(measures: Mapping[str, Any], constraints: Mapping[str, Any], scenario: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    max_late_limit = constraints.get("max_lateness_s")
    max_late = float(measures.get("max_lateness_s", 0.0))
    if max_late_limit is not None and max_late > max_late_limit:
        reasons.append(f"Max lateness {max_late:.1f}s exceeded limit {max_late_limit:.1f}s")
    elif max_late_limit is None and max_late > 0:
        if (scenario.get("operating_rules") or {}).get("lateness_hard_failure", False) or constraints.get("strict_lateness", False):
            reasons.append(f"Lateness {max_late:.1f}s violates required deadline")
    if int(measures.get("physical_violations", 0)) > 0 and not constraints.get("allow_physical_violations", False):
        reasons.append(f"{int(measures['physical_violations'])} physical violations")
    if int(measures.get("unfinished_students", 0)) > 0 and not constraints.get("allow_unfinished", False):
        reasons.append(f"{int(measures['unfinished_students'])} unfinished students")
    return reasons


def _passes_group(summary: dict, group: str) -> bool:
    bucket = summary["typical_results"] if group == "typical" else summary["stress_results"]
    if bucket["case_count"] == 0:
        return False
    failed = set(summary["failed_cases"])
    return not any(case_id in failed for case_id in bucket["cases"])


def _sensitivity(results_by_policy: Mapping[str, dict]) -> dict:
    def typical_wait(summary: dict) -> float:
        return float(summary["typical_results"].get("mean_wait_s") or 0.0)

    def stress_wait(summary: dict) -> float:
        return float(summary["stress_results"].get("worst_wait_student_s") or 0.0)

    typical_rank = sorted(
        results_by_policy.values(),
        key=lambda s: (0 if _passes_group(s, "typical") else 1, typical_wait(s), s["policy_id"]),
    )
    stress_rank = sorted(
        results_by_policy.values(),
        key=lambda s: (0 if _passes_group(s, "stress") else 1, stress_wait(s), s["policy_id"]),
    )
    preferred_typical = next((s["policy_id"] for s in typical_rank if _passes_group(s, "typical")), None)
    preferred_stress = next((s["policy_id"] for s in stress_rank if _passes_group(s, "stress")), None)
    case_winners: dict[str, str | None] = {}
    case_ids: set[str] = set()
    for summary in results_by_policy.values():
        case_ids.update(summary["typical_results"]["cases"].keys())
        case_ids.update(summary["stress_results"]["cases"].keys())
    for case_id in case_ids:
        best_id = None
        best_wait = None
        for summary in results_by_policy.values():
            measures = summary["typical_results"]["cases"].get(case_id) or summary["stress_results"]["cases"].get(case_id)
            if measures is None:
                continue
            wait = float(measures.get("total_student_waiting_student_s") or 0.0)
            failed = case_id in summary["failed_cases"]
            if failed:
                continue
            if best_wait is None or wait < best_wait:
                best_wait = wait
                best_id = summary["policy_id"]
        case_winners[case_id] = best_id
    winner_ids = {pid for pid in case_winners.values() if pid is not None}
    return {
        "preferred_by_typical": preferred_typical,
        "preferred_by_worst_stress": preferred_stress,
        "preferred_plan_changed": preferred_typical != preferred_stress,
        "rank_by_typical_wait": [s["policy_id"] for s in typical_rank],
        "rank_by_worst_stress_wait": [s["policy_id"] for s in stress_rank],
        "case_winners": case_winners,
        "assumption_changes_preferred_plan": len(winner_ids) > 1 or preferred_typical != preferred_stress,
        "note": (
            "Sensitivity lists which feasible plan wins on the base/typical cases versus the "
            "worst required stress case. A change means a plausible assumption changes the preferred plan."
        ),
        "aggregate_rule": dict(DEFAULT_AGGREGATE_RULE),
    }


def compare_policies(
    policies: Mapping[str, Mapping[str, Any]] | Sequence[Mapping[str, Any]],
    cases: Sequence[Any],
    *,
    base_scenario: Mapping[str, Any] | None = None,
    required_cases: Collection[str] | None = None,
    hard_constraints: Mapping[str, Any] | None = None,
    dataset_role: str = "development",
    claim_independent_validation: bool = False,
) -> dict:
    """Compare candidate policies across uncertainty cases.

    Typical and stress results are reported separately.
    Any policy failing a required stress case is disqualified from the feasible set,
    and all failed cases are named. Every policy is simulated on the same resolved cases.
    """
    if claim_independent_validation and dataset_role != "final_independent":
        raise SimulationError(
            "fixed_rule_violation",
            f"Cannot claim independent validation using cases with dataset_role '{dataset_role}'. "
            "Selection and development cases cannot also be claimed as independent validation.",
            field="dataset_role",
        )

    policy_dict = _normalize_policies(policies)
    resolved_scenarios = _resolve_cases(cases, base_scenario)
    all_case_ids = [sc["case_metadata"]["case_id"] for sc in resolved_scenarios]
    req_set = set(all_case_ids) if required_cases is None else set(required_cases)
    constraints = dict(hard_constraints or {})

    results_by_policy: dict[str, dict] = {}
    feasible_policies: list[str] = []
    disqualified_policies: list[str] = []

    for pid, policy in policy_dict.items():
        typical_runs: list[dict] = []
        stress_runs: list[dict] = []
        failed_cases: list[str] = []
        failure_reasons: dict[str, list[str]] = {}
        case_outputs: dict[str, dict] = {}

        for sc in resolved_scenarios:
            case_id = sc["case_metadata"]["case_id"]
            case_type = sc["case_metadata"].get("case_type", "typical")
            sim_res = simulate_case_safely(sc, policy)
            if case_id in case_outputs:
                dup_key = f"{case_id}_{len(case_outputs)}"
                case_outputs[dup_key] = sim_res
            else:
                case_outputs[case_id] = sim_res

            measures = sim_res.get("measures", {})
            reasons = simulation_failure_reasons(sim_res, constraints, sc)
            if reasons:
                failed_cases.append(case_id)
                failure_reasons.setdefault(case_id, []).extend(reasons)
            run_record = {
                "case_id": case_id,
                "case_type": case_type,
                "failed": bool(reasons),
                "reasons": reasons,
                "measures": measures,
                "accuracy_checks": sim_res.get("accuracy_checks", []),
            }
            if case_type == "stress":
                stress_runs.append(run_record)
            else:
                typical_runs.append(run_record)

        req_failures = [cid for cid in failed_cases if cid in req_set]
        is_feasible = len(req_failures) == 0
        typical_means = [r["measures"]["mean_wait_s"] for r in typical_runs]
        stress_worst = max([r["measures"]["total_student_waiting_student_s"] for r in stress_runs], default=0.0)
        stress_means = [r["measures"]["mean_wait_s"] for r in stress_runs]
        base_run = next((r for r in typical_runs if "base" in r["case_id"].lower()), typical_runs[0] if typical_runs else None)

        p_summary = {
            "policy_id": pid,
            "is_feasible": is_feasible,
            "disqualified": not is_feasible,
            "failed_cases": failed_cases,
            "failed_case_count": len(failed_cases),
            "required_failed_cases": req_failures,
            "failure_reasons": failure_reasons,
            "base_case": base_run["measures"] if base_run else None,
            "worst_case": max(stress_runs, key=lambda r: r["measures"]["total_student_waiting_student_s"])["measures"]
            if stress_runs
            else (base_run["measures"] if base_run else None),
            "typical_results": {
                "case_count": len(typical_runs),
                "mean_wait_s": sum(typical_means) / len(typical_means) if typical_means else 0.0,
                "cases": {r["case_id"]: r["measures"] for r in typical_runs},
            },
            "stress_results": {
                "case_count": len(stress_runs),
                "mean_wait_s": sum(stress_means) / len(stress_means) if stress_means else 0.0,
                "worst_wait_student_s": stress_worst,
                "cases": {r["case_id"]: r["measures"] for r in stress_runs},
            },
            "simulation_outputs": case_outputs,
            "aggregate_rule": dict(DEFAULT_AGGREGATE_RULE),
        }
        results_by_policy[pid] = p_summary
        if is_feasible:
            feasible_policies.append(pid)
        else:
            disqualified_policies.append(pid)

    return {
        "policies": results_by_policy,
        "feasible_policies": feasible_policies,
        "disqualified_policies": disqualified_policies,
        "coverage_note": RANGE_COVERAGE_NOTE,
        "weights_represent": "benchmark_coverage",
        "dataset_role": dataset_role,
        "aggregate_rule": dict(DEFAULT_AGGREGATE_RULE),
        "sensitivity": _sensitivity(results_by_policy),
        "shared_case_ids": all_case_ids,
    }
