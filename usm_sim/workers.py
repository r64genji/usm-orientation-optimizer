"""Finite PPSL workforce: location, travel, handover, exclusive duties."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from typing import Any, Mapping

from usm_sim.constants import FORMAT_VERSION, TIMEZONE_NAME
from usm_sim.errors import SimulationError
from usm_sim.timeutil import ms_to_s, to_ms

DUTY_ESCORT = "escort"
DUTY_COUNT = "count"
DUTY_STATION = "station"
DUTY_TRAVEL = "travel"
DUTY_HANDOVER = "handover"

# Same worker may hold these together only when operating rules allow it
# at that place.
_COMBINABLE = frozenset({DUTY_ESCORT, DUTY_COUNT})


@dataclass
class Worker:
    worker_id: str
    role: str
    place_id: str | None
    busy: bool = False
    assigned_part_id: str | None = None
    assigned_session_id: str | None = None
    roles: set[str] = field(default_factory=set)
    calendar_id: str | None = None
    available_from_ms: int = 0
    free_at_ms: int = 0
    duties: set[str] = field(default_factory=set)
    traveling_to: str | None = None
    pool_id: str | None = None
    work_periods: list[dict] = field(default_factory=list)
    station_id: str | None = None


@dataclass
class Assignment:
    worker_id: str
    duties: list[str]
    place_id: str | None
    part_id: str | None
    start_ms: int
    end_ms: int | None = None
    travel_ms: int = 0
    session_id: str | None = None
    combined: bool = False


class WorkerPool:
    """Located worker capacity. One unit cannot hold two incompatible duties."""

    def __init__(
        self,
        workers: list[Worker],
        *,
        travel: dict[tuple[str, str], int],
        require_escorts: bool,
        min_escorts_per_part: int,
        staffing_ratio: dict,
        min_station_staff: dict[str, int],
        permitted_handover_places: set[str],
        combined_places: set[str],
        handover_ms: int,
        ppsl_total_reference: int | None,
        understaffed_reason: str | None = None,
    ) -> None:
        self.workers = workers
        self.by_id: dict[str, Worker] = {worker.worker_id: worker for worker in workers}
        self._travel = travel
        self.require_escorts = require_escorts
        self.min_escorts_per_part = min_escorts_per_part
        self.staffing_ratio = dict(staffing_ratio)
        self.min_station_staff = dict(min_station_staff)
        self.permitted_handover_places = set(permitted_handover_places)
        self.combined_places = set(combined_places)
        self.handover_ms = int(handover_ms)
        self.ppsl_total_reference = ppsl_total_reference
        self._understaffed_reason = understaffed_reason
        self.assignments: list[Assignment] = []
        self._open: dict[str, Assignment] = {}

    @classmethod
    def from_scenario(cls, scenario: Mapping[str, Any], policy: Mapping[str, Any] | None = None) -> WorkerPool:
        operating = dict(scenario.get("operating_rules") or {})
        policy_d = dict(policy or {})
        grouping = dict(policy_d.get("grouping") or {})
        travel = _travel_map(scenario, operating)
        require_escorts = _require_escorts(operating, grouping)
        min_escorts = _min_escorts(operating, grouping)
        staffing_ratio = dict(operating.get("staffing_ratio") or {})
        min_station = _as_place_int_map(operating.get("min_station_staff"))
        handover_places = set(operating.get("permitted_handover_places") or [])
        combined = _combined_places(operating)
        handover_s = operating.get("handover_s")
        if handover_s is None:
            handover_s = 0
        ppsl_ref = operating.get("ppsl_total_reference")
        if ppsl_ref is None:
            ppsl_ref = scenario.get("ppsl_total_reference")
        workers = _load_worker_records(scenario.get("initial_state") or {})
        _apply_worker_assignments(workers, policy_d, travel)
        if policy_d.get("min_station_staff"):
            min_station.update(_as_place_int_map(policy_d["min_station_staff"]))
        if policy_d.get("staffing_ratio"):
            staffing_ratio.update(dict(policy_d["staffing_ratio"]))
        if policy_d.get("escorts_per_group") is not None:
            min_escorts = max(min_escorts, int(policy_d["escorts_per_group"]))
        pool = cls(
            workers,
            travel=travel,
            require_escorts=require_escorts,
            min_escorts_per_part=min_escorts,
            staffing_ratio=staffing_ratio,
            min_station_staff=min_station,
            permitted_handover_places=handover_places,
            combined_places=combined,
            handover_ms=to_ms(handover_s),
            ppsl_total_reference=int(ppsl_ref) if ppsl_ref is not None else None,
        )
        pool._understaffed_reason = pool._compute_understaffed_reason()
        return pool

    def travel_lookup(self, from_place: str | None, to_place: str | None) -> int | None:
        if not from_place or not to_place or from_place == to_place:
            return 0
        if (from_place, to_place) in self._travel:
            return self._travel[(from_place, to_place)]
        if (to_place, from_place) in self._travel:
            return self._travel[(to_place, from_place)]
        return None

    def travel_ms(self, from_place: str | None, to_place: str | None) -> int:
        found = self.travel_lookup(from_place, to_place)
        if found is None:
            raise SimulationError(
                "missing_input",
                (
                    "worker travel between "
                    f"{from_place!r} and {to_place!r} is not declared"
                ),
                field="scenario.operating_rules.worker_travel",
            )
        return found

    def combined_permitted(self, place_id: str | None) -> bool:
        if not place_id:
            return False
        if "*" in self.combined_places:
            return True
        return place_id in self.combined_places

    def escorts_needed(self, part: Any) -> int:
        if not self.require_escorts:
            return 0
        if getattr(part, "internal_calculation", False):
            return 0
        count = int(getattr(part, "student_count", 0) or 0)
        need = 0
        supervision = getattr(part, "required_supervision", None) or {}
        if supervision.get("escorts") is not None:
            declared = int(supervision["escorts"])
            if declared <= 0:
                return 0
            need = max(need, declared)
        students_per = self.staffing_ratio.get("students_per_escort")
        if students_per and count > 0:
            need = max(need, max(1, int(ceil(count / float(students_per)))))
        elif self.staffing_ratio.get("escorts_per_group") is not None:
            need = max(need, max(1, int(self.staffing_ratio["escorts_per_group"])))
        if self.min_escorts_per_part:
            need = max(need, int(self.min_escorts_per_part))
        return need

    def uses_station_staff(self, place_id: str | None) -> bool:
        if not place_id:
            return False
        if "*" in self.min_station_staff:
            return True
        return place_id in self.min_station_staff

    def min_station_for(self, place_id: str | None) -> int:
        if not place_id:
            return 0
        if place_id in self.min_station_staff:
            return int(self.min_station_staff[place_id])
        return int(self.min_station_staff.get("*") or 0)

    def permanently_understaffed(self) -> bool:
        return self._understaffed_reason is not None

    def understaffed_reason(self) -> str | None:
        return self._understaffed_reason

    def capable_count(self, duty: str) -> int:
        return sum(1 for worker in self.workers if self.can_perform(worker, duty))

    def can_perform(self, worker: Worker, duty: str, place_id: str | None = None) -> bool:
        roles = worker.roles or {worker.role}
        if not roles or "ppsl" in roles or "any" in roles:
            return True
        if duty in roles:
            return True
        if duty == DUTY_COUNT and "counter" in roles:
            return True
        if duty == DUTY_COUNT and "escort" in roles and self.combined_permitted(place_id):
            return True
        if duty == DUTY_STATION and roles & {"escort", "count", "counter", "station"}:
            return True
        if duty == DUTY_ESCORT and "ppsl" in roles:
            return True
        return False

    def duties_compatible(self, worker: Worker, duty: str, place_id: str | None) -> bool:
        if not worker.duties or worker.duties == {DUTY_TRAVEL}:
            return True
        active = {item for item in worker.duties if item != DUTY_TRAVEL}
        if not active:
            return True
        if duty in active:
            return True
        proposed = active | {duty}
        if proposed <= _COMBINABLE and self.combined_permitted(place_id):
            return True
        return False

    def time_available(self, worker: Worker, now_ms: int, calendar_open: Mapping[str, bool]) -> bool:
        if now_ms < worker.available_from_ms:
            return False
        if worker.calendar_id and not calendar_open.get(worker.calendar_id):
            return False
        if worker.work_periods:
            now_s = ms_to_s(now_ms)
            in_period = False
            for period in worker.work_periods:
                start_s = float(period.get("start_s") or 0)
                end_s = float(period.get("end_s") if period.get("end_s") is not None else 10**12)
                if start_s <= now_s < end_s:
                    in_period = True
                    break
            if not in_period:
                return False
        return True

    def earliest_start_ms(
        self,
        worker: Worker,
        place_id: str | None,
        now_ms: int,
        calendar_open: Mapping[str, bool],
        calendars: Mapping[str, Mapping],
    ) -> int:
        start = max(now_ms, worker.free_at_ms, worker.available_from_ms)
        if worker.calendar_id and not calendar_open.get(worker.calendar_id):
            calendar = calendars.get(worker.calendar_id) or {}
            start = max(start, to_ms(calendar.get("open_time_s") or 0))
        if worker.work_periods:
            now_s = ms_to_s(start)
            next_s = None
            for period in worker.work_periods:
                start_s = float(period.get("start_s") or 0)
                end_s = float(period.get("end_s") if period.get("end_s") is not None else 10**12)
                if start_s <= now_s < end_s:
                    next_s = now_s
                    break
                if start_s >= now_s:
                    next_s = start_s if next_s is None else min(next_s, start_s)
            if next_s is None:
                return start + 10**12
            start = max(start, to_ms(next_s))
        travel = self.travel_lookup(worker.place_id, place_id)
        if travel is None:
            return start + 10**12
        start += travel
        return start

    def idle_now(
        self,
        place_id: str | None,
        duty: str,
        now_ms: int,
        calendar_open: Mapping[str, bool],
    ) -> list[Worker]:
        idle: list[Worker] = []
        for worker in self.workers:
            if worker.busy:
                continue
            if not self.time_available(worker, now_ms, calendar_open):
                continue
            if not self.can_perform(worker, duty, place_id):
                continue
            if not self.duties_compatible(worker, duty, place_id):
                continue
            if place_id and worker.place_id not in {None, place_id}:
                continue
            if now_ms < worker.free_at_ms:
                continue
            idle.append(worker)
        idle.sort(
            key=lambda worker: (
                0 if worker.place_id == place_id else 1,
                0 if duty in (worker.roles or {worker.role}) else 1,
                worker.worker_id,
            )
        )
        return idle

    def pick_free(
        self,
        n: int,
        duty: str,
        place_id: str | None,
        now_ms: int,
        calendar_open: Mapping[str, bool],
        calendars: Mapping[str, Mapping],
    ) -> tuple[list[Worker], int] | None:
        if n <= 0:
            return [], now_ms
        candidates = [
            worker
            for worker in self.workers
            if not worker.busy and self.can_perform(worker, duty, place_id)
        ]
        if len(candidates) < n:
            return None
        ranked = sorted(
            candidates,
            key=lambda worker: (
                self.earliest_start_ms(worker, place_id, now_ms, calendar_open, calendars),
                worker.worker_id,
            ),
        )
        chosen = ranked[:n]
        start_ms = max(
            self.earliest_start_ms(worker, place_id, now_ms, calendar_open, calendars)
            for worker in chosen
        )
        return chosen, start_ms

    def reserve_now(
        self,
        workers: list[Worker],
        duty: str,
        place_id: str | None,
        now_ms: int,
        part_id: str | None,
        session_id: str | None = None,
    ) -> list[str]:
        ids: list[str] = []
        for worker in workers:
            worker.busy = True
            worker.duties.add(duty)
            worker.assigned_part_id = part_id
            worker.assigned_session_id = session_id
            worker.free_at_ms = now_ms
            if place_id:
                worker.place_id = place_id
            self._open_assignment(
                worker,
                [duty],
                place_id,
                part_id,
                now_ms,
                session_id=session_id,
            )
            ids.append(worker.worker_id)
        return ids

    def commit_travel(
        self,
        workers: list[Worker],
        duty: str,
        place_id: str | None,
        now_ms: int,
        start_ms: int,
        part_id: str | None,
    ) -> list[str]:
        ids: list[str] = []
        for worker in workers:
            worker.busy = True
            worker.assigned_part_id = part_id
            travel = self.travel_ms(worker.place_id, place_id)
            arrive_ms = max(int(start_ms), int(now_ms))
            travel_start = arrive_ms - travel if travel > 0 else arrive_ms
            if travel_start < now_ms:
                travel_start = now_ms
            if travel > 0 and arrive_ms > now_ms:
                worker.duties.add(DUTY_TRAVEL)
                worker.traveling_to = place_id
                worker.free_at_ms = arrive_ms
                self._open_assignment(
                    worker,
                    [DUTY_TRAVEL],
                    place_id,
                    part_id,
                    travel_start,
                    travel_ms=travel,
                )
            elif arrive_ms <= now_ms:
                worker.duties.add(duty)
                worker.free_at_ms = now_ms
                if place_id:
                    worker.place_id = place_id
                self._open_assignment(worker, [duty], place_id, part_id, now_ms)
            else:
                worker.free_at_ms = arrive_ms
            ids.append(worker.worker_id)
        return ids

    def arrive(self, worker_ids: list[str], place_id: str | None, now_ms: int, duty: str) -> None:
        for worker_id in worker_ids:
            worker = self.by_id.get(worker_id)
            if worker is None:
                continue
            if DUTY_TRAVEL in worker.duties:
                self._close_assignment(worker_id, now_ms)
            worker.place_id = place_id
            worker.traveling_to = None
            worker.duties.discard(DUTY_TRAVEL)
            worker.duties.add(duty)
            worker.busy = True
            worker.free_at_ms = now_ms
            self._open_assignment(worker, [duty], place_id, worker.assigned_part_id, now_ms)

    def colocate(self, worker_ids: list[str], place_id: str | None) -> None:
        for worker_id in worker_ids:
            worker = self.by_id.get(worker_id)
            if worker is None:
                continue
            worker.place_id = place_id

    def add_duty(self, worker_ids: list[str], duty: str, now_ms: int) -> None:
        for worker_id in worker_ids:
            worker = self.by_id.get(worker_id)
            if worker is None:
                continue
            worker.duties.add(duty)
            worker.busy = True
            open_row = self._open.get(worker_id)
            if open_row is not None:
                if duty not in open_row.duties:
                    open_row.duties.append(duty)
                open_row.combined = True
            else:
                self._open_assignment(
                    worker,
                    [duty],
                    worker.place_id,
                    worker.assigned_part_id,
                    now_ms,
                    combined=True,
                )

    def drop_duty(self, worker_id: str, duty: str, now_ms: int) -> None:
        worker = self.by_id.get(worker_id)
        if worker is None:
            return
        worker.duties.discard(duty)
        open_row = self._open.get(worker_id)
        if open_row is not None and duty in open_row.duties and len(open_row.duties) > 1:
            remaining = [item for item in open_row.duties if item != duty]
            self._close_assignment(worker_id, now_ms)
            if remaining:
                self._open_assignment(
                    worker,
                    remaining,
                    worker.place_id,
                    worker.assigned_part_id,
                    now_ms,
                )
        if not worker.duties:
            self.release([worker_id], now_ms)

    def release(self, worker_ids: list[str], now_ms: int) -> None:
        for worker_id in worker_ids:
            worker = self.by_id.get(worker_id)
            if worker is None:
                continue
            self._close_assignment(worker_id, now_ms)
            worker.busy = False
            worker.duties.clear()
            worker.assigned_part_id = None
            worker.assigned_session_id = None
            worker.traveling_to = None
            worker.free_at_ms = now_ms

    def close_open(self, now_ms: int) -> None:
        for worker_id in list(self._open):
            self._close_assignment(worker_id, now_ms)

    def assignment_records(self) -> list[dict]:
        rows = []
        for item in self.assignments:
            rows.append(
                {
                    "worker_id": item.worker_id,
                    "duties": list(item.duties),
                    "place_id": item.place_id,
                    "part_id": item.part_id,
                    "start_ms": item.start_ms,
                    "end_ms": item.end_ms,
                    "travel_ms": item.travel_ms,
                    "combined": item.combined,
                }
            )
        return rows

    def summarize(self, now_ms: int) -> dict:
        closed = list(self.assignments)
        for open_row in self._open.values():
            closed.append(
                Assignment(
                    worker_id=open_row.worker_id,
                    duties=list(open_row.duties),
                    place_id=open_row.place_id,
                    part_id=open_row.part_id,
                    start_ms=open_row.start_ms,
                    end_ms=now_ms,
                    travel_ms=open_row.travel_ms,
                    combined=open_row.combined,
                )
            )
        reserved_ms = 0
        travel_ms = 0
        escort_ms = 0
        count_ms = 0
        station_ms = 0
        handover_ms = 0
        combined_ms = 0
        standby_ms = 0
        duty_ms = 0
        by_worker: dict[str, list[tuple[int, int]]] = {}
        duty_by_worker: dict[str, list[tuple[int, int]]] = {}
        for row in closed:
            end_ms = row.end_ms if row.end_ms is not None else now_ms
            duration = max(0, end_ms - row.start_ms)
            if duration <= 0:
                continue
            by_worker.setdefault(row.worker_id, []).append((row.start_ms, end_ms))
            duties = set(row.duties)
            if DUTY_TRAVEL in duties:
                travel_ms += duration
            if DUTY_ESCORT in duties:
                escort_ms += duration
            if DUTY_COUNT in duties:
                count_ms += duration
            if DUTY_STATION in duties:
                station_ms += duration
            if DUTY_HANDOVER in duties:
                handover_ms += duration
            if "standby" in duties:
                standby_ms += duration
            if row.combined or duties >= _COMBINABLE:
                combined_ms += duration
            duty_set = duties - {DUTY_TRAVEL}
            if duty_set:
                duty_by_worker.setdefault(row.worker_id, []).append((row.start_ms, end_ms))
        for worker_id, intervals in by_worker.items():
            reserved_ms += _union_ms(intervals)
        for worker_id, intervals in duty_by_worker.items():
            duty_ms += _union_ms(intervals)
        unused_ms = 0
        for worker in self.workers:
            available_end = now_ms
            available_start = worker.available_from_ms
            unused_ms += max(0, available_end - available_start)
        unused_ms = max(0, unused_ms - reserved_ms)
        peak = _peak_concurrent(by_worker)
        return {
            "worker_reserved_s": ms_to_s(reserved_ms),
            "worker_travel_s": ms_to_s(travel_ms),
            "worker_escort_s": ms_to_s(escort_ms),
            "worker_count_s": ms_to_s(count_ms),
            "worker_station_s": ms_to_s(station_ms),
            "worker_handover_s": ms_to_s(handover_ms),
            "worker_combined_s": ms_to_s(combined_ms),
            "worker_standby_s": ms_to_s(standby_ms),
            "worker_duty_s": ms_to_s(duty_ms),
            "worker_unused_availability_s": ms_to_s(unused_ms),
            "peak_concurrent_workers": peak,
            "assignments": self.assignment_records(),
        }

    def _open_assignment(
        self,
        worker: Worker,
        duties: list[str],
        place_id: str | None,
        part_id: str | None,
        start_ms: int,
        session_id: str | None = None,
        travel_ms: int = 0,
        combined: bool = False,
    ) -> None:
        existing = self._open.get(worker.worker_id)
        if existing is not None:
            for duty in duties:
                if duty not in existing.duties:
                    existing.duties.append(duty)
            if combined or set(existing.duties) >= _COMBINABLE:
                existing.combined = True
            return
        row = Assignment(
            worker_id=worker.worker_id,
            duties=list(duties),
            place_id=place_id,
            part_id=part_id,
            start_ms=start_ms,
            session_id=session_id,
            travel_ms=travel_ms,
            combined=combined or set(duties) >= _COMBINABLE,
        )
        self._open[worker.worker_id] = row

    def _close_assignment(self, worker_id: str, end_ms: int) -> None:
        row = self._open.pop(worker_id, None)
        if row is None:
            return
        row.end_ms = end_ms
        self.assignments.append(row)

    def _compute_understaffed_reason(self) -> str | None:
        total = len(self.workers)
        for place_id, need in self.min_station_staff.items():
            if total < int(need):
                return f"min_station_staff at {place_id} is {need} but only {total} workers are declared"
        if self.require_escorts:
            capable = self.capable_count(DUTY_ESCORT)
            if capable < int(self.min_escorts_per_part):
                return (
                    f"escorts required ({self.min_escorts_per_part}) but only "
                    f"{capable} capable workers are declared"
                )
        return None


def staffing_floor_violations(scenario: Mapping[str, Any], policy: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Return (field, message) when a policy lowers a staffing floor."""
    operating = dict(scenario.get("operating_rules") or {})
    policy_staffing = _policy_staffing(policy)
    hits: list[tuple[str, str]] = []
    scenario_min = _as_place_int_map(operating.get("min_station_staff"))
    policy_min = policy_staffing.get("min_station_staff")
    if policy_min is not None:
        if isinstance(policy_min, Mapping):
            for place_id, floor in scenario_min.items():
                if place_id in policy_min and int(policy_min[place_id]) < int(floor):
                    hits.append(
                        (
                            f"policy.min_station_staff.{place_id}",
                            (
                                f"policy min_station_staff at {place_id!r} is "
                                f"{policy_min[place_id]}, below operating floor {floor}"
                            ),
                        )
                    )
        elif isinstance(policy_min, int) and not isinstance(policy_min, bool):
            for place_id, floor in scenario_min.items():
                if int(policy_min) < int(floor):
                    hits.append(
                        (
                            "policy.min_station_staff",
                            (
                                f"policy min_station_staff {policy_min} is below "
                                f"operating floor {floor} at {place_id}"
                            ),
                        )
                    )
    scenario_ratio = dict(operating.get("staffing_ratio") or {})
    policy_ratio = policy_staffing.get("staffing_ratio")
    if isinstance(policy_ratio, Mapping) and scenario_ratio:
        for key in ("escorts_per_group", "min_escorts_per_group"):
            if key in scenario_ratio and key in policy_ratio:
                if int(policy_ratio[key]) < int(scenario_ratio[key]):
                    hits.append(
                        (
                            f"policy.staffing_ratio.{key}",
                            f"policy {key} {policy_ratio[key]} is below operating floor {scenario_ratio[key]}",
                        )
                    )
        if "students_per_escort" in scenario_ratio and "students_per_escort" in policy_ratio:
            if int(policy_ratio["students_per_escort"]) > int(scenario_ratio["students_per_escort"]):
                hits.append(
                    (
                        "policy.staffing_ratio.students_per_escort",
                        "policy students_per_escort is above the operating limit",
                    )
                )
    for key in ("escorts_per_group", "min_escorts_per_group"):
        floor = operating.get(key)
        if floor is None and isinstance(operating.get("staffing_ratio"), Mapping):
            floor = operating["staffing_ratio"].get(key)
        offered = policy_staffing.get(key)
        if floor is not None and offered is not None and int(offered) < int(floor):
            hits.append(
                (
                    f"policy.{key}",
                    f"policy {key} {offered} is below operating floor {floor}",
                )
            )
    grouping = dict(policy.get("grouping") or {})
    group_escorts = grouping.get("escorts_per_group")
    floor_escorts = operating.get("min_escorts_per_group")
    if floor_escorts is None:
        floor_escorts = (operating.get("staffing_ratio") or {}).get("escorts_per_group")
    if floor_escorts is None:
        floor_escorts = operating.get("escorts_per_group")
    if floor_escorts is not None and group_escorts is not None and int(group_escorts) < int(floor_escorts):
        hits.append(
            (
                "policy.grouping.escorts_per_group",
                "policy escorts_per_group is below the operating floor",
            )
        )
    return hits


