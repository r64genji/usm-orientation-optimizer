from __future__ import annotations

import copy
from typing import Any

from operator_dashboard.contracts import (
    ALLOWED_RUN_FIELDS,
    CASE_ALIASES,
    DEFAULT_GROUP_TARGET,
    DEFAULT_OUTPUT_MODE,
    HALL_SEAT_CHOICES,
    HOLDOUT_CASE_IDS,
    LOCKED_FLEET,
    OUTPUT_MODES,
    DashboardError,
    as_int,
    as_optional_positive_int,
)
from usm_sim.cli import CASE_REGISTRY, get_case
from usm_sim.errors import SimulationError

SEATING_PLACE_IDS = ("dtsp_seating",)
FOYER_STORAGE_KEYS = ("foyer_storage_students", "exterior_storage_students")


def known_case_ids() -> list[str]:
    ids = [entry["id"] for entry in CASE_REGISTRY]
    if "whole-campus-full-cohort" not in ids:
        ids.append("whole-campus-full-cohort")
    return ids

def is_holdout_case(case_id: str) -> bool:
    return case_id in HOLDOUT_CASE_IDS or CASE_ALIASES.get(case_id, "") in {
        "restu-17sep",
        "restu-18sep-rainy",
    }


def canonical_case_id(case_id: str) -> str:
    return CASE_ALIASES.get(case_id, case_id)


def list_cases() -> list[dict[str, Any]]:
    rows = []
    for entry in CASE_REGISTRY:
        case_id = entry["id"]
        rows.append(
            {
                "id": case_id,
                "label": (
                    "Official 2026 full campus cohort (3,543 students)"
                    if case_id == "whole-campus-full-cohort"
                    else (
                        "Full realistic campus (all hostels & fleet)"
                        if case_id == "whole-campus-origins"
                        else case_id
                    )
                ),
                "is_realistic": case_id in ("whole-campus-full-cohort", "whole-campus-origins"),
                "builder": entry["builder"],
                "holdout": is_holdout_case(case_id),
                "holdout_note": (
                    "GPS holdout. You may view a labelled reference run. Search and loop cannot use this case."
                    if is_holdout_case(case_id)
                    else None
                ),
            }
        )
    rows.sort(
        key=lambda r: (
            0
            if r["id"] == "whole-campus-full-cohort"
            else (1 if r["id"] == "whole-campus-origins" else 2)
        )
    )
    return rows


