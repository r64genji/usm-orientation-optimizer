from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from operator_dashboard.contracts import (
    GUIDE_TEXT,
    HALL_SEAT_CHOICES,
    LOCKED_FLEET,
    dto_base,
    labeled_fact,
)
from operator_dashboard.geometry import (
    HOSTEL_COLORS,
    LEG_WAYPOINTS,
    _load_place_catalog,
    _load_real_routes,
    project_map,
)
from usm_sim.campus import HOSTEL_REGISTRY
from usm_sim.timeutil import ms_to_s, parse_start

TZ = ZoneInfo("Asia/Kuala_Lumpur")


def _num(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _result(envelope: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {}
    result = envelope.get("result")
    return result if isinstance(result, dict) else {}


def _measures(result: dict[str, Any]) -> dict[str, Any]:
    measures = result.get("measures")
    return measures if isinstance(measures, dict) else {}


def clock_context(scenario: dict[str, Any] | None) -> dict[str, Any]:
    scenario = scenario or {}
    event_date = scenario.get("event_date")
    start_time = scenario.get("start_time_local")
    tz_name = scenario.get("timezone") or "Asia/Kuala_Lumpur"
    if not event_date or not start_time:
        return {
            "has_origin": False,
            "after_09_available": False,
            "deadline_matches_09": False,
            "synthetic": True,
            "start_dt": None,
            "nine_am_s": None,
        }
    try:
        start_dt = parse_start(str(event_date), str(start_time), str(tz_name))
    except Exception:
        return {
            "has_origin": False,
            "after_09_available": False,
            "deadline_matches_09": False,
            "synthetic": True,
            "start_dt": None,
            "nine_am_s": None,
        }
    synthetic = str(start_time) == "00:00:00"
    nine = start_dt.replace(hour=9, minute=0, second=0, microsecond=0)
    nine_s = (nine - start_dt).total_seconds() if nine > start_dt else None
    deadline = scenario.get("deadline_s")
    deadline_matches = (
        nine_s is not None
        and deadline is not None
        and abs(float(deadline) - float(nine_s)) < 0.51
    )
    after_09 = (not synthetic) and nine_s is not None
    return {
        "has_origin": True,
        "after_09_available": after_09,
        "deadline_matches_09": bool(deadline_matches),
        "synthetic": synthetic,
        "start_dt": start_dt,
        "nine_am_s": nine_s,
        "deadline_s": _num(deadline),
        "timezone": tz_name,
    }


def format_clock(ctx: dict[str, Any], time_s: float | int | None) -> str | None:
    if time_s is None:
        return None
    if ctx.get("has_origin") and ctx.get("start_dt") is not None:
        stamp = ctx["start_dt"] + timedelta(seconds=float(time_s))
        return stamp.isoformat(timespec="seconds")
    return f"{float(time_s):.3f}s"


def conservation(measures: dict[str, Any]) -> dict[str, Any]:
    completed = _num(measures.get("completed_students"))
    withdrawn = _num(measures.get("withdrawn_students"))
    unfinished = _num(measures.get("unfinished_students"))
    accounted = _num(measures.get("accounted_students"))
    attending = _num(measures.get("attending_students"))
    no_show = _num(measures.get("non_attendance_students"))
    if completed is None or withdrawn is None or unfinished is None:
        return {
            "ok": None,
            "completed_students": completed,
            "withdrawn_students": withdrawn,
            "unfinished_students": unfinished,
            "accounted_students": accounted,
            "attending_students": attending,
            "no_show_students": no_show,
            "error": "Counts are missing from this result.",
        }
    summed = int(completed) + int(withdrawn) + int(unfinished)
    accounted_i = int(accounted) if accounted is not None else summed
    attending_i = int(attending) if attending is not None else None
    ok = summed == accounted_i
    if attending_i is not None:
        ok = ok and accounted_i == attending_i
    error = None
    if not ok:
        error = (
            f"Count mismatch: completed {int(completed)} + withdrawn {int(withdrawn)} "
            f"+ unfinished {int(unfinished)} = {summed}, accounted {accounted_i}"
            + (f", attending {attending_i}" if attending_i is not None else "")
        )
    return {
        "ok": ok,
        "completed_students": int(completed),
        "withdrawn_students": int(withdrawn),
        "unfinished_students": int(unfinished),
        "accounted_students": accounted_i,
        "attending_students": attending_i,
        "no_show_students": int(no_show) if no_show is not None else None,
        "error": error,
    }


def _assumption_kind(item: Any) -> str:
    if isinstance(item, dict):
        category = str(item.get("category") or item.get("status") or "").lower()
        if category in {"measured", "recorded"}:
            return "Measured"
        if category in {"unknown"}:
            return "Unknown"
        return "Assumed"
    return "Assumed"


def _assumption_text(item: Any) -> str:
    if isinstance(item, dict):
        note = item.get("note") or item.get("id") or json.dumps(item, sort_keys=True)
        return str(note)
    return str(item)


def hall_clock(result: dict[str, Any], scenario: dict[str, Any] | None, output_mode: str) -> dict[str, Any]:
    ctx = clock_context(scenario)
    trace = result.get("event_trace")
    arrivals: list[float] = []
    seated: list[float] = []
    arrival_students = 0
    seated_students = 0
    after_09 = 0
    if isinstance(trace, list):
        for event in trace:
            if not isinstance(event, dict):
                continue
            kind = event.get("event_type")
            time_s = ms_to_s(int(event["time_ms"])) if event.get("time_ms") is not None else None
            if time_s is None:
                continue
            count = int(event.get("student_count") or 0)
            if kind == "hall_area_arrival":
                arrivals.append(time_s)
                arrival_students += count
                if ctx.get("after_09_available") and ctx.get("nine_am_s") is not None:
                    if time_s > float(ctx["nine_am_s"]):
                        after_09 += count
            if kind == "seated_completion":
                seated.append(time_s)
                seated_students += count
    else:
        outcomes = result.get("outcomes") if isinstance(result.get("outcomes"), dict) else {}
        units = outcomes.get("per_source_unit") or []
        for row in units:
            if not isinstance(row, dict):
                continue
            if row.get("hall_area_arrival_s") is not None:
                arrivals.append(float(row["hall_area_arrival_s"]))
            if row.get("seated_completion_s") is not None:
                seated.append(float(row["seated_completion_s"]))
    attending = _num((_measures(result).get("attending_students")))
    no_arrival = None
    if attending is not None and arrivals:
        no_arrival = max(0, int(attending) - arrival_students) if isinstance(trace, list) else None
    elif attending is not None and not arrivals:
        no_arrival = int(attending) if isinstance(trace, list) else None
    missing = None
    if not isinstance(trace, list):
        missing = "Hall arrival counts after 09:00 need a full-detail run."
    if not ctx.get("after_09_available"):
        after_09_value = None
        after_09_note = "This case has no 09:00 campus clock comparison."
    else:
        after_09_value = after_09 if isinstance(trace, list) else None
        after_09_note = None
    engine_late = _num(_measures(result).get("late_students"))
    late_label = "Engine late count uses this case's deadline."
    if ctx.get("deadline_matches_09"):
        late_label = "Engine late count uses the 09:00 deadline."
    return {
        "first_hall_arrival_s": min(arrivals) if arrivals else None,
        "last_hall_arrival_s": max(arrivals) if arrivals else None,
        "first_hall_arrival_clock": format_clock(ctx, min(arrivals) if arrivals else None),
        "last_hall_arrival_clock": format_clock(ctx, max(arrivals) if arrivals else None),
        "first_seated_s": min(seated) if seated else None,
        "last_seated_s": max(seated) if seated else None,
        "first_seated_clock": format_clock(ctx, min(seated) if seated else None),
        "last_seated_clock": format_clock(ctx, max(seated) if seated else None),
        "count_after_09": after_09_value,
        "count_after_09_note": after_09_note,
        "count_no_recorded_arrival": no_arrival,
        "engine_late_students": engine_late,
        "engine_late_note": late_label,
        "after_09_available": ctx.get("after_09_available"),
        "deadline_matches_09": ctx.get("deadline_matches_09"),
        "missing": missing,
    }

def extract_venue_allocation(result: dict[str, Any], scenario: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not isinstance(result, dict) or not result:
        return None
    va = result.get("venue_allocation")
    if isinstance(va, dict) and "dtsp_seated" in va and "g03_seated" in va:
        dtsp = int(va.get("dtsp_seated", 0))
        g03 = int(va.get("g03_seated", 0))
        total = int(va.get("total_seated", dtsp + g03))
        cov = va.get("cohort_coverage_pct")
        if cov is None:
            cov = round(100.0 * total / (dtsp + g03), 2) if (dtsp + g03) > 0 else 0.0
        return {
            "dtsp_seated": dtsp,
            "g03_seated": g03,
            "total_seated": total,
            "cohort_coverage_pct": float(cov),
        }

    trace = result.get("event_trace")
    if isinstance(trace, list) and len(trace) > 0:
        dtsp_seated = sum(
            int(e.get("student_count", 1))
            for e in trace
            if e.get("event_type") == "seated_completion" and e.get("place_id") == "dtsp_seating"
        )
        g03_seated = sum(
            int(e.get("student_count", 1))
            for e in trace
            if e.get("event_type") == "seated_completion" and e.get("place_id") == "g03_seating"
        )
        total_seated = dtsp_seated + g03_seated
        attending = _measures(result).get("attending_students")
        if attending is None:
            attending = total_seated
        cohort_pct = round(100.0 * total_seated / float(attending), 2) if attending else (100.0 if total_seated > 0 else 0.0)
        return {
            "dtsp_seated": dtsp_seated,
            "g03_seated": g03_seated,
            "total_seated": total_seated,
            "cohort_coverage_pct": cohort_pct,
        }

    completed = _num(_measures(result).get("completed_students"))
    if completed is not None:
        total = int(completed)
        is_full_cohort = (total >= 3500)
        dtsp_seated = min(total, 2999) if is_full_cohort else total
        g03_seated = max(0, total - dtsp_seated) if is_full_cohort else 0
        attending = _num(_measures(result).get("attending_students")) or total
        cohort_pct = round(100.0 * total / float(attending), 2) if attending else (100.0 if total > 0 else 0.0)
        return {
            "dtsp_seated": dtsp_seated,
            "g03_seated": g03_seated,
            "total_seated": total,
            "cohort_coverage_pct": cohort_pct,
        }
    return None


def project_overview(
    run_id: str | None,
    envelope: dict[str, Any] | None,
    *,
    case: str | None,
    seed: int | None,
    output_mode: str,
    scenario: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _result(envelope)
    measures = _measures(result)
    outcomes = result.get("outcomes") if isinstance(result.get("outcomes"), dict) else {}
    cons = conservation(measures)
    assumptions = []
    for item in result.get("visible_assumptions") or []:
        assumptions.append(
            labeled_fact(_assumption_kind(item), _assumption_text(item), source="visible_assumptions")
        )
    reporting = result.get("reporting_assumptions")
    if reporting:
        assumptions.append(
            labeled_fact("Assumed", "Reporting times follow the case reporting assumptions.", source="reporting_assumptions")
        )
    for check in result.get("accuracy_checks") or []:
        if isinstance(check, dict):
            assumptions.append(
                labeled_fact(
                    "Measured" if check.get("status") in {"pass", "matched"} else "Assumed",
                    str(check.get("id") or check.get("note") or "accuracy check"),
                    source="accuracy_checks",
                )
            )
    assumptions.append(
        labeled_fact("Assumed", GUIDE_TEXT["fleet"], source="locked_fleet")
    )
    assumptions.append(
        labeled_fact("Assumed", GUIDE_TEXT["restu"], source="restu_last")
    )
    hall_choice = None
    if request and request.get("hall_seats") in HALL_SEAT_CHOICES:
        choice = HALL_SEAT_CHOICES[int(request["hall_seats"])]
        hall_choice = {
            "seats": int(request["hall_seats"]),
            "label": choice["label"],
            "title": choice["title"],
            "note": choice["note"],
        }
        assumptions.append(labeled_fact("Assumed", choice["note"], source="hall_seats"))
    payload = dto_base(
        run_id,
        units={"wait": "s", "count": "students"},
        source_fields=["status", "termination_cause", "measures", "outcomes.campus", "outcomes.per_hostel", "venue_allocation"],
        missing=None if result else "No result yet.",
    )
    payload.update(
        {
            "case": case,
            "seed": seed,
            "output_mode": output_mode,
            "engine_status": result.get("status"),
            "termination_cause": result.get("termination_cause"),
            "completed_students": cons["completed_students"],
            "unfinished_students": cons["unfinished_students"],
            "withdrawn_students": cons["withdrawn_students"],
            "accounted_students": cons["accounted_students"],
            "attending_students": cons["attending_students"],
            "no_show_students": cons["no_show_students"],
            "measures": {
                "completed": cons["completed_students"],
                "withdrawn": cons["withdrawn_students"],
                "unfinished": cons["unfinished_students"],
                "accounted": cons["accounted_students"],
            },
            "conservation_ok": cons["ok"],
            "conservation_error": cons["error"],
            "mean_wait_s": _num(measures.get("mean_wait_s")),
            "p95_wait_s": _num(measures.get("p95_wait_s")),
            "wait_denominator_students": _num(measures.get("wait_denominator_students")),
            "worst_hostel_id": measures.get("worst_hostel_id"),
            "worst_hostel_mean_wait_s": _num(measures.get("max_hostel_mean_wait_s")),
            "campus": outcomes.get("campus"),
            "per_hostel": _strip_student_ids(outcomes.get("per_hostel") or []),
            "hall_clock": hall_clock(result, scenario, output_mode),
            "assumptions": assumptions,
            "accuracy_checks": result.get("accuracy_checks") or [],
            "fleet": LOCKED_FLEET,
            "hall_seats": hall_choice,
            "guide": GUIDE_TEXT,
            "holdout": bool((request or {}).get("holdout")),
            "venue_allocation": extract_venue_allocation(result, scenario),
        }
    )
    return payload


def _strip_student_ids(rows: Any) -> list[dict[str, Any]]:
    cleaned = []
    if not isinstance(rows, list):
        return cleaned
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = {
            key: value
            for key, value in row.items()
            if key not in {"student_key", "student_keys", "members"}
        }
        cleaned.append(item)
    return cleaned


def _stage_clocks_from_events(
    events: list[dict[str, Any]], scenario: dict[str, Any], ctx: dict[str, Any]
) -> dict[str, Any]:
    leave_origin = None
    board = None
    ride = None
    outside_hold = None
    hall_arrival = None
    seated = None
    origin_ids = {
        str(place.get("id"))
        for place in scenario.get("places") or []
        if isinstance(place, dict) and "origin" in str(place.get("id") or "")
    }
    origin_ids.update(
        {
            str(unit.get("origin_place_id") or "")
            for unit in scenario.get("source_units") or []
            if isinstance(unit, dict)
        }
    )
    origin_ids.discard("")
    if not origin_ids:
        origin_ids.add("origin")
    legs_by_id = {
        str(leg.get("id")): leg
        for leg in scenario.get("route_legs") or []
        if isinstance(leg, dict) and leg.get("id")
    }
    for event in events:
        kind = event.get("event_type")
        time_s = ms_to_s(int(event["time_ms"])) if event.get("time_ms") is not None else None
        if time_s is None:
            continue
        place = str(event.get("place_id") or "")
        leg = legs_by_id.get(str(event.get("leg_id") or ""))
        mode = (leg or {}).get("mode")
        if kind == "departure" and leave_origin is None and (place in origin_ids or not origin_ids):
            leave_origin = time_s
        if kind in {"batch_start", "service_start"} and "board" in place:
            board = time_s if board is None else board
        if kind == "departure" and mode in {"coach", "bus", "electric"}:
            board = time_s if board is None else board
            ride = time_s if ride is None else ride
        if kind == "hold_start" and ("exterior" in place or "gathering" in place or "wait" in place):
            outside_hold = time_s if outside_hold is None else outside_hold
        if kind == "hall_area_arrival":
            hall_arrival = time_s if hall_arrival is None else hall_arrival
        if kind == "seated_completion":
            seated = time_s if seated is None else seated
    return {
        "leave_origin_s": leave_origin,
        "board_s": board,
        "ride_s": ride,
        "outside_hold_s": outside_hold,
        "hall_arrival_s": hall_arrival,
        "seated_s": seated,
        "leave_origin_clock": format_clock(ctx, leave_origin),
        "board_clock": format_clock(ctx, board),
        "ride_clock": format_clock(ctx, ride),
        "outside_hold_clock": format_clock(ctx, outside_hold),
        "hall_arrival_clock": format_clock(ctx, hall_arrival),
        "seated_clock": format_clock(ctx, seated),
    }


def _event_status(times: dict[str, Any], key: str, reached_later: bool) -> str:
    if times.get(key) is not None:
        return "recorded"
    if reached_later:
        return "not_recorded"
    return "not_reached"


def project_legs(
    run_id: str | None,
    envelope: dict[str, Any] | None,
    scenario: dict[str, Any] | None,
    *,
    output_mode: str,
) -> dict[str, Any]:
    result = _result(envelope)
    scenario = scenario or {}
    ctx = clock_context(scenario)
    trace = result.get("event_trace")
    detailed = isinstance(trace, list)
    outcomes = result.get("outcomes") if isinstance(result.get("outcomes"), dict) else {}
    hostels: dict[str, dict[str, Any]] = {}
    for row in outcomes.get("per_hostel") or []:
        if not isinstance(row, dict):
            continue
        hid = str(row.get("hostel_id") or "unknown")
        hostels[hid] = {
            "hostel_id": hid,
            "completed_students": row.get("completed_students"),
            "unfinished_students": row.get("unfinished_students"),
            "mean_wait_s": row.get("mean_wait_s"),
            "groups": [],
            "first": {},
            "last": {},
            "status": "used",
        }
    groups = []
    for row in _strip_student_ids(outcomes.get("per_group") or outcomes.get("groups") or []):
        hid_list = row.get("hostel_ids") or []
        hostel_id = hid_list[0] if hid_list else "unknown"
        clocks = {
            "leave_origin_s": row.get("release_s"),
            "hall_arrival_s": row.get("hall_area_arrival_s"),
            "seated_s": row.get("seated_completion_s"),
        }
        if detailed:
            part_ids = set(row.get("part_ids") or [])
            events = [
                event
                for event in trace
                if isinstance(event, dict)
                and (
                    event.get("affected_group_id") == row.get("group_id")
                    or event.get("affected_part_id") in part_ids
                    or (not part_ids and event.get("affected_group_id") == row.get("group_id"))
                )
            ]
            clocks = _stage_clocks_from_events(events, scenario, ctx)
        else:
            clocks = {
                "leave_origin_s": row.get("release_s"),
                "board_s": None,
                "ride_s": None,
                "outside_hold_s": None,
                "hall_arrival_s": row.get("hall_area_arrival_s"),
                "seated_s": row.get("seated_completion_s"),
                "leave_origin_clock": format_clock(ctx, row.get("release_s")),
                "board_clock": None,
                "ride_clock": None,
                "outside_hold_clock": None,
                "hall_arrival_clock": format_clock(ctx, row.get("hall_area_arrival_s")),
                "seated_clock": format_clock(ctx, row.get("seated_completion_s")),
            }
        split = bool(row.get("parent_group_id") and row.get("parent_group_id") != row.get("group_id"))
        group = {
            "group_id": row.get("group_id"),
            "parent_group_id": row.get("parent_group_id"),
            "hostel_ids": hid_list,
            "completed_students": row.get("completed_students"),
            "unfinished_students": row.get("unfinished_students"),
            "status": row.get("status"),
            "split": split,
            "clocks": clocks,
            "stage_arrivals": row.get("stage_arrivals") or [],
        }
        groups.append(group)
        bucket = hostels.setdefault(
            hostel_id,
            {
                "hostel_id": hostel_id,
                "completed_students": None,
                "unfinished_students": None,
                "mean_wait_s": None,
                "groups": [],
                "first": {},
                "last": {},
                "status": "used",
            },
        )
        bucket["groups"].append(group)
        for key in ("leave_origin_s", "board_s", "ride_s", "outside_hold_s", "hall_arrival_s", "seated_s"):
            value = clocks.get(key)
            if value is None:
                continue
            prev_first = bucket["first"].get(key)
            prev_last = bucket["last"].get(key)
            bucket["first"][key] = value if prev_first is None else min(prev_first, value)
            bucket["last"][key] = value if prev_last is None else max(prev_last, value)
    planned_hostels = set((scenario.get("routes") or {}).keys()) if scenario.get("routes") else set()
    for hid in planned_hostels:
        if hid not in hostels:
            hostels[hid] = {
                "hostel_id": hid,
                "status": "not_used",
                "groups": [],
                "first": {},
                "last": {},
            }
    missing = None if detailed else "Detailed legs are unavailable on a summary run. Run again with full detail."
    payload = dto_base(
        run_id,
        units={"time": "s"},
        source_fields=["event_trace", "outcomes.per_group", "route_stages"],
        missing=missing,
    )
    payload.update(
        {
            "detailed_legs_available": detailed,
            "output_mode": output_mode,
            "hostels": sorted(hostels.values(), key=lambda row: str(row.get("hostel_id"))),
            "groups": groups,
            "route_stages": scenario.get("route_stages") or [],
        }
    )
    return payload


def _occupancy_peaks(result: dict[str, Any]) -> list[dict[str, Any]]:
    history = result.get("occupancy_history")
    peaks: dict[str, dict[str, Any]] = {}
    if isinstance(history, list) and history:
        running: dict[str, int] = {}
        for row in history:
            if not isinstance(row, dict):
                continue
            place_id = str(row.get("place_id") or "")
            if not place_id:
                continue
            if row.get("direction") == "in":
                running[place_id] = running.get(place_id, 0) + int(row.get("student_count") or 0)
            elif row.get("direction") == "out":
                running[place_id] = running.get(place_id, 0) - int(row.get("student_count") or 0)
            after = row.get("occupancy_after")
            value = int(after) if after is not None else running.get(place_id, 0)
            sampled = str(row.get("kind") or "") == "sampled"
            current = peaks.get(place_id)
            if current is None or value > int(current["peak_students"]):
                peaks[place_id] = {
                    "place_id": place_id,
                    "peak_students": value,
                    "sampled": sampled,
                    "source": "occupancy_history",
                    "label": "sampled peak" if sampled else "recorded peak",
                }
        return sorted(peaks.values(), key=lambda row: str(row["place_id"]))
    snapshot = result.get("place_occupancy")
    rows = []
    if isinstance(snapshot, list):
        for row in snapshot:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "place_id": row.get("place_id"),
                    "peak_students": None,
                    "end_occupancy_students": row.get("occupancy_students"),
                    "sampled": False,
                    "source": "place_occupancy",
                    "label": "end-of-run occupancy, peak not recorded",
                }
            )
    return rows


def project_bottlenecks(
    run_id: str | None,
    envelope: dict[str, Any] | None,
    *,
    output_mode: str,
) -> dict[str, Any]:
    result = _result(envelope)
    leftovers = []
    for row in result.get("unfinished_demand") or []:
        if not isinstance(row, dict):
            continue
        leftovers.append(
            {
                "place_id": row.get("place_id"),
                "cause": row.get("cause") or row.get("status"),
                "student_count": row.get("student_count"),
                "part_id": row.get("part_id"),
                "group_id": row.get("group_id"),
                "status": row.get("status"),
                "stage_id": row.get("stage_id"),
            }
        )
    delays = []
    for row in result.get("delay_explanations") or []:
        if not isinstance(row, dict):
            continue
        delays.append(
            {
                "place_id": row.get("place_id"),
                "cause": row.get("cause") or row.get("primary_cause"),
                "duration_s": row.get("duration_s"),
                "affected_count": row.get("affected_count"),
                "part_id": row.get("part_id"),
                "resource_id": row.get("resource_id"),
            }
        )
    payload = dto_base(
        run_id,
        units={"time": "s", "count": "students"},
        source_fields=[
            "delay_explanations",
            "unfinished_demand",
            "queue_summaries",
            "resource_summaries",
            "active_holds",
            "destination",
            "worker_summaries",
            "place_occupancy",
            "occupancy_history",
        ],
        missing=None if result else "No result yet.",
    )
    payload.update(
        {
            "delays": delays,
            "unfinished": leftovers,
            "queue_summaries": result.get("queue_summaries") or [],
            "resource_summaries": result.get("resource_summaries") or [],
            "active_holds": result.get("active_holds") or [],
            "destination": result.get("destination"),
            "worker_summaries": result.get("worker_summaries") or [],
            "place_occupancy": result.get("place_occupancy") or [],
            "occupancy_peaks": _occupancy_peaks(result),
            "output_mode": output_mode,
        }
    )
    return payload


def project_optimizer(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        payload = dto_base(
            None,
            units={},
            source_fields=["optimizer_dir"],
            missing="No saved result",
        )
        payload.update(
            {
                "status": "empty",
                "message": "No saved result",
                "explain": GUIDE_TEXT["optimizer"],
                "records": [],
            }
        )
        return payload
    latest = records[0]
    payload = dto_base(
        None,
        units={},
        source_fields=["optimizer_dir"],
        missing=None,
    )
    payload.update(
        {
            "status": latest.get("status"),
            "timestamp": latest.get("timestamp"),
            "cases": latest.get("cases"),
            "assumptions": latest.get("assumptions"),
            "measures": latest.get("measures"),
            "explain": GUIDE_TEXT["optimizer"],
            "records": records[:8],
        }
    )
    return payload


def read_optimizer_records(folder: Path | None) -> list[dict[str, Any]]:
    if folder is None or not Path(folder).exists():
        return []
    rows = []
    for path in sorted(Path(folder).glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        body = data.get("result") if isinstance(data, dict) and isinstance(data.get("result"), dict) else data
        if not isinstance(body, dict):
            continue
        if not any(key in body for key in ("pareto_set", "measures", "status", "feasible_plan_found", "accepted")):
            continue
        rows.append(
            {
                "file": path.name,
                "timestamp": datetime.fromtimestamp(path.stat().st_mtime, tz=TZ).isoformat(timespec="seconds"),
                "status": body.get("status"),
                "cases": body.get("cases") or body.get("case"),
                "assumptions": body.get("visible_assumptions") or body.get("assumptions"),
                "measures": body.get("measures") or (body.get("best_plan") or {}).get("measures"),
            }
        )
    return rows


def project_map_for_run(
    run_id: str | None,
    envelope: dict[str, Any] | None,
    scenario: dict[str, Any] | None,
    *,
    output_mode: str,
    overlay_geojson: dict[str, Any] | None,
) -> dict[str, Any]:
    return project_map(
        run_id,
        _result(envelope),
        scenario,
        output_mode=output_mode,
        overlay_geojson=overlay_geojson,
    )


REPLAY_SECTORS: list[dict[str, Any]] = [
    {
        "id": "restu_origin",
        "name": "Restu Cafe / Rain Shelter Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("restu", "#8B5CF6"),
        "coordinates": [5.356461, 100.289265],
        "hostel_id": "restu",
    },
    {
        "id": "rst_rain_shelter",
        "name": "Restu Cafe Grounds (Rain Shelter)",
        "role": "shelter",
        "color": "#8B5CF6",
        "coordinates": [5.356461, 100.289265],
        "hostel_id": "restu",
    },
    {
        "id": "saujana_origin",
        "name": "Saujana Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("saujana", "#0EA5E9"),
        "coordinates": [5.35640, 100.29050],
        "hostel_id": "saujana",
    },
    {
        "id": "tekun_origin",
        "name": "Tekun Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("tekun", "#F59E0B"),
        "coordinates": [5.35563, 100.29129],
        "hostel_id": "tekun",
    },
    {
        "id": "indah_kembara_origin",
        "name": "Indah Kembara Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("indah_kembara", "#10B981"),
        "coordinates": [5.35603, 100.29604],
        "hostel_id": "indah_kembara",
    },
    {
        "id": "aman_damai_origin",
        "name": "Aman Damai Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("aman_damai", "#EF4444"),
        "coordinates": [5.35431, 100.29615],
        "hostel_id": "aman_damai",
    },
    {
        "id": "bakti_fajar_permai_origin",
        "name": "Bakti Fajar Permai Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("bakti_fajar_permai", "#06B6D4"),
        "coordinates": [5.35776, 100.30055],
        "hostel_id": "bakti_fajar_permai",
    },
    {
        "id": "cahaya_gemilang_origin",
        "name": "Cahaya Gemilang Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("cahaya_gemilang", "#D97706"),
        "coordinates": [5.36046, 100.30360],
        "hostel_id": "cahaya_gemilang",
    },
    {
        "id": "fajar_harapan_origin",
        "name": "Fajar Harapan Origin",
        "role": "origin",
        "color": HOSTEL_COLORS.get("fajar_harapan", "#EC4899"),
        "coordinates": [5.35500, 100.29977],
        "hostel_id": "fajar_harapan",
    },
    {
        "id": "rst_overpass",
        "name": "Overpass / Jejantas",
        "role": "overpass",
        "color": "#8B5CF6",
        "coordinates": [5.356712, 100.291946],
        "hostel_id": None,
    },
    {
        "id": "rst_bus_wait",
        "name": "Persiaran Sains Bus Queue",
        "role": "queue",
        "color": "#2563EB",
        "coordinates": [5.356036, 100.293640],
        "hostel_id": None,
    },
    {
        "id": "rst_boarding_approach",
        "name": "RST Boarding Berth",
        "role": "boarding_berth",
        "color": "#1D4ED8",
        "coordinates": [5.356012, 100.293748],
        "hostel_id": None,
    },
    {
        "id": "bus_transit_corridor",
        "name": "Bus Transit Corridor",
        "role": "transit_corridor",
        "color": "#1D4ED8",
        "coordinates": [5.356850, 100.296900],
        "hostel_id": None,
    },
    {
        "id": "dtsp_alighting_area",
        "name": "DTSP Drop-off / Alighting",
        "role": "alighting",
        "color": "#4F46E5",
        "coordinates": [5.357215, 100.301437],
        "hostel_id": None,
    },
    {
        "id": "dtsp_exterior_gathering",
        "name": "3-Tier Car Park Waiting Area",
        "role": "road_reservoir",
        "color": "#DC2626",
        "coordinates": [5.357153, 100.301749],
        "hostel_id": None,
    },
    {
        "id": "dtsp_north_plaza",
        "name": "Dataran Merah (Shaded Pavilion)",
        "role": "holding_plaza",
        "color": "#D97706",
        "coordinates": [5.356518, 100.303214],
        "hostel_id": None,
    },
    {
        "id": "dtsp_south_plaza",
        "name": "Grass Field (in front of G28 Siswaniaga)",
        "role": "holding_plaza",
        "color": "#059669",
        "coordinates": [5.356118, 100.302400],
        "hostel_id": None,
    },
    {
        "id": "dtsp_door_a",
        "name": "DTSP Door A (North / Bus)",
        "role": "door",
        "color": "#EA580C",
        "coordinates": [5.357000, 100.302800],
        "hostel_id": None,
    },
    {
        "id": "dtsp_door_b",
        "name": "DTSP Door B (South / Walk)",
        "role": "door",
        "color": "#EAB308",
        "coordinates": [5.356800, 100.303000],
        "hostel_id": None,
    },
    {
        "id": "dtsp_foyer",
        "name": "DTSP Foyer Lobby",
        "role": "foyer",
        "color": "#CA8A04",
        "coordinates": [5.356900, 100.303050],
        "hostel_id": None,
    },
    {
        "id": "dtsp_seating",
        "name": "DTSP Hall Seating",
        "role": "seats",
        "color": "#EAB308",
        "coordinates": [5.356920, 100.303080],
        "hostel_id": None,
    },
    {
        "id": "g03_foyer_entrance",
        "name": "Bangunan G03 Foyer Entrance",
        "role": "foyer",
        "color": "#06B6D4",
        "coordinates": [5.357119, 100.302499],
        "hostel_id": None,
    },
    {
        "id": "g03_seating",
        "name": "Bangunan G03 Overflow Seating (DK G/H)",
        "role": "seats",
        "color": "#3B82F6",
        "coordinates": [5.357119, 100.302499],
        "hostel_id": None,
    },
]

REPLAY_LEG_ENDPOINTS: dict[str, tuple[str, str]] = {
    "leg_approach_restu": ("restu_origin", "rst_bus_wait"),
    "leg_approach_saujana": ("saujana_origin", "rst_bus_wait"),
    "leg_approach_tekun": ("tekun_origin", "rst_bus_wait"),
    "leg_to_boarding": ("rst_bus_wait", "rst_boarding_approach"),
    "leg_transit": ("rst_boarding_approach", "dtsp_alighting_area"),
    "leg_transit_return": ("dtsp_alighting_area", "rst_boarding_approach"),
    "leg_transfer_walk": ("dtsp_alighting_area", "dtsp_exterior_gathering"),
    "leg_walk_indah_kembara": ("indah_kembara_origin", "dtsp_walk_approach"),
    "leg_walk_aman_damai": ("aman_damai_origin", "dtsp_walk_approach"),
    "leg_walk_bakti_fajar_permai": ("bakti_fajar_permai_origin", "dtsp_walk_approach"),
    "leg_walk_cahaya_gemilang": ("cahaya_gemilang_origin", "dtsp_walk_approach"),
    "leg_walk_fajar_harapan": ("fajar_harapan_origin", "dtsp_walk_approach"),
    "leg_walk_to_exterior": ("dtsp_walk_approach", "dtsp_exterior_gathering"),
    "leg_hall_approach": ("dtsp_exterior_gathering", "dtsp_hall_reference"),
    "leg_hall_to_door_a": ("dtsp_hall_reference", "dtsp_door_a"),
    "leg_hall_to_door_b": ("dtsp_hall_reference", "dtsp_door_b"),
    "leg_door_a_to_foyer": ("dtsp_door_a", "dtsp_foyer"),
    "leg_door_b_to_foyer": ("dtsp_door_b", "dtsp_foyer"),
    "leg_foyer_to_seating": ("dtsp_foyer", "dtsp_seating"),
    "leg_walk_to_north_plaza": ("dtsp_walk_approach", "dtsp_north_plaza"),
    "leg_walk_to_south_plaza": ("dtsp_walk_approach", "dtsp_south_plaza"),
    "leg_hall_approach_north": ("dtsp_north_plaza", "dtsp_hall_reference"),
    "leg_hall_approach_south": ("dtsp_south_plaza", "dtsp_hall_reference"),
    "leg_carpark_to_g03": ("dtsp_exterior_gathering", "g03_foyer_entrance"),
    "leg_g03_foyer_to_seating": ("g03_foyer_entrance", "g03_seating"),
}


def _extract_bus_trajectories(
    trace: list[dict[str, Any]],
    scenario: dict[str, Any] | None,
    max_time_ms: int,
    place_coords: dict[str, list[float]],
    routes: dict[str, list[list[float]]],
) -> list[dict[str, Any]]:
    scenario = scenario or {}
    scenario_fleets = scenario.get("fleets") or []
    scenario_vehicles = scenario.get("vehicles") or []
    scenario_types = {t.get("id"): t for t in (scenario.get("vehicle_types") or []) if isinstance(t, dict)}

    vids_meta: dict[str, dict[str, Any]] = {}
    for f in scenario_fleets:
        if isinstance(f, dict):
            for vid in f.get("vehicle_ids") or []:
                vid_str = str(vid)
                vtype = "coach" if "coach" in vid_str else ("electric" if "electric" in vid_str else "coach")
                cap = 80 if vtype == "coach" else 40
                seated = 40 if vtype == "coach" else 28
                vids_meta[vid_str] = {
                    "id": vid_str,
                    "vehicle_type": vtype,
                    "capacity": cap,
                    "seated_capacity": seated,
                    "usable_doors": 1,
                }
    for v in scenario_vehicles:
        if isinstance(v, dict) and "id" in v:
            vid_str = str(v["id"])
            vtype = v.get("type") or ("coach" if "coach" in vid_str else ("electric" if "electric" in vid_str else "coach"))
            t_info = scenario_types.get(vtype, {})
            cap = int(v.get("capacity_students") or t_info.get("capacity_students") or (80 if vtype == "coach" else 40))
            seated = int(t_info.get("seated_capacity_students") or (40 if vtype == "coach" else 28))
            vids_meta[vid_str] = {
                "id": vid_str,
                "vehicle_type": vtype,
                "capacity": cap,
                "seated_capacity": seated,
                "usable_doors": int(t_info.get("usable_doors") or 1),
            }

    trace_vids: set[str] = set()
    for e in trace:
        if not isinstance(e, dict):
            continue
        rids = e.get("resource_ids") or []
        if e.get("resource_id"):
            rids = list(rids) + [e.get("resource_id")]
        for r in rids:
            r_str = str(r)
            if r_str.startswith("coach_") or r_str.startswith("electric_"):
                trace_vids.add(r_str)

    for vid in sorted(trace_vids):
        if vid not in vids_meta:
            vtype = "coach" if "coach" in vid else "electric"
            vids_meta[vid] = {
                "id": vid,
                "vehicle_type": vtype,
                "capacity": 80 if vtype == "coach" else 40,
                "seated_capacity": 40 if vtype == "coach" else 28,
                "usable_doors": 1,
            }

    if not vids_meta:
        return []

    rst_boarding = place_coords.get("rst_boarding_approach", [5.356012, 100.293748])
    dtsp_alighting = place_coords.get("dtsp_alighting_area", [5.357215, 100.301437])
    transit_waypoints = routes.get("leg_transit") or [rst_boarding, dtsp_alighting]
    return_waypoints = routes.get("leg_transit_return") or list(reversed(transit_waypoints))

    events_by_veh: dict[str, list[dict[str, Any]]] = {vid: [] for vid in vids_meta}
    for e in trace:
        if not isinstance(e, dict):
            continue
        rids = e.get("resource_ids") or []
        if e.get("resource_id"):
            rids = list(rids) + [e.get("resource_id")]
        for vid in vids_meta:
            if vid in rids:
                events_by_veh[vid].append(e)

    bus_trajectories: list[dict[str, Any]] = []
    ordered_vids = sorted(vids_meta.keys(), key=lambda v: (0 if "coach" in v else 1, v))

    for vid in ordered_vids:
        meta = vids_meta[vid]
        evs = events_by_veh[vid]
        evs.sort(key=lambda x: (int(x.get("time_ms") or 0), 0 if x.get("event_type") == "arrival" else 1))

        segments: list[dict[str, Any]] = []
        curr_t = 0
        i = 0
        n = len(evs)

        while i < n:
            e = evs[i]
            et = e.get("event_type")
            pl = e.get("place_id")
            t = int(e.get("time_ms") or 0)

            if et == "batch_start" and pl == "rst_boarding_approach":
                if t > curr_t:
                    segments.append({
                        "start_ms": curr_t,
                        "end_ms": t,
                        "type": "idle",
                        "place_id": "rst_boarding_approach",
                        "waypoints": [rst_boarding],
                        "passenger_count": 0,
                    })
                    curr_t = t

                pax = int(e.get("student_count") or 0)
                j = i + 1
                dep_t = t
                while j < n:
                    ej = evs[j]
                    if ej.get("event_type") == "departure" and ej.get("leg_id") == "leg_transit":
                        dep_t = int(ej.get("time_ms") or t)
                        break
                    if ej.get("student_count"):
                        pax = max(pax, int(ej.get("student_count") or 0))
                    j += 1

                segments.append({
                    "start_ms": t,
                    "end_ms": dep_t,
                    "type": "boarding",
                    "place_id": "rst_boarding_approach",
                    "waypoints": [rst_boarding],
                    "passenger_count": pax,
                })
                curr_t = dep_t

                arr_t = dep_t
                k = j + 1
                while k < n:
                    ek = evs[k]
                    if ek.get("event_type") == "arrival" and ek.get("place_id") == "dtsp_alighting_area":
                        arr_t = int(ek.get("time_ms") or dep_t)
                        break
                    k += 1

                segments.append({
                    "start_ms": dep_t,
                    "end_ms": arr_t,
                    "type": "transit_loaded",
                    "leg_id": "leg_transit",
                    "place_id": "dtsp_alighting_area",
                    "waypoints": transit_waypoints,
                    "passenger_count": pax,
                })
                curr_t = arr_t

                rel_t = arr_t
                m = k + 1
                while m < n:
                    em = evs[m]
                    if em.get("event_type") == "resource_release" and em.get("place_id") == "dtsp_alighting_area":
                        rel_t = int(em.get("time_ms") or arr_t)
                        break
                    m += 1

                segments.append({
                    "start_ms": arr_t,
                    "end_ms": rel_t,
                    "type": "alighting",
                    "place_id": "dtsp_alighting_area",
                    "waypoints": [dtsp_alighting],
                    "passenger_count": pax,
                })
                curr_t = rel_t

                ret_t = rel_t
                p = m + 1
                while p < n:
                    ep = evs[p]
                    if ep.get("event_type") == "vehicle_return_complete":
                        ret_t = int(ep.get("time_ms") or rel_t)
                        break
                    p += 1

                if ret_t == rel_t and rel_t < max_time_ms:
                    ret_t = min(max_time_ms, rel_t + 210000)

                segments.append({
                    "start_ms": rel_t,
                    "end_ms": ret_t,
                    "type": "transit_empty_return",
                    "leg_id": "leg_transit_return",
                    "place_id": "rst_boarding_approach",
                    "waypoints": return_waypoints,
                    "passenger_count": 0,
                })
                curr_t = ret_t

                turn_t = ret_t
                q = p + 1
                while q < n:
                    eq = evs[q]
                    if eq.get("event_type") == "vehicle_turnaround_complete":
                        turn_t = int(eq.get("time_ms") or ret_t)
                        break
                    q += 1

                if turn_t == ret_t and ret_t < max_time_ms:
                    turn_t = min(max_time_ms, ret_t + 60000)

                segments.append({
                    "start_ms": ret_t,
                    "end_ms": turn_t,
                    "type": "turnaround",
                    "place_id": "rst_boarding_approach",
                    "waypoints": [rst_boarding],
                    "passenger_count": 0,
                })
                curr_t = turn_t
                i = q + 1
            else:
                i += 1

        if curr_t < max_time_ms:
            segments.append({
                "start_ms": curr_t,
                "end_ms": max_time_ms,
                "type": "idle",
                "place_id": "rst_boarding_approach",
                "waypoints": [rst_boarding],
                "passenger_count": 0,
            })

        clean_segs: list[dict[str, Any]] = []
        for s in segments:
            if s["start_ms"] == s["end_ms"]:
                continue
            if clean_segs and clean_segs[-1]["type"] == "idle" and s["type"] == "idle":
                clean_segs[-1]["end_ms"] = max(clean_segs[-1]["end_ms"], s["end_ms"])
            else:
                clean_segs.append(s)

        if not clean_segs:
            clean_segs.append({
                "start_ms": 0,
                "end_ms": max_time_ms,
                "type": "idle",
                "place_id": "rst_boarding_approach",
                "waypoints": [rst_boarding],
                "passenger_count": 0,
            })

        bus_trajectories.append({
            "id": vid,
            "vehicle_type": meta["vehicle_type"],
            "capacity": meta["capacity"],
            "seated_capacity": meta["seated_capacity"],
            "usable_doors": meta["usable_doors"],
            "segments": clean_segs,
        })

    return bus_trajectories

def project_replay(
    run_id: str | None,
    envelope: dict[str, Any] | None,
    scenario: dict[str, Any] | None,
    *,
    output_mode: str = "full",
) -> dict[str, Any]:
    result = _result(envelope)
    scenario = scenario or {}
    ctx = clock_context(scenario)
    clock_start = ctx["start_dt"].isoformat() if ctx.get("start_dt") else "2026-09-17T07:00:00+08:00"

    trace = result.get("event_trace")
    intervals = result.get("student_time_intervals") or []
    detailed = (output_mode != "compact") and isinstance(trace, list) and len(trace) > 0

    # Coordinate lookup
    hostel_coords = {h["origin_place_id"]: [h["latitude_deg"], h["longitude_deg"]] for h in HOSTEL_REGISTRY if "origin_place_id" in h}
    place_catalog = _load_place_catalog()
    place_coords = {p["id"]: [p["latitude_deg"], p["longitude_deg"]] for p in place_catalog if "id" in p}
    place_coords.update(hostel_coords)
    place_coords["restu_origin"] = [5.356461, 100.289265]
    place_coords["rst_rain_shelter"] = [5.356461, 100.289265]
    routes = dict(_load_real_routes())
    if "leg_hall_to_door_a" not in routes:
        routes["leg_hall_to_door_a"] = [
            place_coords.get("dtsp_hall_reference", [5.35695, 100.30311]),
            place_coords.get("dtsp_door_a", [5.35700, 100.30280]),
        ]
    if "leg_hall_to_door_b" not in routes:
        routes["leg_hall_to_door_b"] = [
            place_coords.get("dtsp_hall_reference", [5.35695, 100.30311]),
            place_coords.get("dtsp_door_b", [5.35680, 100.30300]),
        ]
    if "leg_transit_return" not in routes and "leg_transit" in routes:
        routes["leg_transit_return"] = list(reversed(routes["leg_transit"]))

    if not detailed:
        payload = dto_base(
            run_id,
            units={"time": "milliseconds", "coordinates": "degrees_lat_lon"},
            source_fields=["event_trace", "student_time_intervals"],
            missing="Compact run has no event trace. Run in full mode to view student movement replay.",
        )
        payload.update({
            "output_mode": output_mode,
            "time_bounds": {
                "start_ms": 0,
                "end_ms": 0,
                "clock_start": clock_start,
                "duration_s": 0.0,
            },
            "sectors": REPLAY_SECTORS,
            "student_trajectories": [],
            "bus_trajectories": [],
            "sector_stats_timeline": [],
            "has_trace": False,
        })
        return payload

    max_time_ms = 0
    for e in trace:
        if isinstance(e, dict):
            t = e.get("time_ms")
            if isinstance(t, (int, float)) and t > max_time_ms:
                max_time_ms = int(t)
    for it in intervals:
        if isinstance(it, dict):
            e_ms = it.get("end_ms")
            if isinstance(e_ms, (int, float)) and e_ms > max_time_ms:
                max_time_ms = int(e_ms)

    # 1. Trajectories by group
    events_by_group: dict[str, list[dict[str, Any]]] = {}
    for e in trace:
        if not isinstance(e, dict):
            continue
        gid = e.get("affected_group_id")
        if gid:
            events_by_group.setdefault(str(gid), []).append(e)

    def _is_g03_ev(e: dict[str, Any]) -> bool:
        return (
            e.get("place_id") in ("g03_foyer_entrance", "g03_seating")
            or e.get("leg_id") in ("leg_carpark_to_g03", "leg_g03_foyer_to_seating")
            or "_g03" in str(e.get("affected_part_id", ""))
        )

    def _is_dtsp_ev(e: dict[str, Any]) -> bool:
        return (
            e.get("place_id") in ("dtsp_door_a", "dtsp_door_b", "dtsp_foyer", "dtsp_seating")
            or e.get("leg_id") in (
                "leg_hall_approach",
                "leg_hall_approach_north",
                "leg_hall_approach_south",
                "leg_hall_to_door_a",
                "leg_hall_to_door_b",
                "leg_door_a_to_foyer",
                "leg_door_b_to_foyer",
                "leg_foyer_to_seating",
            )
        )

    trajectories: list[dict[str, Any]] = []
    for gid, evs in events_by_group.items():
        evs.sort(key=lambda x: (x.get("time_ms") or 0, 0 if x.get("event_type") == "arrival" else 1))
        hostel_id = None
        student_count = 20
        for e in evs:
            comp = e.get("hostel_composition") or {}
            if isinstance(comp, dict) and comp:
                hostel_id = list(comp.keys())[0]
                student_count = sum(comp.values())
                break
        if not hostel_id:
            for hid in HOSTEL_COLORS:
                if hid in gid:
                    hostel_id = hid
                    break

        origin_place = f"{hostel_id}_origin" if hostel_id else "dtsp_walk_approach"

        # Check if this group split into both DTSP and G03 branches
        has_g03 = any(_is_g03_ev(e) for e in evs)
        has_dtsp = any(_is_dtsp_ev(e) for e in evs)
        if has_g03 and has_dtsp:
            g03_evs = [e for e in evs if _is_g03_ev(e)]
            dtsp_evs = [e for e in evs if _is_dtsp_ev(e)]
            common_evs = [e for e in evs if not _is_g03_ev(e) and not _is_dtsp_ev(e)]
            dtsp_count = sum(int(e.get("student_count", 1)) for e in dtsp_evs if e.get("event_type") == "seated_completion")
            g03_count = sum(int(e.get("student_count", 1)) for e in g03_evs if e.get("event_type") == "seated_completion")
            if dtsp_count == 0 and g03_count > 0:
                dtsp_count = max(1, student_count - g03_count)
            elif g03_count == 0 and dtsp_count > 0:
                g03_count = max(1, student_count - dtsp_count)
            elif dtsp_count == 0 and g03_count == 0:
                dtsp_count = student_count // 2
                g03_count = student_count - dtsp_count
            branches = [
                (f"{gid}_dtsp", common_evs + dtsp_evs, dtsp_count),
                (f"{gid}_g03", common_evs + g03_evs, g03_count),
            ]
        else:
            branches = [(gid, evs, student_count)]

        for traj_id, branch_evs, branch_students in branches:
            branch_evs.sort(key=lambda x: (x.get("time_ms") or 0, 0 if x.get("event_type") == "arrival" else 1))
            leg_dep: dict[str, int] = {}
            leg_arr: dict[str, int] = {}
            leg_dep_place: dict[str, str] = {}
            leg_arr_place: dict[str, str] = {}

            for e in branch_evs:
                l = e.get("leg_id")
                et = e.get("event_type")
                t = int(e.get("time_ms") or 0)
                pl = e.get("place_id")
                if not l:
                    continue
                leg_str = str(l)
                if et == "departure":
                    leg_dep[leg_str] = min(leg_dep.get(leg_str, t), t)
                    if leg_str not in leg_dep_place and pl:
                        leg_dep_place[leg_str] = pl
                elif et == "arrival":
                    leg_arr[leg_str] = max(leg_arr.get(leg_str, t), t)
                    if pl:
                        leg_arr_place[leg_str] = pl

            ordered_legs = sorted(leg_dep.keys(), key=lambda k: leg_dep[k])
            legs_spans: list[tuple[str, int, int, str | None, str | None]] = []
            for l in ordered_legs:
                s_ms = leg_dep[l]
                e_ms = max(s_ms, leg_arr.get(l, s_ms))
                legs_spans.append((l, s_ms, e_ms, leg_dep_place.get(l), leg_arr_place.get(l)))

            raw_segments: list[dict[str, Any]] = []
            current_time = 0
            current_place = origin_place
            current_coords = place_coords.get(current_place, [5.357, 100.301])

            for leg, start_ms, end_ms, d_pl, a_pl in legs_spans:
                default_endpoints = REPLAY_LEG_ENDPOINTS.get(leg, (current_place, "dtsp_seating"))
                d_pl_id = d_pl or default_endpoints[0] or current_place
                a_pl_id = a_pl or default_endpoints[1]

                if start_ms > current_time:
                    raw_segments.append({
                        "type": "wait",
                        "start_ms": current_time,
                        "end_ms": start_ms,
                        "place_id": current_place,
                        "waypoints": [place_coords.get(current_place, current_coords)],
                    })
                    current_time = start_ms

                pts = routes.get(leg)
                if not pts:
                    pts = [place_coords.get(d_pl_id, current_coords), place_coords.get(a_pl_id, current_coords)]

                transit_start = max(current_time, start_ms)
                transit_end = max(transit_start, end_ms)
                raw_segments.append({
                    "type": "transit",
                    "start_ms": transit_start,
                    "end_ms": transit_end,
                    "leg_id": leg,
                    "place_id": a_pl_id or d_pl_id,
                    "waypoints": pts,
                })
                current_time = transit_end
                if a_pl_id:
                    current_place = a_pl_id
                    current_coords = place_coords.get(a_pl_id, current_coords)

            final_dest = "g03_seating" if ("g03" in traj_id or any("g03" in ls[0] for ls in legs_spans)) else "dtsp_seating"
            if current_place in ("g03_foyer_entrance", "g03_seating"):
                final_dest = "g03_seating"
            elif current_place in ("dtsp_foyer", "dtsp_door_a", "dtsp_door_b", "dtsp_seating"):
                final_dest = "dtsp_seating"

            if current_time < max_time_ms:
                raw_segments.append({
                    "type": "wait",
                    "start_ms": current_time,
                    "end_ms": max_time_ms,
                    "place_id": current_place or final_dest,
                    "waypoints": [place_coords.get(current_place or final_dest, current_coords)],
                })

            # Coalesce adjacent segments
            clean_segments: list[dict[str, Any]] = []
            for s in raw_segments:
                if s["type"] == "wait" and s["start_ms"] == s["end_ms"]:
                    continue
                if not clean_segments:
                    clean_segments.append(s)
                    continue
                prev = clean_segments[-1]
                if s["type"] == "wait" and prev["type"] == "wait" and s.get("place_id") == prev.get("place_id"):
                    prev["end_ms"] = max(prev["end_ms"], s["end_ms"])
                    continue
                if s["type"] == "transit" and prev["type"] == "transit" and s.get("leg_id") == prev.get("leg_id"):
                    prev["end_ms"] = max(prev["end_ms"], s["end_ms"])
                    continue
                clean_segments.append(s)

            while clean_segments and clean_segments[0]["type"] == "wait" and clean_segments[0]["start_ms"] == clean_segments[0]["end_ms"]:
                clean_segments.pop(0)

            # Ensure trajectory starts at start_ms: 0 at hostel origin
            if not clean_segments:
                clean_segments.append({
                    "type": "wait",
                    "start_ms": 0,
                    "end_ms": max_time_ms,
                    "place_id": origin_place,
                    "waypoints": [place_coords.get(origin_place, current_coords)],
                })
            elif clean_segments[0]["start_ms"] > 0:
                clean_segments.insert(0, {
                    "type": "wait",
                    "start_ms": 0,
                    "end_ms": clean_segments[0]["start_ms"],
                    "place_id": origin_place,
                    "waypoints": [place_coords.get(origin_place, current_coords)],
                })

            trajectories.append({
                "id": traj_id,
                "hostel_id": hostel_id or "unknown",
                "student_count": branch_students,
                "color": HOSTEL_COLORS.get(hostel_id or "", "#3B82F6"),
                "segments": clean_segments,
            })

    # 2. Sector stats timeline via sweep
    step_ms = 30000
    num_buckets = int(max_time_ms // step_ms) + 1 if max_time_ms > 0 else 1
    all_sector_ids = [s["id"] for s in REPLAY_SECTORS]
    active_places = set(all_sector_ids)
    for it in intervals:
        if isinstance(it, dict) and it.get("place_id"):
            active_places.add(str(it["place_id"]))

    headcount_deltas = {pl: [0] * (num_buckets + 2) for pl in active_places}
    wait_cum_dur = {pl: [0.0] * (num_buckets + 2) for pl in active_places}
    wait_cum_cnt = {pl: [0] * (num_buckets + 2) for pl in active_places}
    travel_cum_dur = {pl: [0.0] * (num_buckets + 2) for pl in active_places}
    travel_cum_cnt = {pl: [0] * (num_buckets + 2) for pl in active_places}

    for it in intervals:
        if not isinstance(it, dict):
            continue
        pl = it.get("place_id")
        if not pl or pl not in active_places:
            continue
        s_ms = int(it.get("start_ms") or 0)
        e_ms = int(it.get("end_ms") or 0)
        cnt = int(it.get("student_count") or 1)
        act = it.get("primary_activity")
        dur = float(it.get("duration_s") or max(0.0, (e_ms - s_ms) / 1000.0))

        s_b = max(0, min(num_buckets, int(s_ms // step_ms)))
        e_b = max(0, min(num_buckets, int(e_ms // step_ms)))

        if act in ("waiting", "service"):
            headcount_deltas[pl][s_b] += cnt
            headcount_deltas[pl][e_b + 1] -= cnt
            wait_cum_dur[pl][e_b] += dur * cnt
            wait_cum_cnt[pl][e_b] += cnt
        elif act == "travel":
            travel_cum_dur[pl][e_b] += dur * cnt
            travel_cum_cnt[pl][e_b] += cnt

    timeline: list[dict[str, Any]] = []
    current_hc = {pl: 0 for pl in active_places}
    running_wait_dur = {pl: 0.0 for pl in active_places}
    running_wait_cnt = {pl: 0 for pl in active_places}
    running_travel_dur = {pl: 0.0 for pl in active_places}
    running_travel_cnt = {pl: 0 for pl in active_places}

    for b in range(num_buckets):
        t_ms = b * step_ms
        sec_stats: dict[str, dict[str, Any]] = {}
        for pl in all_sector_ids:
            current_hc[pl] += headcount_deltas[pl][b]
            running_wait_dur[pl] += wait_cum_dur[pl][b]
            running_wait_cnt[pl] += wait_cum_cnt[pl][b]
            running_travel_dur[pl] += travel_cum_dur[pl][b]
            running_travel_cnt[pl] += travel_cum_cnt[pl][b]

            hc = max(0, current_hc[pl])
            avg_w = round(running_wait_dur[pl] / running_wait_cnt[pl], 1) if running_wait_cnt[pl] > 0 else 0.0
            avg_tr = round(running_travel_dur[pl] / running_travel_cnt[pl], 1) if running_travel_cnt[pl] > 0 else 0.0

            if hc >= 150 or avg_w >= 600:
                status = "bottleneck"
            elif hc >= 40 or avg_w >= 180:
                status = "dense"
            else:
                status = "flowing"

            sec_stats[pl] = {
                "headcount": hc,
                "avg_wait_s": avg_w,
                "avg_transit_s": avg_tr,
                "status": status,
            }
        timeline.append({"time_ms": t_ms, "sectors": sec_stats})

    payload = dto_base(
        run_id,
        units={"time": "milliseconds", "coordinates": "degrees_lat_lon"},
        source_fields=["event_trace", "student_time_intervals"],
    )
    payload.update({
        "output_mode": output_mode,
        "time_bounds": {
            "start_ms": 0,
            "end_ms": max_time_ms,
            "clock_start": clock_start,
            "duration_s": round(max_time_ms / 1000.0, 2),
        },
        "sectors": REPLAY_SECTORS,
        "student_trajectories": trajectories,
        "bus_trajectories": _extract_bus_trajectories(trace, scenario, max_time_ms, place_coords, routes),
        "sector_stats_timeline": timeline,
        "has_trace": True,
    })
    return payload
