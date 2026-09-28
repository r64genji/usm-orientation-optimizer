"""Ticket 10: Bounded search across grouping and operating choices.

Evaluates checked proposals across required uncertainty scenarios using the public
simulator. Returns feasible plans, Pareto tradeoffs, equivalent policy links,
and transparent failure and coverage records. No AI service is called.
"""

from __future__ import annotations

import copy
import json
import itertools
import math
import platform
import time
from typing import Any, Collection, Mapping, Sequence

from usm_sim.constants import ENGINE_VERSION, GROUPING_BASES, SOFTWARE_REVISION
from usm_sim.errors import SimulationError
from usm_sim.proposals import check_proposal
from usm_sim.uncertainty import (
    FORBIDDEN_POLICY_INFORMATION,
    _resolve_cases,
    case_weight,
    infer_dataset_role,
    is_gps_holdout_case,
    simulate_case_safely,
    simulation_failure_reasons,
    validate_policy_information,
)

DEFAULT_OBJECTIVES = (
    {"name": "total_student_waiting", "field": "total_student_waiting_student_s", "direction": "min", "aggregation": "both"},
    {"name": "lateness", "field": "total_lateness_s", "direction": "min", "aggregation": "both"},
    {"name": "late_students", "field": "late_students", "direction": "min", "aggregation": "both"},
    {"name": "reserved_worker_effort", "field": "worker_reserved_s", "direction": "min", "aggregation": "both"},
    {"name": "coordination_effort", "field": "coordination_effort", "direction": "min", "aggregation": "both"},
    {"name": "max_hostel_mean_wait", "field": "max_hostel_mean_wait_s", "direction": "min", "aggregation": "both"},
)

DEFAULT_MAX_CANDIDATES = 200
DEFAULT_MAX_CASES_PER_CANDIDATE = 16
DEFAULT_MAX_EVENTS_PER_RUN = 1_000_000
FLOAT_TOLERANCE = 1e-6

FORBIDDEN_SEARCH_KEYS = frozenset(
    {
        "hidden_future",
        "future_weather",
        "future_travel_times",
        "future_travel_time",
        "future_state",
        "unreported_bus_failure",
        "hidden_attendance",
        "actual_attendance",
        "oracle_schedule",
        "perfect_foresight",
        "uses_future",
        "uses_actual_future",
        "uses_hidden_attendance",
    }
)

# Ticket-12 GPS calibration replays. These are final independent cases and
# cannot be used to select a plan.
GPS_HOLDOUT_SCENARIO_IDS = frozenset(
    {
        "restu_17sep_replay",
        "restu_18sep_rainy_replay",
    }
)
KNOWN_OBJECTIVES = frozenset(
    {
        "total_student_waiting",
        "student_waiting",
        "total_student_waiting_student_s",
        "wait",
        "waiting",
        "late_students",
        "late_student_count",
        "late_count",
        "total_lateness",
        "total_lateness_s",
        "lateness_duration",
        "lateness",
        "max_lateness",
        "max_lateness_s",
        "reserved_worker_effort",
        "worker_reserved",
        "worker_reserved_s",
        "worker_effort",
        "worker_duty_s",
        "coordination_effort",
        "coordination",
        "max_hostel_mean_wait",
        "max_hostel_mean_wait_s",
        "hostel_mean_wait",
        "total_required_journey_student_s",
        "total_required_journey_s",
        "unfinished_students",
        "unfinished",
        "physical_violations",
        "violations",
    }
)



def _validate_forbidden_information(data: Mapping[str, Any]) -> None:
    """Reject any input or policy referencing hidden simulator state or future information."""
    for k in FORBIDDEN_SEARCH_KEYS:
        if k in data:
            raise SimulationError(
                "unsupported_policy",
                f"Proposal attempts to access forbidden hidden/future information: {k}",
                field=k,
            )
        for sub in ("release_rule", "grouping", "vehicle_dispatch_rule", "space_control", "tunable", "fixed_choices"):
            sub_dict = data.get(sub)
            if isinstance(sub_dict, Mapping) and k in sub_dict:
                raise SimulationError(
                    "unsupported_policy",
                    f"Proposal attempts to access forbidden hidden/future information: {sub}.{k}",
                    field=f"{sub}.{k}",
                )
    validate_policy_information(data)


def _dataset_role(case: Any) -> str | None:
    if isinstance(case, tuple) and len(case) == 2:
        return infer_dataset_role(case[0], case[1])
    if isinstance(case, Mapping):
        return infer_dataset_role(case)
    return None


def _reject_selection_holdout(case: Any) -> None:
    """Reject ticket-12 GPS holdouts and any final_independent case from selection."""
    if is_gps_holdout_case(case):
        raise SimulationError(
            "fixed_rule_violation",
            "Ticket-12 GPS holdout scenario (restu_17sep_replay, restu_18sep_rainy_replay) "
            "is a final_independent case and cannot be used to select a plan.",
            field="dataset_role",
        )
    role = _dataset_role(case)
    if role == "final_independent":
        raise SimulationError(
            "fixed_rule_violation",
            "Cases with dataset_role='final_independent' cannot be used in search. "
            "They are reserved for final evaluation after policy selection.",
            field="dataset_role",
        )