def _policy_staffing(policy: Mapping[str, Any]) -> dict:
    out: dict[str, Any] = {}
    raw = policy.get("staffing")
    if isinstance(raw, Mapping):
        out.update(dict(raw))
    nested = policy.get("operating_rules")
    if isinstance(nested, Mapping):
        for key in ("min_station_staff", "staffing_ratio", "escorts_per_group", "min_escorts_per_group"):
            if key in nested and key not in out:
                out[key] = nested[key]
    for key in ("min_station_staff", "staffing_ratio", "escorts_per_group", "min_escorts_per_group"):
        if key in policy:
            out[key] = policy[key]
    return out


def _as_place_int_map(value: Any) -> dict[str, int]:
    if value is None:
        return {}
    if isinstance(value, bool):
        return {}
    if isinstance(value, int):
        return {"*": int(value)}
    if isinstance(value, Mapping):
        return {str(key): int(item) for key, item in value.items() if item is not None}
    return {}


def _combined_places(operating: Mapping[str, Any]) -> set[str]:
    places = operating.get("combined_escort_and_count_places")
    if isinstance(places, list):
        return {str(item) for item in places}
    flag = operating.get("permit_combined_escort_and_count")
    if flag is True:
        return {"*"}
    if isinstance(flag, Mapping):
        return {str(key) for key, item in flag.items() if item}
    return set()


