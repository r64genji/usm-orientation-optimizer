"""Behavioral variance record contracts, validation, and preparation (BV-01).

Implements data contracts for:
- scenario.behavior specification
- member allocation from source-unit cohorts
- evidence rules
- walk occupancy bands
- queue-jump event shapes
- station intercept fields
- conservation verification
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from usm_sim.errors import SimulationError

BEHAVIOR_VERSION = "1.0"

ALL_PHENOMENON_FAMILIES = (
    "late_reporting",
    "mixed_readiness",
    "no_show",
    "withdrawal",
    "schedule_departure",
    "stage_skip",
    "route_deviation",
    "catch_up_walk",
    "queue_jump",
)

ALLOWED_BEHAVIOR_MODES = frozenset({"explicit_events", "resolved_band"})
ALLOWED_EVIDENCE_CATEGORIES = frozenset({"assumed", "abraham", "measured"})
ALLOWED_REPORTING_MODES = frozenset({"absolute", "delay_from_required"})
ALLOWED_ATTENDANCE_STATES = frozenset({"attending", "no_show"})
ALLOWED_STATION_INTERCEPT_ACTIONS = frozenset(
    {
        "refuse_queue_jump",
        "allow_queue_jump",
        "deny_onward_service",
        "refuse_unescorted_walk",
        "hold_the_bus",
        "bump_to_next_vehicle",
        "split_and_go",
        "wait_for_stragglers",
        "intercept_at_station",
    }
)


def validate_evidence(evidence: Any, field_prefix: str) -> None:
    """Validate that an evidence record conforms to allowed categories and references."""
    if not isinstance(evidence, dict):
        raise SimulationError(
            "missing_input" if evidence is None else "invalid_value_or_unit",
            f"evidence at {field_prefix} must be a dict",
            field=field_prefix,
        )
    category = evidence.get("category")
    if category not in ALLOWED_EVIDENCE_CATEGORIES:
        raise SimulationError(
            "unresolved_assumption",
            f"evidence category at {field_prefix} must be one of {sorted(ALLOWED_EVIDENCE_CATEGORIES)}, got {category!r}",
            field=f"{field_prefix}.category",
        )
    note = evidence.get("note")
    ref = evidence.get("ref") or evidence.get("reference")
    if not note and not ref:
        raise SimulationError(
            "unresolved_assumption",
            f"evidence at {field_prefix} must specify a non-empty note or ref",
            field=f"{field_prefix}.note",
        )
    if category == "measured":
        context = evidence.get("context") or evidence.get("collection_context")
        if not context and not ref and not note:
            raise SimulationError(
                "unresolved_assumption",
                f"measured evidence at {field_prefix} requires collection context or reference",
                field=f"{field_prefix}.context",
            )


def validate_walk_occupancy_rule(rule: Any, field_prefix: str = "walk_occupancy_rule") -> None:
    """Validate walk occupancy bands or two-band rule specification."""
    if not isinstance(rule, dict):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field_prefix} must be a dict",
            field=field_prefix,
        )
    rule_type = rule.get("type")
    if rule_type == "two_band":
        empty_factor = rule.get("empty_duration_factor")
        congested_factor = rule.get("congested_duration_factor")
        if empty_factor is None or not isinstance(empty_factor, (int, float)) or empty_factor <= 0:
            raise SimulationError(
                "invalid_value_or_unit",
                f"{field_prefix}.empty_duration_factor must be a positive number",
                field=f"{field_prefix}.empty_duration_factor",
            )
        if congested_factor is None or not isinstance(congested_factor, (int, float)) or congested_factor <= 0:
            raise SimulationError(
                "invalid_value_or_unit",
                f"{field_prefix}.congested_duration_factor must be a positive number",
                field=f"{field_prefix}.congested_duration_factor",
            )
    elif rule_type == "stepwise_bands":
        bands = rule.get("bands")
        if not isinstance(bands, list) or not bands:
            raise SimulationError(
                "invalid_value_or_unit",
                f"{field_prefix}.bands must be a non-empty list",
                field=f"{field_prefix}.bands",
            )
        for idx, band in enumerate(bands):
            factor = band.get("duration_factor")
            if factor is None or not isinstance(factor, (int, float)) or factor <= 0:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"{field_prefix}.bands[{idx}].duration_factor must be positive",
                    field=f"{field_prefix}.bands[{idx}].duration_factor",
                )
    elif rule_type is not None:
        raise SimulationError(
            "invalid_value_or_unit",
            f"unknown walk_occupancy_rule type: {rule_type!r}",
            field=f"{field_prefix}.type",
        )
    if "source" in rule and rule["source"] not in ALLOWED_EVIDENCE_CATEGORIES:
        raise SimulationError(
            "unresolved_assumption",
            f"{field_prefix}.source must be an allowed evidence category",
            field=f"{field_prefix}.source",
        )


def validate_station_intercept_spec(spec: Any, field_prefix: str = "station_intercept") -> None:
    """Validate station intercept configuration fields."""
    if not isinstance(spec, dict):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field_prefix} must be a dict",
            field=field_prefix,
        )
    place_id = spec.get("place_id")
    if not place_id or not isinstance(place_id, str):
        raise SimulationError(
            "missing_input",
            f"{field_prefix} missing required place_id",
            field=f"{field_prefix}.place_id",
        )
    min_staff = spec.get("min_station_staff", 1)
    if not isinstance(min_staff, int) or min_staff < 1:
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field_prefix}.min_station_staff must be an integer >= 1",
            field=f"{field_prefix}.min_station_staff",
        )
    fallback = spec.get("fallback")
    if fallback and fallback not in ALLOWED_STATION_INTERCEPT_ACTIONS:
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field_prefix}.fallback {fallback!r} must be in {sorted(ALLOWED_STATION_INTERCEPT_ACTIONS)}",
            field=f"{field_prefix}.fallback",
        )


def validate_queue_jump_event(event: Any, field_prefix: str) -> None:
    """Validate a queue jump event record shape."""
    if not isinstance(event, dict):
        raise SimulationError(
            "invalid_value_or_unit",
            f"{field_prefix} must be a dict",
            field=field_prefix,
        )
    eid = event.get("event_id")
    if not eid or not isinstance(eid, str):
        raise SimulationError(
            "missing_input",
            f"{field_prefix} missing required event_id",
            field=f"{field_prefix}.event_id",
        )
    place_id = event.get("place_id")
    if not place_id and isinstance(event.get("target"), dict):
        place_id = event["target"].get("place_id")
    if not place_id or not isinstance(place_id, str):
        raise SimulationError(
            "missing_input",
            f"queue_jump event {eid!r} missing required place_id",
            field=f"{field_prefix}.place_id",
        )
    stage_id = event.get("stage_id")
    if stage_id is not None and not isinstance(stage_id, str):
        raise SimulationError(
            "invalid_value_or_unit",
            f"queue_jump event {eid!r} stage_id must be a string",
            field=f"{field_prefix}.stage_id",
        )


def validate_behavior_spec(scenario: Mapping[str, Any]) -> None:
    """Validate scenario behavior specifications or reject illegal legacy fields."""
    if not isinstance(scenario, (dict, Mapping)):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario must be a dict or Mapping",
            field="scenario",
        )

    behavior = scenario.get("behavior")
    source_units = scenario.get("source_units") or []

    # If no behavior specification is attached:
    if behavior is None or not behavior:
        # Check source units: reject nonzero late_assembly_s, non_attendance, or withdrawn without a named case
        for idx, unit in enumerate(source_units):
            uid = unit.get("id", idx)
            non_att = unit.get("non_attendance")
            if non_att is not None and non_att != 0:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"source unit {uid!r} has nonzero non_attendance ({non_att}) without a named behavior case",
                    field=f"scenario.source_units[{idx}].non_attendance",
                )
            late_s = unit.get("late_assembly_s")
            if late_s is not None and late_s != 0:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"source unit {uid!r} has nonzero late_assembly_s ({late_s}) without a named behavior case",
                    field=f"scenario.source_units[{idx}].late_assembly_s",
                )
            withdrawn = unit.get("withdrawn")
            if withdrawn is not None and withdrawn != 0:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"source unit {uid!r} has nonzero withdrawn ({withdrawn}) without a named behavior case",
                    field=f"scenario.source_units[{idx}].withdrawn",
                )

        # Check walk occupancy rule if present
        walk_rule = (
            scenario.get("operating_rules", {}).get("walk_occupancy_rule")
            or scenario.get("walk_occupancy_rule")
        )
        if walk_rule:
            validate_walk_occupancy_rule(walk_rule)
        return

    # When behavior is present, validate all behavior contract fields
    if not isinstance(behavior, dict):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.behavior must be a dict",
            field="scenario.behavior",
        )

    version = behavior.get("version")
    if not version or not isinstance(version, str):
        raise SimulationError(
            "missing_input",
            "scenario.behavior missing version string",
            field="scenario.behavior.version",
        )

    case_id = behavior.get("case_id")
    if not case_id or not isinstance(case_id, str):
        raise SimulationError(
            "missing_input",
            "scenario.behavior missing case_id string",
            field="scenario.behavior.case_id",
        )

    mode = behavior.get("mode")
    if mode not in ALLOWED_BEHAVIOR_MODES:
        raise SimulationError(
            "invalid_value_or_unit",
            f"scenario.behavior.mode must be one of {sorted(ALLOWED_BEHAVIOR_MODES)}, got {mode!r}",
            field="scenario.behavior.mode",
        )

    # Phenomenon declarations: every named case MUST declare ALL phenomenon families
    declared_families: set[str] = set()
    phenomena_dict = behavior.get("phenomena") or behavior.get("declared_phenomena")
    if isinstance(phenomena_dict, dict):
        declared_families.update(phenomena_dict.keys())
    elif isinstance(phenomena_dict, (list, tuple, set)):
        declared_families.update(phenomena_dict)
    # Also check keys directly in behavior
    for fam in ALL_PHENOMENON_FAMILIES:
        if fam in behavior:
            declared_families.add(fam)

    missing_families = [fam for fam in ALL_PHENOMENON_FAMILIES if fam not in declared_families]
    if missing_families:
        raise SimulationError(
            "missing_input",
            f"named behavior case {case_id!r} missing declaration for phenomenon families: {missing_families}",
            field=f"scenario.behavior.{missing_families[0]}",
        )

    # Validate source_unit_splits and cohorts
    splits = behavior.get("source_unit_splits")
    if splits is not None and not isinstance(splits, (dict, list)):
        raise SimulationError(
            "invalid_value_or_unit",
            "scenario.behavior.source_unit_splits must be a dict or list",
            field="scenario.behavior.source_unit_splits",
        )

    for idx, unit in enumerate(source_units):
        uid = unit.get("id")
        unit_cohorts: list[dict] | None = None
        if isinstance(splits, dict) and uid in splits:
            unit_cohorts = splits[uid]
        elif "cohorts" in unit:
            unit_cohorts = unit["cohorts"]
        elif isinstance(splits, list):
            unit_cohorts = [c for c in splits if c.get("source_unit_id") == uid]

        if unit_cohorts is not None:
            if not isinstance(unit_cohorts, list):
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"cohorts for unit {uid!r} must be a list",
                    field=f"scenario.source_units.{uid}.cohorts",
                )
            seen_cohort_ids: set[str] = set()
            sum_count = 0
            required_reporting_s = unit.get("required_reporting_s", 0)

            for c_idx, cohort in enumerate(unit_cohorts):
                if not isinstance(cohort, dict):
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"cohort {c_idx} in unit {uid!r} must be a dict",
                        field=f"scenario.source_units.{uid}.cohorts[{c_idx}]",
                    )
                cid = cohort.get("cohort_id")
                if not cid or not isinstance(cid, str):
                    raise SimulationError(
                        "missing_input",
                        f"cohort {c_idx} in unit {uid!r} missing cohort_id",
                        field=f"scenario.source_units.{uid}.cohorts[{c_idx}].cohort_id",
                    )
                if cid in seen_cohort_ids:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"duplicate cohort_id {cid!r} in unit {uid!r}",
                        field=f"scenario.source_units.{uid}.cohorts.{cid}",
                    )
                seen_cohort_ids.add(cid)

                count = cohort.get("count")
                if count is None or not isinstance(count, int) or count < 0:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"cohort {cid!r} in unit {uid!r} has invalid count {count!r}",
                        field=f"scenario.source_units.{uid}.cohorts.{cid}.count",
                    )
                sum_count += count

                state = cohort.get("attendance_state", "attending")
                if state not in ALLOWED_ATTENDANCE_STATES:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"cohort {cid!r} in unit {uid!r} invalid attendance_state {state!r}",
                        field=f"scenario.source_units.{uid}.cohorts.{cid}.attendance_state",
                    )

                # Evidence is required on cohorts
                validate_evidence(
                    cohort.get("evidence"),
                    f"scenario.source_units.{uid}.cohorts.{cid}.evidence",
                )

                # Reporting mode validation
                rep_mode = cohort.get("reporting_mode")
                actual_s = cohort.get("actual_reporting_s")
                late_s = cohort.get("late_assembly_s")

                if rep_mode == "absolute":
                    if actual_s is None or actual_s < 0:
                        raise SimulationError(
                            "missing_input" if actual_s is None else "invalid_value_or_unit",
                            f"cohort {cid!r} in absolute reporting_mode requires actual_reporting_s >= 0",
                            field=f"scenario.source_units.{uid}.cohorts.{cid}.actual_reporting_s",
                        )
                    if late_s is not None:
                        expected_late = max(0, actual_s - required_reporting_s)
                        if late_s != expected_late:
                            raise SimulationError(
                                "invalid_value_or_unit",
                                f"inconsistent delay and absolute in cohort {cid!r}: "
                                f"actual={actual_s}, required={required_reporting_s}, "
                                f"given late_assembly_s={late_s}, expected={expected_late}",
                                field=f"scenario.source_units.{uid}.cohorts.{cid}",
                            )
                elif rep_mode == "delay_from_required":
                    if late_s is None or late_s < 0:
                        raise SimulationError(
                            "missing_input" if late_s is None else "invalid_value_or_unit",
                            f"cohort {cid!r} in delay_from_required reporting_mode requires late_assembly_s >= 0",
                            field=f"scenario.source_units.{uid}.cohorts.{cid}.late_assembly_s",
                        )
                    if actual_s is not None:
                        expected_actual = required_reporting_s + late_s
                        if actual_s != expected_actual:
                            raise SimulationError(
                                "invalid_value_or_unit",
                                f"inconsistent delay and absolute in cohort {cid!r}: "
                                f"late_delay={late_s}, required={required_reporting_s}, "
                                f"given actual_reporting_s={actual_s}, expected={expected_actual}",
                                field=f"scenario.source_units.{uid}.cohorts.{cid}",
                            )
                elif rep_mode is not None:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"unknown reporting_mode {rep_mode!r} in cohort {cid!r}",
                        field=f"scenario.source_units.{uid}.cohorts.{cid}.reporting_mode",
                    )
                else:
                    if actual_s is not None and late_s is not None:
                        expected_late = max(0, actual_s - required_reporting_s)
                        if late_s != expected_late:
                            raise SimulationError(
                                "invalid_value_or_unit",
                                f"inconsistent actual_reporting_s and late_assembly_s in cohort {cid!r}",
                                field=f"scenario.source_units.{uid}.cohorts.{cid}",
                            )

            declared_pop = unit.get("declared_population")
            if declared_pop is not None and sum_count != declared_pop:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"sum of cohort counts ({sum_count}) does not equal declared_population ({declared_pop}) for unit {uid!r}",
                    field=f"scenario.source_units.{uid}.declared_population",
                )

    # Validate events
    events = behavior.get("events")
    if events is not None:
        if not isinstance(events, list):
            raise SimulationError(
                "invalid_value_or_unit",
                "scenario.behavior.events must be a list",
                field="scenario.behavior.events",
            )
        seen_eids: set[str] = set()
        for e_idx, event in enumerate(events):
            if not isinstance(event, dict):
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"event {e_idx} must be a dict",
                    field=f"scenario.behavior.events[{e_idx}]",
                )
            eid = event.get("event_id")
            if not eid or not isinstance(eid, str):
                raise SimulationError(
                    "missing_input",
                    f"event {e_idx} missing event_id",
                    field=f"scenario.behavior.events[{e_idx}].event_id",
                )
            if eid in seen_eids:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"duplicate event_id {eid!r}",
                    field=f"scenario.behavior.events[{e_idx}].event_id",
                )
            seen_eids.add(eid)

            phenom = event.get("phenomenon")
            if phenom not in ALL_PHENOMENON_FAMILIES:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"unknown phenomenon {phenom!r} in event {eid!r}",
                    field=f"scenario.behavior.events[{e_idx}].phenomenon",
                )

            if "target" not in event or event["target"] in (None, ""):
                raise SimulationError(
                    "missing_input",
                    f"event {eid!r} missing target",
                    field=f"scenario.behavior.events[{e_idx}].target",
                )

            validate_evidence(event.get("evidence"), f"scenario.behavior.events[{e_idx}].evidence")

            trigger = event.get("trigger")
            if not isinstance(trigger, dict):
                raise SimulationError(
                    "missing_input",
                    f"event {eid!r} missing trigger dict",
                    field=f"scenario.behavior.events[{e_idx}].trigger",
                )
            if not any(k in trigger for k in ("time_s", "before_stage", "after_stage")):
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"event {eid!r} trigger must specify time_s, before_stage, or after_stage",
                    field=f"scenario.behavior.events[{e_idx}].trigger",
                )
            if "time_s" in trigger:
                t_val = trigger["time_s"]
                if not isinstance(t_val, (int, float)) or t_val < 0:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"event {eid!r} trigger time_s must be non-negative number",
                        field=f"scenario.behavior.events[{e_idx}].trigger.time_s",
                    )

            if phenom == "queue_jump":
                validate_queue_jump_event(event, f"scenario.behavior.events[{e_idx}]")

    # Validate walk_occupancy_rule if present
    walk_rule = (
        scenario.get("operating_rules", {}).get("walk_occupancy_rule")
        or scenario.get("walk_occupancy_rule")
    )
    if walk_rule:
        validate_walk_occupancy_rule(walk_rule)


def allocate_members_for_unit(
    unit: dict,
    cohorts: list[dict] | None = None,
    existing_members: list[dict] | None = None,
) -> dict[str, Any]:
    """Allocate members to source unit cohorts in stable deterministic order.

    Returns a dict with:
    - declared_population: int
    - non_attendance: int
    - attending: int
    - resolved_attendance: int
    - attending_members: list[dict]
    - no_show_members: list[dict]
    - all_members: list[dict]
    """
    unit_id = unit.get("id", "su")
    hostel_id = unit.get("hostel_id", "hostel")

    if not cohorts:
        declared_pop = unit.get("declared_population", unit.get("resolved_attendance", 0))
        members: list[dict] = []
        if existing_members is not None:
            members = copy.deepcopy(existing_members)
        else:
            for idx in range(declared_pop):
                key = f"{unit_id}:{idx:04d}"
                members.append(
                    {
                        "student_key": key,
                        "queue_tie_key": key,
                        "source_unit_id": unit_id,
                        "hostel_id": hostel_id,
                        "attendance_state": "attending",
                    }
                )
        return {
            "declared_population": declared_pop,
            "non_attendance": 0,
            "attending": declared_pop,
            "resolved_attendance": declared_pop,
            "attending_members": members,
            "no_show_members": [],
            "all_members": members,
        }

    declared_pop = unit.get("declared_population")
    if declared_pop is None:
        declared_pop = sum(c["count"] for c in cohorts)

    # If existing members are supplied, verify count matches declared_population
    if existing_members is not None:
        if len(existing_members) != declared_pop:
            raise SimulationError(
                "invalid_value_or_unit",
                f"existing members count ({len(existing_members)}) does not match declared_population ({declared_pop}) for unit {unit_id!r}",
                field=f"scenario.source_units.{unit_id}.declared_population",
            )
        pool = copy.deepcopy(existing_members)
    else:
        pool = [
            {
                "student_key": f"{unit_id}:{idx:04d}",
                "queue_tie_key": f"{unit_id}:{idx:04d}",
                "source_unit_id": unit_id,
                "hostel_id": hostel_id,
            }
            for idx in range(declared_pop)
        ]

    # Assign members to cohorts:
    # 1. Any cohort with explicit member_keys takes those members
    assigned_keys: set[str] = set()
    cohort_assignments: dict[str, list[dict]] = {c["cohort_id"]: [] for c in cohorts}

    members_by_key = {m["student_key"]: m for m in pool}

    for cohort in cohorts:
        explicit_keys = cohort.get("member_keys")
        if explicit_keys:
            for key in explicit_keys:
                if key in assigned_keys:
                    raise SimulationError(
                        "invalid_value_or_unit",
                        f"member key {key!r} assigned to multiple cohorts in unit {unit_id!r}",
                        field=f"scenario.source_units.{unit_id}.cohorts.{cohort['cohort_id']}",
                    )
                if key not in members_by_key:
                    raise SimulationError(
                        "unknown_reference",
                        f"member key {key!r} not found in unit {unit_id!r}",
                        field=f"scenario.source_units.{unit_id}.cohorts.{cohort['cohort_id']}",
                    )
                assigned_keys.add(key)
                m = members_by_key[key]
                cohort_assignments[cohort["cohort_id"]].append(m)

    # 2. Allocate unassigned members to count-based cohorts in order
    unassigned = [m for m in pool if m["student_key"] not in assigned_keys]
    u_idx = 0
    for cohort in cohorts:
        cid = cohort["cohort_id"]
        needed = cohort["count"] - len(cohort_assignments[cid])
        if needed < 0:
            raise SimulationError(
                "invalid_value_or_unit",
                f"cohort {cid!r} has more explicit member_keys ({len(cohort_assignments[cid])}) than declared count ({cohort['count']})",
                field=f"scenario.source_units.{unit_id}.cohorts.{cid}",
            )
        if needed > 0:
            take = unassigned[u_idx : u_idx + needed]
            u_idx += needed
            cohort_assignments[cid].extend(take)

    # Annotate members with cohort attributes
    attending_members: list[dict] = []
    no_show_members: list[dict] = []
    all_members: list[dict] = []

    for cohort in cohorts:
        cid = cohort["cohort_id"]
        state = cohort.get("attendance_state", "attending")
        for m in cohort_assignments[cid]:
            m["cohort_id"] = cid
            m["attendance_state"] = state
            if "reporting_mode" in cohort:
                m["reporting_mode"] = cohort["reporting_mode"]
            if "actual_reporting_s" in cohort:
                m["actual_reporting_s"] = cohort["actual_reporting_s"]
            if "late_assembly_s" in cohort:
                m["late_assembly_s"] = cohort["late_assembly_s"]
            if "readiness_s" in cohort:
                m["readiness_s"] = cohort["readiness_s"]

            all_members.append(m)
            if state == "no_show":
                no_show_members.append(m)
            else:
                attending_members.append(m)

    non_att = len(no_show_members)
    att = len(attending_members)

    return {
        "declared_population": declared_pop,
        "non_attendance": non_att,
        "attending": att,
        "resolved_attendance": att,
        "attending_members": attending_members,
        "no_show_members": no_show_members,
        "all_members": all_members,
    }


def prepare_behavior(scenario: dict) -> dict:
    """Prepare and freeze behavior records on a scenario dict.

    - Validates behavior spec
    - Stamped with version and idempotency guard
    - Preserves existing student keys in initial_state.students, dropping only no-shows
    - Sets resolved_attendance = declared_population - non_attendance
    - Withdrawal is never subtracted at prepare
    """
    validate_behavior_spec(scenario)

    # Idempotent check
    behavior = scenario.get("behavior")
    if scenario.get("_behavior_prepared") or (behavior and behavior.get("_prepared")):
        return scenario

    source_units = scenario.get("source_units") or []

    # Case 1: No behavior specification attached
    if not behavior:
        for unit in source_units:
            res_att = int(unit.get("resolved_attendance") or 0)
            if "declared_population" not in unit:
                unit["declared_population"] = res_att
            unit["attending"] = res_att
            unit["non_attendance"] = 0
            unit["withdrawn"] = 0
        scenario["_behavior_prepared"] = True
        return scenario

    # Case 2: Named behavior specification present
    splits = behavior.get("source_unit_splits") or {}
    all_dropped_keys: set[str] = set()

    # Collect existing members from initial_state.students if present and not placeholder
    existing_by_unit: dict[str, list[dict]] = {}
    students = scenario.get("initial_state", {}).get("students")
    is_placeholder = bool(
        students
        and any(
            p.get("part_id") == "placeholder"
            or any(m.get("student_key") == "placeholder" for m in p.get("members", []))
            for p in students
        )
    )
    if students and not is_placeholder:
        for part in students:
            p_unit = part.get("source_unit_id")
            for m in part.get("members", []):
                uid = m.get("source_unit_id") or p_unit
                if uid:
                    existing_by_unit.setdefault(uid, []).append(m)

    for unit in source_units:
        uid = unit.get("id")
        unit_cohorts = None
        if isinstance(splits, dict) and uid in splits:
            unit_cohorts = splits[uid]
        elif "cohorts" in unit:
            unit_cohorts = unit["cohorts"]
        elif isinstance(splits, list):
            unit_cohorts = [c for c in splits if c.get("source_unit_id") == uid]

        existing = existing_by_unit.get(uid)
        allocated = allocate_members_for_unit(unit, unit_cohorts, existing_members=existing)

        unit["declared_population"] = allocated["declared_population"]
        unit["non_attendance"] = allocated["non_attendance"]
        unit["attending"] = allocated["attending"]
        unit["resolved_attendance"] = allocated["resolved_attendance"]
        if unit_cohorts is not None:
            unit["cohorts"] = unit_cohorts

        for ns in allocated["no_show_members"]:
            all_dropped_keys.add(ns["student_key"])

    # Update initial_state.students if present and not placeholder: drop declared no-shows, keep attending keys stable
    if students and not is_placeholder:
        for part in students:
            orig_members = part.get("members", [])
            kept = [m for m in orig_members if m["student_key"] not in all_dropped_keys]
            part["members"] = kept
            part["student_count"] = len(kept)
        # Filter out empty parts
        scenario["initial_state"]["students"] = [p for p in students if p["student_count"] > 0]

    # Stamp preparation version and idempotency marker
    behavior["_prepared"] = True
    behavior["_prepared_version"] = behavior.get("version", BEHAVIOR_VERSION)
    scenario["_behavior_prepared"] = True

    return scenario


def verify_behavior_conservation(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """Verify conservation identities on prepared behavior records.

    Identities checked:
    1. declared_population = non_attendance + attending (per unit and total)
    2. attending = resolved_attendance (per unit and total)
    3. attending = completed + withdrawn + unfinished
       (at preparation before movement: completed=0, so attending = withdrawn + unfinished)
    4. Attending and no-show member keys are strictly disjoint
    5. When initial_state.students is present and not placeholder, attending members match exactly
    """
    source_units = scenario.get("source_units") or []
    tot_declared = 0
    tot_non_attendance = 0
    tot_attending = 0
    tot_resolved = 0

    for idx, unit in enumerate(source_units):
        uid = unit.get("id", idx)
        decl = int(unit.get("declared_population", 0))
        non_att = int(unit.get("non_attendance", 0))
        att = int(unit.get("attending", 0))
        res = int(unit.get("resolved_attendance", 0))

        if decl != non_att + att:
            raise SimulationError(
                "fixed_rule_violation",
                f"conservation failed for unit {uid!r}: declared_population ({decl}) != non_attendance ({non_att}) + attending ({att})",
                field=f"scenario.source_units.{uid}.declared_population",
            )
        if att != res:
            raise SimulationError(
                "fixed_rule_violation",
                f"conservation failed for unit {uid!r}: attending ({att}) != resolved_attendance ({res})",
                field=f"scenario.source_units.{uid}.resolved_attendance",
            )

        tot_declared += decl
        tot_non_attendance += non_att
        tot_attending += att
        tot_resolved += res

    if tot_declared != tot_non_attendance + tot_attending:
        raise SimulationError(
            "fixed_rule_violation",
            f"total conservation failed: declared ({tot_declared}) != non_attendance ({tot_non_attendance}) + attending ({tot_attending})",
            field="scenario.declared_population",
        )
    if tot_attending != tot_resolved:
        raise SimulationError(
            "fixed_rule_violation",
            f"total conservation failed: attending ({tot_attending}) != resolved_attendance ({tot_resolved})",
            field="scenario.resolved_attendance",
        )

    # Check initial_state.students if present and not placeholder
    students = scenario.get("initial_state", {}).get("students")
    is_placeholder = bool(
        students
        and any(
            p.get("part_id") == "placeholder"
            or any(m.get("student_key") == "placeholder" for m in p.get("members", []))
            for p in students
        )
    )
    if students and not is_placeholder:
        total_students_in_parts = sum(len(p.get("members", [])) for p in students)
        if total_students_in_parts != tot_attending:
            raise SimulationError(
                "fixed_rule_violation",
                f"initial_state.students headcount ({total_students_in_parts}) != attending ({tot_attending})",
                field="scenario.initial_state.students",
            )

    return {
        "conserved": True,
        "declared_population": tot_declared,
        "non_attendance": tot_non_attendance,
        "attending": tot_attending,
        "resolved_attendance": tot_resolved,
    }
