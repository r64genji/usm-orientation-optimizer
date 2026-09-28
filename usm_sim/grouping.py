"""Form movement groups from disjoint source units and a selected policy.

Rounding uses the largest-remainder (Hamilton) method. Ties break by source-unit
id in ascending order. Remainders stay with the selected hostel attendance.

When occupancy is allocated from a hostel total, each source unit must declare a
positive occupancy_weight, or every unit of that hostel must omit the field so
equal shares apply. A missing or zero weight is not treated as 1.

Creating a model group adds no headcount, worker, setup delay, or coordination
action. Physical assembly uses only declared time, space, and workers.
Internal calculation size does not create extra movement parts.
"""

from __future__ import annotations

from math import floor
from typing import Any, Mapping

from usm_sim.constants import (
    ADAPTATION_TYPES,
    EXACT_SIZE_METHODS,
    GROUPING_BASES,
    MIXING_POLICIES,
    SPLIT_POLICIES,
)
from usm_sim.errors import SimulationError

LAYOUT_FIELDS = {
    "hostel": ("hostel_id",),
    "building": ("hostel_id", "building_id"),
    "floor": ("hostel_id", "floor_id"),
    "wing": ("hostel_id", "wing_id"),
    "floor_wing": ("hostel_id", "floor_id", "wing_id"),
    "target_size": ("hostel_id",),
    "mixed": ("hostel_id",),
}

DEMAND_FIELDS = (
    "registration",
    "resident_occupancy",
    "expected_event_attendance",
    "resolved_attendance",
)


def allocate_integer_counts(
    total: int,
    items: list[tuple[str, float]],
) -> dict[str, int]:
    """Split `total` into integers that sum to `total`.

    Each item is (id, weight). Quotas use largest remainder. Equal fractions
    give the extra seats to the lower id first.
    """
    if total < 0:
        raise SimulationError(
            "invalid_value_or_unit",
            "attendance total must be a nonnegative integer",
            field="attendance_total",
        )
    if not items:
        if total == 0:
            return {}
        raise SimulationError(
            "missing_input",
            "cannot allocate attendance without source units",
            field="source_units",
        )
    weight_sum = sum(weight for _item_id, weight in items)
    if weight_sum <= 0:
        raise SimulationError(
            "invalid_value_or_unit",
            "source-unit weights must be positive",
            field="source_units",
        )
    ranked: list[tuple[float, str, int]] = []
    assigned: dict[str, int] = {}
    for item_id, weight in items:
        raw = total * float(weight) / float(weight_sum)
        base = int(floor(raw))
        assigned[item_id] = base
        ranked.append((raw - base, item_id, base))
    leftover = total - sum(assigned.values())
    ranked.sort(key=lambda row: (-row[0], row[1]))
    for index in range(leftover):
        assigned[ranked[index][1]] += 1
    return assigned