def _require_escorts(operating: Mapping[str, Any], grouping: Mapping[str, Any]) -> bool:
    if operating.get("require_escorts") or operating.get("escorts_required"):
        return True
    if operating.get("min_escorts_per_group") is not None:
        return True
    if operating.get("escorts_per_group") is not None:
        return True
    ratio = operating.get("staffing_ratio") or {}
    if isinstance(ratio, Mapping) and (
        ratio.get("escorts_per_group") is not None
        or ratio.get("students_per_escort") is not None
        or ratio.get("min_escorts_per_group") is not None
    ):
        return True
    return False


def _min_escorts(operating: Mapping[str, Any], grouping: Mapping[str, Any]) -> int:
    for source in (operating, operating.get("staffing_ratio") or {}, grouping):
        if not isinstance(source, Mapping):
            continue
        for key in ("min_escorts_per_group", "escorts_per_group"):
            if source.get(key) is not None:
                return max(1, int(source[key]))
    if _require_escorts(operating, grouping):
        return 1
    return 0


def _travel_map(scenario: Mapping[str, Any], operating: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    rows: list = []
    for key in ("worker_travel", "worker_travel_s"):
        raw = operating.get(key)
        if isinstance(raw, list):
            rows.extend(raw)
        raw = scenario.get(key)
        if isinstance(raw, list):
            rows.extend(raw)
    travel: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        from_id = row.get("from_place_id")
        to_id = row.get("to_place_id")
        if not from_id or not to_id:
            continue
        duration = row.get("duration_s")
        if duration is None:
            duration = row.get("travel_s")
        if duration is None:
            continue
        travel[(str(from_id), str(to_id))] = to_ms(duration)
    return travel


def _load_worker_records(initial: Mapping[str, Any]) -> list[Worker]:
    workers: list[Worker] = []
    for raw in initial.get("workers") or []:
        if not isinstance(raw, Mapping):
            continue
        n = int(raw.get("count") or 1)
        roles = set()
        if raw.get("roles"):
            roles = {str(item) for item in raw["roles"]}
        elif raw.get("role"):
            roles = {str(raw["role"])}
        else:
            roles = {"ppsl"}
        role = str(raw.get("role") or next(iter(roles)))
        for index in range(n):
            worker_id = str(raw["id"]) if n == 1 else f"{raw['id']}#{index + 1}"
            available_s = raw.get("available_time_s") or 0
            workers.append(
                Worker(
                    worker_id=worker_id,
                    role=role,
                    roles=set(roles),
                    place_id=raw.get("place_id"),
                    calendar_id=raw.get("calendar_id"),
                    available_from_ms=to_ms(available_s),
                    pool_id=str(raw.get("id")),
                    work_periods=list(raw.get("work_periods") or []),
                )
            )
    return workers


def _apply_worker_assignments(
    workers: list[Worker],
    policy_d: Mapping[str, Any],
    travel: dict[tuple[str, str], int],
) -> None:
    allocation = policy_d.get("worker_allocation")
    if not isinstance(allocation, Mapping):
        return
    assignments = allocation.get("assignments")
    if not isinstance(assignments, list):
        return
    worker_by_id = {w.worker_id: w for w in workers}
    for raw in assignments:
        if not isinstance(raw, Mapping):
            continue
        worker_id = raw.get("worker_id")
        worker = worker_by_id.get(worker_id)
        if worker is None:
            continue
        role = raw.get("role")
        if role:
            worker.role = str(role)
            worker.roles.add(str(role))
        dest = raw.get("place_id") or raw.get("to_place_id")
        src = raw.get("from_place_id") or worker.place_id
        if dest and dest != worker.place_id:
            travel_s = raw.get("travel_s")
            if travel_s is None:
                travel_s = raw.get("duration_s")
            if travel_s is not None:
                t_ms = to_ms(float(travel_s))
            else:
                t_ms = travel.get((str(src), str(dest)))
                if t_ms is None:
                    t_ms = travel.get((str(dest), str(src)))
            if t_ms is None or t_ms <= 0:
                continue
            worker.place_id = dest
            avail_s = float(raw.get("available_from_s") or 0.0)
            worker.available_from_ms = max(worker.available_from_ms, to_ms(avail_s) + t_ms)
        elif dest and dest == worker.place_id and raw.get("available_from_s") is not None:
            worker.available_from_ms = max(worker.available_from_ms, to_ms(float(raw["available_from_s"])))
        if raw.get("station_id"):
            worker.station_id = raw["station_id"]
        if raw.get("assigned_part_id"):
            worker.assigned_part_id = raw["assigned_part_id"]



def _union_ms(intervals: list[tuple[int, int]]) -> int:
    if not intervals:
        return 0
    ordered = sorted(intervals)
    total = 0
    cur_start, cur_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total += max(0, cur_end - cur_start)
            cur_start, cur_end = start, end
    total += max(0, cur_end - cur_start)
    return total


def _peak_concurrent(by_worker: dict[str, list[tuple[int, int]]]) -> int:
    events: list[tuple[int, int]] = []
    for intervals in by_worker.values():
        merged: list[tuple[int, int]] = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        for start, end in merged:
            events.append((start, 1))
            events.append((end, -1))
    events.sort(key=lambda item: (item[0], item[1]))
    peak = 0
    current = 0
    for _time, delta in events:
        current += delta
        if current > peak:
            peak = current
    return peak


def _record(field: str, value: Any, unit: str = "mixed", category: str = "assumed") -> dict:
    return {
        "field": field,
        "value": value,
        "unit": unit,
        "date": "2026-01-01",
        "method": "ticket-04 staffing fixture",
        "confidence": "high",
        "observation_ref": "spec.md#11-workers",
        "category": category,
    }


def _unbounded(place_id: str, lat: float, lon: float, meaning: str) -> dict:
    return {
        "id": place_id,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "meaning": meaning,
        "capacity_constraint": "unbounded",
        "capacity_note": "explicit unbounded ticket-04 fixture",
        "capacity_from_gps_scatter": False,
    }


def _members(prefix: str, n: int, source_unit_id: str = "su_origin") -> list[dict]:
    return [
        {
            "student_key": f"{prefix}{index}",
            "queue_tie_key": f"{index:02d}",
            "source_unit_id": source_unit_id,
            "hostel_id": "synthetic",
        }
        for index in range(n)
    ]


def _worker(worker_id: str, role: str, place_id: str, **extra: Any) -> dict:
    row = {
        "id": worker_id,
        "role": role,
        "place_id": place_id,
        "available_time_s": extra.pop("available_time_s", 0),
    }
    row.update(extra)
    return row


def _base_policy(policy_id: str, required_endpoint: str, extra: dict | None = None) -> dict:
    policy = {
        "policy_id": policy_id,
        "policy_version": "1",
        "grouping": {"mode": "explicit_parts", "escorts_per_group": 1},
        "required_endpoint": required_endpoint,
        "release_rule": {"type": "immediate"},
        "vehicle_dispatch_rule": {"type": "none"},
        "destination_rule": {"type": "complete_after_stages"},
        "random_seed": 0,
    }
    if extra:
        policy.update(extra)
    return policy


def _shell(
    *,
    scenario_id: str,
    places: list[dict],
    legs: list[dict],
    stages: list[dict],
    students: list[dict],
    workers: list[dict],
    operating_rules: dict,
    source_units: list[dict] | None = None,
    vehicles: list[dict] | None = None,
    calendars: list[dict] | None = None,
    checkpoints: list[dict] | None = None,
    worker_travel: list[dict] | None = None,
    deadline_s: float = 10000,
    simulation_end_s: float = 20000,
    policy_extra: dict | None = None,
    extra_scenario: dict | None = None,
) -> tuple[dict, dict]:
    if source_units is None:
        source_units = [
            {
                "id": "su_origin",
                "hostel_id": "synthetic",
                "estimated_attendance": sum(len(part["members"]) for part in students),
                "resolved_attendance": sum(len(part["members"]) for part in students),
                "actual_reporting_s": 0,
                "readiness_s": 0,
            }
        ]
    endpoint = operating_rules["required_endpoint"]
    rules = {
        "direct_walk_permitted": False,
        "bag_check": False,
        "security_service": False,
        "mechanical_clicker": False,
        "qr_scan": False,
        "seating_modeled": False,
        "ppsl_total_reference": 154,
        **operating_rules,
    }
    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": f"ticket-04-{scenario_id}",
        "scenario_id": scenario_id,
        "uncertainty_case_id": f"{scenario_id}_base",
        "event_date": "2026-01-01",
        "start_time_local": "00:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": deadline_s,
        "simulation_end_s": simulation_end_s,
        "max_events_per_run": 100000,
        "source_units": source_units,
        "places": places,
        "route_legs": legs,
        "route_stages": stages,
        "calendars": calendars or [],
        "initial_state": {
            "students": students,
            "queues": [],
            "workers": workers,
            "vehicles": vehicles or [],
            "hall_occupancy_students": 0,
        },
        "operating_rules": rules,
        "measured_facts": [],
        "uncertain_assumptions": [
            {
                "id": "ticket04_fixture",
                "category": "assumed",
                "note": "controlled finite-staffing case",
            }
        ],
        "decisions": [
            {
                "id": "staffing_fixture",
                "category": "decision",
                "note": "ticket 04 worker locations and duties",
            }
        ],
        "source_records": [
            _record("operating_rules.ppsl_total_reference", 154, "persons", "measured"),
            _record("initial_state.workers", len(workers), "persons", "decision"),
        ],
        "accuracy_references": [],
    }
    if checkpoints is not None:
        scenario["checkpoints"] = checkpoints
        scenario["count_error_assumptions"] = [
            {
                "id": "visual_checkpoint_pass",
                "exposure_unit": "checkpoint_pass",
                "relationship_to_load": "none",
                "p_mismatch": 0.0,
            }
        ]
    if worker_travel is not None:
        scenario["worker_travel"] = worker_travel
        rules["worker_travel"] = worker_travel
    if extra_scenario:
        scenario.update(extra_scenario)
    policy = _base_policy(f"{scenario_id}_policy", endpoint, policy_extra)
    return scenario, policy


