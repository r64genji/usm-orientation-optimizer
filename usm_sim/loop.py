"""Ticket 11: AI proposal, search, and simulation loop.

Public Check -> Search -> Simulate loop.
Accepts campus facts, fixed rules, permitted changes, development cases,
previous development results, and a round budget.
Evaluates human, fixture, or AI proposals strictly through simulation.
No live radio transmission, production dispatch, or organizer decisions.
"""

from __future__ import annotations

import copy
import platform
import time
from typing import Any, Callable, Mapping, Sequence

from usm_sim.benchmark import (
    build_current_operation_policy,
    build_fixed_release_policy,
    build_queue_based_policy,
)
from usm_sim.constants import ENGINE_VERSION
from usm_sim.errors import SimulationError
from usm_sim.proposals import check_proposal
from usm_sim.search import (
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MAX_CASES_PER_CANDIDATE,
    GPS_HOLDOUT_SCENARIO_IDS,
    _extract_candidate_eval_vector,
    _normalize_objectives,
    compute_pareto_set,
    search,
)
from usm_sim.uncertainty import (
    compare_policies,
    infer_dataset_role,
    is_gps_holdout_case,
    iter_case_identity_values,
    resolve_case,
)

DEFAULT_ROUND_BUDGET = 5

UNTRUSTED_AI_FIELDS = frozenset(
    {
        "estimated_queue_time",
        "estimated_queue_time_s",
        "ai_queue_time",
        "ai_queue_time_s",
        "predicted_success",
        "success_claim",
        "success_claims",
        "ai_performance",
        "claimed_performance",
        "claimed_waiting_time_s",
        "claimed_mean_wait_s",
        "claimed_lateness_s",
        "claimed_resource_usage",
        "estimated_resource_usage",
        "predicted_performance",
    }
)


def _sanitize_proposal(raw_proposal: Mapping[str, Any]) -> tuple[dict, list[str]]:
    """Deep copy proposal and strip untrusted AI performance claims.
    
    Returns the cleaned proposal and a list of untrusted fields removed.
    """
    cleaned = copy.deepcopy(dict(raw_proposal))
    removed_untrusted: list[str] = []
    for key in list(cleaned.keys()):
        if key in UNTRUSTED_AI_FIELDS:
            removed_untrusted.append(key)
            del cleaned[key]
    return cleaned, removed_untrusted


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _holdout_ids(case: Any) -> list[str]:
    """Collect identifiers that may mark a ticket-12 GPS replay."""
    return iter_case_identity_values(case)


def _dataset_role(case: Any) -> str | None:
    if isinstance(case, tuple) and len(case) == 2:
        return infer_dataset_role(case[0], case[1])
    if isinstance(case, Mapping):
        return infer_dataset_role(case)
    return None


def _prepare_development_cases(
    cases: Sequence[Any],
    previous_results: Sequence[Mapping[str, Any]] | None,
) -> tuple[list, list[str]]:
    """Reject GPS holdouts. Relabel a former independent case used to adjust."""
    prepared: list = []
    relabelled: list[str] = []
    follow_up_adjustment = bool(previous_results)
    for case in cases:
        if is_gps_holdout_case(case):
            hit = next((item for item in iter_case_identity_values(case) if item in GPS_HOLDOUT_SCENARIO_IDS), "GPS holdout")
            raise SimulationError(
                "fixed_rule_violation",
                f"Case {hit} is a ticket-12 GPS holdout scenario (restu_17sep_replay, restu_18sep_rainy_replay) and cannot be used in development cases",
                field="development_cases",
            )
        if isinstance(case, tuple) and len(case) == 2:
            role = infer_dataset_role(case[0], case[1])
            if role == "final_independent":
                if not follow_up_adjustment:
                    raise SimulationError(
                        "fixed_rule_violation",
                        "Case tuple has dataset_role='final_independent' and cannot be used during proposal development",
                        field="development_cases",
                    )
            prepared.append(case)
            continue
        if not isinstance(case, Mapping):
            prepared.append(case)
            continue
        work = copy.deepcopy(dict(case))
        if _dataset_role(work) == "final_independent":
            label = str(
                (_as_mapping(work.get("case_metadata")) or {}).get("case_id")
                or work.get("case_id")
                or work.get("scenario_id")
                or "unnamed"
            )
            if not follow_up_adjustment:
                raise SimulationError(
                    "fixed_rule_violation",
                    f"Case {label} has dataset_role='final_independent' and cannot be used during proposal development",
                    field="development_cases",
                )
            meta = work.get("case_metadata")
            if not isinstance(meta, dict):
                meta = {}
                work["case_metadata"] = meta
            meta["dataset_role"] = "development"
            meta["relabelled_from"] = "final_independent"
            work["dataset_role"] = "development"
            relabelled.append(label)
        prepared.append(work)
    return prepared, relabelled