def _default_target_students(
    base_proposal: Mapping[str, Any],
    search_space: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> int:
    grouping = base_proposal.get("grouping") if isinstance(base_proposal.get("grouping"), Mapping) else {}
    existing = grouping.get("target_students")
    if existing is not None:
        return max(1, int(existing))
    bounds = (search_space.get("numerical_bounds") or {}).get("grouping.target_students")
    if isinstance(bounds, Mapping) and bounds.get("lower") is not None:
        return max(1, int(bounds["lower"]))
    if scenario:
        sizes = []
        for unit in scenario.get("source_units") or []:
            if not isinstance(unit, Mapping):
                continue
            n = unit.get("estimated_attendance") or unit.get("resident_occupancy")
            if n:
                sizes.append(int(n))
        if sizes:
            return max(1, min(sizes))
    return 20


def _apply_search_parameter(
    cand: dict,
    param_key: str,
    val: Any,
    base_proposal: Mapping[str, Any],
    search_space: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> None:
    _set_nested_key(cand, param_key, val)
    if param_key == "release_rule.interval_s":
        if float(val) > 0:
            _set_nested_key(cand, "release_rule.type", "fixed_interval")
        else:
            _set_nested_key(cand, "release_rule.type", "immediate")
    if param_key == "grouping.basis":
        grouping = cand.setdefault("grouping", {})
        if not isinstance(grouping, dict):
            grouping = {}
            cand["grouping"] = grouping
        if val == "target_size" and grouping.get("target_students") is None:
            grouping["target_students"] = _default_target_students(
                base_proposal, search_space, scenario
            )
        if val == "mixed" and not grouping.get("mixed_default") and not grouping.get("scope_overrides"):
            orig = (base_proposal.get("grouping") or {}).get("basis")
            grouping["mixed_default"] = orig if orig and orig != "mixed" else "hostel"


def _attach_fairness_limit(
    policy: dict,
    proposal: Mapping[str, Any],
    hard_constraints: Mapping[str, Any] | None,
) -> None:
    if policy.get("fairness_limit") not in (None, {}, ""):
        return
    if proposal.get("fairness_limit") not in (None, {}, ""):
        policy["fairness_limit"] = copy.deepcopy(proposal["fairness_limit"])
        return
    hc = hard_constraints or {}
    if hc.get("fairness_limit") not in (None, {}, ""):
        policy["fairness_limit"] = copy.deepcopy(hc["fairness_limit"])
        return
    if hc.get("fairness_limit_s") is not None:
        policy["fairness_limit"] = {
            "max_hostel_increase_vs_campus_s": float(hc["fairness_limit_s"])
        }


def _fairness_failure_reasons(measures: Mapping[str, Any]) -> list[str]:
    fairness = measures.get("fairness")
    if not isinstance(fairness, Mapping):
        return []
    if fairness.get("limit_configured") and fairness.get("passed") is False:
        worst = fairness.get("worst_hostel_id")
        return [
            f"Fairness limit {fairness.get('limit_s')}s exceeded"
            + (f" (worst hostel {worst})" if worst else "")
        ]
    return []


def extract_objective_value(name_or_field: str, measures: Mapping[str, Any]) -> float:
    """Extract a scalar numerical objective from simulation measures."""
    norm = str(name_or_field).lower().replace("-", "_").replace(" ", "_")
    if norm in (
        "total_student_waiting",
        "student_waiting",
        "total_student_waiting_student_s",
        "wait",
        "waiting",
    ):
        return float(measures.get("total_student_waiting_student_s", 0.0))
    elif norm in ("late_students", "late_student_count", "late_count"):
        return float(measures.get("late_students", 0))
    elif norm in ("total_lateness", "total_lateness_s", "lateness_duration", "lateness"):
        return float(measures.get("total_lateness_s", 0.0))
    elif norm in ("max_lateness", "max_lateness_s"):
        return float(measures.get("max_lateness_s", 0.0))
    elif norm in (
        "reserved_worker_effort",
        "worker_reserved",
        "worker_reserved_s",
        "worker_effort",
        "worker_duty_s",
    ):
        return float(measures.get("worker_reserved_s", measures.get("worker_duty_s", 0.0)))
    elif norm in ("coordination_effort", "coordination"):
        coord = measures.get("coordination", {})
        if isinstance(coord, Mapping):
            return float(
                coord.get("policy_decisions", 0)
                + coord.get("reports_requiring_action", 0)
                + coord.get("handovers", 0)
                + coord.get("physical_regrouping_actions", 0)
            )
        return float(coord or 0.0)
    elif norm in ("max_hostel_mean_wait", "max_hostel_mean_wait_s", "hostel_mean_wait"):
        return float(measures.get("max_hostel_mean_wait_s", 0.0))
    elif norm in ("total_required_journey_student_s", "total_required_journey_s"):
        return float(measures.get("total_required_journey_student_s", 0.0))
    elif norm in ("unfinished_students", "unfinished"):
        return float(measures.get("unfinished_students", 0))
    elif norm in ("physical_violations", "violations"):
        return float(measures.get("physical_violations", 0))
    elif norm in measures:
        val = measures[norm]
        if isinstance(val, (int, float)):
            return float(val)
    raw = measures.get(name_or_field)
    if isinstance(raw, (int, float)):
        return float(raw)
    raise SimulationError(
        "invalid_value_or_unit",
        f"Unknown objective name '{name_or_field}'. Supported objectives are {sorted(KNOWN_OBJECTIVES)}.",
        field="objectives",
    )


def _normalize_objectives(
    objectives: Sequence[str | Mapping[str, Any]] | None,
) -> list[dict]:
    """Normalize objective definitions to structured objective specifications."""
    if not objectives:
        return [dict(item) for item in DEFAULT_OBJECTIVES]

    normalized: list[dict] = []
    for item in objectives:
        if isinstance(item, str):
            norm = str(item).lower().replace("-", "_").replace(" ", "_")
            if norm not in KNOWN_OBJECTIVES:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"Unknown objective name '{item}'. Supported objectives are {sorted(KNOWN_OBJECTIVES)}.",
                    field="objectives",
                )
            matched = next(
                (d for d in DEFAULT_OBJECTIVES if d["name"] == item or d["field"] == item),
                None,
            )
            if matched:
                normalized.append(dict(matched))
            else:
                normalized.append(
                    {
                        "name": item,
                        "field": item,
                        "direction": "min",
                        "aggregation": "both",
                    }
                )
        elif isinstance(item, Mapping):
            d = dict(item)
            name = d.get("name") or d.get("field") or "unnamed_objective"
            field = d.get("field") or name
            norm_name = str(name).lower().replace("-", "_").replace(" ", "_")
            norm_field = str(field).lower().replace("-", "_").replace(" ", "_")
            if norm_name not in KNOWN_OBJECTIVES and norm_field not in KNOWN_OBJECTIVES:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"Unknown objective name '{name}'. Supported objectives are {sorted(KNOWN_OBJECTIVES)}.",
                    field="objectives",
                )
            direction = d.get("direction", "min")
            aggregation = d.get("aggregation", "both")
            normalized.append(
                {
                    "name": name,
                    "field": field,
                    "direction": direction,
                    "aggregation": aggregation,
                    "weight": d.get("weight"),
                }
            )
        else:
            raise SimulationError(
                "invalid_value_or_unit",
                f"Unsupported objective definition type: {type(item)}",
                field="objectives",
            )
    return normalized