def build_dtsp_restu_return_case(*, travel_s: float = 30.0, walk_s: float = 20.0) -> tuple[dict, dict]:
    """One escort finishes at DTSP and cannot start at Restu until travel elapses."""
    travel = [
        {
            "from_place_id": "dtsp_hall_reference",
            "to_place_id": "restu_gathering",
            "duration_s": travel_s,
        },
        {
            "from_place_id": "dtsp_exterior_gathering",
            "to_place_id": "restu_gathering",
            "duration_s": travel_s,
        },
    ]
    return _shell(
        scenario_id="dtsp_restu_return_v1",
        places=[
            _unbounded("restu_gathering", 5.357387, 100.290251, "Restu gathering"),
            _unbounded("dtsp_exterior_gathering", 5.357153, 100.301749, "DTSP exterior"),
            _unbounded("dtsp_hall_reference", 5.35695, 100.30311, "DTSP hall"),
        ],
        legs=[
            {
                "id": "restu_to_hall",
                "from_place_id": "restu_gathering",
                "to_place_id": "dtsp_hall_reference",
                "duration_s": walk_s,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "to_hall", "kind": "travel", "leg_id": "restu_to_hall"}],
        students=[
            {
                "part_id": "part_a",
                "group_id": "g_a",
                "source_unit_id": "su_origin",
                "place_id": "restu_gathering",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("a", 1),
                "required_supervision": {"escorts": 1},
            },
            {
                "part_id": "part_b",
                "group_id": "g_b",
                "source_unit_id": "su_origin",
                "place_id": "restu_gathering",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("b", 1),
                "required_supervision": {"escorts": 1},
            },
        ],
        workers=[_worker("w1", "escort", "restu_gathering")],
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "escorts_per_group": 1,
            "permitted_handover_places": ["dtsp_hall_reference", "dtsp_exterior_gathering"],
        },
        worker_travel=travel,
        policy_extra={"grouping": {"mode": "explicit_parts", "escorts_per_group": 1}},
    )