def _is_final_or_holdout_result(row: Mapping[str, Any]) -> bool:
    if is_gps_holdout_case(row):
        return True
    meta = _as_mapping(row.get("case_metadata")) or {}
    for role in (row.get("dataset_role"), row.get("role"), meta.get("dataset_role"), row.get("case_role")):
        if role == "final_independent":
            return True
    if row.get("status") in ("final_evaluation", "final_independent") or row.get("phase") == "final":
        return True
    if row.get("is_final") is True:
        return True
    if "final_evaluation" in row and not row.get("rounds") and not row.get("evaluated_plans"):
        return True
    return False


def _sanitize_history_record(row: Mapping[str, Any]) -> dict | None:
    if _is_final_or_holdout_result(row):
        return None
    cleaned = copy.deepcopy(dict(row))
    for key in (
        "final_evaluation",
        "final_results",
        "final_cases",
        "final_independent_eval",
        "holdout_results",
        "holdout_cases",
    ):
        cleaned.pop(key, None)
    return cleaned


def _evaluate_final_cases(
    best_policy: Mapping[str, Any] | None,
    final_cases: Sequence[Any],
    base_scenario: Mapping[str, Any],
    hard_constraints: Mapping[str, Any] | None,
    seed: int,
) -> dict:
    """Evaluate independent cases only after selection. Never use them to pick a plan."""
    resolved: list = []
    errors: list[dict] = []
    for case in final_cases:
        try:
            if isinstance(case, Mapping) and "case_id" in case and "places" not in case:
                resolved.append(resolve_case(base_scenario, case, seed=seed))
            else:
                resolved.append(case)
        except SimulationError as err:
            errors.append(err.as_dict())

    if not resolved or best_policy is None:
        payload = {
            "dataset_role": "final_independent",
            "used_for_selection": False,
            "shared_case_ids": [],
            "error": bool(errors) or best_policy is None,
            "errors": errors,
        }
        if best_policy is None:
            payload["message"] = "No selected policy was available for final independent evaluation."
        return payload

    try:
        compared = compare_policies(
            {str(best_policy.get("policy_id") or "best_plan"): best_policy},
            resolved,
            base_scenario=base_scenario,
            hard_constraints=hard_constraints,
            dataset_role="final_independent",
            claim_independent_validation=True,
        )
        compared["used_for_selection"] = False
        if errors:
            compared["errors"] = errors
        return compared
    except SimulationError as err:
        payload = err.as_dict()
        payload.update(
            {
                "dataset_role": "final_independent",
                "used_for_selection": False,
                "error": True,
                "errors": errors + [err.as_dict()],
                "message": (
                    "Final independent evaluation did not complete: "
                    f"{err.message}. Final cases were not used to select the plan."
                ),
            }
        )
        return payload