def _extract_candidate_eval_vector(
    objective_values: Mapping[str, Mapping[str, float]],
    normalized_objectives: Sequence[Mapping[str, Any]],
) -> list[float]:
    """Construct vector of scalar values for Pareto comparison."""
    vec: list[float] = []
    for obj in normalized_objectives:
        name = obj["name"]
        agg = obj.get("aggregation", "both")
        direction = obj.get("direction", "min")
        mult = -1.0 if direction == "max" else 1.0

        vals = objective_values.get(name, {})
        base_v = vals.get("base", 0.0)
        worst_v = vals.get("worst_case", 0.0)
        mean_v = vals.get("weighted_mean", vals.get("mean", 0.0))

        if agg == "base":
            vec.append(mult * base_v)
        elif agg == "worst_case":
            vec.append(mult * worst_v)
        elif agg == "weighted_mean":
            vec.append(mult * mean_v)
        else:  # "both" or default
            vec.append(mult * base_v)
            vec.append(mult * worst_v)
    return vec


def _dominates(vec_a: Sequence[float], vec_b: Sequence[float], tol: float = FLOAT_TOLERANCE) -> bool:
    """True if vector A dominates vector B (minimization).

    A is no worse on all components, and strictly better on at least one.
    """
    no_worse = True
    strictly_better = False
    for a, b in zip(vec_a, vec_b):
        if a > b + tol:
            return False
        if a < b - tol:
            strictly_better = True
    return no_worse and strictly_better


def _are_equivalent(vec_a: Sequence[float], vec_b: Sequence[float], tol: float = FLOAT_TOLERANCE) -> bool:
    """True if vector A and vector B have identical objective values within tolerance."""
    return all(abs(a - b) <= tol for a, b in zip(vec_a, vec_b))