def build_handover_case(*, walk_s: float = 15.0) -> tuple[dict, dict]:
    """Escort A hands over to escort B at a permitted transfer place."""
    return _shell(
        scenario_id="handover_transfer_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("transfer", 0.001, 0.0, "permitted handover"),
            _unbounded("dest", 0.002, 0.0, "destination"),
        ],
        legs=[
            {
                "id": "leg_to_transfer",
                "from_place_id": "origin",
                "to_place_id": "transfer",
                "duration_s": walk_s,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_to_dest",
                "from_place_id": "transfer",
                "to_place_id": "dest",
                "duration_s": walk_s,
                "mode": "walk",
                "shared_resource_ids": [],
            },
        ],
        stages=[
            {"id": "walk_1", "kind": "travel", "leg_id": "leg_to_transfer"},
            {"id": "walk_2", "kind": "travel", "leg_id": "leg_to_dest"},
        ],
        students=[
            {
                "part_id": "part_h",
                "group_id": "g_h",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 2},
                "members": _members("h", 2),
                "required_supervision": {"escorts": 1},
            }
        ],
        workers=[
            _worker("w_a", "escort", "origin"),
            _worker("w_b", "escort", "transfer"),
        ],
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "escorts_per_group": 1,
            "permitted_handover_places": ["transfer"],
            "handover_s": 0,
        },
    )