def partition_accuracy_checks(
    checks: Sequence[Mapping[str, Any]] | None,
) -> dict[str, list[dict]]:
    """Distinguish evidence-supported +-10 min checks from unverified predictions.

    Measured route checks with a demonstrated error of at most 600 s are
    evidence-supported. Unmeasured routes and estimated scenarios are unverified.
    Imposed inputs are neither.
    """
    evidence_supported: list[dict] = []
    unverified: list[dict] = []
    if not checks:
        return {
            "evidence_supported_checks": evidence_supported,
            "unverified_predictions": unverified,
        }

    for raw in checks:
        c_dict = dict(raw)
        role = str(c_dict.get("role") or "").lower()
        status = str(c_dict.get("accuracy_status") or c_dict.get("status") or "").lower()
        is_unverified = (
            role in ("unverified", "unmeasured", "estimated")
            or c_dict.get("unmeasured") is True
            or status in ("unverified", "not_demonstrated")
            or c_dict.get("verified") is False
            or c_dict.get("demonstrated") is False
            or c_dict.get("eligible_measured_accuracy") is False
        )
        if is_unverified:
            unverified.append(c_dict)
            continue
        if role in ("imposed_input", "imposed") or c_dict.get("imposed_input") is True:
            continue
        is_evidence = (
            c_dict.get("measured_accuracy_pass") is True
            or c_dict.get("milestone_error_le_600s") is True
            or c_dict.get("verified") is True
            or status in ("pass", "passed")
        )
        if is_evidence:
            evidence_supported.append(c_dict)
        elif role in ("predicted", "predicted_duration", "calibrated", "measured", "observed"):
            if c_dict.get("measured_accuracy_pass") is False or c_dict.get("passed") is False:
                continue
            evidence_supported.append(c_dict)
        else:
            unverified.append(c_dict)

    return {
        "evidence_supported_checks": evidence_supported,
        "unverified_predictions": unverified,
    }


def build_loop_proposal(
    policy: Mapping[str, Any] | None = None,
    *,
    proposal_id: str = "fixture_loop_proposal",
    grouping_basis: str = "floor",
    grouping_overrides: Mapping[str, Any] | None = None,
    assembly_overrides: Mapping[str, Any] | None = None,
    release_rule: Mapping[str, Any] | None = None,
    counting: Mapping[str, Any] | None = None,
    worker_allocation: Mapping[str, Any] | None = None,
    vehicle_dispatch_rule: Mapping[str, Any] | None = None,
    destination_rule: Mapping[str, Any] | None = None,
    fixed_choices: Mapping[str, Any] | None = None,
    tunable: Mapping[str, Any] | None = None,
    assumptions: Sequence[Mapping[str, Any]] | None = None,
    **extra: Any,
) -> dict:
    """Convenience builder for valid human/fixture operating proposals."""
    pol_d = copy.deepcopy(dict(policy or {}))
    grouping = copy.deepcopy(pol_d.get("grouping") or {})
    grouping["basis"] = grouping_basis
    if grouping_overrides:
        grouping.update(grouping_overrides)
    if assembly_overrides:
        grouping.update(assembly_overrides)

    regroup = copy.deepcopy(grouping.get("regroup_policy") or {"required": False})

    cnt = copy.deepcopy(pol_d.get("counting") or {})
    if not isinstance(cnt, dict):
        cnt = {}
    cnt.setdefault("assignments", {})
    cnt.setdefault("placement", "none")
    cnt.setdefault("method", None)
    if counting:
        cnt.update(counting)

    rel = copy.deepcopy(release_rule or pol_d.get("release_rule") or {"type": "immediate"})
    wrk = copy.deepcopy(worker_allocation or pol_d.get("worker_allocation") or {"assignments": [], "count": 0})
    veh = copy.deepcopy(vehicle_dispatch_rule or pol_d.get("vehicle_dispatch_rule") or {"type": "none"})
    dst = copy.deepcopy(destination_rule or pol_d.get("destination_rule") or {"type": "complete_after_stages"})

    fix = copy.deepcopy(dict(fixed_choices or pol_d.get("fixed_choices") or {}))
    if "required_endpoint" not in fix and pol_d.get("required_endpoint"):
        fix["required_endpoint"] = pol_d.get("required_endpoint")

    tun = copy.deepcopy(dict(tunable or pol_d.get("tunable") or {}))
    if not tun:
        tun = {
            "grouping.basis": {
                "allowed": [
                    "floor",
                    "wing",
                    "building",
                    "target_size",
                    "mixed",
                ]
            },
            "grouping.units_per_group": {"lower": 1, "upper": 4, "unit": "units"},
            "grouping.maximum_assembly_wait_s": {"lower": 0, "upper": 300, "unit": "s"},
            "release_rule.interval_s": {"lower": 0, "upper": 120, "unit": "s"},
        }

    asm = list(assumptions or pol_d.get("assumptions") or [
        {
            "id": "loop_fixture_assumption",
            "label": "Loop fixture proposal assumption",
            "kind": "grouping_choice",
            "status": "stated",
        }
    ])

    proposal = {
        "proposal_id": proposal_id,
        "grouping": grouping,
        "regroup_policy": regroup,
        "release_rule": rel,
        "counting": cnt,
        "worker_allocation": wrk,
        "vehicle_dispatch_rule": veh,
        "destination_rule": dst,
        "fixed_choices": fix,
        "tunable": tun,
        "assumptions": asm,
    }
    proposal.update(extra)
    return proposal