def validate_run_request(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise DashboardError("Run request must be an object", field="body")
    unknown = sorted(set(body) - ALLOWED_RUN_FIELDS)
    if unknown:
        raise DashboardError(
            "Unknown fields are not allowed: " + ", ".join(unknown),
            field=unknown[0],
        )
    command = body.get("command") or "simulate"
    if command in {"search", "loop"}:
        case_hint = str(body.get("case") or "")
        if is_holdout_case(case_hint):
            raise DashboardError(
                "GPS holdout cases cannot start search or loop.",
                field="case",
            )
        raise DashboardError(
            "This dashboard cannot start search or loop.",
            field="command",
        )
    if command != "simulate":
        raise DashboardError("Only simulate runs are allowed.", field="command")
    case_raw = body.get("case")
    if not isinstance(case_raw, str) or not case_raw.strip():
        raise DashboardError("Case is required.", field="case")
    case_id = canonical_case_id(case_raw.strip())
    if case_id not in known_case_ids() and case_raw.strip() not in HOLDOUT_CASE_IDS:
        raise DashboardError(f"Unknown case: {case_raw}", field="case")
    if case_id not in known_case_ids():
        raise DashboardError(f"Unknown case: {case_raw}", field="case")
    seed = as_int(body.get("seed"), field="seed")
    if seed is None:
        raise DashboardError("Seed is required.", field="seed")
    output_mode = body.get("output_mode") or DEFAULT_OUTPUT_MODE
    if output_mode == "summary":
        output_mode = "compact"
    if output_mode not in OUTPUT_MODES:
        raise DashboardError("Output mode must be full or compact (summary).", field="output_mode")
    group_target = as_optional_positive_int(
        body.get("group_target_students"), field="group_target_students"
    )
    hall_seats = body.get("hall_seats")
    if hall_seats is not None:
        if isinstance(hall_seats, bool) or not isinstance(hall_seats, int):
            raise DashboardError("Hall seats must be 1338, 2500, or 3500.", field="hall_seats")
        if hall_seats not in HALL_SEAT_CHOICES:
            raise DashboardError("Hall seats must be 1338, 2500, or 3500.", field="hall_seats")
    apply_parameters = bool(body.get("apply_parameters"))
    if group_target is not None or hall_seats is not None:
        apply_parameters = True
    return {
        "command": "simulate",
        "case": case_id,
        "seed": seed,
        "output_mode": output_mode,
        "group_target_students": group_target,
        "hall_seats": hall_seats,
        "apply_parameters": apply_parameters,
        "holdout": is_holdout_case(case_id),
    }


def resolve_case_inputs(case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    canon_id = canonical_case_id(case_id)
    if canon_id in ("whole-campus-full-cohort", "whole-campus-origins"):
        from usm_sim.campus import build_whole_campus_full_cohort_case
        scenario, policy = build_whole_campus_full_cohort_case()
        return copy.deepcopy(scenario), copy.deepcopy(policy)
    try:
        scenario, policy = get_case(canon_id)
    except SimulationError as err:
        raise DashboardError(err.message, field="case") from err
    scenario_d = copy.deepcopy(scenario)
    policy_d = copy.deepcopy(policy)
    return scenario_d, policy_d

def apply_group_target(policy: dict[str, Any], target: int) -> None:
    grouping = dict(policy.get("grouping") or {})
    grouping["basis"] = "target_size"
    grouping["target_students"] = int(target)
    mode = grouping.get("mode")
    if mode in (None, "explicit_parts", "single_contingent"):
        grouping["mode"] = "from_source_units"
    grouping.setdefault("split_policy", "permit_supervised_split")
    grouping.setdefault("mixing_policy", "same_hostel")
    grouping.setdefault("adaptation_rule", {"type": "fixed"})
    policy["grouping"] = grouping


def apply_hall_seats(scenario: dict[str, Any], seats: int) -> None:
    dest = scenario.get("destination")
    if not isinstance(dest, dict):
        raise DashboardError(
            "This case has no hall, so hall seats cannot be changed.",
            field="hall_seats",
        )
    choice = HALL_SEAT_CHOICES[seats]
    foyer_before = dest.get("foyer_storage_students")
    road_before = dest.get("exterior_storage_students")
    dest["available_seats"] = int(seats)
    dest["available_seats_status"] = choice["status"]
    dest["foyer_storage_students"] = foyer_before
    dest["exterior_storage_students"] = road_before
    seating_id = dest.get("seating_place_id") or "dtsp_seating"
    initial = int(dest.get("initial_occupants") or 0)
    reserved = int(dest.get("reserved_seating") or 0)
    seating_capacity = int(seats) - initial - reserved
    if seating_capacity < 0:
        raise DashboardError(
            "Hall seats cannot be below initial occupants plus reserved seats.",
            field="hall_seats",
        )
    for place in scenario.get("places") or []:
        if not isinstance(place, dict):
            continue
        if place.get("id") == seating_id or place.get("id") in SEATING_PLACE_IDS:
            place["capacity_students"] = seating_capacity
            extra_limit = place.get("operating_limit_students")
            if extra_limit is not None:
                place["operating_limit_students"] = seating_capacity
    assumptions = list(scenario.get("uncertain_assumptions") or [])
    assumptions.append(
        {
            "id": "dashboard_hall_seats",
            "value": int(seats),
            "unit": "seats",
            "category": "assumed",
            "label": choice["label"],
            "note": (
                f"{choice['note']} Foyer and road waiting space stay unchanged "
                f"(foyer={foyer_before}, road={road_before})."
            ),
        }
    )
    scenario["uncertain_assumptions"] = assumptions


def apply_allowed_overrides(
    scenario: dict[str, Any],
    policy: dict[str, Any],
    request: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario_d = copy.deepcopy(scenario)
    policy_d = copy.deepcopy(policy)
    from usm_sim.validate import is_operational_profile
    is_op = is_operational_profile(scenario_d) or (request.get("case") in ("whole-campus-full-cohort", "whole-campus-origins"))
    if not request.get("apply_parameters"):
        if is_op:
            _assert_fleet_locked(scenario_d)
        return scenario_d, policy_d
    group_target = request.get("group_target_students")
    if group_target is not None:
        apply_group_target(policy_d, int(group_target))
        assumptions = list(scenario_d.get("uncertain_assumptions") or [])
        assumptions.append(
            {
                "id": "dashboard_group_target",
                "value": int(group_target),
                "unit": "students",
                "category": "assumed",
                "note": f"Operator group target size {group_target}. Default is {DEFAULT_GROUP_TARGET}.",
            }
        )
        scenario_d["uncertain_assumptions"] = assumptions
    hall_seats = request.get("hall_seats")
    if hall_seats is not None:
        apply_hall_seats(scenario_d, int(hall_seats))
    _assert_fleet_locked(scenario_d)
    _assert_storage_unchanged(scenario, scenario_d, request)
    return scenario_d, policy_d


def _assert_fleet_locked(scenario: dict[str, Any]) -> None:
    vehicles = (scenario.get("initial_state") or {}).get("vehicles") or []
    if not vehicles:
        return
    n = len(vehicles)
    if n != LOCKED_FLEET["n_buses"]:
        raise DashboardError(
            "Fleet size is locked at 8 buses.",
            field="fleet",
        )
    n_coach = sum(1 for v in vehicles if v.get("type") == "coach")
    n_electric = sum(1 for v in vehicles if v.get("type") == "electric")
    if n_coach != LOCKED_FLEET["n_coach"] or n_electric != LOCKED_FLEET["n_electric"]:
        raise DashboardError(
            "Fleet mix is locked at 5 coaches and 3 electric buses.",
            field="fleet",
        )
    for v in vehicles:
        doors = v.get("usable_doors")
        if doors is not None and doors != LOCKED_FLEET["usable_doors"]:
            raise DashboardError(
                "Vehicles must have exactly 1 usable door.",
                field="doors",
            )
    for vt in scenario.get("vehicle_types") or []:
        doors = vt.get("usable_doors")
        if doors is not None and doors != LOCKED_FLEET["usable_doors"]:
            raise DashboardError(
                "Vehicles must have exactly 1 usable door.",
                field="doors",
            )
    dest = scenario.get("destination") or {}
    if dest.get("bag_check") or dest.get("security_service"):
        raise DashboardError(
            "DTSP entry must have zero door checks.",
            field="destination",
        )
    for key in ("screening_dwell_s", "screening_dwell", "screening_s_per_person", "check_dwell_s"):
        val = dest.get(key)
        if val is not None and val > 0:
            raise DashboardError(
                "DTSP entry must have zero screening dwell.",
                field="destination",
            )
    for door in dest.get("doors") or []:
        if door.get("bag_check") or door.get("security_service"):
            raise DashboardError(
                "DTSP entry doors must have zero door checks.",
                field="destination",
            )
        for key in ("screening_dwell_s", "screening_dwell", "screening_s_per_person", "check_dwell_s"):
            val = door.get(key)
            if val is not None and val > 0:
                raise DashboardError(
                    "DTSP entry doors must have zero screening dwell.",
                    field="destination",
                )

def _assert_storage_unchanged(
    original: dict[str, Any],
    updated: dict[str, Any],
    request: dict[str, Any],
) -> None:
    if request.get("hall_seats") is None:
        return
    old_dest = original.get("destination") or {}
    new_dest = updated.get("destination") or {}
    for key in FOYER_STORAGE_KEYS:
        if old_dest.get(key) != new_dest.get(key):
            raise DashboardError(
                "Hall seat choice cannot change foyer or road waiting space.",
                field="hall_seats",
            )


def build_input_payload(request: dict[str, Any]) -> dict[str, Any]:
    scenario, policy = resolve_case_inputs(request["case"])
    scenario, policy = apply_allowed_overrides(scenario, policy, request)
    policy = dict(policy)
    policy["random_seed"] = int(request["seed"])
    return {"scenario": scenario, "policy": policy, "request": dict(request)}