def build_exclusive_duty_case(*, walk_s: float = 40.0) -> tuple[dict, dict]:
    """One escort cannot cover two groups at the same time."""
    return _shell(
        scenario_id="exclusive_duties_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("dest", 0.001, 0.0, "destination"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": walk_s,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
        students=[
            {
                "part_id": "part_1",
                "group_id": "g_1",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("p", 1),
                "required_supervision": {"escorts": 1},
            },
            {
                "part_id": "part_2",
                "group_id": "g_2",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("q", 1),
                "required_supervision": {"escorts": 1},
            },
        ],
        workers=[_worker("w1", "escort", "origin")],
        worker_travel=[
            {
                "from_place_id": "dest",
                "to_place_id": "origin",
                "duration_s": walk_s,
            }
        ],
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "escorts_per_group": 1,
            "permitted_handover_places": ["dest"],
        },
    )


def build_physical_split_case(*, internal_part_size: int | None = None) -> tuple[dict, dict]:
    """Bus capacity split needs an escort on each physical part before it moves."""
    members = _members("s", 4)
    policy_extra: dict[str, Any] = {
        "grouping": {
            "mode": "explicit_parts",
            "split_policy": "permit_supervised_split",
            "escorts_per_group": 1,
        }
    }
    if internal_part_size is not None:
        policy_extra["grouping"]["internal_part_size"] = internal_part_size
        return _shell(
            scenario_id="internal_part_size_escorts_v1",
            places=[
                _unbounded("origin", 0.0, 0.0, "origin"),
                _unbounded("dest", 0.001, 0.0, "destination"),
            ],
            legs=[
                {
                    "id": "walk_1",
                    "from_place_id": "origin",
                    "to_place_id": "dest",
                    "duration_s": 10,
                    "mode": "walk",
                    "shared_resource_ids": [],
                }
            ],
            stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
            students=[
                {
                    "part_id": "part_walk",
                    "group_id": "g_walk",
                    "source_unit_id": "su_origin",
                    "place_id": "origin",
                    "hostel_id": "synthetic",
                    "hostel_composition": {"synthetic": 4},
                    "members": members,
                    "required_supervision": {"escorts": 1},
                    "internal_part_size": internal_part_size,
                }
            ],
            workers=[_worker("w1", "escort", "origin")],
            operating_rules={
                "required_endpoint": "stage_complete",
                "require_escorts": True,
                "escorts_per_group": 1,
                "permitted_handover_places": ["dest"],
            },
            policy_extra=policy_extra,
        )
    return _shell(
        scenario_id="physical_split_escorts_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("boarding", 0.001, 0.0, "boarding"),
            _unbounded("dest", 0.002, 0.0, "alighting"),
        ],
        legs=[
            {
                "id": "to_berth",
                "from_place_id": "origin",
                "to_place_id": "boarding",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "bus_ride",
                "from_place_id": "boarding",
                "to_place_id": "dest",
                "duration_s": 20,
                "mode": "coach",
                "shared_resource_ids": ["bus_1"],
            },
        ],
        stages=[
            {"id": "to_berth", "kind": "travel", "leg_id": "to_berth"},
            {
                "id": "boarding",
                "kind": "batch_service",
                "place_id": "boarding",
                "resource_id": "bus_1",
                "action": "board",
                "duration_s": 5,
            },
            {
                "id": "ride",
                "kind": "vehicle_travel",
                "leg_id": "bus_ride",
                "resource_id": "bus_1",
            },
            {
                "id": "alighting",
                "kind": "batch_service",
                "place_id": "dest",
                "resource_id": "bus_1",
                "action": "alight",
                "duration_s": 5,
            },
        ],
        students=[
            {
                "part_id": "part_bus",
                "group_id": "g_bus",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 4},
                "members": members,
                "required_supervision": {"escorts": 1},
            }
        ],
        workers=[
            _worker("w1", "escort", "origin"),
            _worker("w2", "escort", "boarding"),
        ],
        vehicles=[
            {
                "id": "bus_1",
                "type": "coach",
                "place_id": "boarding",
                "available_time_s": 0,
                "capacity_students": 2,
            }
        ],
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "escorts_per_group": 1,
            "permitted_handover_places": ["dest"],
        },
        policy_extra=policy_extra,
    )