def compare_with_references(
    best_policy: Mapping[str, Any],
    development_cases: Sequence[Any],
    base_scenario: Mapping[str, Any] | None = None,
    hard_constraints: Mapping[str, Any] | None = None,
) -> dict:
    """Compare selected policy with reference policies across shared development cases.
    
    All proposals in this comparison share identical reference policies, attendance,
    resource budget, development cases, and external conditions.
    """
    best_pol_d = copy.deepcopy(dict(best_policy))
    best_id = str(best_pol_d.get("policy_id") or "selected_best_plan")

    ref_current = copy.deepcopy(build_current_operation_policy(best_pol_d))
    ref_fixed = copy.deepcopy(build_fixed_release_policy(best_pol_d))
    ref_queue = copy.deepcopy(build_queue_based_policy(best_pol_d))

    ref_current["frozen"] = True
    ref_fixed["frozen"] = True
    ref_queue["frozen"] = True

    policies_to_compare = {
        best_id: best_pol_d,
        "reference_current_operation": ref_current,
        "reference_fixed_release": ref_fixed,
        "reference_queue_based": ref_queue,
    }

    res = compare_policies(
        policies_to_compare,
        development_cases,
        base_scenario=base_scenario,
        hard_constraints=hard_constraints,
        dataset_role="development",
    )
    res["reference_policies_frozen"] = True
    return res