def compute_pareto_set(
    feasible_plans: Sequence[Mapping[str, Any]],
    objectives: Sequence[Mapping[str, Any]],
    tol: float = FLOAT_TOLERANCE,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Compute the Pareto frontier from feasible plans and link equivalent policies.

    Input order does not select an arbitrary winner.
    """
    if not feasible_plans:
        return [], {}

    vectors: dict[str, list[float]] = {}
    for plan in feasible_plans:
        pid = str(plan["policy_id"])
        vectors[pid] = _extract_candidate_eval_vector(plan["objective_values"], objectives)

    pareto_list: list[dict] = []
    for plan_a in feasible_plans:
        pid_a = str(plan_a["policy_id"])
        vec_a = vectors[pid_a]
        is_dominated = False
        for plan_b in feasible_plans:
            pid_b = str(plan_b["policy_id"])
            if pid_a == pid_b:
                continue
            vec_b = vectors[pid_b]
            if _dominates(vec_b, vec_a, tol):
                is_dominated = True
                break
        if not is_dominated:
            pareto_list.append(copy.deepcopy(dict(plan_a)))

    # Link equivalent policies
    equivalent_map: dict[str, list[str]] = {}
    for p_a in pareto_list:
        pid_a = str(p_a["policy_id"])
        vec_a = vectors[pid_a]
        equivs = []
        for other in feasible_plans:
            pid_o = str(other["policy_id"])
            if pid_o != pid_a and _are_equivalent(vec_a, vectors[pid_o], tol):
                equivs.append(pid_o)
        equivalent_map[pid_a] = sorted(equivs)
        p_a["equivalent_policies"] = sorted(equivs)

    return pareto_list, equivalent_map


def _sample_numerical_bounds(spec: Mapping[str, Any], count: int = 3) -> list[Any]:
    lower = spec.get("lower", 0)
    upper = spec.get("upper", 0)
    unit = spec.get("unit")
    if lower == upper:
        return [lower]

    if unit in ("units", "students") or (
        isinstance(lower, int) and isinstance(upper, int) and (upper - lower) <= 6
    ):
        step = max(1, (upper - lower) // (count - 1)) if count > 1 else 1
        pts = list(range(int(lower), int(upper) + 1, step))
        if pts[-1] != upper:
            pts.append(int(upper))
        return sorted(list(dict.fromkeys(pts)))

    pts_f = [lower + i * (upper - lower) / (count - 1) for i in range(count)]
    if isinstance(lower, int) and isinstance(upper, int):
        pts_round = [int(round(x)) for x in pts_f]
        return sorted(list(dict.fromkeys(pts_round)))
    return sorted(list(dict.fromkeys(round(x, 2) for x in pts_f)))


def _set_nested_key(target: dict, key_path: str, value: Any) -> None:
    parts = key_path.split(".")
    curr = target
    for p in parts[:-1]:
        if p not in curr or not isinstance(curr[p], dict):
            curr[p] = {}
        curr = curr[p]
    curr[parts[-1]] = value


def _ensure_proposal(proposal: Mapping[str, Any], search_space: dict | None = None) -> dict:
    """Normalize either a raw proposal dict or a checked proposal result into a proposal dict."""
    prop_d = copy.deepcopy(dict(proposal))
    if prop_d.get("accepted") is True and "policy" in prop_d:
        pol = dict(prop_d["policy"])
        ss = dict(prop_d.get("search_space") or search_space or {})
        fixed = dict(ss.get("fixed_decisions") or prop_d.get("fixed_decisions") or {})
        tunable = {}
        for k, v in (ss.get("allowed_values") or {}).items():
            tunable[k] = {"allowed": list(v)}
        for k, v in (ss.get("numerical_bounds") or {}).items():
            tunable[k] = dict(v)
        grouping = copy.deepcopy(pol.get("grouping") or {})
        regroup = copy.deepcopy(grouping.get("regroup_policy") or {"required": False})
        counting = copy.deepcopy(
            pol.get("counting") or {"placement": "none", "method": None, "assignments": {}}
        )
        rebuilt = {
            "proposal_id": pol.get("policy_id") or "checked_proposal",
            "grouping": grouping,
            "regroup_policy": regroup,
            "release_rule": copy.deepcopy(pol.get("release_rule") or {"type": "immediate"}),
            "counting": counting,
            "worker_allocation": copy.deepcopy(
                pol.get("worker_allocation") or {"assignments": [], "count": 0}
            ),
            "vehicle_dispatch_rule": copy.deepcopy(
                pol.get("vehicle_dispatch_rule") or {"type": "none"}
            ),
            "destination_rule": copy.deepcopy(
                pol.get("destination_rule") or {"type": "complete_after_stages"}
            ),
            "fixed_choices": fixed,
            "tunable": tunable,
            "assumptions": list(
                prop_d.get("assumptions")
                or [
                    {
                        "id": "checked_default",
                        "label": "Checked proposal",
                        "kind": "grouping_choice",
                        "status": "stated",
                    }
                ]
            ),
        }
        fairness = pol.get("fairness_limit") or prop_d.get("fairness_limit")
        if fairness not in (None, {}, ""):
            rebuilt["fairness_limit"] = copy.deepcopy(fairness)
        return rebuilt
    return prop_d


def generate_candidates(
    base_proposal: Mapping[str, Any],
    search_space: Mapping[str, Any],
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    scenario: Mapping[str, Any] | None = None,
) -> list[dict]:
    """Deterministically generate candidate proposals within the bounded search space."""
    candidates: list[dict] = []
    allowed_values = dict(search_space.get("allowed_values") or {})
    numerical_bounds = dict(search_space.get("numerical_bounds") or {})
    grouping_bases = list(search_space.get("grouping_bases") or GROUPING_BASES)

    fixed = dict(
        search_space.get("fixed_decisions")
        or search_space.get("fixed_choices")
        or base_proposal.get("fixed_choices")
        or base_proposal.get("fixed_decisions")
        or {}
    )
    grouping_fixed = (
        "grouping.basis" in fixed
        or "grouping_basis" in fixed
        or (
            isinstance(fixed.get("grouping"), Mapping)
            and "basis" in fixed["grouping"]
        )
    )
    tunable = search_space.get("tunable") or base_proposal.get("tunable")
    if isinstance(tunable, Mapping):
        grouping_tunable = (
            "grouping.basis" in tunable
            or "grouping_basis" in tunable
            or "grouping" in tunable
            or "basis" in tunable
        )
    else:
        grouping_tunable = False

    if grouping_fixed:
        allowed_values.pop("grouping.basis", None)
    elif "grouping.basis" not in allowed_values and grouping_tunable:
        allowed_values["grouping.basis"] = grouping_bases
    # Candidate 0: the unmodified base proposal
    c0 = copy.deepcopy(dict(base_proposal))
    c0["proposal_id"] = str(base_proposal.get("proposal_id") or "proposal_baseline")
    c0["parameters"] = {}
    candidates.append(c0)

    # Compile discrete parameter choices
    param_options: dict[str, list[Any]] = {}
    for k, vals in allowed_values.items():
        if vals:
            param_options[k] = list(vals)

    for k, bounds in numerical_bounds.items():
        if isinstance(bounds, Mapping):
            param_options[k] = _sample_numerical_bounds(bounds, count=3)

    # 1D single-parameter variations
    for param_key in sorted(param_options.keys()):
        for val in param_options[param_key]:
            if len(candidates) >= max_candidates:
                break
            cand = copy.deepcopy(dict(base_proposal))
            _apply_search_parameter(
                cand, param_key, val, base_proposal, search_space, scenario
            )
            cid = f"cand_{len(candidates):03d}_{param_key.replace('.', '_')}_{str(val).replace('.', '_')}"
            cand["proposal_id"] = cid
            cand["parameters"] = {param_key: val}
            candidates.append(cand)

    # Joint combinations across primary grouping and release choices if space permits
    primary_keys = [
        k
        for k in (
            "grouping.basis",
            "release_rule.interval_s",
            "grouping.maximum_assembly_wait_s",
            "grouping.split_policy",
        )
        if k in param_options
    ]
    if len(primary_keys) >= 2 and len(candidates) < max_candidates:
        val_lists = [param_options[k] for k in primary_keys]
        for combo in itertools.product(*val_lists):
            if len(candidates) >= max_candidates:
                break
            cand = copy.deepcopy(dict(base_proposal))
            param_map = {}
            for k, val in zip(primary_keys, combo):
                _apply_search_parameter(
                    cand, k, val, base_proposal, search_space, scenario
                )
                param_map[k] = val
            # Avoid duplicate of candidate 0
            if any(c.get("parameters") == param_map for c in candidates):
                continue
            cid = f"cand_{len(candidates):03d}_joint"
            cand["proposal_id"] = cid
            cand["parameters"] = param_map
            candidates.append(cand)

    return candidates


def search(
    proposal: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    scenarios: Mapping[str, Any] | Sequence[Any],
    *,
    base_scenario: Mapping[str, Any] | None = None,
    objectives: Sequence[str | Mapping[str, Any]] | None = None,
    evaluation_limits: Mapping[str, Any] | None = None,
    budget: Mapping[str, Any] | None = None,
    permitted_decisions: Mapping[str, Any] | None = None,
    layout_assumptions: Mapping[str, Any] | list | None = None,
    hard_constraints: Mapping[str, Any] | None = None,
    dataset_role: str = "development",
    seed: int = 42,
) -> dict:
    """Bounded search across grouping and operating choices.

    Accepts only checked proposals and required scenarios.
    Returns evaluated feasible plans, Pareto tradeoffs, equivalent policy links,
    failure records, search coverage, and stopping reason.
    """
    t_start = time.perf_counter()

    # Rule: Do not feed ticket-12 final independent cases into selection
    if dataset_role == "final_independent":
        raise SimulationError(
            "fixed_rule_violation",
            f"Cannot claim independent validation or use dataset_role '{dataset_role}' during search/selection. "
            "Final independent cases cannot be fed back into candidate selection.",
            field="dataset_role",
        )

    # Resolve evaluation limits / budget
    limits = dict(evaluation_limits or budget or {})
    max_candidates = int(limits.get("max_candidates", DEFAULT_MAX_CANDIDATES))
    max_cases_per_candidate = int(limits.get("max_cases_per_candidate", DEFAULT_MAX_CASES_PER_CANDIDATE))
    # Do not raise a case's own event limit. Apply a tighter cap only when requested.
    explicit_max_events = "max_events_per_run" in limits
    max_events_per_run = int(limits["max_events_per_run"]) if explicit_max_events else None

    if max_candidates <= 0:
        raise SimulationError(
            "invalid_value_or_unit",
            f"max_candidates must be positive, got {max_candidates}",
            field="evaluation_limits.max_candidates",
        )

    # Scenarios normalization
    if isinstance(scenarios, Mapping) and ("route_stages" in scenarios or "places" in scenarios):
        case_list = [scenarios]
        base_sc = dict(scenarios) if base_scenario is None else dict(base_scenario)
    elif isinstance(scenarios, Sequence):
        case_list = list(scenarios)
        base_sc = (
            dict(base_scenario)
            if base_scenario is not None
            else (
                dict(case_list[0])
                if (
                    case_list
                    and isinstance(case_list[0], Mapping)
                    and ("route_stages" in case_list[0] or "places" in case_list[0])
                )
                else None
            )
        )
    else:
        raise SimulationError(
            "missing_input",
            "scenarios must be a scenario Mapping or a Sequence of cases",
            field="scenarios",
        )

    resolved_scenarios = _resolve_cases(case_list, base_sc)
    if not resolved_scenarios:
        raise SimulationError(
            "missing_input",
            "At least one scenario/case is required for search evaluation",
            field="scenarios",
        )

    # Rule: ticket-12 GPS holdouts and final_independent cases stay out of selection
    if base_sc is not None:
        _reject_selection_holdout(base_sc)
    for c in case_list:
        _reject_selection_holdout(c)
    for sc in resolved_scenarios:
        _reject_selection_holdout(sc)

    # Rule: Requested cases cannot be silently dropped
    if len(resolved_scenarios) > max_cases_per_candidate:
        raise SimulationError(
            "invalid_value_or_unit",
            f"Requested {len(resolved_scenarios)} cases exceeds max_cases_per_candidate={max_cases_per_candidate}. "
            "Requested cases cannot be silently dropped. Any reduction must occur before candidate comparison.",
            field="evaluation_limits.max_cases_per_candidate",
        )

    # Normalize objectives
    normalized_objectives = _normalize_objectives(objectives)

    # Validate proposal
    if proposal is None:
        raise SimulationError(
            "missing_input",
            "Missing critical input: proposal",
            field="proposal",
        )

    candidates_to_evaluate: list[dict] = []
    search_space: dict = {}
    failure_records: list[dict] = []
    candidate_order: list[str] = []

    if isinstance(proposal, Sequence) and not isinstance(proposal, (str, bytes, Mapping)):
        # Explicit sequence of candidate proposals provided
        for idx, p in enumerate(proposal):
            if not isinstance(p, Mapping):
                raise SimulationError("invalid_value_or_unit", f"proposal {idx} must be an object", field=f"proposal[{idx}]")
            _validate_forbidden_information(p)
            cid = str(p.get("proposal_id", f"candidate_{idx}"))
            candidate_order.append(cid)
            candidates_to_evaluate.append(dict(p))
    else:
        if not isinstance(proposal, Mapping):
            raise SimulationError("invalid_value_or_unit", "proposal must be an object", field="proposal")
        _validate_forbidden_information(proposal)

        # Single proposal provided: check it first
        if proposal.get("accepted") is True and "search_space" in proposal:
            checked_base = dict(proposal)
            search_space = dict(checked_base["search_space"])
            base_prop = _ensure_proposal(checked_base, search_space)
        else:
            if base_sc is None:
                raise SimulationError(
                    "missing_input",
                    "base_scenario required to check proposal",
                    field="base_scenario",
                )
            checked_base = check_proposal(
                proposal,
                base_sc,
                layout_assumptions=layout_assumptions,
                permitted_decisions=permitted_decisions,
            )
            if not checked_base.get("accepted"):
                category = checked_base.get("category") or "unsupported_policy"
                message = checked_base.get("message") or "Proposal check failed"
                raise SimulationError(
                    category,
                    f"Search accepts only checked valid proposals. Check failed: {message}",
                    field=checked_base.get("field"),
                    details=checked_base.get("details"),
                )
            search_space = dict(checked_base["search_space"])
            base_prop = dict(proposal)

        # Generate candidates within the search space
        generated = generate_candidates(
            base_prop,
            search_space,
            max_candidates=max_candidates,
            scenario=base_sc,
        )
        candidates_to_evaluate = generated
        candidate_order = [str(c["proposal_id"]) for c in candidates_to_evaluate]

    # Evaluate each candidate across all required scenarios
    evaluated_plans: list[dict] = []
    feasible_plans: list[dict] = []
    disqualified_plans: list[dict] = []
    candidates_attempted = 0
    total_simulations = 0
    bases_seen: set[str] = set()
    params_varied: set[str] = set()
    sim_cache: dict[tuple[str, str], dict] = {}

    for cand_prop in candidates_to_evaluate:
        if candidates_attempted >= max_candidates:
            break

        candidates_attempted += 1
        cid = str(cand_prop.get("proposal_id", f"cand_{candidates_attempted}"))
        cand_params = dict(cand_prop.get("parameters") or {})
        for pk in cand_params:
            params_varied.add(pk)

        # Re-check candidate proposal through check_proposal to ensure correctness
        checked_cand = check_proposal(
            cand_prop,
            base_sc,
            layout_assumptions=layout_assumptions,
            permitted_decisions=permitted_decisions,
        )

        if not checked_cand.get("accepted"):
            err_record = {
                "policy_id": cid,
                "proposal_id": cid,
                "is_feasible": False,
                "reasons": [checked_cand.get("message", "proposal_check_failed")],
                "failed_cases": ["proposal_validation"],
                "parameters": cand_params,
                "error": True,
            }
            failure_records.append(err_record)
            disqualified_plans.append(err_record)
            continue

        cand_policy = dict(checked_cand["policy"])
        cand_policy["policy_id"] = cid
        _attach_fairness_limit(cand_policy, cand_prop, hard_constraints)

        # Rule: Reactive rules use delivered reports only. No hidden future.
        try:
            _validate_forbidden_information(cand_policy)
        except SimulationError as err:
            err_record = {
                "policy_id": cid,
                "proposal_id": cid,
                "is_feasible": False,
                "reasons": [str(err)],
                "failed_cases": ["hidden_future_validation"],
                "parameters": cand_params,
                "error": True,
            }
            failure_records.append(err_record)
            disqualified_plans.append(err_record)
            continue

        basis = cand_policy.get("grouping", {}).get("basis")
        if basis:
            bases_seen.add(basis)

        # Canonical key for physical candidate deduplication (ignoring policy_id)
        canon_cand = copy.deepcopy(cand_policy)
        canon_cand.pop("policy_id", None)
        canon_key = json.dumps(canon_cand, sort_keys=True, default=str)

        # Simulate across all required resolved scenarios
        cand_runs: list[dict] = []
        failed_cases: list[str] = []
        failure_reasons: dict[str, list[str]] = {}
        cand_outputs: dict[str, dict] = {}

        for sc in resolved_scenarios:
            case_id = sc["case_metadata"]["case_id"]
            sc_work = copy.deepcopy(sc)
            if max_events_per_run is not None:
                existing_limit = (
                    sc_work.get("max_events_per_run")
                    or (sc_work.get("operating_rules") or {}).get("max_events_per_run")
                    or sc_work.get("max_events")
                )
                if existing_limit is not None:
                    sc_work["max_events_per_run"] = min(int(existing_limit), max_events_per_run)
                else:
                    sc_work["max_events_per_run"] = max_events_per_run

            cache_key = (canon_key, case_id)
            if cache_key in sim_cache:
                sim_res = copy.deepcopy(sim_cache[cache_key])
            else:
                sim_res = simulate_case_safely(sc_work, cand_policy)
                total_simulations += 1
                sim_cache[cache_key] = copy.deepcopy(sim_res)

            if case_id in cand_outputs:
                dup_key = f"{case_id}_{len(cand_outputs)}"
                cand_outputs[dup_key] = sim_res
            else:
                cand_outputs[case_id] = sim_res

            measures = sim_res.get("measures", {})
            reasons = simulation_failure_reasons(sim_res, hard_constraints or {}, sc_work)
            reasons.extend(_fairness_failure_reasons(measures))

            if reasons:
                failed_cases.append(case_id)
                failure_reasons.setdefault(case_id, []).extend(reasons)

            cand_runs.append(
                {
                    "case_id": case_id,
                    "measures": measures,
                    "status": sim_res.get("status"),
                    "failed": bool(reasons),
                    "reasons": reasons,
                }
            )

        is_feasible = len(failed_cases) == 0


        # Base run and worst run identification
        base_run = next(
            (r for r in cand_runs if "base" in r["case_id"].lower()),
            cand_runs[0] if cand_runs else None,
        )

        # Compute values for all normalized objectives
        obj_values_by_name: dict[str, dict[str, float]] = {}
        for obj in normalized_objectives:
            field = obj["field"]
            name = obj["name"]
            direction = obj.get("direction", "min")

            base_val = extract_objective_value(field, base_run["measures"]) if base_run else 0.0
            all_vals = [extract_objective_value(field, r["measures"]) for r in cand_runs]

            if direction == "max":
                worst_val = min(all_vals) if all_vals else base_val
            else:
                worst_val = max(all_vals) if all_vals else base_val

            mean_val = sum(all_vals) / len(all_vals) if all_vals else base_val
            weights = [case_weight(sc) for sc in resolved_scenarios]
            tot_w = sum(weights)
            weighted_val = (
                sum(w * v for w, v in zip(weights, all_vals)) / tot_w
                if tot_w > 0
                else mean_val
            )

            obj_values_by_name[name] = {
                "base": round(base_val, 4),
                "worst_case": round(worst_val, 4),
                "mean": round(mean_val, 4),
                "weighted_mean": round(weighted_val, 4),
                "all_cases": {r["case_id"]: round(v, 4) for r, v in zip(cand_runs, all_vals)},
            }
        cand_summary = {
            "policy_id": cid,
            "proposal_id": cid,
            "is_feasible": is_feasible,
            "parameters": cand_params,
            "policy": cand_policy,
            "objective_values": obj_values_by_name,
            "failed_cases": failed_cases,
            "failure_reasons": failure_reasons,
            "base_case": base_run["measures"] if base_run else None,
            "worst_case_wait_s": max(
                (r["measures"]["total_student_waiting_student_s"] for r in cand_runs), default=0.0
            ),
            "visible_metrics": {
                "outdoor_waiting_student_s": base_run["measures"].get("outdoor_waiting_student_s")
                if base_run
                else {},
                "total_required_journey_student_s": base_run["measures"].get(
                    "total_required_journey_student_s"
                )
                if base_run
                else 0.0,
                "operating_limit_exceedance": base_run["measures"].get("operating_limit_exceedance")
                if base_run
                else {},
                "headcount_actions": base_run["measures"].get("headcount_actions") if base_run else 0,
                "recounts": base_run["measures"].get("recounts") if base_run else 0,
                "vehicles": base_run["measures"].get("vehicles") if base_run else {},
                "fairness": base_run["measures"].get("fairness") if base_run else {},
                "by_hostel": base_run["measures"].get("by_hostel") if base_run else [],
            },
            "simulation_outputs": cand_outputs,
        }

        evaluated_plans.append(cand_summary)

        if is_feasible:
            feasible_plans.append(cand_summary)
        else:
            failure_records.append(cand_summary)
            disqualified_plans.append(cand_summary)

    # Determine stopping reason
    if candidates_attempted >= max_candidates or len(evaluated_plans) >= max_candidates:
        stopping_reason = "evaluation_budget_reached"
    else:
        stopping_reason = "search_space_exhausted"

    # Compute Pareto set from feasible plans
    pareto_set, equivalent_links = compute_pareto_set(feasible_plans, normalized_objectives)

    # Build coverage summary
    search_coverage = {
        "candidates_attempted": candidates_attempted,
        "candidates_evaluated": len(evaluated_plans),
        "candidates_feasible": len(feasible_plans),
        "candidates_disqualified": len(disqualified_plans),
        "pareto_plans_count": len(pareto_set),
        "grouping_bases_evaluated": sorted(list(bases_seen)),
        "parameters_varied": sorted(list(params_varied)),
        "total_simulations": total_simulations,
    }

    elapsed_s = round(time.perf_counter() - t_start, 4)

    return {
        "claim": "best plans found within the stated search",
        "claims": ["best plans found within the stated search"],
        "search_method": "bounded_search",
        "stopping_reason": stopping_reason,
        "candidates_attempted": candidates_attempted,
        "candidate_order": candidate_order,
        "bounds": search_space.get("numerical_bounds", {}),
        "allowed_values": search_space.get("allowed_values", {}),
        "evaluated_plans": evaluated_plans,
        "evaluated_choices": evaluated_plans,
        "feasible_plans": feasible_plans,
        "feasible_set": feasible_plans,
        "feasible_policies": [p["policy_id"] for p in feasible_plans],
        "pareto_set": pareto_set,
        "pareto_policies": [p["policy_id"] for p in pareto_set],
        "tradeoffs": pareto_set,
        "equivalent_policies": equivalent_links,
        "failed_cases": failure_records,
        "failure_records": failure_records,
        "disqualified_plans": disqualified_plans,
        "search_coverage": search_coverage,
        "evaluation_limits": {
            "max_candidates": max_candidates,
            "max_cases_per_candidate": max_cases_per_candidate,
            "max_events_per_run": max_events_per_run,
            "max_events_per_run_source": "request" if explicit_max_events else "scenario",
        },
        "objectives": normalized_objectives,
        "versions": {
            "engine_version": ENGINE_VERSION,
            "software_revision": SOFTWARE_REVISION,
            "format_version": base_sc.get("format_version") if base_sc else None,
            "data_version": base_sc.get("data_version") if base_sc else None,
        },
        "runtime": {
            "elapsed_s": elapsed_s,
            "machine": platform.node(),
        },
        "workload": {
            "candidates_attempted": candidates_attempted,
            "candidates_evaluated": len(evaluated_plans),
            "total_simulations": total_simulations,
        },
    }


def bounded_search(*args: Any, **kwargs: Any) -> dict:
    """Public alias for search."""
    return search(*args, **kwargs)