def build_zero_workers_case() -> tuple[dict, dict]:
    return _shell(
        scenario_id="zero_workers_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("dest", 0.001, 0.0, "destination"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 10,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
        students=[
            {
                "part_id": "part_walk",
                "group_id": "g_walk",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 2},
                "members": _members("z", 2),
                "required_supervision": {"escorts": 1},
            }
        ],
        workers=[],
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "escorts_per_group": 1,
        },
        simulation_end_s=100,
    )


def build_insufficient_staff_case() -> tuple[dict, dict]:
    return _shell(
        scenario_id="insufficient_station_staff_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("entrance", 0.001, 0.0, "entrance"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "entrance",
                "duration_s": 1,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
            {
                "id": "entrance_service",
                "kind": "queue_service",
                "place_id": "entrance",
                "service_duration_s": 10,
                "server_count": 1,
                "queue_discipline": "fcfs",
            },
        ],
        students=[
            {
                "part_id": "part_q",
                "group_id": "g_q",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 2},
                "members": _members("i", 2),
            }
        ],
        workers=[_worker("w1", "station", "entrance")],
        operating_rules={
            "required_endpoint": "service_complete",
            "min_station_staff": {"entrance": 3},
        },
        deadline_s=95,
        simulation_end_s=200,
    )


def build_combined_escort_count_case(*, permitted: bool) -> tuple[dict, dict]:
    workers = [_worker("w1", "ppsl", "origin", roles=["escort", "count"])]
    if not permitted:
        workers.append(_worker("w2", "ppsl", "origin", roles=["escort", "count"]))
    combined_places = ["origin"] if permitted else []
    checkpoint = {
        "id": "cp_origin",
        "location_id": "origin",
        "required": True,
        "permitted_methods": ["column"],
        "stage_id": "origin_count",
        "max_retries": 0,
        "column": {
            "setup_s": 0,
            "cadence_s_per_person": 1,
            "aggregation_s": 0,
            "space_columns": 1,
            "workers_per_column": 1,
            "requested_columns": 1,
        },
    }
    scenario, policy = _shell(
        scenario_id="combined_escort_count_v1" if permitted else "separate_escort_count_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("dest", 0.001, 0.0, "destination"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 10,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {
                "id": "origin_count",
                "kind": "manual_count",
                "place_id": "origin",
                "checkpoint_id": "cp_origin",
                "method": "column",
            },
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
        ],
        students=[
            {
                "part_id": "part_c",
                "group_id": "g_c",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 4},
                "members": _members("c", 4),
                "required_supervision": {"escorts": 1},
                "count_record_ids": [],
                "covered_checkpoint_ids": [],
            }
        ],
        workers=workers,
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "escorts_per_group": 1,
            "required_checkpoints": ["cp_origin"],
            "permitted_counting_locations": ["origin"],
            "combined_escort_and_count_places": combined_places,
            "permitted_handover_places": ["dest"],
        },
        checkpoints=[checkpoint],
        policy_extra={
            "grouping": {"mode": "explicit_parts", "escorts_per_group": 1},
            "counting": {
                "required_checkpoints": ["cp_origin"],
                "assignments": {
                    "cp_origin": {"location_id": "origin", "method": "column", "requested_columns": 1}
                },
            },
        },
    )
    return scenario, policy


