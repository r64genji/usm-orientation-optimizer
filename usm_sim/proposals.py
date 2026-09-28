"""Public Check a proposal operation.

A human-written proposal is enough. This module does not call an AI service.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from usm_sim.behavior import ALL_PHENOMENON_FAMILIES
from usm_sim.constants import (
    ADAPTATION_TYPES,
    BEHAVIOR_ACTIONS,
    CONDITION_KINDS,
    DESTINATION_SPACE_RULES,
    ENGINE_VERSION,
    FORBIDDEN_MODES,
    GROUPING_BASES,
    SOFTWARE_REVISION,
    VEHICLE_DISPATCH_RULES,
)
from usm_sim.errors import SimulationError
from usm_sim.grouping import apply_grouping, needs_materialize
from usm_sim.validate import is_operational_profile, validate_inputs

PROPOSAL_FIELD_ALIASES = {
    "proposal_id": ("proposal_id", "id"),
    "grouping": ("grouping",),
    "regroup_policy": ("regroup_policy",),
    "release_rule": ("release_rule",),
    "counting": ("counting", "count_placement"),
    "worker_allocation": ("worker_allocation", "workers"),
    "vehicle_dispatch_rule": ("vehicle_dispatch_rule", "bus_dispatch"),
    "destination_rule": ("destination_rule", "destination_arrangement"),
    "fixed_choices": ("fixed_choices", "fixed"),
    "tunable": ("tunable", "tunable_choices"),
    "assumptions": ("assumptions",),
}

PROTECTED_FACT_KEYS = frozenset(
    {
        "resident_occupancy",
        "estimated_occupancy",
        "estimated_attendance",
        "resolved_attendance",
        "expected_event_attendance",
        "registration",
        "physical_capacity_students",
        "physical_capacity_vehicles",
        "capacity_students",
        "measured_facts",
        "occupancy",
        "attendance",
    }
)

SCENARIO_OWNED_BLOCKS = (
    "hostels",
    "source_units",
    "places",
    "route_legs",
    "route_stages",
    "measured_facts",
    "operating_rules",
    "checkpoints",
)

SCENARIO_OWNED_RULES = (
    "required_checkpoints",
    "required_endpoint",
    "route_id",
    "direct_walk_permitted",
    "min_station_staff",
    "staffing_ratio",
    "escorts_per_group",
    "min_escorts_per_group",
    "permitted_counting_locations",
    "permitted_count_methods",
    "ppsl_total_reference",
    "worker_budget",
    "bus_budget",
)

FORBIDDEN_INFORMATION = frozenset(
    {
        "hidden_attendance",
        "actual_attendance",
        "resolved_attendance",
        "actual_future",
        "future_events",
        "actual_future_events",
        "future_weather",
        "future_travel_times",
        "unreported_bus_failure",
        "actual_readiness",
        "simulator_hidden_state",
        "hidden_state",
        "hidden_future",
        "future_arrivals",
        "future_arrival",
        "hidden_no_shows",
        "hidden_no_show",
        "hidden_no_show_truth",
        "no_show_truth",
        "oracle_schedule",
        "oracle",
        "actual_no_shows",
    }
)

ALLOWED_INFORMATION = frozenset(
    {
        "delivered_report",
        "delivered_reports",
        "declared_forecast",
        "forecast",
        "announced_schedule",
        "schedule",
        "reported_readiness",
        "count_outcome",
        "count_outcomes",
        "resource_availability",
    }
)

INFORMATION_SOURCE_KEYS = frozenset(
    {
        "information",
        "information_source",
        "observes",
        "observe",
        "knowledge",
        "based_on",
        "signal",
        "reads",
        "read",
        "key_off",
        "keys_off",
    }
)

GROUPING_SIZE_KEYS = frozenset(
    {
        "target_students",
        "min_students",
        "max_students",
        "units_per_group",
    }
)

FUTURE_FLAGS = (
    "uses_hidden_attendance",
    "uses_future",
    "uses_actual_future",
    "inspect_hidden_attendance",
    "uses_unreported_failure",
    "uses_future_readiness",
    "uses_future_weather",
    "uses_actual_attendance",
    "uses_future_arrivals",
    "uses_hidden_no_shows",
    "uses_hidden_no_show_truth",
    "uses_oracle_schedule",
    "uses_future_travel_times",
    "future_arrivals",
    "future_arrival",
    "hidden_no_shows",
    "hidden_no_show",
    "hidden_no_show_truth",
    "no_show_truth",
    "oracle_schedule",
    "oracle",
    "actual_no_shows",
)
AUTO_COUNT_FLAGS = (
    "auto_count",
    "auto_count_on_create",
    "count_on_create",
    "count_on_split",
    "introduce_manual_count",
)

DURATION_KEYS = frozenset(
    {
        "duration_s",
        "travel_s",
        "wait_s",
        "maximum_assembly_wait_s",
        "assembly_duration_s",
        "assembly_time_s",
        "interval_s",
        "coordination_delay_s",
        "min_hold_duration_s",
        "available_time_s",
        "wait_limit_s",
        "max_wait_s",
        "maximum_wait_s",
        "hold_limit_s",
        "max_hold_s",
        "maximum_hold_s",
        "hold_s",
        "hold_bus_limit_s",
    }
)


def call_ai(*_args: Any, **_kwargs: Any) -> None:
    """Never used. Human-written proposals do not need an AI service."""
    raise RuntimeError("proposal checks do not call an AI service")


def check(proposal, scenario_rules, layout_assumptions=None, permitted_decisions=None):
    """Alias for check_proposal."""
    return check_proposal(
        proposal,
        scenario_rules,
        layout_assumptions,
        permitted_decisions,
    )


def check_proposal(
    proposal: Mapping[str, Any] | None,
    scenario_rules: Mapping[str, Any] | None,
    layout_assumptions: Mapping[str, Any] | list | None = None,
    permitted_decisions: Mapping[str, Any] | None = None,
) -> dict:
    """Check a structured operating proposal against scenario fixed rules.

    Returns a valid policy and search space, or structured errors. Does not
    call an AI service.
    """
    try:
        return _check_proposal(
            proposal, scenario_rules, layout_assumptions, permitted_decisions
        )
    except SimulationError as error:
        payload = error.as_dict()
        return _reject([payload])


def _check_proposal(
    proposal: Mapping[str, Any] | None,
    scenario_rules: Mapping[str, Any] | None,
    layout_assumptions: Mapping[str, Any] | list | None,
    permitted_decisions: Mapping[str, Any] | None,
) -> dict:
    missing = _missing_top_level(proposal, scenario_rules)
    if missing:
        return _reject(missing)

    proposal_d = copy.deepcopy(dict(proposal))
    scenario_d = copy.deepcopy(dict(scenario_rules))
    layout_d = _normalize_layout(layout_assumptions)
    permitted_d = dict(permitted_decisions) if isinstance(permitted_decisions, Mapping) else {}

    resolved = _resolve_proposal_fields(proposal_d)
    _require_proposal_fields(resolved)
    _validate_units_and_ranges(resolved, permitted_d)
    _reject_protected_overrides(proposal_d, scenario_d)
    _reject_rule_overrides(resolved, scenario_d)
    _reject_forbidden_modes(proposal_d)
    _reject_rst_override(proposal_d, resolved, scenario_d)
    _reject_operational_proposal_violations(proposal_d, resolved, scenario_d)
    _reject_auto_count(resolved["grouping"])
    _reject_hidden_or_future_information(proposal_d)
    _reject_unlabelled_external_assumptions(resolved["assumptions"], scenario_d)
    _apply_layout_assumptions(scenario_d, layout_d)
    _check_references(resolved, scenario_d)
    _check_behavior_responses(resolved, scenario_d, permitted_d)
    _check_worker_travel(resolved["worker_allocation"], scenario_d)
    _check_regrouping(resolved, scenario_d)
    _check_grouping_basis_allowed(resolved["grouping"], permitted_d)
    _validate_space_and_dispatch_rules(resolved)

    policy = _policy_from_proposal(resolved, scenario_d)
    if layout_d:
        policy["layout_assumptions"] = copy.deepcopy(layout_d)
    grouping_summary = None
    work_scenario = copy.deepcopy(scenario_d)
    work_policy = copy.deepcopy(policy)
    if needs_materialize(work_policy):
        grouping_summary = apply_grouping(work_scenario, work_policy)
        _assert_no_automatic_count(grouping_summary)
    work_scenario, work_policy = validate_inputs(work_scenario, work_policy)
    search_space = _build_search_space(resolved, scenario_d, permitted_d)
    if grouping_summary is None:
        grouping_summary = {
            "basis": (resolved["grouping"] or {}).get("basis"),
            "groups": [],
            "headcounts_added": 0,
            "worker_assignments_added": 0,
            "setup_delay_s": 0,
            "coordination_actions_added": 0,
            "count_actions_added": 0,
            "layout_status": _layout_status(scenario_d),
        }
    grouping_view = {
        key: value
        for key, value in grouping_summary.items()
        if key != "source_units"
    }
    grouping_view.setdefault("headcounts_added", 0)
    grouping_view.setdefault("count_actions_added", 0)
    return {
        "accepted": True,
        "policy": policy,
        "layout_assumptions": copy.deepcopy(layout_d),
        "search_space": search_space,
        "assumptions": list(resolved["assumptions"]),
        "versions": {
            "format_version": scenario_d.get("format_version"),
            "data_version": scenario_d.get("data_version"),
            "software_revision": SOFTWARE_REVISION,
            "engine_version": ENGINE_VERSION,
        },
        "source_scenario": {
            "scenario_id": scenario_d.get("scenario_id"),
            "format_version": scenario_d.get("format_version"),
            "data_version": scenario_d.get("data_version"),
            "uncertainty_case_id": scenario_d.get("uncertainty_case_id"),
        },
        "grouping": grouping_view,
        "layout_status": grouping_view.get("layout_status") or _layout_status(scenario_d),
        "fixed_decisions": search_space["fixed_decisions"],
        "allowed_values": search_space["allowed_values"],
        "numerical_bounds": search_space["numerical_bounds"],
    }


def _reject(errors: list[dict]) -> dict:
    first = errors[0] if errors else {
        "error": True,
        "category": "missing_input",
        "message": "proposal check failed",
    }
    payload = {
        "accepted": False,
        "error": True,
        "category": first.get("category"),
        "message": first.get("message"),
        "errors": errors,
    }
    if first.get("field") is not None:
        payload["field"] = first["field"]
    if first.get("details"):
        payload["details"] = first["details"]
    return payload


def _missing_top_level(proposal, scenario_rules) -> list[dict]:
    errors: list[dict] = []
    if proposal is None:
        errors.append(
            SimulationError(
                "missing_input",
                "Missing critical input: proposal",
                field="proposal",
            ).as_dict()
        )
        return errors
    if not isinstance(proposal, Mapping):
        errors.append(
            SimulationError(
                "invalid_value_or_unit",
                "proposal must be an object",
                field="proposal",
            ).as_dict()
        )
        return errors
    if scenario_rules is None:
        errors.append(
            SimulationError(
                "missing_input",
                "Missing critical input: scenario_rules",
                field="scenario_rules",
            ).as_dict()
        )
        return errors
    if not isinstance(scenario_rules, Mapping):
        errors.append(
            SimulationError(
                "invalid_value_or_unit",
                "scenario_rules must be an object",
                field="scenario_rules",
            ).as_dict()
        )
    return errors


def _normalize_layout(layout_assumptions) -> dict:
    if layout_assumptions is None:
        return {}
    if isinstance(layout_assumptions, list):
        return {"source_units": list(layout_assumptions), "layout_status": "estimated"}
    if not isinstance(layout_assumptions, Mapping):
        raise SimulationError(
            "invalid_value_or_unit",
            "layout_assumptions must be an object or a source-unit list",
            field="layout_assumptions",
        )
    return dict(layout_assumptions)


def _resolve_proposal_fields(proposal: dict) -> dict:
    resolved = {}
    for canonical, aliases in PROPOSAL_FIELD_ALIASES.items():
        value = None
        for alias in aliases:
            if alias in proposal and proposal[alias] is not None:
                value = proposal[alias]
                break
        resolved[canonical] = value
    grouping = resolved["grouping"]
    if resolved["regroup_policy"] is None and isinstance(grouping, Mapping):
        if grouping.get("regroup_policy") is not None:
            resolved["regroup_policy"] = grouping.get("regroup_policy")
    if resolved["counting"] is not None and not isinstance(resolved["counting"], Mapping):
        raise SimulationError(
            "invalid_value_or_unit",
            "counting must be an object with placement and method",
            field="proposal.counting",
        )
    for opt_key in (
        "space_control",
        "destination_space_rule",
        "coordination_delay_s",
        "adaptation_rule",
        "behavior_response",
    ):
        val = proposal.get(opt_key)
        if val is None and isinstance(proposal.get("release_rule"), Mapping):
            val = proposal["release_rule"].get(opt_key)
        if val is None and isinstance(proposal.get("fixed_choices"), Mapping):
            val = proposal["fixed_choices"].get(opt_key)
        if val is None and opt_key == "adaptation_rule" and isinstance(grouping, Mapping):
            val = grouping.get("adaptation_rule")
        if val is None and opt_key == "behavior_response":
            val = (
                proposal.get("behavior")
                or (proposal.get("fixed_choices") or {}).get("behavior")
            )
        resolved[opt_key] = val
    for claim_key in ("handles_case", "behavior_case_id", "claims_to_handle"):
        if claim_key in proposal:
            resolved[claim_key] = proposal[claim_key]
    return resolved


def _require_proposal_fields(resolved: dict) -> None:
    for field in PROPOSAL_FIELD_ALIASES:
        value = resolved.get(field)
        if value is None or value == "":
            raise SimulationError(
                "missing_input",
                f"Missing critical input: proposal.{field}",
                field=f"proposal.{field}",
            )
    grouping = resolved["grouping"]
    if not isinstance(grouping, Mapping):
        raise SimulationError(
            "invalid_value_or_unit",
            "proposal.grouping must be an object",
            field="proposal.grouping",
        )
    for field in (
        "regroup_policy",
        "release_rule",
        "counting",
        "worker_allocation",
        "vehicle_dispatch_rule",
        "destination_rule",
        "fixed_choices",
        "tunable",
    ):
        if not isinstance(resolved[field], Mapping):
            raise SimulationError(
                "invalid_value_or_unit",
                f"proposal.{field} must be an object",
                field=f"proposal.{field}",
            )
    if not isinstance(resolved["assumptions"], list):
        raise SimulationError(
            "invalid_value_or_unit",
            "proposal.assumptions must be a list",
            field="proposal.assumptions",
        )
    grouping_d = dict(grouping)
    regroup = dict(resolved["regroup_policy"])
    grouping_d.setdefault("regroup_policy", regroup)
    resolved["grouping"] = grouping_d
    counting = dict(resolved["counting"])
    counting.setdefault("assignments", counting.get("assignments") or {})
    if "placement" not in counting:
        counting["placement"] = "assigned" if counting.get("assignments") else "none"
    resolved["counting"] = counting


def _validate_units_and_ranges(resolved: dict, permitted: dict) -> None:
    _scan_values(resolved, "proposal")
    tunable = resolved["tunable"]
    permitted_bounds = {}
    if isinstance(permitted.get("numerical_bounds"), Mapping):
        permitted_bounds = dict(permitted["numerical_bounds"])
    for field_name, spec in tunable.items():
        allowed_values = _allowed_from_spec(spec)
        if allowed_values is not None:
            for item in allowed_values:
                if field_name.endswith("basis") and item not in GROUPING_BASES:
                    raise SimulationError(
                        "unsupported_policy",
                        f"unsupported grouping basis {item!r}",
                        field=f"proposal.tunable.{field_name}",
                    )
        bounds = _bounds_from_spec(spec, f"proposal.tunable.{field_name}")
        if bounds is None:
            continue
        lower, upper = bounds
        if lower > upper:
            raise SimulationError(
                "invalid_value_or_unit",
                f"{field_name} lower bound cannot exceed upper bound",
                field=f"proposal.tunable.{field_name}",
            )
        unit = _explicit_unit(spec, f"proposal.tunable.{field_name}")
        allowed = permitted_bounds.get(field_name)
        if not isinstance(allowed, Mapping):
            continue
        allowed_bounds = _bounds_from_spec(
            allowed, f"permitted_decisions.numerical_bounds.{field_name}"
        )
        if allowed_bounds is None:
            continue
        allowed_lower, allowed_upper = allowed_bounds
        if lower < allowed_lower or upper > allowed_upper:
            raise SimulationError(
                "invalid_value_or_unit",
                f"{field_name} bounds are outside the permitted range",
                field=f"proposal.tunable.{field_name}",
            )
        allowed_unit = allowed.get("unit")
        if allowed_unit not in (None, "") and unit != allowed_unit:
            raise SimulationError(
                "invalid_value_or_unit",
                f"{field_name} unit {unit!r} is incompatible with "
                f"permitted unit {allowed_unit!r}",
                field=f"proposal.tunable.{field_name}.unit",
            )
    behavior_response = resolved.get("behavior_response")
    if behavior_response is not None:
        _validate_behavior_limits(behavior_response, permitted)


def _bounds_from_spec(spec: Any, field: str) -> tuple[float, float] | None:
    if not isinstance(spec, Mapping):
        return None
    if "lower" in spec or "upper" in spec:
        if "lower" not in spec or "upper" not in spec:
            raise SimulationError(
                "missing_input",
                f"{field} needs both lower and upper",
                field=field,
            )
        lower = _finite_number(spec["lower"], f"{field}.lower")
        upper = _finite_number(spec["upper"], f"{field}.upper")
        return lower, upper
    if "min" in spec or "max" in spec:
        lower = _finite_number(spec.get("min"), f"{field}.min")
        upper = _finite_number(spec.get("max"), f"{field}.max")
        return lower, upper
    span = spec.get("bounds")
    if isinstance(span, (list, tuple)) and len(span) == 2:
        return (
            _finite_number(span[0], f"{field}.bounds[0]"),
            _finite_number(span[1], f"{field}.bounds[1]"),
        )
    return None


def _explicit_unit(spec: Mapping, field: str) -> str:
    unit = spec.get("unit")
    if unit in (None, ""):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} bounds need an explicit unit",
            field=f"{field}.unit",
        )
    if not isinstance(unit, str):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} unit must be a string",
            field=f"{field}.unit",
        )
    return unit


def _allowed_from_spec(spec: Any) -> list | None:
    if not isinstance(spec, Mapping):
        return None
    allowed = spec.get("allowed") or spec.get("values")
    if allowed is None:
        return None
    if not isinstance(allowed, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "allowed values must be a list",
            field="proposal.tunable",
        )
    return list(allowed)


def _scan_values(value: Any, path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in DURATION_KEYS or str(key).endswith("_s"):
                if item is not None and not isinstance(item, (list, tuple, dict)):
                    _finite_nonneg_number(item, child)
            if key in {
                "count",
                "worker_count",
                "bus_count",
                "units_per_group",
                "target_students",
                "min_students",
                "max_students",
                "escorts_per_group",
            }:
                if item is not None and not isinstance(item, (list, tuple, dict)):
                    _nonneg_int(item, child)
            if key in {"server_count", "usable_doors"} and item is not None:
                if isinstance(item, int) and not isinstance(item, bool) and item < 1:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"{child} used for active service must be a positive integer",
                        field=child,
                    )
            _scan_values(item, child)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_values(item, f"{path}[{index}]")


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be a finite number",
            field=field,
        )
    if not math.isfinite(value):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be a finite number",
            field=field,
        )
    return float(value)


def _finite_nonneg_number(value: Any, field: str) -> float:
    number = _finite_number(value, field)
    if number < 0:
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field} must be a finite nonnegative number",
            field=field,
        )
    return number


def _nonneg_int(value: Any, field: str) -> int:
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


def _reject_protected_overrides(proposal: dict, scenario: dict) -> None:
    for block in SCENARIO_OWNED_BLOCKS:
        if block in proposal:
            raise SimulationError(
                "fixed_rule_violation",
                f"a proposal cannot change {block} through decision fields",
                field=f"proposal.{block}",
            )
    for path, key, _value in _walk(proposal, "proposal"):
        if not _is_protected_key(path, key):
            continue
        leaf = key.rsplit(".", 1)[-1]
        if "tunable" in path and leaf in GROUPING_SIZE_KEYS:
            continue
        if path.startswith("proposal.grouping") and leaf in GROUPING_SIZE_KEYS:
            continue
        raise SimulationError(
            "fixed_rule_violation",
            f"a proposal cannot change occupancy, attendance, measured facts, "
            f"route physics, or physical capacities through {path}",
            field=path,
        )


def _is_protected_key(path: str, key: str) -> bool:
    leaf = key.rsplit(".", 1)[-1]
    if key in PROTECTED_FACT_KEYS or leaf in PROTECTED_FACT_KEYS:
        return True
    if leaf in {
        "capacity_students",
        "physical_capacity_students",
        "physical_capacity_vehicles",
    }:
        return True
    if leaf == "duration_s" and (
        "route_leg" in path or "walking_route" in path or "places" in path
    ):
        return True
    return False


def _reject_rule_overrides(resolved: dict, scenario: dict) -> None:
    operating = dict(scenario.get("operating_rules") or {})
    counting = resolved["counting"]
    required = list(operating.get("required_checkpoints") or [])
    copied = counting.get("required_checkpoints")
    assignments = counting.get("assignments")
    if required:
        if copied == []:
            raise SimulationError(
                "fixed_rule_violation",
                "policy cannot drop a required checkpoint",
                field="proposal.counting.required_checkpoints",
            )
        if isinstance(copied, list) and set(required) - set(copied):
            raise SimulationError(
                "fixed_rule_violation",
                "policy cannot drop a required checkpoint",
                field="proposal.counting.required_checkpoints",
            )
        if assignments == {} or assignments is None:
            raise SimulationError(
                "fixed_rule_violation",
                "policy cannot omit or empty required checkpoint assignments",
                field="proposal.counting.assignments",
            )
        if isinstance(assignments, Mapping):
            missing = [cid for cid in required if cid not in assignments]
            if missing:
                raise SimulationError(
                    "fixed_rule_violation",
                    f"policy dropped required checkpoint {missing[0]!r}",
                    field="proposal.counting.assignments",
                )
    fixed = resolved["fixed_choices"]
    scenario_endpoint = operating.get("required_endpoint")
    offered_endpoint = fixed.get("required_endpoint")
    if (
        offered_endpoint not in (None, "", scenario_endpoint)
        and scenario_endpoint is not None
    ):
        raise SimulationError(
            "fixed_rule_violation",
            "proposal cannot override scenario.operating_rules.required_endpoint",
            field="proposal.fixed_choices.required_endpoint",
        )
    for key in SCENARIO_OWNED_RULES:
        if key in fixed and key in operating and fixed[key] != operating[key]:
            if key == "direct_walk_permitted" and fixed[key]:
                raise SimulationError(
                    "fixed_rule_violation",
                    "proposal cannot override the scenario route rule",
                    field=f"proposal.fixed_choices.{key}",
                )
            if key != "required_endpoint":
                raise SimulationError(
                    "fixed_rule_violation",
                    f"proposal cannot override scenario-owned {key}",
                    field=f"proposal.fixed_choices.{key}",
                )
    staffing = resolved["worker_allocation"]
    budget = operating.get("worker_budget")
    count = staffing.get("count")
    if budget is not None and count is not None and int(count) > int(budget):
        raise SimulationError(
            "fixed_rule_violation",
            "proposal worker count exceeds the scenario worker budget",
            field="proposal.worker_allocation.count",
        )
    bus_budget = operating.get("bus_budget")
    bus_count = resolved["vehicle_dispatch_rule"].get("bus_count")
    if bus_budget is not None and bus_count is not None and int(bus_count) > int(bus_budget):
        raise SimulationError(
            "fixed_rule_violation",
            "proposal bus count exceeds the scenario bus budget",
            field="proposal.vehicle_dispatch_rule.bus_count",
        )


def _reject_forbidden_modes(proposal: dict) -> None:
    for path, _key, value in _walk(proposal, "proposal"):
        if isinstance(value, str) and value in FORBIDDEN_MODES:
            raise SimulationError(
                "unsupported_policy",
                f"Forbidden process or route mode {value!r} is not in this model",
                field=path,
            )


def _reject_rst_override(proposal: dict, resolved: dict, scenario: dict) -> None:
    operating = dict(scenario.get("operating_rules") or {})
    if proposal.get("direct_walk_permitted") or (
        isinstance(proposal.get("operating_rules"), Mapping)
        and proposal["operating_rules"].get("direct_walk_permitted")
    ):
        raise SimulationError(
            "fixed_rule_violation",
            "proposal cannot permit direct walking off the fixed RST route",
            field="proposal.direct_walk_permitted",
        )
    if operating.get("route_id") == "rst_fixed_bus_chain":
        offered_route = resolved["fixed_choices"].get("route_id")
        if offered_route not in (None, "", "rst_fixed_bus_chain"):
            raise SimulationError(
                "fixed_rule_violation",
                "proposal cannot replace the fixed RST bus route",
                field="proposal.fixed_choices.route_id",
            )


def _reject_operational_proposal_violations(proposal: dict, resolved: dict, scenario: dict) -> None:
    if not is_operational_profile(scenario):
        return

    dispatch = resolved.get("vehicle_dispatch_rule") or {}
    if isinstance(dispatch, Mapping):
        bus_count = dispatch.get("bus_count")
        if bus_count is not None and int(bus_count) != 8:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot change bus count to {bus_count}; fleet is locked at 8 buses",
                field="proposal.vehicle_dispatch_rule.bus_count",
            )
        n_buses = dispatch.get("n_buses")
        if n_buses is not None and int(n_buses) != 8:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot change fleet size to {n_buses}; fleet is locked at 8 buses",
                field="proposal.vehicle_dispatch_rule.n_buses",
            )
        n_coach = dispatch.get("n_coach")
        if n_coach is not None and int(n_coach) != 5:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot alter coach count to {n_coach}; locked at 5 coaches",
                field="proposal.vehicle_dispatch_rule.n_coach",
            )
        n_electric = dispatch.get("n_electric")
        if n_electric is not None and int(n_electric) != 3:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot alter electric bus count to {n_electric}; locked at 3 electric buses",
                field="proposal.vehicle_dispatch_rule.n_electric",
            )
        doors = dispatch.get("usable_doors")
        if doors is not None and int(doors) != 1:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot change usable doors per bus to {doors}; locked at 1 door",
                field="proposal.vehicle_dispatch_rule.usable_doors",
            )

    dest_rule = resolved.get("destination_rule") or {}
    if isinstance(dest_rule, Mapping):
        if dest_rule.get("bag_check") or dest_rule.get("security_service"):
            raise SimulationError(
                "fixed_rule_violation",
                "operational proposal cannot introduce door screening or checks at DTSP",
                field="proposal.destination_rule",
            )
        for key in ("screening_dwell_s", "screening_dwell", "screening_s_per_person", "check_dwell_s"):
            val = dest_rule.get(key)
            if val is not None and val > 0:
                raise SimulationError(
                    "fixed_rule_violation",
                    f"operational proposal cannot introduce screening dwell at DTSP ({key}={val})",
                    field=f"proposal.destination_rule.{key}",
                )

    counting = resolved.get("counting") or {}
    assignments = counting.get("assignments") or {}
    if isinstance(assignments, Mapping):
        for cid, assign in assignments.items():
            if isinstance(assign, Mapping):
                loc = assign.get("location_id")
                if loc in {"dtsp_door_a", "dtsp_door_b", "dtsp_door_c", "dtsp_door_d", "door_a", "door_b", "door_c", "door_d", "dtsp_hall_reference"}:
                    raise SimulationError(
                        "fixed_rule_violation",
                        f"operational proposal cannot place headcount or check at DTSP entrance door {loc!r}; zero door checks permitted",
                        field=f"proposal.counting.assignments.{cid}.location_id",
                    )

    for path, key, value in _walk(proposal, "proposal"):
        leaf = key.rsplit(".", 1)[-1]
        if leaf in {"n_buses", "bus_count", "fleet_size"} and value is not None and value != 8:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot change fleet size through {path}",
                field=path,
            )
        if leaf in {"n_coach", "n_coaches"} and value is not None and value != 5:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot change coach count through {path}",
                field=path,
            )
        if leaf in {"n_electric"} and value is not None and value != 3:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot change electric bus count through {path}",
                field=path,
            )
        if leaf in {"usable_doors"} and value is not None and value != 1:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot change usable doors through {path}",
                field=path,
            )
        if leaf in {"bag_check", "security_service"} and value:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot enable {leaf} through {path}",
                field=path,
            )
        if leaf in {"screening_dwell_s", "screening_dwell", "screening_s_per_person", "check_dwell_s"} and isinstance(value, (int, float)) and value > 0:
            raise SimulationError(
                "fixed_rule_violation",
                f"operational proposal cannot introduce screening dwell through {path}",
                field=path,
            )

def _reject_auto_count(grouping: Mapping) -> None:
    for flag in AUTO_COUNT_FLAGS:
        if grouping.get(flag):
            raise SimulationError(
                "fixed_rule_violation",
                "creating or splitting a group does not automatically introduce a manual count",
                field=f"proposal.grouping.{flag}",
            )


def _reject_hidden_or_future_information(proposal: dict) -> None:
    for path, key, value in _walk(proposal, "proposal"):
        if key in FUTURE_FLAGS and value:
            raise SimulationError(
                "unsupported_policy",
                "control rules cannot inspect hidden attendance or actual future events",
                field=path,
            )
        if (
            isinstance(key, str)
            and any(
                term in key.lower()
                for term in ("future_arrival", "hidden_no_show", "oracle_schedule", "no_show_truth")
            )
            and value
        ):
            raise SimulationError(
                "unsupported_policy",
                "control rules cannot inspect hidden attendance or actual future events",
                field=path,
            )
        if isinstance(value, str):
            val_norm = value.strip().lower().replace("-", "_").replace(" ", "_")
            if (
                val_norm in FORBIDDEN_INFORMATION
                or any(
                    term in val_norm
                    for term in (
                        "future_arrival",
                        "hidden_no_show",
                        "oracle_schedule",
                        "no_show_truth",
                        "future_travel_time",
                        "actual_attendance",
                    )
                )
            ):
                if key not in {"description", "notes", "evidence_ref", "observation_ref"}:
                    raise SimulationError(
                        "unsupported_policy",
                        "control rules cannot inspect hidden attendance, future arrivals, or oracle information",
                        field=path,
                    )
        if key not in INFORMATION_SOURCE_KEYS or not isinstance(value, str):
            continue
        if value in {"", "none"} or value in ALLOWED_INFORMATION:
            continue
        if value in FORBIDDEN_INFORMATION or "future" in value or "hidden" in value or "oracle" in value:
            raise SimulationError(
                "unsupported_policy",
                "control rules cannot inspect hidden attendance or actual future events",
                field=path,
            )
        raise SimulationError(
            "unsupported_policy",
            "control rules can use delivered reports and declared forecasts only",
            field=path,
        )


def _reject_unlabelled_external_assumptions(assumptions: list, scenario: dict) -> None:
    current_id = scenario.get("scenario_id")
    for index, raw in enumerate(assumptions):
        if not isinstance(raw, Mapping):
            raise SimulationError(
                "invalid_value_or_unit",
                "each assumption must be an object",
                field=f"proposal.assumptions[{index}]",
            )
        kind = raw.get("kind")
        changes = bool(raw.get("changes_external_conditions"))
        if kind in CONDITION_KINDS:
            changes = True
        if raw.get("external_conditions"):
            changes = True
        if not changes:
            continue
        labelled = (
            raw.get("labelled_scenario_id")
            or raw.get("separate_scenario_id")
            or raw.get("scenario_id")
        )
        if not labelled or labelled == current_id:
            raise SimulationError(
                "unresolved_assumption",
                "an assumption that changes external conditions needs a separately labelled scenario",
                field=f"proposal.assumptions[{index}]",
            )


def _apply_layout_assumptions(scenario: dict, layout: dict) -> None:
    units = scenario.get("source_units")
    if not isinstance(units, list):
        return
    declared_status = layout.get("layout_status")
    extra = layout.get("source_units")
    by_id = {unit.get("id"): unit for unit in units if isinstance(unit, Mapping)}
    if isinstance(extra, list):
        for index, raw in enumerate(extra):
            if not isinstance(raw, Mapping):
                raise SimulationError(
                    "invalid_value_or_unit",
                    "layout source unit must be an object",
                    field=f"layout_assumptions.source_units[{index}]",
                )
            unit_id = raw.get("id")
            existing = by_id.get(unit_id)
            if existing is None:
                raise SimulationError(
                    "unknown_reference",
                    f"layout assumptions reference unknown source unit {unit_id!r}",
                    field=f"layout_assumptions.source_units[{index}].id",
                )
            for fact in PROTECTED_FACT_KEYS:
                if fact in raw and raw[fact] != existing.get(fact):
                    raise SimulationError(
                        "fixed_rule_violation",
                        "layout assumptions cannot change occupancy or attendance",
                        field=f"layout_assumptions.source_units[{index}].{fact}",
                    )
            for label in ("building_id", "floor_id", "wing_id", "layout_status"):
                if raw.get(label) not in (None, ""):
                    existing[label] = raw[label]
    for unit in units:
        if not isinstance(unit, Mapping):
            continue
        if unit.get("layout_status") in (None, ""):
            unit["layout_status"] = declared_status or "estimated"
        if declared_status == "estimated" and unit.get("layout_status") != "surveyed":
            unit["layout_status"] = "estimated"


def _check_references(resolved: dict, scenario: dict) -> None:
    place_ids = {
        place.get("id")
        for place in scenario.get("places") or []
        if isinstance(place, Mapping)
    }
    hostel_ids = {
        hostel.get("id")
        for hostel in scenario.get("hostels") or []
        if isinstance(hostel, Mapping)
    }
    worker_ids = {
        worker.get("id")
        for worker in (scenario.get("initial_state") or {}).get("workers") or []
        if isinstance(worker, Mapping)
    }
    vehicle_ids = {
        vehicle.get("id")
        for vehicle in (scenario.get("initial_state") or {}).get("vehicles") or []
        if isinstance(vehicle, Mapping)
    }
    fleet_ids = {
        fleet.get("id")
        for fleet in scenario.get("fleets") or []
        if isinstance(fleet, Mapping)
    }
    door_ids = {
        door.get("id")
        for door in (scenario.get("destination") or {}).get("doors") or []
        if isinstance(door, Mapping)
    }
    resource_ids = {
        resource.get("id")
        for resource in scenario.get("shared_resources") or []
        if isinstance(resource, Mapping)
    }
    checkpoint_ids = {
        checkpoint.get("id")
        for checkpoint in scenario.get("checkpoints") or []
        if isinstance(checkpoint, Mapping)
    }
    grouping = resolved["grouping"]
    overrides = grouping.get("scope_overrides") or {}
    if isinstance(overrides, Mapping):
        for origin in overrides:
            if origin not in hostel_ids and origin not in {
                unit.get("building_id")
                for unit in scenario.get("source_units") or []
                if isinstance(unit, Mapping)
            }:
                raise SimulationError(
                    "unknown_reference",
                    f"grouping override references unknown origin {origin!r}",
                    field=f"proposal.grouping.scope_overrides.{origin}",
                )
    regroup = resolved["regroup_policy"]
    place_id = regroup.get("place_id")
    if place_id and place_id not in place_ids:
        raise SimulationError(
            "unknown_reference",
            f"regrouping references unknown place {place_id!r}",
            field="proposal.regroup_policy.place_id",
        )
    physical = grouping.get("physical_assembly") or {}
    if isinstance(physical, Mapping) and physical.get("place_id"):
        if physical["place_id"] not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"physical assembly references unknown place {physical['place_id']!r}",
                field="proposal.grouping.physical_assembly.place_id",
            )
    for index, raw in enumerate(resolved["worker_allocation"].get("assignments") or []):
        if not isinstance(raw, Mapping):
            raise SimulationError(
                "invalid_value_or_unit",
                "worker assignment must be an object",
                field=f"proposal.worker_allocation.assignments[{index}]",
            )
        worker_id = raw.get("worker_id")
        if worker_id and worker_ids and worker_id not in worker_ids:
            raise SimulationError(
                "unknown_reference",
                f"worker allocation references unknown worker {worker_id!r}",
                field=f"proposal.worker_allocation.assignments[{index}].worker_id",
            )
        dest = raw.get("place_id") or raw.get("to_place_id")
        if dest and dest not in place_ids:
            raise SimulationError(
                "unknown_reference",
                f"worker allocation references unknown place {dest!r}",
                field=f"proposal.worker_allocation.assignments[{index}].place_id",
            )
    fleet_id = resolved["vehicle_dispatch_rule"].get("fleet_id")
    if fleet_id and fleet_ids and fleet_id not in fleet_ids:
        raise SimulationError(
            "unknown_reference",
            f"bus dispatch references unknown fleet {fleet_id!r}",
            field="proposal.vehicle_dispatch_rule.fleet_id",
        )
    vehicle_id = resolved["vehicle_dispatch_rule"].get("vehicle_id")
    if vehicle_id and vehicle_ids and vehicle_id not in vehicle_ids:
        raise SimulationError(
            "unknown_reference",
            f"bus dispatch references unknown vehicle {vehicle_id!r}",
            field="proposal.vehicle_dispatch_rule.vehicle_id",
        )
    assignments = resolved["counting"].get("assignments") or {}
    if isinstance(assignments, Mapping):
        for cid, raw in assignments.items():
            if checkpoint_ids and cid not in checkpoint_ids:
                raise SimulationError(
                    "unknown_reference",
                    f"count assignment references unknown checkpoint {cid!r}",
                    field=f"proposal.counting.assignments.{cid}",
                )
            if isinstance(raw, Mapping):
                location_id = raw.get("location_id")
                if location_id and location_id not in place_ids:
                    raise SimulationError(
                        "unknown_reference",
                        f"count assignment references unknown place {location_id!r}",
                        field=f"proposal.counting.assignments.{cid}.location_id",
                    )
    dest_door = resolved["destination_rule"].get("door_id")
    if dest_door and door_ids and dest_door not in door_ids:
        raise SimulationError(
            "unknown_reference",
            f"destination arrangement references unknown door {dest_door!r}",
            field="proposal.destination_rule.door_id",
        )
    resource_id = resolved["destination_rule"].get("resource_id")
    if resource_id and resource_ids and resource_id not in resource_ids:
        raise SimulationError(
            "unknown_reference",
            f"destination arrangement references unknown resource {resource_id!r}",
            field="proposal.destination_rule.resource_id",
        )
    behavior_response = resolved.get("behavior_response")
    if behavior_response is not None:
        _check_behavior_references(behavior_response, place_ids)


def _check_worker_travel(allocation: Mapping, scenario: dict) -> None:
    assignments = allocation.get("assignments") or []
    if not isinstance(assignments, list):
        raise SimulationError(
            "invalid_value_or_unit",
            "worker_allocation.assignments must be a list",
            field="proposal.worker_allocation.assignments",
        )
    workers = {
        worker.get("id"): worker
        for worker in (scenario.get("initial_state") or {}).get("workers") or []
        if isinstance(worker, Mapping)
    }
    travel_map: dict[tuple[Any, Any], Any] = {}
    operating = dict(scenario.get("operating_rules") or {})
    for source in (
        scenario.get("worker_travel"),
        scenario.get("worker_travel_s"),
        operating.get("worker_travel"),
        operating.get("worker_travel_s"),
    ):
        if not isinstance(source, list):
            continue
        for row in source:
            if not isinstance(row, Mapping):
                continue
            travel_map[(row.get("from_place_id"), row.get("to_place_id"))] = row.get(
                "duration_s"
            )
    for index, raw in enumerate(assignments):
        if not isinstance(raw, Mapping):
            continue
        dest = raw.get("place_id") or raw.get("to_place_id")
        src = raw.get("from_place_id")
        worker_id = raw.get("worker_id")
        if src is None and worker_id in workers:
            src = workers[worker_id].get("place_id")
        if not dest or not src or dest == src:
            continue
        if raw.get("skip_travel") or raw.get("teleport"):
            raise SimulationError(
                "fixed_rule_violation",
                "workers cannot move between places without travel",
                field=f"proposal.worker_allocation.assignments[{index}].skip_travel",
            )
        travel_s = raw.get("travel_s")
        if travel_s is None:
            travel_s = raw.get("duration_s") if "duration_s" in raw else None
        if travel_s == 0:
            raise SimulationError(
                "fixed_rule_violation",
                "workers cannot move between places without travel",
                field=f"proposal.worker_allocation.assignments[{index}].travel_s",
            )
        declared = travel_map.get((src, dest))
        if declared is None:
            declared = travel_map.get((dest, src))
        if travel_s is None and declared is None:
            raise SimulationError(
                "missing_input",
                "worker assignment between different places needs travel time",
                field=f"proposal.worker_allocation.assignments[{index}].travel_s",
            )


def _check_regrouping(resolved: dict, scenario: dict) -> None:
    regroup = dict(resolved["regroup_policy"])
    grouping = resolved["grouping"]
    physical = grouping.get("physical_assembly")
    if isinstance(physical, Mapping):
        _check_assembly_block(physical, scenario, "proposal.grouping.physical_assembly")
    if not regroup.get("required"):
        return
    place_id = regroup.get("place_id")
    if not place_id:
        raise SimulationError(
            "missing_input",
            "required destination regrouping needs a declared place_id",
            field="proposal.regroup_policy.place_id",
        )
    duration = (
        regroup.get("duration_s")
        if regroup.get("duration_s") is not None
        else regroup.get("assembly_duration_s", regroup.get("assembly_time_s"))
    )
    if duration is None:
        raise SimulationError(
            "missing_input",
            "required regrouping needs declared assembly time",
            field="proposal.regroup_policy.duration_s",
        )
    _finite_nonneg_number(duration, "proposal.regroup_policy.duration_s")
    if regroup.get("worker_count") is not None:
        _nonneg_int(regroup["worker_count"], "proposal.regroup_policy.worker_count")
    operating = dict(scenario.get("operating_rules") or {})
    permitted_places = list(
        operating.get("permitted_regroup_places")
        or operating.get("permitted_gathering_places")
        or []
    )
    if permitted_places and place_id not in permitted_places:
        raise SimulationError(
            "unsupported_policy",
            f"regrouping place {place_id!r} is not a permitted gathering place",
            field="proposal.regroup_policy.place_id",
        )
    place = _place_by_id(scenario, place_id)
    if place is None:
        raise SimulationError(
            "unknown_reference",
            f"regrouping references unknown place {place_id!r}",
            field="proposal.regroup_policy.place_id",
        )
    if not _place_has_waiting_space(place):
        raise SimulationError(
            "impossible_static_requirement",
            f"regrouping place {place_id!r} has no physical waiting space",
            field="proposal.regroup_policy.place_id",
        )


def _check_assembly_block(physical: Mapping, scenario: dict, prefix: str) -> None:
    for key in ("duration_s", "place_id", "worker_count"):
        if key not in physical or physical[key] in (None, ""):
            raise SimulationError(
                "missing_input",
                f"physical assembly needs declared {key}",
                field=f"{prefix}.{key}",
            )
    _finite_nonneg_number(physical["duration_s"], f"{prefix}.duration_s")
    _nonneg_int(physical["worker_count"], f"{prefix}.worker_count")
    place = _place_by_id(scenario, physical["place_id"])
    if place is None:
        raise SimulationError(
            "unknown_reference",
            f"physical assembly references unknown place {physical['place_id']!r}",
            field=f"{prefix}.place_id",
        )
    if not _place_has_waiting_space(place):
        raise SimulationError(
            "impossible_static_requirement",
            f"assembly place {physical['place_id']!r} has no physical waiting space",
            field=f"{prefix}.place_id",
        )


def _place_by_id(scenario: dict, place_id: str | None) -> dict | None:
    if not place_id:
        return None
    for place in scenario.get("places") or []:
        if isinstance(place, Mapping) and place.get("id") == place_id:
            return dict(place)
    return None


def _place_has_waiting_space(place: Mapping) -> bool:
    if place.get("capacity_constraint") == "unbounded":
        return True
    physical = place.get("physical_capacity_students")
    if physical is None:
        physical = place.get("capacity_students")
    if physical is None:
        return True
    return int(physical) > 0


def _check_grouping_basis_allowed(grouping: Mapping, permitted: dict) -> None:
    basis = grouping.get("basis")
    if basis is None:
        return
    if basis not in GROUPING_BASES:
        raise SimulationError(
            "unsupported_policy",
            f"unsupported grouping basis {basis!r}",
            field="proposal.grouping.basis",
        )
    allowed = permitted.get("grouping_bases")
    if isinstance(allowed, list) and basis not in allowed:
        raise SimulationError(
            "unsupported_policy",
            f"grouping basis {basis!r} is not a permitted search choice",
            field="proposal.grouping.basis",
        )
    overrides = grouping.get("scope_overrides") or {}
    if isinstance(overrides, Mapping):
        for origin, origin_basis in overrides.items():
            if origin_basis not in GROUPING_BASES - {"mixed"}:
                raise SimulationError(
                    "unsupported_policy",
                    f"unsupported override basis {origin_basis!r} for {origin!r}",
                    field=f"proposal.grouping.scope_overrides.{origin}",
                )

def _validate_space_and_dispatch_rules(resolved: dict) -> None:
    rel = resolved.get("release_rule") or {}
    if isinstance(rel, Mapping) and rel.get("type") == "queue_based":
        if not resolved.get("destination_space_rule") and not resolved.get("space_control"):
            raise SimulationError(
                "unsupported_policy",
                "queue_based release requires destination_space_rule or space_control",
                field="proposal.release_rule",
            )
    dest_space = resolved.get("destination_space_rule")
    if dest_space is not None and dest_space not in DESTINATION_SPACE_RULES:
        raise SimulationError(
            "unsupported_policy",
            f"unsupported destination_space_rule {dest_space!r}",
            field="proposal.destination_space_rule",
        )
    veh = resolved.get("vehicle_dispatch_rule") or {}
    if isinstance(veh, Mapping):
        vtype = veh.get("type")
        if vtype and vtype not in VEHICLE_DISPATCH_RULES:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported vehicle_dispatch_rule.type {vtype!r}",
                field="proposal.vehicle_dispatch_rule.type",
            )
        if vtype in {"headway", "fixed_interval"} and not any(
            veh.get(key) is not None
            for key in ("headway_s", "dispatch_interval_s", "interval_s")
        ):
            raise SimulationError(
                "unsupported_policy",
                f"{vtype} vehicle_dispatch_rule needs an interval",
                field="proposal.vehicle_dispatch_rule.headway_s",
            )
    dst = resolved.get("destination_rule") or {}
    if isinstance(dst, Mapping):
        dtype = dst.get("type")
        implemented_dest = {"complete_after_stages", "wait_for_imposed_opening"}
        if dtype and dtype not in implemented_dest:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported destination_rule.type {dtype!r}",
                field="proposal.destination_rule.type",
            )
        if dtype == "wait_for_imposed_opening" and not dst.get("calendar_id"):
            raise SimulationError(
                "missing_input",
                "wait_for_imposed_opening needs calendar_id",
                field="proposal.destination_rule.calendar_id",
            )
    adapt = resolved.get("adaptation_rule")
    if isinstance(adapt, Mapping):
        atype = adapt.get("type")
        if atype and atype not in ADAPTATION_TYPES:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported adaptation_rule.type {atype!r}",
                field="proposal.adaptation_rule.type",
            )
        if atype and atype != "fixed" and not adapt.get("permitted_place_id"):
            raise SimulationError(
                "missing_input",
                "a run-time grouping change needs permitted_place_id",
                field="proposal.adaptation_rule.permitted_place_id",
            )


def _extract_behavior_rules(
    br: Any, base_path: str = "proposal.behavior_response"
) -> list[tuple[Mapping, str, str | None, str | None]]:
    rules: list[tuple[Mapping, str, str | None, str | None]] = []
    seen_ids: set[int] = set()
    if isinstance(br, list):
        for idx, item in enumerate(br):
            if isinstance(item, Mapping):
                seen_ids.add(id(item))
                rules.append((item, f"{base_path}[{idx}]", item.get("trigger"), item.get("place_id")))
    elif isinstance(br, Mapping):
        if "rules" in br and isinstance(br["rules"], list):
            for idx, item in enumerate(br["rules"]):
                if isinstance(item, Mapping) and id(item) not in seen_ids:
                    seen_ids.add(id(item))
                    rules.append((item, f"{base_path}.rules[{idx}]", item.get("trigger"), item.get("place_id")))
        if "by_trigger" in br and isinstance(br["by_trigger"], Mapping):
            for trig, item in br["by_trigger"].items():
                if isinstance(item, Mapping) and id(item) not in seen_ids:
                    seen_ids.add(id(item))
                    rules.append((item, f"{base_path}.by_trigger.{trig}", trig, item.get("place_id")))
        if "by_location" in br and isinstance(br["by_location"], Mapping):
            for loc, item in br["by_location"].items():
                if isinstance(item, Mapping) and id(item) not in seen_ids:
                    seen_ids.add(id(item))
                    rules.append((item, f"{base_path}.by_location.{loc}", item.get("trigger"), loc))
        for k, v in br.items():
            if k in ("rules", "by_trigger", "by_location"):
                continue
            if isinstance(v, Mapping) and id(v) not in seen_ids:
                seen_ids.add(id(v))
                rules.append((v, f"{base_path}.{k}", k, v.get("place_id")))
    return rules


def _check_behavior_references(br: Any, place_ids: set[str]) -> None:
    if not place_ids or br is None:
        return
    rules = _extract_behavior_rules(br, "proposal.behavior_response")
    for rule, path, _trig, _loc in rules:
        loc = (
            rule.get("place_id")
            or rule.get("location")
            or rule.get("station_id")
            or rule.get("location_id")
            or _loc
        )
        if loc and loc not in place_ids:
            field = f"{path}.place_id" if "place_id" in rule else path
            raise SimulationError(
                "unknown_reference",
                f"behavior response references unknown place {loc!r}",
                field=field,
            )


def _validate_behavior_limits(br: Any, permitted: dict) -> None:
    if br is None:
        return
    permitted_bounds = {}
    if isinstance(permitted.get("numerical_bounds"), Mapping):
        permitted_bounds = dict(permitted["numerical_bounds"])

    rules = _extract_behavior_rules(br, "proposal.behavior_response")
    for rule, path, _trig, _loc in rules:
        for dur_key in (
            "wait_limit_s",
            "max_wait_s",
            "maximum_wait_s",
            "wait_s",
            "hold_limit_s",
            "max_hold_s",
            "maximum_hold_s",
            "hold_s",
            "hold_bus_limit_s",
            "min_hold_duration_s",
        ):
            if dur_key in rule and rule[dur_key] is not None:
                val = rule[dur_key]
                num_val = _finite_nonneg_number(val, f"{path}.{dur_key}")
                if dur_key in permitted_bounds:
                    allowed = permitted_bounds[dur_key]
                    bounds = _bounds_from_spec(
                        allowed, f"permitted_decisions.numerical_bounds.{dur_key}"
                    )
                    if bounds is not None:
                        lower, upper = bounds
                        if num_val < lower or num_val > upper:
                            raise SimulationError(
                                "invalid_value_or_unit",
                                f"{dur_key} value {num_val} is outside permitted range [{lower}, {upper}]",
                                field=f"{path}.{dur_key}",
                            )


def _check_behavior_responses(resolved: dict, scenario: dict, permitted: dict) -> None:
    scenario_behavior = scenario.get("behavior")
    active_triggers: set[str] = set()
    if isinstance(scenario_behavior, Mapping):
        for event in scenario_behavior.get("events") or []:
            if isinstance(event, Mapping):
                phenom = event.get("phenomenon")
                if phenom:
                    active_triggers.add(phenom)
                trig = event.get("trigger")
                if isinstance(trig, Mapping):
                    for k in ("before_stage", "after_stage"):
                        if trig.get(k):
                            active_triggers.add(trig[k])
        for phenom, cfg in (scenario_behavior.get("phenomena") or {}).items():
            if isinstance(cfg, Mapping) and cfg:
                active_triggers.add(phenom)

    br = resolved.get("behavior_response")
    claims_to_handle = (
        br is not None
        or bool(resolved.get("handles_case"))
        or bool(resolved.get("behavior_case_id"))
        or bool(resolved.get("claims_to_handle"))
        or (
            isinstance(scenario_behavior, Mapping)
            and scenario_behavior.get("case_id")
            and resolved.get("proposal_id", "").startswith(str(scenario_behavior.get("case_id", "")))
        )
    )

    if claims_to_handle and br is None:
        raise SimulationError(
            "missing_input",
            "proposal claims to handle named behavior case but does not specify behavior_response",
            field="proposal.behavior_response",
        )

    if br is None:
        return

    if not isinstance(br, (Mapping, list)):
        raise SimulationError(
            "invalid_value_or_unit",
            "proposal.behavior_response must be an object or list",
            field="proposal.behavior_response",
        )

    rules = _extract_behavior_rules(br, "proposal.behavior_response")
    if not rules:
        if active_triggers and claims_to_handle:
            missing_trigger = sorted(active_triggers)[0]
            raise SimulationError(
                "missing_input",
                f"missing behavior_response for active case trigger {missing_trigger!r}",
                field=f"proposal.behavior_response.{missing_trigger}",
            )
        return

    covered_triggers: set[str] = set()

    for rule, path, key_trig, key_loc in rules:
        action = rule.get("action")
        if action is None and key_trig in BEHAVIOR_ACTIONS:
            action = key_trig
        if action is None:
            raise SimulationError(
                "missing_input",
                "behavior rule missing action",
                field=f"{path}.action",
            )
        if not isinstance(action, str):
            raise SimulationError(
                "invalid_value_or_unit",
                "behavior action must be a string",
                field=f"{path}.action",
            )
        if action not in BEHAVIOR_ACTIONS:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported behavior action {action!r}",
                field=f"{path}.action",
            )

        fallback = rule.get("fallback")
        if fallback is not None:
            if isinstance(fallback, str):
                if fallback not in BEHAVIOR_ACTIONS:
                    raise SimulationError(
                        "unsupported_policy",
                        f"unsupported behavior action fallback {fallback!r}",
                        field=f"{path}.fallback",
                    )
            elif isinstance(fallback, Mapping):
                fb_act = fallback.get("action")
                if not fb_act or fb_act not in BEHAVIOR_ACTIONS:
                    raise SimulationError(
                        "unsupported_policy",
                        f"unsupported behavior action fallback {fb_act!r}",
                        field=f"{path}.fallback.action",
                    )
            else:
                raise SimulationError(
                    "invalid_value_or_unit",
                    "behavior rule fallback must be an action string or object",
                    field=f"{path}.fallback",
                )

        trig = rule.get("trigger") or rule.get("phenomenon") or key_trig
        if trig:
            covered_triggers.add(trig)
        loc = (
            rule.get("place_id")
            or rule.get("location")
            or rule.get("station_id")
            or rule.get("location_id")
            or key_loc
        )
        if loc:
            covered_triggers.add(loc)

        if action in ("refuse_queue_jump", "refuse-queue-jump", "allow_queue_jump", "allow-queue-jump"):
            covered_triggers.add("queue_jump")
        if action in ("intercept_at_station", "intercept-at-station"):
            covered_triggers.add("late_reporting")
            covered_triggers.add("queue_jump")
            covered_triggers.add("catch_up_walk")
        if action in (
            "wait",
            "wait_for_stragglers",
            "wait-for-stragglers",
            "split_and_go",
            "split-and-go",
            "hold_bus",
            "hold-bus",
            "hold_the_bus",
            "hold-the-bus",
            "bump_next_vehicle",
            "bump-next-vehicle",
            "bump_to_next_vehicle",
            "bump-to-next-vehicle",
        ):
            covered_triggers.add("late_reporting")
            covered_triggers.add("mixed_readiness")
        if action in ("refuse_unescorted_walk", "refuse-unescorted-walk"):
            covered_triggers.add("route_deviation")
            covered_triggers.add("schedule_departure")
            covered_triggers.add("catch_up_walk")
        if action in ("deny", "deny_onward_service", "deny-onward-service"):
            covered_triggers.add("stage_skip")
            covered_triggers.add("route_deviation")
            covered_triggers.add("withdrawal")

    if claims_to_handle and active_triggers:
        for act_trig in sorted(active_triggers):
            if act_trig not in covered_triggers:
                raise SimulationError(
                    "missing_input",
                    f"missing behavior_response for active case trigger {act_trig!r}",
                    field=f"proposal.behavior_response.{act_trig}",
                )


def _copy_behavior_response(br: Any) -> dict:
    if isinstance(br, Mapping):
        policy_br = copy.deepcopy(dict(br))
    elif isinstance(br, list):
        policy_br = {"rules": copy.deepcopy(br)}
    else:
        return {}

    rules_tuples = _extract_behavior_rules(policy_br, "proposal.behavior_response")
    by_trigger = dict(policy_br.get("by_trigger") or {})
    by_location = dict(policy_br.get("by_location") or {})
    all_rules = list(policy_br.get("rules") or [])

    for rule, _path, trig_key, loc_key in rules_tuples:
        rule_dict = dict(rule)
        trig = rule_dict.get("trigger") or rule_dict.get("phenomenon") or trig_key
        loc = (
            rule_dict.get("place_id")
            or rule_dict.get("location")
            or rule_dict.get("station_id")
            or rule_dict.get("location_id")
            or loc_key
        )
        if trig and "trigger" not in rule_dict:
            rule_dict["trigger"] = trig
        if loc and "place_id" not in rule_dict:
            rule_dict["place_id"] = loc

        if trig:
            by_trigger.setdefault(trig, rule_dict)
            policy_br.setdefault(trig, rule_dict)
        if loc:
            by_location.setdefault(loc, rule_dict)
            policy_br.setdefault(loc, rule_dict)

        if not any(r is rule for r in all_rules) and rule_dict not in all_rules:
            all_rules.append(rule_dict)

    policy_br["rules"] = all_rules
    policy_br["by_trigger"] = by_trigger
    policy_br["by_location"] = by_location
    return policy_br

def _policy_from_proposal(resolved: dict, scenario: dict) -> dict:
    operating = dict(scenario.get("operating_rules") or {})
    grouping = dict(resolved["grouping"])
    grouping.setdefault("regroup_policy", dict(resolved["regroup_policy"]))
    if resolved.get("adaptation_rule") is not None:
        grouping["adaptation_rule"] = copy.deepcopy(resolved["adaptation_rule"])
    policy = {
        "policy_id": resolved["proposal_id"],
        "policy_version": "1",
        "grouping": grouping,
        "release_rule": dict(resolved["release_rule"]),
        "vehicle_dispatch_rule": dict(resolved["vehicle_dispatch_rule"]),
        "destination_rule": dict(resolved["destination_rule"]),
        "counting": dict(resolved["counting"]),
        "worker_allocation": dict(resolved["worker_allocation"]),
        "required_endpoint": operating.get("required_endpoint"),
        "random_seed": 0,
        "numerical_rounding_limit_s": 0.001,
    }
    if resolved.get("space_control") is not None:
        policy["space_control"] = copy.deepcopy(resolved["space_control"])
    if resolved.get("destination_space_rule") is not None:
        policy["destination_space_rule"] = resolved["destination_space_rule"]
    if resolved.get("coordination_delay_s") is not None:
        policy["coordination_delay_s"] = float(resolved["coordination_delay_s"])
    elif policy.get("space_control") or policy.get("destination_space_rule"):
        policy.setdefault("coordination_delay_s", 0.0)
    allocation = resolved["worker_allocation"]
    for key in ("min_station_staff", "staffing_ratio", "escorts_per_group"):
        if key in allocation:
            policy[key] = allocation[key]
    if resolved.get("behavior_response") is not None:
        policy["behavior_response"] = _copy_behavior_response(resolved["behavior_response"])
    return policy


def _build_search_space(resolved: dict, scenario: dict, permitted: dict) -> dict:
    operating = dict(scenario.get("operating_rules") or {})
    fixed = {
        "required_endpoint": operating.get("required_endpoint"),
        "route_id": operating.get("route_id"),
        "direct_walk_permitted": bool(operating.get("direct_walk_permitted")),
        "required_checkpoints": list(operating.get("required_checkpoints") or []),
        "permitted_counting_locations": list(
            operating.get("permitted_counting_locations") or []
        ),
        "min_station_staff": copy.deepcopy(operating.get("min_station_staff") or {}),
        "staffing_ratio": copy.deepcopy(operating.get("staffing_ratio") or {}),
    }
    for key, value in resolved["fixed_choices"].items():
        if key in SCENARIO_OWNED_RULES and key in operating:
            fixed[key] = operating[key]
        elif key not in PROTECTED_FACT_KEYS:
            fixed.setdefault(key, value)
    allowed_values: dict[str, list] = {}
    numerical_bounds: dict[str, dict] = {}
    bases = list(permitted.get("grouping_bases") or sorted(GROUPING_BASES))
    tunable = resolved["tunable"]
    for field_name, spec in tunable.items():
        allowed = _allowed_from_spec(spec)
        if allowed is not None:
            if field_name.endswith("basis"):
                allowed = [item for item in allowed if item in bases]
            allowed_values[field_name] = allowed
        bounds = _bounds_from_spec(spec, f"proposal.tunable.{field_name}")
        if bounds is not None:
            numerical_bounds[field_name] = {
                "lower": bounds[0],
                "upper": bounds[1],
                "unit": spec.get("unit") if isinstance(spec, Mapping) else None,
            }
    grouping_is_fixed = (
        "grouping.basis" in fixed
        or "grouping_basis" in fixed
        or "grouping.basis" in resolved["fixed_choices"]
        or "grouping_basis" in resolved["fixed_choices"]
    )
    if grouping_is_fixed:
        allowed_values.pop("grouping.basis", None)
    extra_allowed = permitted.get("allowed_values")
    if isinstance(extra_allowed, Mapping):
        for field_name, values in extra_allowed.items():
            allowed_values.setdefault(field_name, list(values))
    extra_bounds = permitted.get("numerical_bounds")
    if isinstance(extra_bounds, Mapping):
        for field_name, spec in extra_bounds.items():
            if field_name in numerical_bounds:
                continue
            bounds = _bounds_from_spec(
                spec, f"permitted_decisions.numerical_bounds.{field_name}"
            )
            if bounds is not None:
                numerical_bounds[field_name] = {
                    "lower": bounds[0],
                    "upper": bounds[1],
                    "unit": spec.get("unit") if isinstance(spec, Mapping) else None,
                }
    return {
        "fixed_decisions": fixed,
        "allowed_values": allowed_values,
        "numerical_bounds": numerical_bounds,
        "grouping_bases": bases,
    }


def _assert_no_automatic_count(summary: Mapping) -> None:
    if int(summary.get("headcounts_added") or 0) != 0:
        raise SimulationError(
            "fixed_rule_violation",
            "creating a group cannot automatically introduce a manual count",
            field="proposal.grouping",
        )
    for group in summary.get("groups") or []:
        if group.get("headcount_added") or group.get("count_record_ids"):
            raise SimulationError(
                "fixed_rule_violation",
                "creating a group cannot automatically introduce a manual count",
                field="proposal.grouping",
            )


def _layout_status(scenario: dict) -> str:
    units = scenario.get("source_units") or []
    if any(
        isinstance(unit, Mapping) and unit.get("layout_status") != "surveyed"
        for unit in units
    ):
        return "estimated"
    if units:
        return "surveyed"
    return "estimated"


def _walk(value: Any, path: str):
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            yield child, str(key), item
            yield from _walk(item, child)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