def materialize_groups(
    source_units: list[Mapping[str, Any]],
    grouping: Mapping[str, Any],
    hostels: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build operational groups from source units. Adds no physical action."""
    grouping_d = dict(grouping)
    _validate_grouping_fields(grouping_d)
    units = [_normalize_unit(index, raw) for index, raw in enumerate(source_units)]
    _assert_disjoint_source_units(units)
    _apply_occupancy(units, hostels)
    _assert_disjoint_generated_keys(units)
    groups = _form_groups(units, grouping_d)
    groups = _apply_size_bounds(groups, grouping_d)
    for unit in units:
        if unit.get("cohorts"):
            unit["cohort_readiness_s"] = {
                c["cohort_id"]: c.get("readiness_s", unit.get("readiness_s", 0))
                for c in unit["cohorts"]
                if "cohort_id" in c
            }
    for group in groups:
        group["count_record_ids"] = list(group.get("count_record_ids") or [])
        group["required_supervision"] = dict(
            group.get("required_supervision")
            or _declared_supervision(grouping_d)
        )
        group["headcount_added"] = False
        group["workers_assigned_on_create"] = 0
        group["setup_delay_s"] = 0
        group["coordination_actions_added"] = 0
        group["regroup_policy"] = dict(grouping_d.get("regroup_policy") or {})
    total_resolved = sum(group["student_count"] for group in groups)
    total_estimated = sum(int(unit["estimated_attendance"]) for unit in units)
    return {
        "basis": grouping_d.get("basis"),
        "groups": groups,
        "source_units": units,
        "total_resolved_attendance": total_resolved,
        "total_estimated_attendance": total_estimated,
        "headcounts_added": 0,
        "worker_assignments_added": 0,
        "setup_delay_s": 0,
        "coordination_actions_added": 0,
        "split_policy": grouping_d.get("split_policy"),
        "mixing_policy": grouping_d.get("mixing_policy"),
        "regroup_policy": dict(grouping_d.get("regroup_policy") or {}),
        "adaptation_rule": dict(grouping_d.get("adaptation_rule") or {}),
        "layout_status": _combined_layout_status(units),
    }


def form_groups(
    source_units: list[Mapping[str, Any]],
    basis: str,
    *,
    hostel_id: str = "synthetic",
) -> list[dict[str, Any]]:
    """Build movement parts from disjoint source units for a grouping basis.

    Ticket 03 fixtures may use `floor`/`wing` instead of `floor_id`/`wing_id`.
    Creating these groups adds no count action.
    """
    normalized: list[dict[str, Any]] = []
    for raw in source_units:
        unit = dict(raw)
        if unit.get("floor_id") in (None, "") and unit.get("floor") not in (None, ""):
            unit["floor_id"] = str(unit["floor"])
        if unit.get("wing_id") in (None, "") and unit.get("wing") not in (None, ""):
            unit["wing_id"] = str(unit["wing"])
        if unit.get("building_id") in (None, "") and unit.get("building") not in (None, ""):
            unit["building_id"] = str(unit["building"])
        unit.setdefault("hostel_id", hostel_id)
        unit.setdefault("layout_status", "estimated")
        normalized.append(unit)
    summary = materialize_groups(
        normalized,
        {
            "basis": basis,
            "split_policy": "forbid",
            "mixing_policy": "same_hostel",
            "adaptation_rule": {"type": "fixed"},
        },
    )
    parts: list[dict[str, Any]] = []
    for group in summary["groups"]:
        members = list(group["members"])
        parts.append(
            {
                "part_id": f"part_{group['group_id']}",
                "group_id": group["group_id"],
                "source_unit_id": group["source_unit_id"],
                "source_unit_ids": list(group["source_unit_ids"]),
                "place_id": "origin",
                "hostel_id": group["hostel_id"],
                "hostel_composition": dict(group["hostel_composition"]),
                "members": members,
                "student_count": len(members),
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
                "grouping_basis": basis,
            }
        )
    parts.sort(key=lambda row: row["group_id"])
    return parts


def apply_grouping(scenario: dict, policy: dict) -> dict[str, Any]:
    """Replace movement parts with groups from source units and policy."""
    grouping = policy.get("grouping") or {}
    if not isinstance(grouping, Mapping) or not grouping.get("basis"):
        raise SimulationError(
            "missing_input",
            "policy.grouping.basis is required to materialize groups",
            field="policy.grouping.basis",
        )
    source_units = scenario.get("source_units")
    if not isinstance(source_units, list):
        raise SimulationError(
            "missing_input",
            "Missing critical input: scenario.source_units",
            field="scenario.source_units",
        )
    summary = materialize_groups(
        source_units,
        grouping,
        scenario.get("hostels"),
    )
    parts = _parts_from_groups(summary["groups"], scenario, policy)
    initial = dict(scenario.get("initial_state") or {})
    initial["students"] = parts
    if "queues" not in initial:
        initial["queues"] = []
    if "workers" not in initial:
        initial["workers"] = []
    if "vehicles" not in initial:
        initial["vehicles"] = []
    if "hall_occupancy_students" not in initial:
        initial["hall_occupancy_students"] = 0
    scenario["initial_state"] = initial
    scenario["_grouping_summary"] = summary
    return summary


def needs_materialize(policy: Mapping[str, Any] | None) -> bool:
    grouping = (policy or {}).get("grouping") or {}
    if not isinstance(grouping, Mapping):
        return False
    return bool(grouping.get("basis"))


def split_part_members(
    part: Mapping[str, Any],
    capacity_students: int,
    split_policy: str | None,
) -> list[dict[str, Any]] | None:
    """Split one movement part to fit capacity. None means splitting is forbidden."""
    members = list(part["members"])
    if len(members) <= capacity_students:
        return [dict(part)]
    if split_policy in (None, "forbid"):
        return None
    chunks: list[list[dict]]
    if split_policy == "keep_units_whole":
        packed = _pack_whole_units(part, capacity_students)
        if packed is None:
            return None
        chunks = packed
    elif split_policy == "permit_supervised_split":
        chunks = [
            members[index : index + capacity_students]
            for index in range(0, len(members), capacity_students)
        ]
    else:
        raise SimulationError(
            "unsupported_policy",
            f"unsupported split_policy {split_policy!r}",
            field="policy.grouping.split_policy",
        )
    parent_id = part.get("part_id")
    group_id = part["group_id"]
    results: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        child = dict(part)
        child["part_id"] = f"{parent_id}~split{index}"
        child["group_id"] = group_id
        child["parent_group_id"] = group_id
        child["parent_part_id"] = parent_id
        child["members"] = chunk
        child["student_count"] = len(chunk)
        child["hostel_composition"] = _composition_from_members(
            chunk, part.get("hostel_id")
        )
        child["source_unit_membership"] = _membership_from_members(chunk)
        child["source_unit_ids"] = sorted(child["source_unit_membership"])
        child["source_unit_id"] = child["source_unit_ids"][0]
        child["count_record_ids"] = list(part.get("count_record_ids") or [])
        child["covered_checkpoint_ids"] = list(part.get("covered_checkpoint_ids") or [])
        child["required_supervision"] = dict(part.get("required_supervision") or {})
        child["headcount_added"] = False
        child["workers_assigned_on_create"] = 0
        child["setup_delay_s"] = 0
        child_cohort_ids = sorted({m["cohort_id"] for m in chunk if m.get("cohort_id")})
        if child_cohort_ids:
            child["cohort_ids"] = child_cohort_ids
            if len(child_cohort_ids) == 1:
                child["cohort_id"] = child_cohort_ids[0]
        results.append(child)
    return results


def _validate_grouping_fields(grouping: dict) -> None:
    basis = grouping.get("basis")
    if basis not in GROUPING_BASES:
        raise SimulationError(
            "unsupported_policy",
            f"unsupported grouping basis {basis!r}",
            field="policy.grouping.basis",
        )
    split_policy = grouping.get("split_policy")
    if split_policy is not None and split_policy not in SPLIT_POLICIES:
        raise SimulationError(
            "unsupported_policy",
            f"unsupported split_policy {split_policy!r}",
            field="policy.grouping.split_policy",
        )
    mixing_policy = grouping.get("mixing_policy")
    if mixing_policy is not None and mixing_policy not in MIXING_POLICIES:
        raise SimulationError(
            "unsupported_policy",
            f"unsupported mixing_policy {mixing_policy!r}",
            field="policy.grouping.mixing_policy",
        )
    adaptation = grouping.get("adaptation_rule")
    if adaptation is not None:
        if not isinstance(adaptation, Mapping):
            raise SimulationError(
                "invalid_value_or_unit",
                "adaptation_rule must be an object",
                field="policy.grouping.adaptation_rule",
            )
        adapt_type = adaptation.get("type")
        if adapt_type not in ADAPTATION_TYPES:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported adaptation_rule.type {adapt_type!r}",
                field="policy.grouping.adaptation_rule.type",
            )
        if adapt_type != "fixed" and not adaptation.get("permitted_place_id"):
            raise SimulationError(
                "missing_input",
                "a run-time grouping change needs permitted_place_id",
                field="policy.grouping.adaptation_rule.permitted_place_id",
            )
    regroup = grouping.get("regroup_policy")
    if isinstance(regroup, Mapping) and regroup.get("required"):
        if not regroup.get("place_id"):
            raise SimulationError(
                "missing_input",
                "required destination regrouping needs a declared place_id",
                field="policy.grouping.regroup_policy.place_id",
            )
    if grouping.get("exact_size") or grouping.get("exact_target_size"):
        method = grouping.get("exact_size_method")
        if not method:
            raise SimulationError(
                "unresolved_assumption",
                "an exact target-size rule must state how workers establish that size; "
                "estimated occupancy alone does not grant exact physical knowledge",
                field="policy.grouping.exact_size_method",
            )
        if method not in EXACT_SIZE_METHODS:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported exact_size_method {method!r}",
                field="policy.grouping.exact_size_method",
            )
    if basis == "mixed":
        overrides = grouping.get("scope_overrides") or {}
        if not grouping.get("mixed_default") and not overrides:
            raise SimulationError(
                "missing_input",
                "mixed grouping needs mixed_default or scope_overrides",
                field="policy.grouping.mixed_default",
            )
        mixed_default = grouping.get("mixed_default")
        if mixed_default is not None and mixed_default not in GROUPING_BASES - {"mixed"}:
            raise SimulationError(
                "unsupported_policy",
                f"unsupported mixed_default {mixed_default!r}",
                field="policy.grouping.mixed_default",
            )
        if not isinstance(overrides, Mapping):
            raise SimulationError(
                "invalid_value_or_unit",
                "scope_overrides must be an object",
                field="policy.grouping.scope_overrides",
            )
        for origin, origin_basis in overrides.items():
            if origin_basis not in GROUPING_BASES - {"mixed"}:
                raise SimulationError(
                    "unsupported_policy",
                    f"unsupported override basis {origin_basis!r} for {origin!r}",
                    field=f"policy.grouping.scope_overrides.{origin}",
                )
    for field_name in (
        "units_per_group",
        "target_students",
        "min_students",
        "max_students",
        "escorts_per_group",
        "internal_part_size",
    ):
        if field_name in grouping and grouping[field_name] is not None:
            value = grouping[field_name]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"{field_name} must be a positive integer",
                    field=f"policy.grouping.{field_name}",
                )
    min_students = grouping.get("min_students")
    max_students = grouping.get("max_students")
    target_students = grouping.get("target_students")
    if (
        min_students is not None
        and max_students is not None
        and min_students > max_students
    ):
        raise SimulationError(
            "invalid_value_or_unit",
            "min_students cannot exceed max_students",
            field="policy.grouping.min_students",
        )
    if (
        min_students is not None
        and target_students is not None
        and target_students < min_students
    ):
        raise SimulationError(
            "invalid_value_or_unit",
            "target_students cannot be below min_students",
            field="policy.grouping.target_students",
        )
    if "maximum_assembly_wait_s" in grouping and grouping["maximum_assembly_wait_s"] is not None:
        wait = grouping["maximum_assembly_wait_s"]
        if isinstance(wait, bool) or not isinstance(wait, (int, float)) or wait < 0:
            raise SimulationError(
                "invalid_value_or_unit",
                "maximum_assembly_wait_s must be a nonnegative number of seconds",
                field="policy.grouping.maximum_assembly_wait_s",
            )
    physical = grouping.get("physical_assembly")
    if physical is not None:
        if not isinstance(physical, Mapping):
            raise SimulationError(
                "invalid_value_or_unit",
                "physical_assembly must be an object",
                field="policy.grouping.physical_assembly",
            )
        for key in ("duration_s", "place_id", "worker_count"):
            if key not in physical or physical[key] in (None, ""):
                raise SimulationError(
                    "missing_input",
                    f"physical assembly needs declared {key}",
                    field=f"policy.grouping.physical_assembly.{key}",
                )


def _normalize_unit(index: int, raw: Mapping[str, Any]) -> dict:
    if not isinstance(raw, Mapping):
        raise SimulationError(
            "invalid_value_or_unit",
            "source unit must be an object",
            field=f"scenario.source_units[{index}]",
        )
    unit = dict(raw)
    if not unit.get("id"):
        raise SimulationError(
            "missing_input",
            "source unit is missing id",
            field=f"scenario.source_units[{index}].id",
        )
    if not unit.get("hostel_id"):
        raise SimulationError(
            "missing_input",
            "source unit is missing hostel_id",
            field=f"scenario.source_units[{index}].hostel_id",
        )
    if "layout_status" not in unit or unit["layout_status"] in (None, ""):
        unit["layout_status"] = "estimated"
    if unit["layout_status"] not in {"estimated", "surveyed"}:
        raise SimulationError(
            "invalid_value_or_unit",
            "layout_status must be estimated or surveyed",
            field=f"scenario.source_units[{index}].layout_status",
        )
    return unit


def _apply_occupancy(units: list[dict], hostels: list[Mapping[str, Any]] | None) -> None:
    hostel_by_id = {row["id"]: dict(row) for row in hostels or [] if row.get("id")}
    grouped: dict[str, list[dict]] = {}
    for unit in units:
        grouped.setdefault(unit["hostel_id"], []).append(unit)
    for hostel_id, hostel_units in grouped.items():
        hostel = hostel_by_id.get(hostel_id)
        for field_name, hostel_key in (
            ("estimated_attendance", "expected_event_attendance"),
            ("resolved_attendance", "resolved_attendance"),
        ):
            missing = [unit for unit in hostel_units if unit.get(field_name) is None]
            present = [unit for unit in hostel_units if unit.get(field_name) is not None]
            if missing and present:
                raise SimulationError(
                    "missing_input",
                    f"{field_name} must be present on every source unit of {hostel_id}",
                    field=f"source_units.{field_name}",
                )
            if missing:
                if hostel is None or hostel.get(hostel_key) is None:
                    raise SimulationError(
                        "missing_input",
                        f"missing {field_name} for source units of {hostel_id}",
                        field=f"source_units.{field_name}",
                    )
                weights = _occupancy_weights(hostel_units)
                allocated = allocate_integer_counts(int(hostel[hostel_key]), weights)
                for unit in hostel_units:
                    unit[field_name] = allocated[unit["id"]]
            else:
                for unit in hostel_units:
                    value = unit[field_name]
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        raise SimulationError(
                            "invalid_value_or_unit",
                            f"{field_name} must be a nonnegative integer",
                            field=f"source_units.{unit['id']}.{field_name}",
                        )
                total = sum(int(unit[field_name]) for unit in hostel_units)
                if hostel is not None and hostel.get(hostel_key) is not None:
                    if total != int(hostel[hostel_key]):
                        raise SimulationError(
                            "invalid_value_or_unit",
                            f"{field_name} for {hostel_id} is {total}, "
                            f"not hostel {hostel_key} {hostel[hostel_key]}",
                            field=f"hostels.{hostel_id}.{hostel_key}",
                        )
        for unit in hostel_units:
            unit["members"] = _members_for_unit(unit)


def _members_for_unit(unit: dict) -> list[dict]:
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
        from usm_sim.behavior import allocate_members_for_unit
        allocated = allocate_members_for_unit(unit, unit["cohorts"], existing_members=unit.get("members"))
        res = []
        for m in allocated["attending_members"]:
            item = dict(m)
            if "readiness_s" not in item:
                item["readiness_s"] = float(unit.get("readiness_s") or item.get("actual_reporting_s") or 0.0)
            if "actual_reporting_s" not in item:
                item["actual_reporting_s"] = float(unit.get("actual_reporting_s") or 0.0)
            res.append(item)
        return res
    if unit.get("members"):
        attending = [m for m in unit["members"] if m.get("attendance_state", "attending") == "attending"]
        if len(attending) == int(unit.get("resolved_attendance", 0)):
            res = []
            for m in attending:
                item = dict(m)
                if "readiness_s" not in item and unit.get("readiness_s") is not None:
                    item["readiness_s"] = unit["readiness_s"]
                if "actual_reporting_s" not in item and unit.get("actual_reporting_s") is not None:
                    item["actual_reporting_s"] = unit["actual_reporting_s"]
                res.append(item)
            return res
    count = int(unit["resolved_attendance"])
    members = []
    for index in range(count):
        members.append(
            {
                "student_key": f"{unit['id']}:{index:04d}",
                "queue_tie_key": f"{unit['id']}:{index:04d}",
                "source_unit_id": unit["id"],
                "hostel_id": unit["hostel_id"],
            }
        )
    return members


def _occupancy_weights(units: list[dict]) -> list[tuple[str, float]]:
    declared = [unit for unit in units if unit.get("occupancy_weight") is not None]
    omitted = [unit for unit in units if unit.get("occupancy_weight") is None]
    if declared and omitted:
        raise SimulationError(
            "missing_input",
            "occupancy_weight must be set on every source unit of a hostel, or on none",
            field="source_units.occupancy_weight",
        )
    if omitted:
        return [(unit["id"], 1.0) for unit in units]
    weights: list[tuple[str, float]] = []
    for unit in units:
        value = unit["occupancy_weight"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise SimulationError(
                "invalid_value_or_unit",
                "occupancy_weight must be a positive number",
                field=f"source_units.{unit['id']}.occupancy_weight",
            )
        weights.append((unit["id"], float(value)))
    return weights


def _assert_disjoint_source_units(units: list[dict]) -> None:
    seen_ids: set[str] = set()
    seen_layout: dict[tuple, str] = {}
    for unit in units:
        unit_id = unit["id"]
        if unit_id in seen_ids:
            raise SimulationError(
                "invalid_value_or_unit",
                f"duplicate source-unit id {unit_id!r}",
                field=f"source_units.{unit_id}.id",
            )
        seen_ids.add(unit_id)
        if not (unit.get("building_id") or unit.get("floor_id") or unit.get("wing_id")):
            continue
        layout_key = (
            unit["hostel_id"],
            str(unit.get("building_id") or ""),
            str(unit.get("floor_id") or ""),
            str(unit.get("wing_id") or ""),
        )
        previous = seen_layout.get(layout_key)
        if previous is not None:
            raise SimulationError(
                "invalid_value_or_unit",
                f"source units {previous!r} and {unit_id!r} overlap the same layout cell",
                field=f"source_units.{unit_id}",
            )
        seen_layout[layout_key] = unit_id


def _assert_disjoint_generated_keys(units: list[dict]) -> None:
    seen: set[str] = set()
    for unit in units:
        for member in unit["members"]:
            key = member["student_key"]
            if key in seen:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"overlapping source-unit membership for {key!r}",
                    field="scenario.source_units",
                )
            seen.add(key)


def _form_groups(units: list[dict], grouping: dict) -> list[dict]:
    basis = grouping["basis"]
    if basis == "target_size":
        return _groups_by_target_size(units, grouping)
    target_units = [u for u in units if _unit_basis(u, grouping) == "target_size"]
    other_units = [u for u in units if _unit_basis(u, grouping) != "target_size"]
    groups: list[dict] = []
    if target_units:
        groups.extend(_groups_by_target_size(target_units, grouping))
    if not other_units:
        return groups
    buckets: dict[tuple, list[dict]] = {}
    for unit in other_units:
        key = _unit_group_key(unit, grouping)
        buckets.setdefault(key, []).append(unit)
    units_per_group = grouping.get("units_per_group")
    mixing = grouping.get("mixing_policy") or "same_hostel"
    for key in sorted(buckets, key=lambda item: tuple(str(part) for part in item)):
        bucket = sorted(buckets[key], key=lambda unit: unit["id"])
        if mixing == "same_hostel":
            by_hostel: dict[str, list[dict]] = {}
            for unit in bucket:
                by_hostel.setdefault(unit["hostel_id"], []).append(unit)
            chunks_source = [by_hostel[hid] for hid in sorted(by_hostel)]
        else:
            chunks_source = [bucket]
        for compatible in chunks_source:
            if units_per_group is None:
                slices = [compatible]
            else:
                slices = [
                    compatible[index : index + units_per_group]
                    for index in range(0, len(compatible), units_per_group)
                ]
            sliced = units_per_group is not None or len(slices) > 1
            for slice_index, slice_units in enumerate(slices):
                groups.append(
                    _group_from_units(
                        slice_units,
                        key,
                        grouping,
                        slice_index=slice_index,
                        include_slice=sliced,
                    )
                )
    return groups


def _unit_basis(unit: dict, grouping: dict) -> str:
    basis = grouping["basis"]
    overrides = grouping.get("scope_overrides") or {}
    if unit["hostel_id"] in overrides:
        return overrides[unit["hostel_id"]]
    building = unit.get("building_id")
    if building and building in overrides:
        return overrides[building]
    if basis == "mixed":
        return grouping["mixed_default"]
    return basis


def _unit_group_key(unit: dict, grouping: dict) -> tuple:
    basis = _unit_basis(unit, grouping)
    if basis == "target_size":
        return ("target_size", unit["hostel_id"], unit["id"])
    fields = LAYOUT_FIELDS[basis]
    values = []
    for field_name in fields:
        if field_name not in unit or unit[field_name] in (None, ""):
            if basis in {"floor", "wing", "floor_wing", "building"}:
                raise SimulationError(
                    "missing_input",
                    f"source unit {unit['id']!r} needs {field_name} for {basis} grouping",
                    field=f"source_units.{unit['id']}.{field_name}",
                )
            values.append("")
        else:
            values.append(str(unit[field_name]))
    return (basis, *values)


def _groups_by_target_size(units: list[dict], grouping: dict) -> list[dict]:
    target = grouping.get("target_students")
    if target is None:
        raise SimulationError(
            "missing_input",
            "target_size grouping needs target_students",
            field="policy.grouping.target_students",
        )
    exact_size = bool(grouping.get("exact_size") or grouping.get("exact_target_size"))
    split_policy = grouping.get("split_policy")
    mixing = grouping.get("mixing_policy") or "same_hostel"
    ordered = sorted(units, key=lambda unit: (unit["hostel_id"], unit["id"]))
    groups: list[dict] = []
    current: list[dict] = []
    current_count = 0
    current_hostel: str | None = None

    def close_current() -> None:
        nonlocal current, current_count, current_hostel
        if current:
            key = ("target_size", current[0]["hostel_id"], f"g{len(groups)}")
            groups.append(
                _group_from_units(current, key, grouping, slice_index=len(groups))
            )
        current = []
        current_count = 0
        current_hostel = None

    for unit in ordered:
        if mixing != "permit_mixed_hostels" and current and unit["hostel_id"] != current_hostel:
            close_current()
        if exact_size:
            remaining = list(unit["members"])
            while remaining:
                room = target - current_count
                if room <= 0:
                    close_current()
                    room = target
                if mixing != "permit_mixed_hostels" and current and unit["hostel_id"] != current_hostel:
                    close_current()
                    room = target
                take = min(room, len(remaining))
                if take < len(remaining) and split_policy != "permit_supervised_split":
                    if current:
                        close_current()
                        continue
                    raise SimulationError(
                        "impossible_static_requirement",
                        f"source unit {unit['id']!r} exceeds target_students {target} "
                        "and split_policy does not permit a supervised split",
                        field="policy.grouping.split_policy",
                    )
                piece = dict(unit)
                piece["members"] = remaining[:take]
                piece["resolved_attendance"] = take
                remaining = remaining[take:]
                current.append(piece)
                current_count += take
                current_hostel = unit["hostel_id"]
                if current_count >= target:
                    close_current()
        else:
            est = int(unit.get("estimated_attendance") or len(unit["members"]))
            rem_est = est
            rem_members = list(unit["members"])
            while rem_est > 0 or rem_members:
                room = target - current_count
                if room <= 0:
                    close_current()
                    room = target
                if mixing != "permit_mixed_hostels" and current and unit["hostel_id"] != current_hostel:
                    close_current()
                    room = target
                if rem_est <= room:
                    piece = dict(unit)
                    piece["members"] = rem_members
                    piece["resolved_attendance"] = len(rem_members)
                    current.append(piece)
                    current_count += rem_est
                    current_hostel = unit["hostel_id"]
                    rem_est = 0
                    rem_members = []
                    if current_count >= target:
                        close_current()
                else:
                    if split_policy != "permit_supervised_split":
                        if current:
                            close_current()
                            continue
                        raise SimulationError(
                            "impossible_static_requirement",
                            f"source unit {unit['id']!r} exceeds target_students {target} "
                            "and split_policy does not permit a supervised split",
                            field="policy.grouping.split_policy",
                        )
                    frac = room / float(rem_est)
                    take = max(1, min(len(rem_members), round(frac * len(rem_members)))) if rem_members else 0
                    piece = dict(unit)
                    piece["members"] = rem_members[:take]
                    piece["resolved_attendance"] = take
                    rem_members = rem_members[take:]
                    rem_est -= room
                    current.append(piece)
                    current_count += room
                    current_hostel = unit["hostel_id"]
                    close_current()
    close_current()
    return groups

def _group_from_units(
    units: list[dict],
    key: tuple,
    grouping: dict,
    slice_index: int = 0,
    include_slice: bool = False,
) -> dict:
    members: list[dict] = []
    membership: dict[str, int] = {}
    composition: dict[str, int] = {}
    layout_statuses: list[str] = []
    for unit in units:
        chunk = list(unit["members"])
        members.extend(chunk)
        membership[unit["id"]] = membership.get(unit["id"], 0) + len(chunk)
        composition[unit["hostel_id"]] = composition.get(unit["hostel_id"], 0) + len(chunk)
        layout_statuses.append(unit.get("layout_status") or "estimated")
    members.sort(key=lambda item: (item["queue_tie_key"], item["student_key"]))
    hostel_id = units[0]["hostel_id"]
    group_id = "g_" + "_".join(str(part) for part in key if part not in (None, ""))
    if include_slice or slice_index:
        group_id = f"{group_id}_s{int(slice_index)}"
    layout_status = "estimated" if "estimated" in layout_statuses else "surveyed"
    return {
        "group_id": group_id,
        "parent_group_id": group_id,
        "hostel_id": hostel_id,
        "hostel_composition": composition,
        "source_unit_ids": [unit["id"] for unit in units],
        "source_unit_membership": membership,
        "source_unit_id": units[0]["id"],
        "student_count": len(members),
        "members": members,
        "layout_status": layout_status,
        "count_record_ids": [],
        "required_supervision": _declared_supervision(grouping),
        "basis_key": list(key),
        "slice_index": int(slice_index),
        "regroup_policy": dict(grouping.get("regroup_policy") or {}),
    }


def _apply_size_bounds(groups: list[dict], grouping: dict) -> list[dict]:
    max_students = grouping.get("max_students")
    split_policy = grouping.get("split_policy")
    if max_students is None:
        return groups
    bounded: list[dict] = []
    for group in groups:
        if group["student_count"] <= max_students:
            bounded.append(group)
            continue
        parts = split_part_members(group, max_students, split_policy)
        if parts is None:
            raise SimulationError(
                "impossible_static_requirement",
                f"group {group['group_id']!r} exceeds max_students {max_students} "
                "and split_policy does not permit a split",
                field="policy.grouping.max_students",
            )
        parent_id = group["group_id"]
        for index, part in enumerate(parts):
            child = dict(group)
            child.update(part)
            child["parent_group_id"] = parent_id
            child["group_id"] = f"{parent_id}_m{index}"
            child["part_index"] = index
            child["slice_index"] = index
            bounded.append(child)
    return bounded


def _declared_supervision(grouping: dict) -> dict:
    if grouping.get("escorts_per_group") is None:
        return {}
    return {"escorts": int(grouping["escorts_per_group"])}


def _combined_layout_status(units: list[dict]) -> str:
    if any(unit.get("layout_status") == "estimated" for unit in units):
        return "estimated"
    return "surveyed"


def _parts_from_groups(groups: list[dict], scenario: dict, policy: dict) -> list[dict]:
    grouping = policy.get("grouping") or {}
    internal_size = grouping.get("internal_part_size")
    hostel_place = {}
    for hostel in scenario.get("hostels") or []:
        if hostel.get("origin_place_id"):
            hostel_place[hostel["id"]] = hostel["origin_place_id"]
    unit_place = {}
    for unit in scenario.get("source_units") or []:
        if unit.get("origin_place_id"):
            unit_place[unit["id"]] = unit["origin_place_id"]
    parts: list[dict] = []
    for group in groups:
        members = list(group["members"])
        origins = sorted(
            {
                place
                for place in (
                    unit_place.get(m.get("source_unit_id")) or hostel_place.get(m.get("hostel_id"))
                    for m in members
                    if m.get("source_unit_id") or m.get("hostel_id")
                )
                if place
            }
        )
        if len(origins) > 1:
            routes = scenario.get("routes") or {}
            regroup = (
                group.get("regroup_policy")
                or (policy.get("grouping") or {}).get("regroup_policy")
                or {}
            )
            regroup_place = regroup.get("place_id")
            if not (regroup.get("required") and regroup_place):
                raise SimulationError(
                    "unsupported_policy",
                    f"mixed-origin group {group['group_id']!r} cannot start without separate approaches and a physical join",
                    field="policy.grouping",
                )
            for origin in origins:
                origin_hostels = {
                    m.get("hostel_id")
                    for m in members
                    if (unit_place.get(m.get("source_unit_id")) or hostel_place.get(m.get("hostel_id"))) == origin
                }
                for hid in origin_hostels:
                    if routes and hid not in routes:
                        raise SimulationError(
                            "unsupported_policy",
                            f"mixed-origin group {group['group_id']!r} has no route for origin {origin!r} ({hid!r})",
                            field="policy.grouping",
                        )
            for origin_idx, origin in enumerate(origins):
                origin_members = [
                    m for m in members
                    if (unit_place.get(m.get("source_unit_id")) or hostel_place.get(m.get("hostel_id"))) == origin
                ]
                p_id = f"part_{group['group_id']}_orig{origin_idx}"
                part_dict = {
                    "part_id": p_id,
                    "group_id": group["group_id"],
                    "parent_group_id": group.get("parent_group_id") or group["group_id"],
                    "parent_part_id": None,
                    "source_unit_id": origin_members[0]["source_unit_id"],
                    "source_unit_ids": sorted({m["source_unit_id"] for m in origin_members}),
                    "source_unit_membership": _membership_from_members(origin_members),
                    "place_id": origin,
                    "hostel_id": origin_members[0].get("hostel_id") or group["hostel_id"],
                    "hostel_composition": _composition_from_members(origin_members, origin_members[0].get("hostel_id") or group["hostel_id"]),
                    "members": origin_members,
                    "count_record_ids": list(group.get("count_record_ids") or []),
                    "covered_checkpoint_ids": list(group.get("covered_checkpoint_ids") or []),
                    "required_supervision": dict(group.get("required_supervision") or {}),
                    "layout_status": group.get("layout_status"),
                    "internal_calculation": False,
                    "internal_part_size": internal_size,
                    "slice_index": int(group.get("slice_index") or 0),
                    "part_index": group.get("part_index"),
                    "headcount_added": False,
                    "setup_delay_s": 0,
                    "regroup_policy": dict(regroup),
                }
                c_ids = sorted({m["cohort_id"] for m in origin_members if m.get("cohort_id")})
                if c_ids:
                    part_dict["cohort_ids"] = c_ids
                    if len(c_ids) == 1:
                        part_dict["cohort_id"] = c_ids[0]
                parts.append(part_dict)
            continue
        place_id = (
            unit_place.get(group["source_unit_id"])
            or hostel_place.get(group["hostel_id"])
        )
        if not place_id:
            raise SimulationError(
                "missing_input",
                f"no origin place for group {group['group_id']!r}",
                field="hostels.origin_place_id",
            )
        members = list(group["members"])
        part_id = f"part_{group['group_id']}"
        if group.get("part_index") is not None:
            part_id = f"{part_id}_p{int(group['part_index'])}"
        if internal_size is not None:
            part_id = f"{part_id}_i{int(group.get('slice_index') or group.get('part_index') or 0)}"
        part_dict = {
            "part_id": part_id,
            "group_id": group["group_id"],
            "parent_group_id": group.get("parent_group_id") or group["group_id"],
            "parent_part_id": None,
            "source_unit_id": members[0]["source_unit_id"] if members else group["source_unit_id"],
            "source_unit_ids": sorted({member["source_unit_id"] for member in members}),
            "source_unit_membership": _membership_from_members(members),
            "place_id": place_id,
            "hostel_id": group["hostel_id"],
            "hostel_composition": _composition_from_members(members, group["hostel_id"]),
            "members": members,
            "count_record_ids": list(group.get("count_record_ids") or []),
            "covered_checkpoint_ids": list(group.get("covered_checkpoint_ids") or []),
            "required_supervision": dict(group.get("required_supervision") or {}),
            "layout_status": group.get("layout_status"),
            "internal_calculation": False,
            "internal_part_size": internal_size,
            "slice_index": int(group.get("slice_index") or 0),
            "part_index": group.get("part_index"),
            "headcount_added": False,
            "setup_delay_s": 0,
            "regroup_policy": dict(group.get("regroup_policy") or {}),
        }
        c_ids = sorted({m["cohort_id"] for m in members if m.get("cohort_id")})
        if c_ids:
            part_dict["cohort_ids"] = c_ids
            if len(c_ids) == 1:
                part_dict["cohort_id"] = c_ids[0]
        parts.append(part_dict)
    return parts


def _composition_from_members(members: list[dict], default_hostel: str | None) -> dict[str, int]:
    composition: dict[str, int] = {}
    for member in members:
        hostel = member.get("hostel_id") or default_hostel
        if not hostel:
            raise SimulationError(
                "missing_input",
                "movement member is missing hostel_id",
                field="members.hostel_id",
            )
        composition[hostel] = composition.get(hostel, 0) + 1
    return composition


def _membership_from_members(members: list[dict]) -> dict[str, int]:
    membership: dict[str, int] = {}
    for member in members:
        unit_id = member.get("source_unit_id")
        if not unit_id:
            continue
        membership[unit_id] = membership.get(unit_id, 0) + 1
    return membership


def _pack_whole_units(part: Mapping[str, Any], capacity_students: int) -> list[list[dict]] | None:
    membership = dict(part.get("source_unit_membership") or {})
    if not membership:
        for member in part["members"]:
            unit_id = member.get("source_unit_id") or part.get("source_unit_id")
            membership[unit_id] = membership.get(unit_id, 0) + 1
    for unit_id, count in membership.items():
        if count > capacity_students:
            return None
    by_unit: dict[str, list[dict]] = {}
    for member in part["members"]:
        unit_id = member.get("source_unit_id") or part.get("source_unit_id")
        by_unit.setdefault(unit_id, []).append(member)
    loads: list[list[dict]] = []
    current: list[dict] = []
    for unit_id in sorted(by_unit):
        chunk = by_unit[unit_id]
        if len(current) + len(chunk) > capacity_students:
            if current:
                loads.append(current)
            current = list(chunk)
        else:
            current.extend(chunk)
    if current:
        loads.append(current)
    return loads