def run_loop(
    campus_facts: Mapping[str, Any],
    *,
    fixed_rules: Mapping[str, Any] | None = None,
    permitted_changes: Mapping[str, Any] | None = None,
    development_cases: Sequence[Any] | None = None,
    previous_results: Sequence[Mapping[str, Any]] | None = None,
    round_budget: int = DEFAULT_ROUND_BUDGET,
    proposals: Sequence[Mapping[str, Any]] | Callable[[int, Sequence[dict]], Mapping[str, Any] | None] | None = None,
    evaluation_limits: Mapping[str, Any] | None = None,
    budget: Mapping[str, Any] | None = None,
    objectives: Sequence[str | Mapping[str, Any]] | None = None,
    hard_constraints: Mapping[str, Any] | None = None,
    layout_assumptions: Mapping[str, Any] | list | None = None,
    final_cases: Sequence[Any] | None = None,
    claim_independent_validation: bool = False,
    claim_production_dispatch: bool = False,
    seed: int = 42,
) -> dict:
    """Run proposal check -> search -> simulate iteration loop.

    Accepts campus facts, fixed rules, permitted changes, development cases,
    previous results, and a round budget.
    Evaluates human or fixture proposals without requiring a live LLM.
    Returns calculated performance, Pareto tradeoffs, reference comparisons,
    and structured delay records.
    """
    t_start = time.perf_counter()

    # Rule 1: No live radio transmission or production dispatch
    if claim_production_dispatch:
        raise SimulationError(
            "fixed_rule_violation",
            "Live radio transmission, production dispatch, or organizer decisions "
            "are not performed by the simulation loop. Loop is simulation only.",
            field="claim_production_dispatch",
        )

    # Rule 2: Exclude final independent benchmark cases from development feedback
    if claim_independent_validation:
        raise SimulationError(
            "fixed_rule_violation",
            "Cannot claim independent validation during development loop. "
            "Development feedback excludes final independent benchmark cases until "
            "candidate selection is complete.",
            field="claim_independent_validation",
        )

    if round_budget <= 0:
        raise SimulationError(
            "invalid_value_or_unit",
            f"round_budget must be positive, got {round_budget}",
            field="round_budget",
        )

    # Prepare base scenario and fixed rules
    base_scenario = copy.deepcopy(dict(campus_facts))
    if fixed_rules:
        op_rules = base_scenario.setdefault("operating_rules", {})
        if isinstance(op_rules, dict):
            op_rules.update(dict(fixed_rules))
        else:
            base_scenario["operating_rules"] = dict(fixed_rules)

    if is_gps_holdout_case(base_scenario):
        hit = next(
            item for item in _holdout_ids(base_scenario) if item in GPS_HOLDOUT_SCENARIO_IDS
        )
        raise SimulationError(
            "fixed_rule_violation",
            f"Scenario {hit} is a GPS holdout case and cannot be used for development/selection",
            field="campus_facts.scenario_id",
        )

    if development_cases is None or len(development_cases) == 0:
        raw_dev_cases = [base_scenario]
    else:
        raw_dev_cases = list(development_cases)

    history_records = [
        cleaned
        for row in (previous_results or [])
        if isinstance(row, Mapping) and (cleaned := _sanitize_history_record(row)) is not None
    ]
    prepared_dev_cases, relabelled_to_development = _prepare_development_cases(
        raw_dev_cases, previous_results
    )

    resolved_dev_cases = [
        resolve_case(base_scenario, c, seed=seed)
        if isinstance(c, Mapping) and "case_id" in c and "places" not in c
        else c
        for c in prepared_dev_cases
    ]

    # Setup limits
    limits = dict(evaluation_limits or budget or {})
    max_cand = limits.get("max_candidates", DEFAULT_MAX_CANDIDATES)
    max_cases = limits.get("max_cases_per_candidate", DEFAULT_MAX_CASES_PER_CANDIDATE)
    limits_resolved = {
        "max_candidates": int(max_cand),
        "max_cases_per_candidate": int(max_cases),
    }
    if "max_events_per_run" in limits:
        limits_resolved["max_events_per_run"] = int(limits["max_events_per_run"])
    elif "max_events" in limits:
        limits_resolved["max_events_per_run"] = int(limits["max_events"])
    # Tracking records across rounds
    rounds_executed: list[dict] = []
    recorded_proposals: list[dict] = []
    validation_errors: list[dict] = []
    all_evaluated_plans: list[dict] = []
    all_feasible_plans: list[dict] = []
    all_pareto_plans: list[dict] = []
    delay_explanations: list[dict] = []
    all_accuracy_checks: list[dict] = []
    stopping_reason = "round_budget_exhausted"
    failed_cases: list[dict] = []

    if isinstance(proposals, (str, bytes)):
        raise SimulationError(
            "invalid_value_or_unit",
            "proposals must be a sequence of proposal objects or a callable generator",
            field="proposals",
        )

    proposal_sequence: Sequence[Mapping[str, Any]] | None
    if isinstance(proposals, Mapping):
        proposal_sequence = [proposals]
    elif isinstance(proposals, Sequence):
        proposal_sequence = proposals
    else:
        proposal_sequence = None

    # Run proposal rounds
    for round_num in range(1, round_budget + 1):
        # Obtain proposal for this round
        raw_proposal: Mapping[str, Any] | None = None
        if proposal_sequence is not None:
            if round_num - 1 < len(proposal_sequence):
                raw_proposal = proposal_sequence[round_num - 1]
            else:
                stopping_reason = "all_proposals_evaluated"
                break
        elif callable(proposals):
            history_for_gen = history_records + rounds_executed
            raw_proposal = proposals(round_num, history_for_gen)
            if raw_proposal is None:
                stopping_reason = "proposal_generator_stopped"
                break
        else:
            stopping_reason = "no_proposals_provided"
            break

        if raw_proposal is None:
            stopping_reason = "proposal_is_none"
            break

        # Sanitize proposal: strip untrusted AI claims
        proposal, removed_ai_fields = _sanitize_proposal(raw_proposal)
        prop_id = str(proposal.get("proposal_id") or f"proposal_round_{round_num}")
        recorded_proposals.append(copy.deepcopy(proposal))

        # Check proposal against authoritative scenario rules
        # Invalid proposals stop at Check with field-specific errors, NO search
        check_result = check_proposal(
            proposal,
            base_scenario,
            layout_assumptions=layout_assumptions,
            permitted_decisions=permitted_changes,
        )

        if not check_result.get("accepted"):
            errors = check_result.get("errors") or [check_result]
            validation_errors.extend(errors)
            round_record = {
                "round": round_num,
                "proposal_id": prop_id,
                "proposal": copy.deepcopy(proposal),
                "status": "rejected_at_check",
                "accepted": False,
                "validation_errors": copy.deepcopy(errors),
                "untrusted_ai_fields_ignored": removed_ai_fields,
                "search_performed": False,
                "evaluated_choices": [],
                "feasible_plans": [],
                "pareto_set": [],
                "stopping_reason": "proposal_check_failed",
            }
            rounds_executed.append(round_record)
            continue

        # Proposal is valid: group formation must not add fictional headcounts
        grouping_summary = check_result.get("grouping") or {}
        headcounts_added = grouping_summary.get("headcounts_added", 0)
        if headcounts_added > 0:
            err = {
                "error": True,
                "category": "fixed_rule_violation",
                "field": "grouping.headcounts_added",
                "message": f"Group formation added {headcounts_added} fictional headcounts",
            }
            validation_errors.append(err)
            rounds_executed.append({
                "round": round_num,
                "proposal_id": prop_id,
                "proposal": copy.deepcopy(proposal),
                "status": "rejected_at_check",
                "accepted": False,
                "validation_errors": [err],
                "untrusted_ai_fields_ignored": removed_ai_fields,
                "search_performed": False,
                "evaluated_choices": [],
                "feasible_plans": [],
                "pareto_set": [],
                "stopping_reason": "fictional_headcount_added",
            })
            continue

        # Valid proposal: execute bounded numerical search within approved bounds
        search_res = search(
            check_result,
            resolved_dev_cases,
            base_scenario=base_scenario,
            objectives=objectives,
            evaluation_limits=limits_resolved,
            budget=budget,
            permitted_decisions=permitted_changes,
            layout_assumptions=layout_assumptions,
            hard_constraints=hard_constraints,
            dataset_role="development",
            seed=seed + round_num,
        )

        eval_plans = search_res.get("evaluated_plans", [])
        feas_plans = search_res.get("feasible_plans", [])
        pareto_plans = search_res.get("pareto_set", [])
        tradeoffs = search_res.get("tradeoffs", [])

        # Collect accuracy checks and delay explanations from simulation results
        round_delays: list[dict] = []
        round_accuracy: list[dict] = []
        for plan in eval_plans:
            if "measures" not in plan:
                plan["measures"] = plan.get("base_case") or {}
            sim_outputs = plan.get("simulation_outputs") or {}
            for case_id, sim_res in sim_outputs.items():
                if isinstance(sim_res, Mapping):
                    delays = sim_res.get("delay_explanations") or []
                    round_delays.extend(delays)
                    acc = sim_res.get("accuracy_checks") or []
                    round_accuracy.extend(acc)

        all_evaluated_plans.extend(eval_plans)
        all_feasible_plans.extend(feas_plans)
        all_pareto_plans.extend(pareto_plans)
        delay_explanations.extend(round_delays)
        all_accuracy_checks.extend(round_accuracy)
        failed_cases.extend(search_res.get("failed_cases") or [])

        best_cand = feas_plans[0] if feas_plans else None

        round_record = {
            "round": round_num,
            "proposal_id": prop_id,
            "proposal": copy.deepcopy(proposal),
            "status": "evaluated",
            "accepted": True,
            "validation_errors": [],
            "untrusted_ai_fields_ignored": removed_ai_fields,
            "search_performed": True,
            "search_coverage": search_res.get("search_coverage", {}),
            "evaluated_choices": eval_plans,
            "feasible_plans": feas_plans,
            "pareto_set": pareto_plans,
            "tradeoffs": tradeoffs,
            "best_candidate": best_cand,
            "failed_cases": search_res.get("failed_cases", []),
            "stopping_reason": search_res.get("stopping_reason"),
        }
        rounds_executed.append(round_record)

    # Post-search selection and reference comparison
    feasible_plan_found = len(all_feasible_plans) > 0
    best_plan: dict | None = None
    ref_comparisons: dict | None = None
    final_independent_eval: dict | None = None

    normalized_objectives = _normalize_objectives(objectives)
    global_pareto, global_equiv = compute_pareto_set(
        all_feasible_plans, normalized_objectives
    )
    all_pareto_plans = global_pareto

    if feasible_plan_found:
        # Pick best plan using declared objectives
        best_plan = min(
            all_feasible_plans,
            key=lambda p: (
                _extract_candidate_eval_vector(
                    p.get("objective_values", {}), normalized_objectives
                ),
                str(p.get("policy_id", "")),
            ),
        )
        if "measures" not in best_plan:
            best_plan["measures"] = best_plan.get("base_case") or {}

        # Final comparison against ticket 12 reference policies
        best_policy = best_plan.get("policy")
        if best_policy:
            ref_comparisons = compare_with_references(
                best_policy,
                resolved_dev_cases,
                base_scenario=base_scenario,
                hard_constraints=hard_constraints,
            )

        # Evaluate final independent cases only after candidate selection is complete.
        # GPS holdouts and other final cases never feed back into selection.
        if final_cases:
            final_independent_eval = _evaluate_final_cases(
                best_policy,
                final_cases,
                base_scenario,
                hard_constraints,
                seed,
            )
    else:
        # Clearly report no feasible plan found with reasons. Do not invent success.
        reasons: list[str] = []
        if validation_errors:
            reasons.append(f"{len(validation_errors)} proposal validation errors occurred at Check.")
        if all_evaluated_plans:
            reasons.append(
                f"{len(all_evaluated_plans)} candidate plans were evaluated, but all failed hard constraints or stress cases."
            )
        else:
            reasons.append("No candidates could be evaluated.")

    # Partition accuracy checks: evidence-supported +-10 min checks vs unverified predictions
    accuracy_summary = partition_accuracy_checks(all_accuracy_checks)

    elapsed_s = round(time.perf_counter() - t_start, 4)

    return {
        "claim": "best choices found within the search",
        "claims": ["best choices found within the search"],
        "dispatch_mode": "simulation_only",
        "live_radio_performed": False,
        "production_dispatch_performed": False,
        "status": "completed" if feasible_plan_found else "no_feasible_plan",
        "feasible_plan_found": feasible_plan_found,
        "best_plan": best_plan,
        "reasons": [] if feasible_plan_found else reasons,
        "rounds": rounds_executed,
        "recorded_proposals": recorded_proposals,
        "validation_errors": validation_errors,
        "evaluated_choices": all_evaluated_plans,
        "feasible_plans": all_feasible_plans,
        "pareto_set": all_pareto_plans,
        "tradeoffs": all_pareto_plans,
        "reference_comparisons": ref_comparisons,
        "final_independent_evaluation": final_independent_eval,
        "delay_explanations": delay_explanations,
        "failed_cases": failed_cases,
        "accuracy_summary": accuracy_summary,
        "relabelled_to_development": relabelled_to_development,
        "previous_results_count": len(history_records),
        "stopping_reason": stopping_reason,
        "budgets": {
            "round_budget": round_budget,
            "rounds_executed": len(rounds_executed),
            "evaluation_limits": limits_resolved,
        },
        "versions": {
            "engine_version": ENGINE_VERSION,
            "format_version": base_scenario.get("format_version"),
            "data_version": base_scenario.get("data_version"),
        },
        "runtime": {
            "elapsed_s": elapsed_s,
            "machine": platform.node(),
        },
    }


def replay_loop(
    record: Mapping[str, Any],
    campus_facts: Mapping[str, Any],
    *,
    seed: int = 42,
    **kwargs: Any,
) -> dict:
    """Replay recorded proposals with identical inputs and random choices.
    
    Reproduces calculated results without calling an AI service.
    """
    recorded = record.get("recorded_proposals") or [
        r["proposal"] for r in record.get("rounds", []) if "proposal" in r
    ]
    budgets = record.get("budgets") or {}
    round_budget = kwargs.pop("round_budget", budgets.get("round_budget", len(recorded) or DEFAULT_ROUND_BUDGET))
    evaluation_limits = kwargs.pop("evaluation_limits", budgets.get("evaluation_limits"))

    return run_loop(
        campus_facts,
        proposals=recorded,
        round_budget=round_budget,
        evaluation_limits=evaluation_limits,
        seed=seed,
        **kwargs,
    )


# Public aliases
run_proposal_loop = run_loop
ai_loop = run_loop
optimize_loop = run_loop
