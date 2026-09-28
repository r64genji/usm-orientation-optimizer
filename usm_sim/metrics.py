"""Ticket 07: student obligation, worker effort, and delay explanations.

Measures are compiled from the event record, wait intervals, and retained
assignments. Group size does not change what a measure means: waiting is
student-count times duration, and percentiles are student-weighted.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping

from usm_sim.constants import WAIT_CLASS_BY_CAUSE, WAIT_CLASSES
from usm_sim.counting import COUNT_ACTION_EVENTS
from usm_sim.timeutil import ms_to_s

DELAY_EXPLANATION_KEYS = (
    "place_id",
    "resource_id",
    "primary_cause",
    "duration_s",
    "affected_count",
    "related_event_ids",
)

OUTDOOR_CLASSES = frozenset({"exposed", "shaded", "sheltered"})

ACTIVITY_TRAVEL_START = frozenset({"departure"})
ACTIVITY_TRAVEL_END = frozenset({"arrival"})
ACTIVITY_SERVICE_START = frozenset({"service_start", "batch_start"})
ACTIVITY_SERVICE_END = frozenset({"service_complete", "batch_complete"})
ACTIVITY_COUNT_START = frozenset({"count_start", "recount_start"})
ACTIVITY_COUNT_END = frozenset({"count_complete", "recount_complete"})
ACTIVITY_ASSEMBLY_START = frozenset({"assembly_start"})
ACTIVITY_ASSEMBLY_END = frozenset({"assembly_complete"})

ENDPOINT_EVENTS = {
    "hall_area_arrival": "hall_area_arrival_s",
    "entrance_completion": "entrance_completion_s",
    "seated_completion": "seated_completion_s",
}


def student_weighted_p95(values: list[float]) -> float:
    """Smallest wait at or below which 95% of students fall."""
    if not values:
        return 0.0
    ordered = sorted(float(item) for item in values)
    n = len(ordered)
    need = 0.95 * n
    index = max(0, min(n - 1, int(math.ceil(need)) - 1))
    return ordered[index]


def compile_metrics(engine: Any, unfinished: list[dict]) -> dict:
    """Build public measures, per-entity records, and delay explanations."""
    scenario = engine.scenario
    policy = engine.policy
    parts = engine.parts
    trace = list(engine.trace)
    wait_intervals = list(engine.wait_intervals)
    completions = list(engine.completions)
    places = engine.places
    rounding_s = float((policy.get("numerical_rounding_limit_s") or 0.001))

    students = _student_index(parts, completions, unfinished)
    reporting = _reporting_context(scenario, policy, students)
    wait_rows = _explode_waits(wait_intervals, parts)
    wait_by_student = defaultdict(float)
    wait_by_hostel = defaultdict(float)
    wait_by_unit = defaultdict(float)
    wait_by_group = defaultdict(float)
    wait_by_cause: dict[str, float] = {}
    wait_by_class: dict[str, float] = {name: 0.0 for name in WAIT_CLASSES}
    queue_wait_s = 0.0
    hold_wait_s = 0.0
    outdoor = {"exposed": 0.0, "shaded": 0.0, "sheltered": 0.0}
    early_idle_s = 0.0
    event_start_s = _event_start_s(scenario)
    dest_place_ids = _destination_place_ids(scenario, engine)

    for row in wait_rows:
        wait_by_student[row["student_key"]] += row["duration_s"]
        wait_by_hostel[row["hostel_id"]] += row["duration_s"]
        wait_by_unit[row["source_unit_id"]] += row["duration_s"]
        wait_by_group[row["group_id"]] += row["duration_s"]
        wait_by_cause[row["cause"]] = wait_by_cause.get(row["cause"], 0.0) + row["student_s"]
        wait_class = WAIT_CLASS_BY_CAUSE.get(row["cause"], "resource_waiting")
        wait_by_class.setdefault(wait_class, 0.0)
        wait_by_class[wait_class] += row["student_s"]
        if row["cause"] == "waiting_for_server" or wait_class == "queue_waiting":
            queue_wait_s += row["student_s"]
        else:
            hold_wait_s += row["student_s"]
        outdoor_class = _outdoor_class(places.get(row["place_id"]) or {})
        if outdoor_class in OUTDOOR_CLASSES:
            outdoor[outdoor_class] += row["student_s"]
        if (
            event_start_s is not None
            and row["place_id"] in dest_place_ids
            and row["start_s"] < event_start_s
            and wait_class == "intentional_hold"
        ):
            overlap = max(0.0, min(row["end_s"], event_start_s) - row["start_s"])
            early_idle_s += overlap * row["student_count"]

    total_wait_s = queue_wait_s + hold_wait_s
    attending_n = len(students)
    unfinished_n = int(sum(row["student_count"] for row in unfinished))
    completed_n = len(completions)
    withdrawn_n = 0
    seen_withdrawn: set[str] = set()
    for part in parts.values():
        if getattr(part, "status", None) != "withdrawn":
            continue
        for member in list(getattr(part, "members", None) or []):
            key = member.get("student_key")
            if key and key not in seen_withdrawn:
                seen_withdrawn.add(key)
                withdrawn_n += 1
        if not getattr(part, "members", None):
            withdrawn_n += int(getattr(part, "student_count", 0) or 0)
    attending_from_units = 0
    for unit in scenario.get("source_units") or []:
        attending_from_units += int(unit.get("resolved_attendance") or 0)
    wait_values = [wait_by_student.get(key, 0.0) for key in students]
    mean_wait_s = (total_wait_s / attending_n) if attending_n else 0.0
    p95_wait_s = student_weighted_p95(wait_values)

    late_students = [row for row in completions if row["late_s"] > 0]
    journeys = []
    reporting_lateness_s = 0.0
    earlier_burden_s = 0.0
    free_time_s = 0.0
    window = reporting["reporting_window"]
    for _key, info in students.items():
        req = info["required_reporting_s"]
        actual = info["actual_reporting_s"]
        avail = info["availability_s"]
        reporting_lateness_s += max(0.0, actual - req)
        if actual < req:
            earlier_burden_s += req - actual
        if window is not None:
            earlier_burden_s += max(0.0, float(window["latest_s"]) - req)
        if avail < req and actual >= req:
            free_time_s += req - avail
        elif avail < req and actual < req:
            free_time_s += max(0.0, actual - avail)

    for row in completions:
        info = students.get(row["student_key"]) or {}
        start_s = max(
            float(info.get("required_reporting_s") or 0.0),
            float(info.get("actual_reporting_s") or 0.0),
        )
        journey_s = max(0.0, float(row["completion_time_s"]) - start_s)
        row["required_journey_s"] = journey_s
        row["reporting_lateness_s"] = max(
            0.0,
            float(info.get("actual_reporting_s") or 0.0)
            - float(info.get("required_reporting_s") or 0.0),
        )
        row["wait_s"] = wait_by_student.get(row["student_key"], 0.0)
        journeys.append(journey_s)

    total_journey_s = sum(journeys)
    count_s = ms_to_s(int(getattr(engine, "count_student_ms", 0) or 0))
    assembly_s = ms_to_s(int(getattr(engine, "assembly_student_ms", 0) or 0))
    service_s = ms_to_s(int(engine.service_student_ms or 0))
    stationary_s = service_s + assembly_s

    hostel_rows = _hostel_rows(
        students,
        completions,
        unfinished,
        wait_by_student,
        wait_by_hostel,
        scenario,
    )
    campus_mean = mean_wait_s
    worst_hostel_id = None
    max_hostel_mean = 0.0
    if hostel_rows:
        ranked = sorted(hostel_rows, key=lambda item: (-item["mean_wait_s"], item["hostel_id"]))
        worst_hostel_id = ranked[0]["hostel_id"]
        max_hostel_mean = ranked[0]["mean_wait_s"]

    fairness = _fairness(policy, scenario, hostel_rows, campus_mean)
    delay_explanations = _delay_explanations(wait_intervals, parts, trace)
    student_time_intervals = _student_time_intervals(
        wait_intervals, parts, trace, places
    )
    behavior_outcomes = _compile_behavior_outcomes(
        engine, parts, trace, students, completions, unfinished, seen_withdrawn
    )
    unit_records = _source_unit_records(
        scenario,
        parts,
        trace,
        completions,
        unfinished,
        wait_by_unit,
        reporting,
        list(engine.count_records),
        behavior_outcomes=behavior_outcomes,
    )
    group_records = _group_records(
        parts, trace, completions, unfinished, wait_by_group, scenario, reporting
    )
    vehicle_totals = _vehicle_totals(engine)
    coordination = _coordination(engine, trace)
    exceedance = _operating_limit_measures(engine)
    denied_n = _denied_entry_students(trace)
    peak_map = getattr(engine, "peak_queue_students", None) or {}
    peak_queue = max(peak_map.values(), default=0)

    unused_service_s = ms_to_s(int(getattr(engine, "unused_service_ms", 0) or 0))
    headcount_actions = len(engine.count_records)
    recounts = sum(1 for row in engine.count_records if int(row.get("attempt") or 1) > 1)
    unresolved_counts = sum(1 for row in engine.count_records if row.get("outcome") == "unresolved")

    measures = {
        "total_queue_waiting_student_s": queue_wait_s,
        "total_hold_waiting_student_s": hold_wait_s,
        "total_student_waiting_student_s": total_wait_s,
        "waiting_student_s_by_cause": wait_by_cause,
        "waiting_student_s_by_class": wait_by_class,
        "total_service_student_s": service_s,
        "required_stationary_service_student_s": stationary_s,
        "counting_student_s": count_s,
        "assembly_student_s": assembly_s,
        "unused_service_s": unused_service_s,
        "unused_service_is_student_waiting": False,
        "late_students": len(late_students),
        "total_lateness_s": sum(row["late_s"] for row in late_students),
        "max_lateness_s": max((row["late_s"] for row in late_students), default=0.0),
        "unfinished_students": unfinished_n,
        "completed_students": completed_n,
        "withdrawn_students": withdrawn_n,
        "attending_students": attending_from_units or attending_n,
        "accounted_students": completed_n + withdrawn_n + unfinished_n,
        "wait_denominator_students": attending_n,
        "unfinished_in_wait_denominator": unfinished_n,
        "mean_wait_s": mean_wait_s,
        "p95_wait_s": p95_wait_s,
        "p95_weighting": "student_count",
        "total_required_journey_student_s": total_journey_s,
        "total_required_journey_s": total_journey_s,
        "reporting_lateness_student_s": reporting_lateness_s,
        "earlier_reporting_burden_student_s": earlier_burden_s,
        "early_arrival_idle_student_s": early_idle_s,
        "free_time_before_reporting_student_s": free_time_s,
        "post_completion_stationary_student_s": 0.0,
        "outdoor_waiting_student_s": {
            "exposed": outdoor["exposed"],
            "shaded": outdoor["shaded"],
            "sheltered": outdoor["sheltered"],
        },
        "outdoor_waiting": {
            "exposed_student_s": outdoor["exposed"],
            "shaded_student_s": outdoor["shaded"],
            "sheltered_student_s": outdoor["sheltered"],
            "measured_medical_risk": False,
        },
        "max_queue_students": peak_queue,
        "denied_entry_students": denied_n,
        "operating_limit_exceedance": exceedance,
        "headcount_actions": headcount_actions,
        "recounts": recounts,
        "unresolved_counts": unresolved_counts,
        "max_hostel_mean_wait_s": max_hostel_mean,
        "worst_hostel_id": worst_hostel_id,
        "by_hostel": hostel_rows,
        "by_campus": {
            "mean_wait_s": mean_wait_s,
            "p95_wait_s": p95_wait_s,
            "total_student_waiting_student_s": total_wait_s,
            "late_students": len(late_students),
            "total_lateness_s": sum(row["late_s"] for row in late_students),
            "unfinished_students": unfinished_n,
            "wait_denominator_students": attending_n,
            "total_required_journey_student_s": total_journey_s,
        },
        "vehicles": vehicle_totals,
        "coordination": coordination,
        "fairness": fairness,
        "numerical_rounding_limit_s": rounding_s,
        "reporting_late_students": behavior_outcomes["totals"]["reporting_late_students"],
        "assembly_leftover_students": behavior_outcomes["totals"]["assembly_leftover_students"],
        "assembly_leftover_events": behavior_outcomes["totals"]["assembly_leftover_events"],
        "missed_pulse_students": behavior_outcomes["totals"]["missed_pulse_students"],
        "deviation_attempt_students": behavior_outcomes["totals"]["deviation_attempt_students"],
        "path_skip_students": behavior_outcomes["totals"]["path_skip_students"],
        "hall_area_late_students": behavior_outcomes["totals"]["hall_area_late_students"],
        "hall_area_lateness_student_s": behavior_outcomes["totals"]["hall_area_lateness_student_s"],
        "unfinished_leftover_students": behavior_outcomes["totals"]["unfinished_leftover_students"],
        "non_attendance_students": behavior_outcomes["totals"]["non_attendance_students"],
        "catch_up_walk_students": behavior_outcomes["totals"]["catch_up_walk_students"],
        "catch_up_time_saved_student_s": behavior_outcomes["totals"]["catch_up_time_saved_student_s"],
        "queue_jump_attempt_students": behavior_outcomes["totals"]["queue_jump_attempt_students"],
        "queue_jump_enacted_students": behavior_outcomes["totals"]["queue_jump_enacted_students"],
        "station_intercept_students": behavior_outcomes["totals"]["station_intercept_students"],
        "station_miss_students": behavior_outcomes["totals"]["station_miss_students"],
        "station_intercept_students_by_place": behavior_outcomes["totals"]["station_intercept_students_by_place"],
        "station_miss_students_by_place": behavior_outcomes["totals"]["station_miss_students_by_place"],
        "unsupervised_flow_students": behavior_outcomes["totals"]["unsupervised_flow_students"],
    }
    measures["by_campus"].update(behavior_outcomes["totals"])
    return {
        "measures": measures,
        "delay_explanations": delay_explanations,
        "student_time_intervals": student_time_intervals,
        "source_unit_records": unit_records,
        "group_records": group_records,
        "hostel_records": hostel_rows,
        "reporting_assumptions": reporting["assumptions"],
        "students": students,
        "event_trace_retained": True,
    }


def merge_worker_measures(measures: dict, worker_stats: Mapping[str, Any]) -> dict:
    stats = dict(worker_stats)
    stats.pop("assignments", None)
    measures.update(
        {
            "worker_reserved_s": stats.get("worker_reserved_s", 0.0),
            "worker_travel_s": stats.get("worker_travel_s", 0.0),
            "worker_escort_s": stats.get("worker_escort_s", 0.0),
            "worker_count_s": stats.get("worker_count_s", 0.0),
            "worker_station_s": stats.get("worker_station_s", 0.0),
            "worker_handover_s": stats.get("worker_handover_s", 0.0),
            "worker_standby_s": stats.get("worker_standby_s", 0.0),
            "worker_duty_s": stats.get("worker_duty_s", stats.get("worker_reserved_s", 0.0)),
            "worker_unused_availability_s": stats.get("worker_unused_availability_s", 0.0),
            "peak_concurrent_workers": stats.get("peak_concurrent_workers", 0),
            "worker_overlap_double_counted": False,
        }
    )
    return measures


def _student_index(parts: Mapping[str, Any], completions: list[dict], unfinished: list[dict]) -> dict[str, dict]:
    students: dict[str, dict] = {}
    for part in parts.values():
        for member in getattr(part, "members", []) or []:
            key = member.get("student_key")
            if not key:
                continue
            entry = students.setdefault(
                key,
                {
                    "student_key": key,
                    "hostel_id": member.get("hostel_id") or part.hostel_id,
                    "source_unit_id": member.get("source_unit_id") or part.source_unit_id,
                    "group_id": part.group_id,
                    "part_id": part.part_id,
                },
            )
            for attr in (
                "cohort_id",
                "attendance_state",
                "actual_reporting_s",
                "required_reporting_s",
                "readiness_s",
                "availability_s",
                "late_assembly_s",
                "reporting_mode",
            ):
                if attr in member and member[attr] is not None:
                    entry[attr] = member[attr]
    for row in completions:
        key = row["student_key"]
        students.setdefault(
            key,
            {
                "student_key": key,
                "hostel_id": row.get("hostel_id") or "unknown",
                "source_unit_id": row.get("source_unit_id") or "unknown",
                "group_id": row.get("group_id"),
                "part_id": row.get("part_id"),
            },
        )
    return students


def _reporting_context(scenario: Mapping[str, Any], policy: Mapping[str, Any], students: dict[str, dict]) -> dict:
    operating = dict(scenario.get("operating_rules") or {})
    window = operating.get("reporting_window") or policy.get("reporting_window")
    if isinstance(window, Mapping):
        window_d = {
            "earliest_s": float(window.get("earliest_s") or 0),
            "latest_s": float(window.get("latest_s") or window.get("earliest_s") or 0),
        }
    else:
        window_d = None
    rule = operating.get("attendance_response_rule") or policy.get("attendance_response_rule") or {
        "type": "fixed"
    }
    if not isinstance(rule, Mapping):
        rule = {"type": str(rule)}
    choice = policy.get("reporting_time_s")
    if choice is None:
        nested = policy.get("reporting") or {}
        if isinstance(nested, Mapping):
            choice = nested.get("required_reporting_s") or nested.get("reporting_time_s")
    units = {unit["id"]: dict(unit) for unit in scenario.get("source_units") or []}
    availability = {}
    for unit_id, unit in units.items():
        availability[unit_id] = float(
            unit.get("availability_s") if unit.get("availability_s") is not None else 0
        )
    required_by_unit: dict[str, float] = {}
    actual_by_unit: dict[str, float] = {}
    for unit_id, unit in units.items():
        required = unit.get("required_reporting_s")
        if required is None:
            required = choice
        actual = unit.get("actual_reporting_s")
        if actual is None:
            actual = 0
        actual = float(actual)
        if required is None:
            required = actual
        required = float(required)
        if str(rule.get("type") or "fixed") == "report_at_instruction":
            actual = max(float(unit.get("availability_s") or 0), required)
        required_by_unit[unit_id] = required
        actual_by_unit[unit_id] = actual
    for _key, info in students.items():
        unit = units.get(info["source_unit_id"]) or {}
        req_val = info.get("required_reporting_s")
        if req_val is None:
            req_val = required_by_unit.get(info["source_unit_id"])
        if req_val is None:
            req_val = float(unit.get("required_reporting_s") or unit.get("actual_reporting_s") or 0)
        req_val = float(req_val)

        act_val = info.get("actual_reporting_s")
        if act_val is None:
            act_val = actual_by_unit.get(info["source_unit_id"])
        if act_val is None:
            act_val = float(unit.get("actual_reporting_s") or 0)
        act_val = float(act_val)

        info["required_reporting_s"] = req_val
        info["actual_reporting_s"] = act_val
        if info.get("readiness_s") is None:
            info["readiness_s"] = float(unit.get("readiness_s") or 0)
        else:
            info["readiness_s"] = float(info["readiness_s"])
        if info.get("availability_s") is None:
            info["availability_s"] = float(
                unit.get("availability_s")
                if unit.get("availability_s") is not None
                else min(act_val, req_val)
            )
        else:
            info["availability_s"] = float(info["availability_s"])
        availability[info["source_unit_id"]] = info["availability_s"]
    return {
        "reporting_window": window_d,
        "assumptions": {
            "availability_s_by_unit": availability,
            "required_reporting_s_by_unit": required_by_unit,
            "actual_reporting_s_by_unit": actual_by_unit,
            "reporting_window": window_d,
            "attendance_response_rule": dict(rule),
            "required_reporting_is_search_choice": choice is not None,
            "exogenous_availability_retained": True,
        },
    }


def _explode_waits(wait_intervals: Iterable[Any], parts: Mapping[str, Any]) -> list[dict]:
    rows: list[dict] = []
    for interval in wait_intervals:
        duration_s = ms_to_s(max(0, int(interval.end_ms) - int(interval.start_ms)))
        if duration_s <= 0:
            continue
        part = parts.get(interval.part_id)
        members = list(part.members) if part is not None else []
        n = int(interval.student_count or 0)
        if members:
            share = members
        else:
            share = [
                {
                    "student_key": f"{interval.part_id}:{index}",
                    "hostel_id": getattr(interval, "hostel_id", None) or "unknown",
                    "source_unit_id": "unknown",
                }
                for index in range(max(1, n))
            ]
        for member in share:
            rows.append(
                {
                    "student_key": member["student_key"],
                    "hostel_id": member.get("hostel_id")
                    or (part.hostel_id if part is not None else "unknown"),
                    "source_unit_id": member.get("source_unit_id")
                    or (part.source_unit_id if part is not None else "unknown"),
                    "group_id": part.group_id if part is not None else interval.part_id,
                    "duration_s": duration_s,
                    "student_s": duration_s,
                    "student_count": 1,
                    "cause": interval.cause,
                    "place_id": interval.place_id,
                    "resource_id": getattr(interval, "resource_id", None),
                    "part_id": interval.part_id,
                    "start_s": ms_to_s(int(interval.start_ms)),
                    "end_s": ms_to_s(int(interval.end_ms)),
                    "start_ms": int(interval.start_ms),
                    "end_ms": int(interval.end_ms),
                }
            )
        if members and n and len(members) != n:
            # Interval student_count is the occupancy weight. Prefer members
            # so P95 stays student-weighted; student-seconds follow members.
            pass
    return rows


def _outdoor_class(place: Mapping[str, Any]) -> str:
    raw = place.get("outdoor_class") or place.get("exposure_class")
    if raw:
        return str(raw)
    if place.get("shelter_access") is True:
        return "sheltered"
    if place.get("shaded") is True:
        return "shaded"
    if place.get("indoor") is True:
        return "indoor"
    text = f"{place.get('id') or ''} {place.get('meaning') or ''}".lower()
    if "shelter" in text:
        return "sheltered"
    if "shade" in text:
        return "shaded"
    if any(
        token in text
        for token in (
            "gather",
            "bus_wait",
            "exterior",
            "path",
            "road",
            "outdoor",
            "approach",
            "alight",
            "yard",
            "hold",
        )
    ):
        return "exposed"
    if any(token in text for token in ("hall", "foyer", "entrance", "seat", "indoor")):
        return "indoor"
    return "unknown"


def _event_start_s(scenario: Mapping[str, Any]) -> float | None:
    operating = scenario.get("operating_rules") or {}
    if operating.get("event_start_s") is not None:
        return float(operating["event_start_s"])
    if scenario.get("event_start_s") is not None:
        return float(scenario["event_start_s"])
    return None


def _destination_place_ids(scenario: Mapping[str, Any], engine: Any) -> set[str]:
    ids: set[str] = set()
    dest = scenario.get("destination") or {}
    for key in ("seating_place_id", "hall_place_id", "entrance_place_id"):
        if dest.get(key):
            ids.add(str(dest[key]))
    seating_place_id = getattr(engine, "seating_place_id", None)
    if seating_place_id:
        ids.add(str(seating_place_id))
    for stage in scenario.get("route_stages") or []:
        if stage.get("completion_event") in ENDPOINT_EVENTS and stage.get("place_id"):
            ids.add(str(stage["place_id"]))
        if stage.get("kind") == "hold" and stage.get("place_id"):
            meaning = f"{stage.get('place_id')} {stage.get('id') or ''}".lower()
            if any(token in meaning for token in ("hall", "dtsp", "foyer", "seat")):
                ids.add(str(stage["place_id"]))
    for place in scenario.get("places") or []:
        pid = str(place.get("id") or "")
        meaning = f"{pid} {place.get('meaning') or ''}".lower()
        if any(token in meaning for token in ("hall", "dtsp", "foyer", "seat")):
            ids.add(pid)
    return ids


def _hostel_rows(
    students: dict[str, dict],
    completions: list[dict],
    unfinished: list[dict],
    wait_by_student: Mapping[str, float],
    wait_by_hostel: Mapping[str, float],
    scenario: Mapping[str, Any],
) -> list[dict]:
    by_hostel: dict[str, dict] = {}
    for key, info in students.items():
        hostel_id = info["hostel_id"]
        row = by_hostel.setdefault(
            hostel_id,
            {
                "hostel_id": hostel_id,
                "student_count": 0,
                "completed_students": 0,
                "late_students": 0,
                "unfinished_students": 0,
                "total_waiting_student_s": 0.0,
                "waits": [],
            },
        )
        row["student_count"] += 1
        row["total_waiting_student_s"] += wait_by_student.get(key, 0.0)
        row["waits"].append(wait_by_student.get(key, 0.0))
    completed_keys = {row["student_key"] for row in completions}
    for row in completions:
        hostel_id = row.get("hostel_id") or "unknown"
        bucket = by_hostel.setdefault(
            hostel_id,
            {
                "hostel_id": hostel_id,
                "student_count": 0,
                "completed_students": 0,
                "late_students": 0,
                "unfinished_students": 0,
                "total_waiting_student_s": 0.0,
                "waits": [],
            },
        )
        bucket["completed_students"] += 1
        if row["late_s"] > 0:
            bucket["late_students"] += 1
    unfinished_hostels: dict[str, int] = defaultdict(int)
    for row in unfinished:
        hostel_id = row.get("hostel_id")
        if not hostel_id:
            part_students = [
                info for info in students.values() if info.get("part_id") == row.get("part_id")
            ]
            if part_students:
                hostel_id = part_students[0]["hostel_id"]
            else:
                hostel_id = "unknown"
        unfinished_hostels[hostel_id] += int(row["student_count"])
    for hostel_id, count in unfinished_hostels.items():
        bucket = by_hostel.setdefault(
            hostel_id,
            {
                "hostel_id": hostel_id,
                "student_count": 0,
                "completed_students": 0,
                "late_students": 0,
                "unfinished_students": 0,
                "total_waiting_student_s": 0.0,
                "waits": [],
            },
        )
        bucket["unfinished_students"] += count
    rows = []
    for hostel_id in sorted(by_hostel):
        bucket = by_hostel[hostel_id]
        denom = bucket["student_count"] or bucket["completed_students"] + bucket["unfinished_students"]
        mean = (bucket["total_waiting_student_s"] / denom) if denom else 0.0
        rows.append(
            {
                "hostel_id": hostel_id,
                "student_count": denom,
                "completed_students": bucket["completed_students"],
                "late_students": bucket["late_students"],
                "unfinished_students": bucket["unfinished_students"],
                "wait_denominator_students": denom,
                "total_waiting_student_s": bucket["total_waiting_student_s"],
                "mean_wait_s": mean,
                "p95_wait_s": student_weighted_p95(list(bucket["waits"])),
            }
        )
    return rows


def _fairness(
    policy: Mapping[str, Any],
    scenario: Mapping[str, Any],
    hostel_rows: list[dict],
    campus_mean: float,
) -> dict:
    raw = policy.get("fairness_limit") or (scenario.get("operating_rules") or {}).get("fairness_limit")
    disadvantaged = []
    for row in hostel_rows:
        delta = row["mean_wait_s"] - campus_mean
        if delta > 0:
            disadvantaged.append(
                {
                    "hostel_id": row["hostel_id"],
                    "mean_wait_s": row["mean_wait_s"],
                    "campus_mean_wait_s": campus_mean,
                    "increase_s": delta,
                }
            )
    if not raw:
        return {
            "limit_configured": False,
            "limit_s": None,
            "evaluated": False,
            "passed": None,
            "comparison": "campus_mean_wait",
            "disadvantaged_hostels": disadvantaged,
            "max_hostel_mean_wait_s": max((row["mean_wait_s"] for row in hostel_rows), default=0.0),
            "worst_hostel_id": max(hostel_rows, key=lambda row: row["mean_wait_s"])["hostel_id"]
            if hostel_rows
            else None,
        }
    limit_s = float(
        raw.get("max_hostel_increase_vs_campus_s")
        if isinstance(raw, Mapping)
        else raw
    )
    failed = [row for row in disadvantaged if row["increase_s"] > limit_s + 1e-9]
    return {
        "limit_configured": True,
        "limit_s": limit_s,
        "evaluated": True,
        "passed": not failed,
        "comparison": "campus_mean_wait",
        "disadvantaged_hostels": disadvantaged,
        "hostels_over_limit": failed,
        "max_hostel_mean_wait_s": max((row["mean_wait_s"] for row in hostel_rows), default=0.0),
        "worst_hostel_id": max(hostel_rows, key=lambda row: row["mean_wait_s"])["hostel_id"]
        if hostel_rows
        else None,
    }


def _delay_explanations(wait_intervals: Iterable[Any], parts: Mapping[str, Any], trace: list[dict]) -> list[dict]:
    by_part_events: dict[str, list[dict]] = defaultdict(list)
    by_place_events: dict[str, list[dict]] = defaultdict(list)
    for event in trace:
        if event.get("affected_part_id"):
            by_part_events[event["affected_part_id"]].append(event)
        if event.get("place_id"):
            by_place_events[str(event["place_id"])].append(event)
    rows = []
    for interval in wait_intervals:
        duration_s = ms_to_s(max(0, int(interval.end_ms) - int(interval.start_ms)))
        if duration_s <= 0:
            continue
        related = []
        for event in by_part_events.get(interval.part_id, []):
            if int(interval.start_ms) <= int(event["time_ms"]) <= int(interval.end_ms):
                related.append(event["event_id"])
        if not related and interval.place_id:
            for event in by_place_events.get(str(interval.place_id), []):
                if int(interval.start_ms) <= int(event["time_ms"]) <= int(interval.end_ms):
                    related.append(event["event_id"])
                    if len(related) >= 8:
                        break
        resource_id = getattr(interval, "resource_id", None)
        rows.append(
            {
                "place_id": interval.place_id,
                "resource_id": resource_id,
                "cause": interval.cause,
                "primary_cause": interval.cause,
                "duration_s": duration_s,
                "affected_count": int(interval.student_count),
                "part_id": interval.part_id,
                "related_event_ids": related,
            }
        )
    return rows


def _student_time_intervals(
    wait_intervals: Iterable[Any],
    parts: Mapping[str, Any],
    trace: list[dict],
    places: Mapping[str, Any],
) -> list[dict]:
    rows: list[dict] = []
    for interval in wait_intervals:
        duration_s = ms_to_s(max(0, int(interval.end_ms) - int(interval.start_ms)))
        if duration_s <= 0:
            continue
        rows.append(
            {
                "part_id": interval.part_id,
                "student_count": int(interval.student_count),
                "primary_activity": "waiting",
                "primary_waiting_cause": interval.cause,
                "secondary_reasons": list(getattr(interval, "secondary_reasons", None) or []),
                "place_id": interval.place_id,
                "resource_id": getattr(interval, "resource_id", None),
                "start_ms": int(interval.start_ms),
                "end_ms": int(interval.end_ms),
                "duration_s": duration_s,
            }
        )
    open_acts: dict[str, dict] = {}

    def close(part_id: str, time_ms: int, event_id: str | None = None) -> None:
        current = open_acts.pop(part_id, None)
        if current is None:
            return
        duration_s = ms_to_s(max(0, time_ms - current["start_ms"]))
        if duration_s <= 0:
            return
        related = list(current["related_event_ids"])
        if event_id:
            related.append(event_id)
        rows.append(
            {
                "part_id": part_id,
                "student_count": current["student_count"],
                "primary_activity": current["primary_activity"],
                "primary_waiting_cause": None,
                "secondary_reasons": [],
                "place_id": current["place_id"],
                "resource_id": current.get("resource_id"),
                "start_ms": current["start_ms"],
                "end_ms": time_ms,
                "duration_s": duration_s,
                "related_event_ids": related,
            }
        )

    def start(event: dict, activity: str) -> None:
        part_id = event.get("affected_part_id")
        if not part_id:
            return
        close(part_id, event["time_ms"], event.get("event_id"))
        part = parts.get(part_id)
        open_acts[part_id] = {
            "primary_activity": activity,
            "start_ms": event["time_ms"],
            "place_id": event.get("place_id") or (part.place_id if part else None),
            "resource_id": (event.get("resource_ids") or [None])[0],
            "student_count": int(event.get("student_count") or (part.student_count if part else 0)),
            "related_event_ids": [event["event_id"]],
        }

    for event in trace:
        etype = event.get("event_type")
        if etype in ACTIVITY_TRAVEL_START:
            start(event, "travel")
        elif etype in ACTIVITY_TRAVEL_END:
            if event.get("affected_part_id"):
                close(event["affected_part_id"], event["time_ms"], event.get("event_id"))
        elif etype in ACTIVITY_SERVICE_START:
            start(event, "service")
        elif etype in ACTIVITY_SERVICE_END:
            if event.get("affected_part_id"):
                close(event["affected_part_id"], event["time_ms"], event.get("event_id"))
        elif etype in ACTIVITY_COUNT_START:
            start(event, "counting")
        elif etype in ACTIVITY_COUNT_END:
            if event.get("affected_part_id"):
                close(event["affected_part_id"], event["time_ms"], event.get("event_id"))
        elif etype in ACTIVITY_ASSEMBLY_START:
            start(event, "assembling")
        elif etype in ACTIVITY_ASSEMBLY_END:
            if event.get("affected_part_id"):
                close(event["affected_part_id"], event["time_ms"], event.get("event_id"))
    return rows


def _first_time(events: Iterable[dict], event_type: str) -> float | None:
    for event in events:
        if event.get("event_type") == event_type:
            return ms_to_s(int(event["time_ms"]))
    return None


def _members_descending_from_part(part_id: str, parts: Mapping[str, Any]) -> list[dict]:
    parents = {p.parent_part_id for p in parts.values() if p.parent_part_id}
    leaf_parts = [p for p in parts.values() if p.part_id not in parents and p.status != "split"]
    members: list[dict] = []
    seen: set[str] = set()
    for lp in leaf_parts:
        anc: list[str] = []
        curr: Any = lp
        while curr:
            anc.append(curr.part_id)
            curr = parts.get(curr.parent_part_id) if curr.parent_part_id else None
        if part_id in anc:
            for m in getattr(lp, "members", []) or []:
                k = m.get("student_key")
                if k and k not in seen:
                    seen.add(k)
                    members.append(m)
    if not members and part_id in parts:
        for m in getattr(parts[part_id], "members", []) or []:
            k = m.get("student_key")
            if k and k not in seen:
                seen.add(k)
                members.append(m)
    return members


def _walk_rule_congested_factor(rule: dict) -> float:
    if "congested_duration_factor" in rule:
        return float(rule["congested_duration_factor"])
    if "bands" in rule and rule["bands"]:
        return max(float(b.get("duration_factor", 1.0)) for b in rule["bands"])
    return 1.0


def _compile_behavior_outcomes(
    engine: Any,
    parts: Mapping[str, Any],
    trace: list[dict],
    students: dict[str, dict],
    completions: list[dict],
    unfinished: list[dict],
    seen_withdrawn: set[str],
) -> dict[str, Any]:
    scenario = engine.scenario
    source_units = scenario.get("source_units") or []
    if not scenario.get("behavior"):
        totals = {
            "reporting_late_students": 0,
            "reporting_lateness_student_s": 0.0,
            "assembly_leftover_students": 0,
            "assembly_leftover_events": 0,
            "missed_pulse_students": 0,
            "deviation_attempt_students": 0,
            "path_skip_students": 0,
            "hall_area_late_students": 0,
            "hall_area_lateness_student_s": 0.0,
            "unfinished_leftover_students": 0,
            "non_attendance_students": 0,
            "catch_up_walk_students": 0,
            "catch_up_time_saved_student_s": 0.0,
            "queue_jump_attempt_students": 0,
            "queue_jump_enacted_students": 0,
            "station_intercept_students": 0,
            "station_miss_students": 0,
            "station_intercept_students_by_place": {},
            "station_miss_students_by_place": {},
            "unsupervised_flow_students": 0,
        }
        by_su = {
            unit.get("id", ""): {
                "reporting_late_students": 0,
                "reporting_lateness_student_s": 0.0,
                "assembly_leftover_students": 0,
                "assembly_leftover_events": 0,
                "missed_pulse_students": 0,
                "deviation_attempt_students": 0,
                "path_skip_students": 0,
                "hall_area_late_students": 0,
                "hall_area_lateness_student_s": 0.0,
                "unfinished_leftover_students": 0,
                "non_attendance_students": 0,
                "withdrawn_students": 0,
                "catch_up_walk_students": 0,
                "catch_up_time_saved_student_s": 0.0,
                "queue_jump_attempt_students": 0,
                "queue_jump_enacted_students": 0,
                "station_intercept_students": 0,
                "station_miss_students": 0,
                "unsupervised_flow_students": 0,
            }
            for unit in source_units
        }
        return {"totals": totals, "by_source_unit": by_su}

    # 1. Non-attendance
    non_att_by_unit: dict[str, int] = defaultdict(int)
    non_attendance_n = 0
    for unit in source_units:
        uid = unit.get("id") or ""
        u_non_att = 0
        if unit.get("non_attendance") is not None:
            u_non_att = int(unit["non_attendance"])
        elif unit.get("cohorts"):
            u_non_att = sum(
                int(c.get("count", 0))
                for c in unit["cohorts"]
                if c.get("attendance_state") == "no_show"
            )
        elif unit.get("declared_population") is not None and unit.get("resolved_attendance") is not None:
            u_non_att = max(0, int(unit["declared_population"]) - int(unit["resolved_attendance"]))
        non_att_by_unit[uid] = u_non_att
        non_attendance_n += u_non_att

    # 2. Reporting lateness and late students
    reporting_late_by_unit: dict[str, int] = defaultdict(int)
    reporting_lateness_by_unit: dict[str, float] = defaultdict(float)
    reporting_late_students_set: set[str] = set()
    total_reporting_lateness_s = 0.0

    for key, info in students.items():
        if info.get("attendance_state") == "no_show":
            continue
        req = float(info.get("required_reporting_s") or 0.0)
        actual = float(info.get("actual_reporting_s") or 0.0)
        delay = max(0.0, actual - req)
        total_reporting_lateness_s += delay
        uid = info.get("source_unit_id") or ""
        if delay > 0:
            reporting_late_students_set.add(key)
            reporting_late_by_unit[uid] += 1
            reporting_lateness_by_unit[uid] += delay

    # 3. Assembly leftover
    assembly_leftover_students_set: set[str] = set()
    assembly_leftover_events = 0
    assembly_leftover_by_unit: dict[str, set[str]] = defaultdict(set)
    assembly_leftover_events_by_unit: dict[str, int] = defaultdict(int)

    for event in trace:
        if event.get("event_type") == "part_split" and event.get("cause") == "assembly_cutoff":
            assembly_leftover_events += 1
            child_ids = event.get("child_part_ids") or []
            late_id = child_ids[1] if len(child_ids) > 1 else event.get("affected_part_id")
            if late_id:
                late_members = _members_descending_from_part(late_id, parts)
                uids_affected = set()
                for m in late_members:
                    k = m.get("student_key")
                    uid = m.get("source_unit_id") or ""
                    if k:
                        assembly_leftover_students_set.add(k)
                        assembly_leftover_by_unit[uid].add(k)
                        uids_affected.add(uid)
                for uid in uids_affected:
                    assembly_leftover_events_by_unit[uid] += 1

    # 4. Missed pulse
    missed_pulse_students_set: set[str] = set()
    missed_pulse_by_unit: dict[str, set[str]] = defaultdict(set)

    for k in assembly_leftover_students_set:
        missed_pulse_students_set.add(k)
        info = students.get(k) or {}
        uid = info.get("source_unit_id") or ""
        missed_pulse_by_unit[uid].add(k)

    for event in trace:
        if event.get("event_type") == "part_split" and (
            event.get("cause") == "capacity_split"
            or event.get("primary_cause") == "capacity_split"
        ):
            parent_id = event.get("affected_part_id") or event.get("parent_part_id")
            child_subs = [p for p in parts.values() if p.parent_part_id == parent_id and p.status != "split"]
            if len(child_subs) > 1:
                for sub in child_subs[1:]:
                    for m in getattr(sub, "members", []) or []:
                        k = m.get("student_key")
                        uid = m.get("source_unit_id") or ""
                        if k:
                            missed_pulse_students_set.add(k)
                            missed_pulse_by_unit[uid].add(k)

    # 5. Queue jumps
    queue_jump_attempt_set: set[str] = set()
    queue_jump_enacted_set: set[str] = set()
    jump_attempt_by_unit: dict[str, set[str]] = defaultdict(set)
    jump_enacted_by_unit: dict[str, set[str]] = defaultdict(set)

    for event in trace:
        etype = event.get("event_type")
        if etype == "queue_jump_attempt":
            pid = event.get("affected_part_id")
            if pid:
                mems = _members_descending_from_part(pid, parts)
                for m in mems:
                    k = m.get("student_key")
                    uid = m.get("source_unit_id") or ""
                    if k:
                        queue_jump_attempt_set.add(k)
                        jump_attempt_by_unit[uid].add(k)
        elif etype == "queue_jump_enacted":
            pid = event.get("affected_part_id")
            if pid:
                mems = _members_descending_from_part(pid, parts)
                for m in mems:
                    k = m.get("student_key")
                    uid = m.get("source_unit_id") or ""
                    if k:
                        queue_jump_enacted_set.add(k)
                        jump_enacted_by_unit[uid].add(k)

    # 6. Station intercept and miss (by place_id)
    station_intercept_set: set[str] = set()
    station_miss_set: set[str] = set()
    station_intercept_by_place: dict[str, set[str]] = defaultdict(set)
    station_miss_by_place: dict[str, set[str]] = defaultdict(set)
    intercept_by_unit: dict[str, set[str]] = defaultdict(set)
    miss_by_unit: dict[str, set[str]] = defaultdict(set)

    for event in trace:
        etype = event.get("event_type")
        place_id = event.get("place_id") or "unknown"
        if etype == "station_intercept":
            pid = event.get("affected_part_id")
            if pid:
                mems = _members_descending_from_part(pid, parts)
                for m in mems:
                    k = m.get("student_key")
                    uid = m.get("source_unit_id") or ""
                    if k:
                        station_intercept_set.add(k)
                        station_intercept_by_place[place_id].add(k)
                        intercept_by_unit[uid].add(k)
        elif etype == "station_miss":
            pid = event.get("affected_part_id")
            if pid:
                mems = _members_descending_from_part(pid, parts)
                for m in mems:
                    k = m.get("student_key")
                    uid = m.get("source_unit_id") or ""
                    if k:
                        station_miss_set.add(k)
                        station_miss_by_place[place_id].add(k)
                        miss_by_unit[uid].add(k)

    # 7. Catch-up walk
    catch_up_walk_set: set[str] = set()
    catch_up_time_saved_s = 0.0
    catch_up_by_unit: dict[str, set[str]] = defaultdict(set)
    catch_up_saved_by_unit: dict[str, float] = defaultdict(float)

    rule = (
        scenario.get("operating_rules", {}).get("walk_occupancy_rule")
        or scenario.get("walk_occupancy_rule")
    )
    if rule and isinstance(rule, dict):
        congested_factor = _walk_rule_congested_factor(rule)
        legs_dict = {leg["id"]: leg for leg in scenario.get("route_legs") or []}
        shared_resources = {res["id"]: res for res in scenario.get("shared_resources") or []}
        if hasattr(engine, "shared_resources") and isinstance(engine.shared_resources, dict):
            shared_resources.update(engine.shared_resources)
        rate_factor = float(getattr(engine, "walking_rate_factor", 1.0) or 1.0)

        for event in trace:
            if event.get("event_type") == "departure":
                pid = event.get("affected_part_id")
                p = parts.get(pid) if pid else None
                is_leftover = bool(
                    p and (
                        p.parent_part_id is not None
                        or (p.part_id and "_late" in p.part_id)
                        or any(m.get("late_assembly_s") for m in getattr(p, "members", []))
                    )
                )
                if not is_leftover:
                    continue

                leg_id = event.get("leg_id")
                leg = legs_dict.get(leg_id) if leg_id else None
                if leg and leg.get("mode") == "walk":
                    unique = float(leg.get("duration_s") or 0.0)
                    extra = 0.0
                    for rid in leg.get("shared_resource_ids") or []:
                        res_item = shared_resources.get(rid) or {}
                        if res_item.get("duration_s") is not None:
                            extra += float(res_item["duration_s"])
                    congested_dur = (unique + extra) * congested_factor
                    if rate_factor not in (0, None):
                        congested_dur = congested_dur / rate_factor

                    actual_dur = event.get("walk_duration_s")
                    if actual_dur is not None:
                        actual_dur = float(actual_dur)
                        if actual_dur < congested_dur:
                            saved_per_pax = max(0.0, congested_dur - actual_dur)
                            cnt = int(event.get("student_count") or len(getattr(p, "members", [])))
                            time_saved = saved_per_pax * cnt
                            catch_up_time_saved_s += time_saved
                            for m in getattr(p, "members", []) or []:
                                k = m.get("student_key")
                                uid = m.get("source_unit_id") or p.source_unit_id
                                if k:
                                    catch_up_walk_set.add(k)
                                    catch_up_by_unit[uid].add(k)
                                    catch_up_saved_by_unit[uid] += saved_per_pax
    # 8. Hall-area arrival and lateness
    hall_area_late_set: set[str] = set()
    hall_area_lateness_s = 0.0
    hall_late_by_unit: dict[str, set[str]] = defaultdict(set)
    hall_lateness_by_unit: dict[str, float] = defaultdict(float)

    hall_deadline = scenario.get("hall_deadline_s")
    if hall_deadline is None:
        hall_deadline = (scenario.get("operating_rules") or {}).get("hall_deadline_s")
    if hall_deadline is None:
        hall_deadline = scenario.get("deadline_s")

    if hall_deadline is not None:
        hall_deadline_f = float(hall_deadline)
        student_hall_arrival: dict[str, float] = {}
        for event in trace:
            if event.get("event_type") == "hall_area_arrival":
                t_s = ms_to_s(int(event["time_ms"]))
                pid = event.get("affected_part_id")
                if pid:
                    for m in _members_descending_from_part(pid, parts):
                        k = m.get("student_key")
                        if k and k not in student_hall_arrival:
                            student_hall_arrival[k] = t_s

        for k, arr_s in student_hall_arrival.items():
            if arr_s > hall_deadline_f:
                diff = arr_s - hall_deadline_f
                hall_area_late_set.add(k)
                hall_area_lateness_s += diff
                info = students.get(k) or {}
                uid = info.get("source_unit_id") or ""
                hall_late_by_unit[uid].add(k)
                hall_lateness_by_unit[uid] += diff

    # 9. Unfinished leftover
    unfinished_leftover_n = sum(int(row.get("student_count", 0)) for row in unfinished)
    unfinished_by_unit: dict[str, int] = defaultdict(int)
    for row in unfinished:
        pid = row.get("part_id")
        if pid and pid in parts:
            part_item = parts[pid]
            for m in getattr(part_item, "members", []) or []:
                uid = m.get("source_unit_id") or part_item.source_unit_id
                unfinished_by_unit[uid] += 1
        else:
            su = row.get("source_unit_id")
            if su:
                unfinished_by_unit[su] += int(row.get("student_count", 0))

    # 10. Deviation and stage skip
    dev_attempt_set: set[str] = set()
    path_skip_set: set[str] = set()
    dev_attempt_by_unit: dict[str, set[str]] = defaultdict(set)
    path_skip_by_unit: dict[str, set[str]] = defaultdict(set)

    b_events = (scenario.get("behavior") or {}).get("events") or []
    for bev in b_events:
        phenom = bev.get("phenomenon")
        if phenom in ("route_deviation", "stage_skip", "schedule_departure"):
            tgt = bev.get("target")
            for k, info in students.items():
                matched = False
                if isinstance(tgt, str) and (k == tgt or info.get("cohort_id") == tgt or info.get("source_unit_id") == tgt):
                    matched = True
                elif isinstance(tgt, list) and k in tgt:
                    matched = True
                elif isinstance(tgt, dict):
                    if tgt.get("member_keys") and k in tgt["member_keys"]:
                        matched = True
                    if tgt.get("cohort_id") and info.get("cohort_id") == tgt["cohort_id"]:
                        matched = True
                    if tgt.get("part_id") and info.get("part_id") == tgt["part_id"]:
                        matched = True
                if matched:
                    dev_attempt_set.add(k)
                    uid = info.get("source_unit_id") or ""
                    dev_attempt_by_unit[uid].add(k)

    for event in trace:
        etype = event.get("event_type")
        if etype in ("stage_skip", "path_skip"):
            pid = event.get("affected_part_id")
            if pid:
                mems = _members_descending_from_part(pid, parts)
                for m in mems:
                    k = m.get("student_key")
                    uid = m.get("source_unit_id") or ""
                    if k:
                        path_skip_set.add(k)
                        path_skip_by_unit[uid].add(k)

    # 11. Unsupervised flow (I2 in force, zero escort/station worker)
    unsupervised_set: set[str] = set()
    unsupervised_by_unit: dict[str, set[str]] = defaultdict(set)

    for event in trace:
        if event.get("event_type") in ("departure", "hold_start", "arrival"):
            pid = event.get("affected_part_id")
            if pid and pid in parts:
                p = parts[pid]
                req_escorts = int(getattr(p, "required_supervision", {}).get("escorts") or 0)
                if req_escorts > 0:
                    curr_escorts = len(getattr(p, "escort_ids", []) or event.get("escort_ids", []))
                    curr_station = getattr(p, "station_worker_id", None)
                    if curr_escorts == 0 and not curr_station:
                        for m in _members_descending_from_part(pid, parts):
                            k = m.get("student_key")
                            uid = m.get("source_unit_id") or ""
                            if k:
                                unsupervised_set.add(k)
                                unsupervised_by_unit[uid].add(k)

    # Withdrawn by unit
    withdrawn_by_unit: dict[str, int] = defaultdict(int)
    for k in seen_withdrawn:
        info = students.get(k) or {}
        uid = info.get("source_unit_id") or ""
        if uid:
            withdrawn_by_unit[uid] += 1

    totals = {
        "reporting_late_students": len(reporting_late_students_set),
        "reporting_lateness_student_s": total_reporting_lateness_s,
        "assembly_leftover_students": len(assembly_leftover_students_set),
        "assembly_leftover_events": assembly_leftover_events,
        "missed_pulse_students": len(missed_pulse_students_set),
        "deviation_attempt_students": len(dev_attempt_set),
        "path_skip_students": len(path_skip_set),
        "hall_area_late_students": len(hall_area_late_set),
        "hall_area_lateness_student_s": hall_area_lateness_s,
        "unfinished_leftover_students": unfinished_leftover_n,
        "non_attendance_students": non_attendance_n,
        "catch_up_walk_students": len(catch_up_walk_set),
        "catch_up_time_saved_student_s": catch_up_time_saved_s,
        "queue_jump_attempt_students": len(queue_jump_attempt_set),
        "queue_jump_enacted_students": len(queue_jump_enacted_set),
        "station_intercept_students": len(station_intercept_set),
        "station_miss_students": len(station_miss_set),
        "station_intercept_students_by_place": {p: len(s) for p, s in station_intercept_by_place.items()},
        "station_miss_students_by_place": {p: len(s) for p, s in station_miss_by_place.items()},
        "unsupervised_flow_students": len(unsupervised_set),
    }

    by_su = {}
    for unit in source_units:
        uid = unit.get("id") or ""
        by_su[uid] = {
            "reporting_late_students": reporting_late_by_unit[uid],
            "reporting_lateness_student_s": reporting_lateness_by_unit[uid],
            "assembly_leftover_students": len(assembly_leftover_by_unit[uid]),
            "assembly_leftover_events": assembly_leftover_events_by_unit[uid],
            "missed_pulse_students": len(missed_pulse_by_unit[uid]),
            "deviation_attempt_students": len(dev_attempt_by_unit[uid]),
            "path_skip_students": len(path_skip_by_unit[uid]),
            "hall_area_late_students": len(hall_late_by_unit[uid]),
            "hall_area_lateness_student_s": hall_lateness_by_unit[uid],
            "unfinished_leftover_students": unfinished_by_unit[uid],
            "non_attendance_students": non_att_by_unit[uid],
            "withdrawn_students": withdrawn_by_unit[uid],
            "catch_up_walk_students": len(catch_up_by_unit[uid]),
            "catch_up_time_saved_student_s": catch_up_saved_by_unit[uid],
            "queue_jump_attempt_students": len(jump_attempt_by_unit[uid]),
            "queue_jump_enacted_students": len(jump_enacted_by_unit[uid]),
            "station_intercept_students": len(intercept_by_unit[uid]),
            "station_miss_students": len(miss_by_unit[uid]),
            "unsupervised_flow_students": len(unsupervised_by_unit[uid]),
        }

    return {"totals": totals, "by_source_unit": by_su}


def _source_unit_records(
    scenario: Mapping[str, Any],
    parts: Mapping[str, Any],
    trace: list[dict],
    completions: list[dict],
    unfinished: list[dict],
    wait_by_unit: Mapping[str, float],
    reporting: dict,
    count_records: list[dict] | None = None,
    behavior_outcomes: dict | None = None,
) -> list[dict]:
    units = [dict(unit) for unit in scenario.get("source_units") or []]
    by_unit_parts: dict[str, list[Any]] = defaultdict(list)
    for part in parts.values():
        for unit_id in part.source_unit_ids or [part.source_unit_id]:
            by_unit_parts[unit_id].append(part)
    completed_by_unit: dict[str, list[dict]] = defaultdict(list)
    for row in completions:
        completed_by_unit[row.get("source_unit_id") or ""].append(row)
    unfinished_by_unit: dict[str, int] = defaultdict(int)
    for part in parts.values():
        if part.status in {"completed", "split", "withdrawn"}:
            continue
        unfinished_by_unit[part.source_unit_id] += part.student_count
    rows = []
    for unit in units:
        unit_id = unit["id"]
        unit_parts = by_unit_parts.get(unit_id) or []
        part_ids = {part.part_id for part in unit_parts}
        events = [event for event in trace if event.get("affected_part_id") in part_ids]
        required = reporting["assumptions"].get("required_reporting_s_by_unit", {}).get(unit_id)
        actual = reporting["assumptions"].get("actual_reporting_s_by_unit", {}).get(unit_id)
        if actual is None:
            actual = float(unit.get("actual_reporting_s") or 0)
        if required is None:
            required = unit.get("required_reporting_s")
            if required is None:
                required = actual
        assembly_start = _first_time(events, "assembly_start")
        assembly_finish = _first_time(events, "assembly_complete")
        release = _release_s(events)
        endpoints = _endpoint_times(events)
        expected = unit.get("estimated_attendance")
        observed = _observed_count_for_unit(unit_id, count_records or [])
        status = "completed"
        unfinished_n = unfinished_by_unit.get(unit_id, 0)
        completed_n = len(completed_by_unit.get(unit_id) or [])
        if observed is None:
            observed = completed_n
        if unfinished_n and completed_n:
            status = "partial"
        elif unfinished_n:
            status = "unfinished"
        bo = (behavior_outcomes or {}).get("by_source_unit", {}).get(unit_id, {})
        rows.append(
            {
                "source_unit_id": unit_id,
                "hostel_id": unit.get("hostel_id"),
                "required_reporting_s": float(required),
                "actual_reporting_s": actual,
                "readiness_s": float(unit.get("readiness_s") or 0),
                "availability_s": float(unit.get("availability_s") or 0),
                "assembly_start_s": assembly_start,
                "assembly_finish_s": assembly_finish,
                "release_s": release,
                "stage_arrivals": _stage_arrivals(events),
                "service_times": _service_times(events),
                "hall_area_arrival_s": endpoints.get("hall_area_arrival_s"),
                "entrance_completion_s": endpoints.get("entrance_completion_s"),
                "seated_completion_s": endpoints.get("seated_completion_s"),
                "expected_count": expected,
                "observed_count": observed,
                "completed_students": completed_n,
                "unfinished_students": unfinished_n,
                "status": status,
                "total_waiting_student_s": wait_by_unit.get(unit_id, 0.0),
                "supported_completion_points": [
                    name
                    for name, value in endpoints.items()
                    if value is not None
                ],
                "unknown_completion_points": [
                    name.replace("_s", "")
                    for name, value in endpoints.items()
                    if value is None
                ],
                "reporting_late_students": bo.get("reporting_late_students", 0),
                "reporting_lateness_student_s": bo.get("reporting_lateness_student_s", 0.0),
                "assembly_leftover_students": bo.get("assembly_leftover_students", 0),
                "assembly_leftover_events": bo.get("assembly_leftover_events", 0),
                "missed_pulse_students": bo.get("missed_pulse_students", 0),
                "deviation_attempt_students": bo.get("deviation_attempt_students", 0),
                "path_skip_students": bo.get("path_skip_students", 0),
                "hall_area_late_students": bo.get("hall_area_late_students", 0),
                "hall_area_lateness_student_s": bo.get("hall_area_lateness_student_s", 0.0),
                "unfinished_leftover_students": bo.get("unfinished_leftover_students", 0),
                "non_attendance_students": bo.get("non_attendance_students", 0),
                "withdrawn_students": bo.get("withdrawn_students", 0),
                "catch_up_walk_students": bo.get("catch_up_walk_students", 0),
                "catch_up_time_saved_student_s": bo.get("catch_up_time_saved_student_s", 0.0),
                "queue_jump_attempt_students": bo.get("queue_jump_attempt_students", 0),
                "queue_jump_enacted_students": bo.get("queue_jump_enacted_students", 0),
                "station_intercept_students": bo.get("station_intercept_students", 0),
                "station_miss_students": bo.get("station_miss_students", 0),
                "unsupervised_flow_students": bo.get("unsupervised_flow_students", 0),
            }
        )
    return rows


def _group_records(
    parts: Mapping[str, Any],
    trace: list[dict],
    completions: list[dict],
    unfinished: list[dict],
    wait_by_group: Mapping[str, float],
    scenario: Mapping[str, Any],
    reporting: dict,
) -> list[dict]:
    groups: dict[str, dict] = {}
    for part in parts.values():
        row = groups.setdefault(
            part.group_id,
            {
                "group_id": part.group_id,
                "parent_group_id": part.parent_group_id or part.group_id,
                "hostel_ids": set(),
                "source_unit_ids": set(),
                "part_ids": set(),
                "student_keys": set(),
            },
        )
        row["hostel_ids"].add(part.hostel_id)
        row["source_unit_ids"].update(part.source_unit_ids or [part.source_unit_id])
        row["part_ids"].add(part.part_id)
        for member in part.members:
            row["student_keys"].add(member["student_key"])
    completed_by_group: dict[str, list[dict]] = defaultdict(list)
    for item in completions:
        completed_by_group[item["group_id"]].append(item)
    unfinished_by_group: dict[str, int] = defaultdict(int)
    for part in parts.values():
        if part.status in {"completed", "split", "withdrawn"}:
            continue
        unfinished_by_group[part.group_id] += part.student_count
    rows = []
    for group_id in sorted(groups):
        meta = groups[group_id]
        part_ids = meta["part_ids"]
        events = [event for event in trace if event.get("affected_part_id") in part_ids]
        endpoints = _endpoint_times(events)
        unfinished_n = unfinished_by_group.get(group_id, 0)
        completed_n = len(completed_by_group.get(group_id) or [])
        status = "completed"
        if unfinished_n and completed_n:
            status = "partial"
        elif unfinished_n:
            status = "unfinished"
        rows.append(
            {
                "group_id": group_id,
                "parent_group_id": meta["parent_group_id"],
                "hostel_ids": sorted(meta["hostel_ids"]),
                "source_unit_ids": sorted(meta["source_unit_ids"]),
                "required_reporting_s": _group_reporting(meta["source_unit_ids"], scenario, "required_reporting_s"),
                "actual_reporting_s": _group_reporting(meta["source_unit_ids"], scenario, "actual_reporting_s"),
                "readiness_s": _group_reporting(meta["source_unit_ids"], scenario, "readiness_s"),
                "assembly_start_s": _first_time(events, "assembly_start"),
                "assembly_finish_s": _first_time(events, "assembly_complete"),
                "release_s": _release_s(events),
                "stage_arrivals": _stage_arrivals(events),
                "service_times": _service_times(events),
                "hall_area_arrival_s": endpoints.get("hall_area_arrival_s"),
                "entrance_completion_s": endpoints.get("entrance_completion_s"),
                "seated_completion_s": endpoints.get("seated_completion_s"),
                "expected_count": len(meta["student_keys"]),
                "observed_count": completed_n,
                "completed_students": completed_n,
                "unfinished_students": unfinished_n,
                "status": status,
                "total_waiting_student_s": wait_by_group.get(group_id, 0.0),
                "supported_completion_points": [
                    name for name, value in endpoints.items() if value is not None
                ],
                "unknown_completion_points": [
                    name.replace("_s", "")
                    for name, value in endpoints.items()
                    if value is None
                ],
            }
        )
    return rows


def _observed_count_for_unit(unit_id: str, count_records: list[dict]) -> int | None:
    observed = None
    for row in count_records:
        units = row.get("source_unit_ids") or []
        if unit_id == row.get("source_unit_id") or unit_id in units:
            if row.get("observed_count") is not None:
                observed = int(row["observed_count"])
    return observed


def _group_reporting(unit_ids: Iterable[str], scenario: Mapping[str, Any], field: str) -> float | None:
    units = {unit["id"]: unit for unit in scenario.get("source_units") or []}
    values = []
    for unit_id in unit_ids:
        unit = units.get(unit_id) or {}
        if unit.get(field) is not None:
            values.append(float(unit[field]))
        elif field == "required_reporting_s" and unit.get("actual_reporting_s") is not None:
            values.append(float(unit["actual_reporting_s"]))
    if not values:
        return None
    return max(values)


def _release_s(events: list[dict]) -> float | None:
    for event in events:
        if event.get("event_type") == "hold_end" and event.get("primary_cause") in {
            None,
            "waiting_for_release",
            "imposed_calendar",
            "calendar_open",
        }:
            return ms_to_s(int(event["time_ms"]))
        if event.get("event_type") == "departure":
            return ms_to_s(int(event["time_ms"]))
    for event in events:
        if event.get("event_type") == "hold_end":
            return ms_to_s(int(event["time_ms"]))
    return None


def _stage_arrivals(events: list[dict]) -> list[dict]:
    rows = []
    seen = set()
    for event in events:
        if event.get("event_type") not in {"arrival", "service_start", "batch_start", "hall_area_arrival"}:
            continue
        stage_id = event.get("stage_id")
        key = (stage_id, event.get("event_type"), event.get("place_id"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "stage_id": stage_id,
                "event_type": event.get("event_type"),
                "place_id": event.get("place_id"),
                "time_s": ms_to_s(int(event["time_ms"])),
            }
        )
    return rows


def _service_times(events: list[dict]) -> list[dict]:
    open_at: dict[str, dict] = {}
    rows = []
    for event in events:
        part_id = event.get("affected_part_id") or ""
        if event.get("event_type") in ACTIVITY_SERVICE_START | ACTIVITY_COUNT_START:
            open_at[part_id] = event
        elif event.get("event_type") in ACTIVITY_SERVICE_END | ACTIVITY_COUNT_END:
            start = open_at.pop(part_id, None)
            start_s = ms_to_s(int(start["time_ms"])) if start else None
            end_s = ms_to_s(int(event["time_ms"]))
            rows.append(
                {
                    "place_id": event.get("place_id"),
                    "part_id": part_id,
                    "start_s": start_s,
                    "end_s": end_s,
                    "duration_s": None if start_s is None else end_s - start_s,
                    "kind": "counting"
                    if event.get("event_type") in ACTIVITY_COUNT_END
                    else "service",
                }
            )
    return rows


def _endpoint_times(events: list[dict]) -> dict[str, float | None]:
    out = {field: None for field in ENDPOINT_EVENTS.values()}
    for event in events:
        field = ENDPOINT_EVENTS.get(event.get("event_type") or "")
        if field and out[field] is None:
            out[field] = ms_to_s(int(event["time_ms"]))
    return out


def _vehicle_totals(engine: Any) -> dict:
    intervals = list(getattr(engine, "vehicle_intervals", None) or [])
    busy_s = 0.0
    held_s = 0.0
    idle_s = 0.0
    alight_wait_s = 0.0
    by_id: dict[str, dict] = {}
    for row in intervals:
        duration_s = ms_to_s(max(0, int(row["end_ms"]) - int(row["start_ms"])))
        state = row["state"]
        if state == "busy":
            busy_s += duration_s
        elif state == "held":
            held_s += duration_s
            if row.get("reason") == "waiting_to_alight":
                alight_wait_s += duration_s
        else:
            idle_s += duration_s
        bucket = by_id.setdefault(
            row["resource_id"],
            {"resource_id": row["resource_id"], "busy_s": 0.0, "held_s": 0.0, "idle_s": 0.0},
        )
        bucket[f"{state}_s"] = bucket.get(f"{state}_s", 0.0) + duration_s
    if not intervals:
        for resource in getattr(engine, "resources", {}).values():
            by_id[resource.resource_id] = {
                "resource_id": resource.resource_id,
                "busy_s": 0.0,
                "held_s": 0.0,
                "idle_s": ms_to_s(int(engine.now)),
                "busy": resource.busy,
                "available": resource.available,
            }
            idle_s += ms_to_s(int(engine.now))
    return {
        "busy_s": busy_s,
        "held_s": held_s,
        "idle_s": idle_s,
        "waiting_to_alight_s": alight_wait_s,
        "by_vehicle": [by_id[key] for key in sorted(by_id)],
    }


def _coordination(engine: Any, trace: list[dict]) -> dict:
    decisions = list(engine.space_policy.decisions)
    reports = list(getattr(engine, "reports", None) or [])
    action_reports = [
        row
        for row in reports
        if row.get("requires_action") or row.get("kind") in {"count_disagreement"}
    ]
    disagreements = [event for event in trace if event.get("event_type") == "count_disagreement"]
    handovers = [event for event in trace if event.get("event_type") == "handover"]
    regroup = [
        event
        for event in trace
        if event.get("event_type") == "hold_end" and event.get("primary_cause") == "group_assembled"
    ]
    active_stations = sorted(
        {
            event.get("place_id")
            for event in trace
            if event.get("event_type") in {"service_start", "count_start", "batch_start"}
            and event.get("place_id")
        }
    )
    rules = set()
    policy = engine.policy
    if policy.get("destination_space_rule"):
        rules.add(f"destination_space_rule:{policy['destination_space_rule']}")
    grouping = policy.get("grouping") or {}
    if grouping.get("basis"):
        rules.add(f"grouping:{grouping['basis']}")
    if grouping.get("mode"):
        rules.add(f"grouping_mode:{grouping['mode']}")
    release = policy.get("release_rule") or {}
    if isinstance(release, Mapping) and release.get("type"):
        rules.add(f"release:{release['type']}")
    for event in trace:
        if event.get("event_type") in COUNT_ACTION_EVENTS and event.get("method"):
            rules.add(f"count_method:{event['method']}")
    return {
        "policy_decisions": len(decisions),
        "reports_requiring_action": len(action_reports) + len(disagreements),
        "handovers": len(handovers),
        "physical_regrouping_actions": len(regroup),
        "active_stations": active_stations,
        "active_station_count": len(active_stations),
        "distinct_operating_rules": len(rules),
        "distinct_operating_rule_ids": sorted(rules),
    }


def _operating_limit_measures(engine: Any) -> dict:
    intervals = list(getattr(engine, "over_limit_intervals", None) or [])
    duration_s = 0.0
    max_excess = 0
    max_size = 0
    by_place: dict[str, dict] = {}
    for row in intervals:
        dur = ms_to_s(max(0, int(row["end_ms"]) - int(row["start_ms"])))
        duration_s += dur
        excess = int(row.get("max_excess_students") or 0)
        size = int(row.get("max_occupancy_students") or 0)
        max_excess = max(max_excess, excess)
        max_size = max(max_size, size)
        bucket = by_place.setdefault(
            row["place_id"],
            {
                "place_id": row["place_id"],
                "duration_s": 0.0,
                "max_excess_students": 0,
                "max_occupancy_students": 0,
            },
        )
        bucket["duration_s"] += dur
        bucket["max_excess_students"] = max(bucket["max_excess_students"], excess)
        bucket["max_occupancy_students"] = max(bucket["max_occupancy_students"], size)
    return {
        "duration_s": duration_s,
        "max_excess_students": max_excess,
        "max_occupancy_students": max_size,
        "by_place": [by_place[key] for key in sorted(by_place)],
    }


def _denied_entry_students(trace: list[dict]) -> int:
    total = 0
    seen = set()
    for event in trace:
        if event.get("event_type") != "denied_entry":
            continue
        part_id = event.get("affected_part_id")
        if part_id and part_id in seen:
            continue
        if part_id:
            seen.add(part_id)
        total += int(event.get("student_count") or 0)
    return total