def build_min_station_staff_policy_case() -> tuple[dict, dict]:
    return build_station_queue_case(worker_count=3, min_station_staff=2, server_count=2)


def build_station_queue_case(
    *,
    worker_count: int,
    min_station_staff: int = 1,
    server_count: int = 2,
    service_duration_s: float = 10.0,
    student_count: int = 4,
) -> tuple[dict, dict]:
    members = _members("s", student_count)
    workers = [_worker(f"st{index}", "station", "entrance") for index in range(worker_count)]
    return _shell(
        scenario_id=f"station_queue_{worker_count}w_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("entrance", 0.001, 0.0, "entrance"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "entrance",
                "duration_s": 0,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
            {
                "id": "entrance_service",
                "kind": "queue_service",
                "place_id": "entrance",
                "service_duration_s": service_duration_s,
                "server_count": server_count,
                "queue_discipline": "fcfs",
            },
        ],
        students=[
            {
                "part_id": "part_q",
                "group_id": "g_q",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": student_count},
                "members": members,
            }
        ],
        workers=workers,
        operating_rules={
            "required_endpoint": "service_complete",
            "min_station_staff": {"entrance": min_station_staff},
        },
        deadline_s=95,
    )


def build_contended_assembly_case(
    *,
    worker_available_s: float = 0.0,
    assembly_place_id: str = "origin",
    worker_place_id: str = "origin",
    worker_travel: list[dict] | None = None,
) -> tuple[dict, dict]:
    """Two groups each need the only assembly worker."""
    travel = worker_travel
    if travel is None and worker_place_id != assembly_place_id:
        travel = [
            {
                "from_place_id": worker_place_id,
                "to_place_id": assembly_place_id,
                "duration_s": 30,
            }
        ]
    return _shell(
        scenario_id="contended_assembly_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("yard", 0.0, 0.001, "assembly yard"),
            _unbounded("dest", 0.001, 0.0, "destination"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
        students=[
            {
                "part_id": "part_a",
                "group_id": "g_a",
                "source_unit_id": "su_a",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("a", 1, "su_a"),
            },
            {
                "part_id": "part_b",
                "group_id": "g_b",
                "source_unit_id": "su_b",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("b", 1, "su_b"),
            },
        ],
        source_units=[
            {
                "id": "su_a",
                "hostel_id": "synthetic",
                "estimated_attendance": 1,
                "resolved_attendance": 1,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            },
            {
                "id": "su_b",
                "hostel_id": "synthetic",
                "estimated_attendance": 1,
                "resolved_attendance": 1,
                "actual_reporting_s": 0,
                "readiness_s": 0,
            },
        ],
        workers=[
            _worker(
                "w1",
                "escort",
                worker_place_id,
                available_time_s=worker_available_s,
            )
        ],
        worker_travel=travel,
        operating_rules={"required_endpoint": "stage_complete"},
        policy_extra={
            "grouping": {
                "mode": "explicit_parts",
                "physical_assembly": {
                    "duration_s": 10,
                    "place_id": assembly_place_id,
                    "worker_count": 1,
                },
            }
        },
    )


def build_escort_ratio_grouping_override_case() -> tuple[dict, dict]:
    """100 students, one escort per 20, grouping offers one escort."""
    members = _members("s", 100)
    workers = [_worker(f"w{index}", "escort", "origin") for index in range(1, 6)]
    return _shell(
        scenario_id="escort_ratio_override_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("dest", 0.001, 0.0, "destination"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
        students=[
            {
                "part_id": "part_100",
                "group_id": "g_100",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 100},
                "members": members,
                "required_supervision": {"escorts": 1},
            }
        ],
        workers=workers,
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "staffing_ratio": {"students_per_escort": 20},
        },
        policy_extra={
            "grouping": {
                "mode": "explicit_parts",
                "escorts_per_group": 1,
            }
        },
    )


def build_late_calendar_case(*, walk_s: float = 80.0, open_s: float = 40.0) -> tuple[dict, dict]:
    return _shell(
        scenario_id="late_worker_calendar_v1",
        places=[
            _unbounded("origin", 0.0, 0.0, "origin"),
            _unbounded("dest", 0.001, 0.0, "destination"),
        ],
        legs=[
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": walk_s,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        stages=[{"id": "walk", "kind": "travel", "leg_id": "walk_1"}],
        students=[
            {
                "part_id": "part_early",
                "group_id": "g_early",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("e", 1),
                "required_supervision": {"escorts": 1},
            },
            {
                "part_id": "part_late",
                "group_id": "g_late",
                "source_unit_id": "su_origin",
                "place_id": "origin",
                "hostel_id": "synthetic",
                "hostel_composition": {"synthetic": 1},
                "members": _members("l", 1),
                "required_supervision": {"escorts": 1},
            },
        ],
        workers=[
            _worker("w_early", "escort", "origin"),
            _worker("w_late", "escort", "origin", calendar_id="late_shift"),
        ],
        calendars=[
            {
                "id": "late_shift",
                "kind": "worker_shift",
                "place_id": "origin",
                "open_time_s": open_s,
                "imposed": True,
                "label": "late worker availability",
            }
        ],
        operating_rules={
            "required_endpoint": "stage_complete",
            "require_escorts": True,
            "escorts_per_group": 1,
            "permitted_handover_places": ["dest"],
        },
    )
