"""Public Simulate operation: one resolved scenario plus one selected policy."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from usm_sim.accuracy import evaluate_accuracy
from usm_sim.behavior import prepare_behavior, validate_behavior_spec
from usm_sim.constants import ENGINE_VERSION, SOFTWARE_REVISION
from usm_sim.engine import Engine
from usm_sim.errors import SimulationError
from usm_sim.grouping import apply_grouping, needs_materialize
from usm_sim.validate import validate_inputs
def _assert_attendance_conservation(scenario: dict, result: dict) -> None:
    attending = sum(
        int(unit.get("resolved_attendance") or 0)
        for unit in scenario.get("source_units") or []
    )
    measures = result.setdefault("measures", {})
    completed = int(measures.get("completed_students") or 0)
    withdrawn = int(measures.get("withdrawn_students") or 0)
    unfinished = int(measures.get("unfinished_students") or 0)
    accounted = completed + withdrawn + unfinished
    measures["attending_students"] = attending
    measures["accounted_students"] = accounted
    measures["withdrawn_students"] = withdrawn
    if accounted != attending:
        result.setdefault("violations", []).append(
            {
                "type": "attendance_conservation",
                "attending_students": attending,
                "completed_students": completed,
                "withdrawn_students": withdrawn,
                "unfinished_students": unfinished,
            }
        )
        if result.get("status") == "completed":
            result["status"] = "infeasible"
            result["termination_cause"] = "attendance_conservation"

    for unit in scenario.get("source_units") or []:
        uid = unit.get("id")
        decl = unit.get("declared_population")
        non_att = unit.get("non_attendance")
        att = unit.get("attending")
        res = unit.get("resolved_attendance")
        if decl is not None and non_att is not None and att is not None:
            if int(decl) != int(non_att) + int(att):
                result.setdefault("violations", []).append(
                    {
                        "type": "attendance_conservation",
                        "unit_id": uid,
                        "declared_population": int(decl),
                        "non_attendance": int(non_att),
                        "attending": int(att),
                    }
                )
                if result.get("status") == "completed":
                    result["status"] = "infeasible"
                    result["termination_cause"] = "attendance_conservation"
        if att is not None and res is not None:
            if int(att) != int(res):
                result.setdefault("violations", []).append(
                    {
                        "type": "attendance_conservation",
                        "unit_id": uid,
                        "attending": int(att),
                        "resolved_attendance": int(res),
                    }
                )
                if result.get("status") == "completed":
                    result["status"] = "infeasible"
                    result["termination_cause"] = "attendance_conservation"

    initial_students = scenario.get("initial_state", {}).get("students") or []
    initial_keys: set[str] = set()
    for part in initial_students:
        for m in part.get("members", []):
            k = m.get("student_key")
            if k and k != "placeholder":
                initial_keys.add(k)

    completions = result.get("outcomes", {}).get("student_completions", [])
    completed_keys = {
        row["student_key"]
        for row in completions
        if isinstance(row, dict) and row.get("student_key")
    }

    if initial_keys:
        unexpected_keys = completed_keys - initial_keys
        if unexpected_keys:
            result.setdefault("violations", []).append(
                {
                    "type": "attendance_identity_mismatch",
                    "unexpected_keys": sorted(unexpected_keys),
                }
            )
            if result.get("status") == "completed":
                result["status"] = "infeasible"
                result["termination_cause"] = "attendance_conservation"

        if result.get("status") == "completed" and withdrawn == 0 and unfinished == 0:
            missing_keys = initial_keys - completed_keys
            if missing_keys:
                result.setdefault("violations", []).append(
                    {
                        "type": "attendance_identity_mismatch",
                        "missing_keys": sorted(missing_keys),
                    }
                )
                result["status"] = "infeasible"
                result["termination_cause"] = "attendance_conservation"

    no_show_keys: set[str] = set()
    for unit in scenario.get("source_units") or []:
        for cohort in unit.get("cohorts") or []:
            if cohort.get("attendance_state") == "no_show":
                for k in cohort.get("member_keys") or []:
                    no_show_keys.add(k)
    if no_show_keys and (completed_keys & no_show_keys):
        result.setdefault("violations", []).append(
            {
                "type": "attendance_identity_mismatch",
                "no_show_completed_keys": sorted(completed_keys & no_show_keys),
            }
        )
        if result.get("status") == "completed":
            result["status"] = "infeasible"
            result["termination_cause"] = "attendance_conservation"

def _apply_release_rule(scenario: dict, policy: dict) -> None:
    """Apply a simple fixed-interval release to source-unit readiness.

    Demand, budgets, deadlines, and other externals stay unchanged. Only
    readiness times move. Queue-based hold/release uses destination_space_rule.
    External readiness stays on external_readiness_s.
    """
    units = list(scenario.get("source_units") or [])
    for unit in units:
        if unit.get("external_readiness_s") is None:
            unit["external_readiness_s"] = float(unit.get("readiness_s") or 0.0)
        for cohort in unit.get("cohorts") or []:
            if cohort.get("external_readiness_s") is None:
                cohort["external_readiness_s"] = float(cohort.get("readiness_s") or unit["external_readiness_s"] or 0.0)
    rule = policy.get("release_rule") or {}
    if not isinstance(rule, dict) or rule.get("type") != "fixed_interval":
        return
    interval_s = float(rule.get("interval_s") or 0.0)
    start_s = float(rule.get("start_s") or 0.0)
    if interval_s <= 0 and start_s <= 0:
        return
    units.sort(key=lambda row: str(row.get("id") or ""))
    for index, unit in enumerate(units):
        external = float(unit.get("external_readiness_s") or 0.0)
        unit["readiness_s"] = max(external, start_s) + index * max(interval_s, 0.0)


def simulate(scenario: Mapping[str, Any] | None, policy: Mapping[str, Any] | None) -> dict:
    """Run the movement simulator and return a JSON-ready result dict."""
    if scenario is None:
        raise SimulationError("missing_input", "Missing critical input: scenario", field="scenario")
    if policy is None:
        raise SimulationError("missing_input", "Missing critical input: policy", field="policy")
    snapshot = {
        "scenario": copy.deepcopy(dict(scenario)),
        "policy": copy.deepcopy(dict(policy)),
    }
    scenario_d = copy.deepcopy(dict(scenario))
    policy_d = copy.deepcopy(dict(policy))
    has_behavior = bool(scenario_d.get("behavior")) or bool(scenario_d.get("_behavior_prepared"))
    has_legacy = any(
        (unit.get("late_assembly_s") not in (None, 0))
        or (unit.get("non_attendance") not in (None, 0))
        or (unit.get("withdrawn") not in (None, 0))
        for unit in scenario_d.get("source_units") or []
    )
    if has_behavior or has_legacy:
        validate_behavior_spec(scenario_d)
        prepare_behavior(scenario_d)
        for unit in scenario_d.get("source_units") or []:
            if unit.get("cohorts"):
                for c in unit["cohorts"]:
                    if "actual_reporting_s" not in c:
                        if "late_assembly_s" in c:
                            req = float(unit.get("required_reporting_s") or 0.0)
                            c["actual_reporting_s"] = req + float(c["late_assembly_s"])
                        else:
                            c["actual_reporting_s"] = float(unit.get("actual_reporting_s") or 0.0)
                    if "readiness_s" not in c:
                        c["readiness_s"] = float(c["actual_reporting_s"])
                attending_cohorts = [c for c in unit["cohorts"] if c.get("attendance_state") != "no_show"]
                if attending_cohorts:
                    unit["actual_reporting_s"] = max(float(c["actual_reporting_s"]) for c in attending_cohorts)
                    unit["readiness_s"] = max(float(unit.get("readiness_s") or 0.0), max(float(c["readiness_s"]) for c in attending_cohorts))
                unit["cohort_readiness_s"] = {
                    c["cohort_id"]: c["readiness_s"]
                    for c in unit["cohorts"]
                    if "cohort_id" in c
                }
        if scenario_d.get("initial_state", {}).get("students"):
            from usm_sim.behavior import allocate_members_for_unit
            ann_by_key = {}
            for unit in scenario_d.get("source_units") or []:
                if unit.get("cohorts"):
                    existing = unit.get("members")
                    allocated = allocate_members_for_unit(unit, unit["cohorts"], existing_members=existing)
                    for m in allocated["attending_members"]:
                        ann_by_key[m["student_key"]] = m
            if ann_by_key:
                for part in scenario_d["initial_state"]["students"]:
                    for m in part.get("members", []):
                        k = m.get("student_key")
                        if k in ann_by_key:
                            ann = ann_by_key[k]
                            for prop in ("cohort_id", "actual_reporting_s", "readiness_s", "attendance_state", "late_assembly_s", "reporting_mode"):
                                if prop in ann and prop not in m:
                                    m[prop] = ann[prop]
                    part_c_ids = sorted({m["cohort_id"] for m in part.get("members", []) if m.get("cohort_id")})
                    if part_c_ids:
                        part["cohort_ids"] = part_c_ids
                        if len(part_c_ids) == 1:
                            part["cohort_id"] = part_c_ids[0]
        operating = scenario_d.setdefault("operating_rules", {})
        if operating.get("attendance_response_rule"):
            operating["attendance_response_rule"] = {"type": "fixed"}
        if policy_d.get("attendance_response_rule"):
            policy_d["attendance_response_rule"] = {"type": "fixed"}
        for unit in scenario_d.get("source_units") or []:
            if unit.get("required_reporting_s") is None:
                unit["required_reporting_s"] = 0.0

    if policy_d.get("layout_assumptions"):
        from usm_sim.proposals import _apply_layout_assumptions
        _apply_layout_assumptions(scenario_d, policy_d["layout_assumptions"])
    _apply_release_rule(scenario_d, policy_d)
    grouping_summary = None
    if needs_materialize(policy_d):
        grouping_summary = apply_grouping(scenario_d, policy_d)
    scenario_d, policy_d = validate_inputs(scenario_d, policy_d)
    result = Engine(scenario_d, policy_d).run()
    result["input_snapshot"] = snapshot
    result["versions"]["engine_version"] = ENGINE_VERSION
    result["versions"]["software_revision"] = SOFTWARE_REVISION
    _assert_attendance_conservation(scenario_d, result)
    result["accuracy_checks"] = evaluate_accuracy(scenario_d, result["event_trace"])
    if grouping_summary is not None:
        result["grouping"] = {
            key: value
            for key, value in grouping_summary.items()
            if key != "source_units"
        }
    result["visible_assumptions"] = list(scenario_d.get("uncertain_assumptions") or [])
    if scenario_d.get("background_demand") is not None:
        result["background_demand"] = scenario_d["background_demand"]
    return result
