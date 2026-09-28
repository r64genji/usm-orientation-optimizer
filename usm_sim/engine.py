"""Deterministic discrete-event movement engine for ticket 01."""

from __future__ import annotations

import copy
import heapq
import random
from dataclasses import dataclass, field
from typing import Any, Mapping

from usm_sim.constants import (
    ENGINE_VERSION,
    BEHAVIOR_ACTIONS,
    EVENT_TYPES,
    PHASE_ARRIVAL_EXTERNAL,
    PHASE_COMPLETION_RELEASE,
    PHASE_REPORT_DECISION,
    PHASE_START_DEPART,
    SOFTWARE_REVISION,
    STAGE_KINDS,
    WAIT_CLASSES,
    WAIT_CLASS_BY_CAUSE,
)
WAIT_CLASS_BY_CAUSE["imposed_sequencing_wait"] = "intentional_hold"
from usm_sim.reports import SpacePolicy
from usm_sim.space import OccupancyLedger
from usm_sim.counting import (
    accumulate_group_counts,
    assignment_for,
    checkpoints_attached_to_stage,
    column_count_duration_s,
    coverage_report,
    draw_observed_count,
    passthrough_batch_duration_s,
    passthrough_person_duration_s,
    reconciliation_status,
    required_checkpoint_ids,
    required_checkpoints_for_part,
)
from usm_sim.errors import SimulationError
from usm_sim.grouping import (
    _composition_from_members,
    _membership_from_members,
    split_part_members,
)
from usm_sim.metrics import compile_metrics, merge_worker_measures
from usm_sim.timeutil import local_iso, ms_to_s, parse_start, to_ms
from usm_sim.workers import WorkerPool

# Re-exported for tests that inspect the modelled surface.
__all__ = ["Engine", "EVENT_TYPES", "STAGE_KINDS"]


@dataclass
class Part:
    part_id: str
    group_id: str
    parent_part_id: str | None
    source_unit_id: str
    hostel_id: str
    hostel_composition: dict[str, int]
    student_count: int
    members: list[dict]
    queue_tie_key: str
    stage_index: int
    place_id: str | None
    leg_id: str | None
    resource_ids: list[str]
    status: str
    waiting_since_ms: int | None = None
    wait_cause: str | None = None
    last_event_id: str | None = None
    arrival_ms: int = 0
    current_stage_id: str | None = None
    parent_group_id: str | None = None
    source_unit_ids: list[str] = field(default_factory=list)
    source_unit_membership: dict[str, int] = field(default_factory=dict)
    count_record_ids: list[str] = field(default_factory=list)
    required_supervision: dict = field(default_factory=dict)
    internal_calculation: bool = False
    covered_checkpoint_ids: list[str] = field(default_factory=list)
    service_duration_ms: int | None = None
    count_session_id: str | None = None
    estimated_occupancy: int | None = None
    escort_ids: list[str] = field(default_factory=list)
    pending_escort_ids: list[str] = field(default_factory=list)
    station_worker_id: str | None = None
    reserved_place_id: str | None = None
    blocked_for_place_id: str | None = None
    aboard: bool = False
    pending_assembly_s: float | None = None
    assembly_start_ms: int | None = None
    assembly_finish_ms: int | None = None
    release_ms: int | None = None
    assembly_worker_ids: list[str] = field(default_factory=list)
    assembly_arrive_pending: bool = False
    shared_held: dict = field(default_factory=dict)
    root_part_id: str | None = None
    version: int = 1
    queue_priority: int = 0
    pending_withdrawal: dict | None = None
    stages: list[dict] | None = None
    cohort_id: str | None = None

@dataclass
class Resource:
    resource_id: str
    kind: str
    place_id: str
    capacity_students: int
    home_place_id: str | None = None
    available: bool = False
    busy: bool = False
    assigned_part_id: str | None = None
    fleet_id: str | None = None
    calendar_id: str | None = None
    earliest_available_ms: int = 0
    return_travel_s: float | None = None
    turnaround_s: float | None = None
    usable_doors: int | None = None
    boarding_setup_s: float | None = None
    boarding_s_per_passenger_per_door: float | None = None
    alighting_setup_s: float | None = None
    alighting_s_per_passenger_per_door: float | None = None
    outages: list = field(default_factory=list)
    seated_capacity_students: int | None = None
    aboard_students: int = 0
    state: str = "idle"
    state_since_ms: int = 0
    state_reason: str | None = None


@dataclass
class CountSession:
    session_id: str
    checkpoint_id: str
    parent_part_id: str
    group_id: str
    source_unit_ids: list[str]
    member_part_ids: list[str]
    remaining: int
    expected: int
    estimated_occupancy: int
    actual_attendance: int
    method: str
    workers: list[str]
    attempt: int
    max_retries: int
    related_event_ids: list[str]
    started_ms: int
    place_id: str | None
    added_student_queue: bool = False
    n_columns: int | None = None
    longest_column: int | None = None
    duration_s: float = 0.0
    is_recount: bool = False
    resource_ids: list[str] = field(default_factory=list)
    batch_action: str | None = None
    already_advanced: bool = False
    pending_recount: bool = False


@dataclass
class WaitInterval:
    part_id: str
    student_count: int
    cause: str
    place_id: str | None
    start_ms: int
    end_ms: int = 0
    resource_id: str | None = None
    secondary_reasons: list = field(default_factory=list)
    related_event_ids: list = field(default_factory=list)


class Engine:
    def __init__(self, scenario: dict, policy: dict) -> None:
        self.scenario = scenario
        self.policy = policy
        self.start_dt = parse_start(
            scenario["event_date"],
            scenario["start_time_local"],
            scenario["timezone"],
        )
        self.deadline_ms = to_ms(scenario["deadline_s"])
        self.simulation_end_ms = to_ms(scenario["simulation_end_s"])
        self.max_events = int(scenario["max_events_per_run"])
        self.required_endpoint = scenario["operating_rules"]["required_endpoint"]
        self.stages = list(scenario["route_stages"])
        self.stages_by_id = {stage["id"]: stage for stage in self.stages}
        self.legs = {leg["id"]: leg for leg in scenario["route_legs"]}
        self.places = {place["id"]: place for place in scenario["places"]}
        self.routes = {
            hostel_id: [self.stages_by_id[stage_id] for stage_id in stage_ids]
            for hostel_id, stage_ids in (scenario.get("routes") or {}).items()
        }
        grouping = policy.get("grouping") or {}
        self.split_policy = grouping.get("split_policy")
        self.mixing_policy = grouping.get("mixing_policy")
        self.regroup_policy = dict(grouping.get("regroup_policy") or {})
        self.adaptation_rule = dict(grouping.get("adaptation_rule") or {})
        self.fleets: dict[str, dict] = {}
        self.fleet_berths_busy: dict[str, int] = {}
        self.fleet_dropoff_busy: dict[str, int] = {}
        self.berth_active_workers: dict[str, list[str]] = {}
        self.max_simultaneous_boarding_berths_used: dict[str, int] = {}
        self.peak_berth_ppsl_workers: dict[str, int] = {}
        self.wait_group: dict[str, list[str]] = {}
        self.now = 0
        self.current_phase = PHASE_COMPLETION_RELEASE
        self.seq = 0
        self.processed = 0
        self.event_n = 0
        self.heap: list[tuple] = []
        self.trace: list[dict] = []
        self.parts: dict[str, Part] = {}
        self.space = OccupancyLedger(self.places)
        self.occupancy = self.space.actual
        self.space_policy = SpacePolicy.from_policy(policy)
        self.wait_entry: dict[str, list[str]] = {}
        self.wait_reserve: dict[str, list[str]] = {}
        self.wait_policy: list[str] = []
        self.wait_path: dict[str, list[str]] = {}
        self.reports: list[dict] = []
        self.report_n = 0
        self.walking_rate_factor = 1.0
        self.closed_legs: set[str] = set()
        self.calendar_open_at: dict[str, int] = {}
        self.shelter_required = False
        self.hard_infeasible = False
        self.queues: dict[str, list[str]] = {}
        self.servers_busy: dict[str, int] = {}
        self.server_count: dict[str, int] = {}
        self.service_duration_ms: dict[str, int] = {}
        self.resources: dict[str, Resource] = {}
        self.wait_calendar: dict[str, list[str]] = {}
        self.wait_resource: dict[str, list[str]] = {}
        self.calendar_open: dict[str, bool] = {}
        self.calendars: dict[str, dict] = {}
        self.completions: list[dict] = []
        self.wait_intervals: list[WaitInterval] = []
        self.wait_hostels_departed: list[tuple[str, list[str], int, str]] = []
        self.open_waits: dict[str, WaitInterval] = {}
        self.violations: list[dict] = []
        self.service_student_ms = 0
        self.count_student_ms = 0
        self.assembly_student_ms = 0
        self.unused_service_ms = 0
        self._starvation_state: dict[str, tuple[int, int]] = {}
        self.peak_queue_students: dict[str, int] = {}
        self.vehicle_intervals: list[dict] = []
        self.over_limit_intervals: list[dict] = []
        self._over_limit_open: dict[str, dict] = {}
        self._begin_depth = 0
        self.rng = random.Random(policy.get("random_seed") or 0)
        self.worker_pool = WorkerPool.from_scenario({}, {})
        self.workers = self.worker_pool.workers
        self.workers_by_id = self.worker_pool.by_id
        self.wait_workers: list[str] = []
        self.checkpoints: dict[str, dict] = {}
        self.count_sessions: dict[str, CountSession] = {}
        self.count_records: list[dict] = []
        self.count_n = 0
        self.session_n = 0
        self.error_assumption: dict = {}
        self.shared_resources: dict[str, dict] = {}
        self.shared_occupancy: dict[str, int] = {}
        self._fleet_last_dispatch_ms: dict[str, int] = {}
        self._fleet_dispatch_scheduled: dict[str, bool] = {}
        self._fleet_vehicle_cursor: dict[str, int] = {}
        self._regroup_in_progress: dict[str, bool] = {}
        self.shared_held_by_part: dict[str, dict[str, int]] = {}
        self.wait_shared: list[str] = []
        self.shared_flow: list[dict] = []
        self.destination: dict = {}
        self.effective_seats: int | None = None
        self.seating_place_id: str | None = None
        self.seated_count = 0
        self.seated_count_by_place: dict[str, int] = {}
        self.pending_queue_jumps: list[dict] = []
        self.executed_behavior_events: set[str] = set()
        self.dtsp_allocated_students = 0
        self.dtsp_carpark_allocated_students = 0
        self.g03_allocated_students = 0
        walking_hostels = {r["hostel_id"] for r in scenario.get("walking_routes") or []}
        self.expected_walking_students = sum(
            int(u.get("resolved_attendance") or 0)
            for u in scenario.get("source_units") or []
            if u.get("hostel_id") in walking_hostels
        )

        self._validate_behavior_response()

        self._apply_reporting_choice()
        self._load_calendars()
        self._load_resources()
        self._load_shared_resources()
        self._load_destination()
        self._load_workers()
        self._load_counting()
        self._load_service_places()
        self._load_parts()
        self._load_background_occupancy()
        self._observe_initial_occupancy()
        self._load_conditions()

    def run(self) -> dict:
        self._schedule_initial()
        termination_cause = "all_completed"
        status = "completed"
        limits_reached: list[str] = []

        while True:
            if self._unfinished_students() == 0 and not self._active_work():
                status = "completed"
                termination_cause = "all_completed"
                break
            if self.processed >= self.max_events:
                status = "incomplete"
                termination_cause = "max_events_per_run"
                limits_reached.append("max_events_per_run")
                break
            if not self.heap:
                if self.hard_infeasible:
                    status = "infeasible"
                    termination_cause = "no_waiting_space"
                    limits_reached.append("no_waiting_space")
                elif self._unfinished_students() > 0:
                    status = "incomplete"
                    termination_cause = "deadlock"
                    limits_reached.append("deadlock")
                else:
                    status = "completed"
                    termination_cause = "all_completed"
                break
            time_ms, phase, _seq, event_type, part_id, payload = self.heap[0]
            if time_ms > self.simulation_end_ms:
                status = "incomplete"
                termination_cause = "simulation_end_s"
                limits_reached.append("simulation_end_s")
                break
            heapq.heappop(self.heap)
            self.now = time_ms
            self.current_phase = phase
            self.processed += 1
            self._dispatch(event_type, part_id, payload)

        unfinished_n = self._unfinished_students()
        if unfinished_n > 0 or self.hard_infeasible or status != "completed":
            self.now = max(self.now, self.simulation_end_ms)
        self._close_open_waits()
        self._close_starvation()
        self._close_vehicle_states()
        self._close_over_limit()
        unfinished = self._unfinished_snapshot()
        if status == "completed" and unfinished:
            status = "incomplete"
            termination_cause = "deadlock"
            limits_reached.append("deadlock")
        if any(row.get("type") == "no_waiting_space" for row in self.violations):
            status = "infeasible"
            termination_cause = "no_waiting_space"
        elif any(row.get("type") == "unresolved_count" for row in self.violations) and (
            status == "completed" or termination_cause == "deadlock"
        ):
            status = "infeasible"
            termination_cause = "unresolved_count"
        elif self.violations and (
            status == "completed" or termination_cause == "deadlock"
        ):
            status = "infeasible"
            termination_cause = "physical_violation"
        if status == "completed":
            required_ids = required_checkpoint_ids(self.scenario)
            coverage = coverage_report(required_ids, self.count_records)
            if coverage["unresolved"] or any(
                row.get("outcome") == "unresolved" for row in self.count_records
            ):
                status = "infeasible"
                termination_cause = "unresolved_count"
            elif coverage["missing"]:
                status = "infeasible"
                termination_cause = "missing_required_checkpoint"
                self.violations.append(
                    {
                        "type": "missing_required_checkpoint",
                        "checkpoint_ids": list(coverage["missing"]),
                        "outcome": "incomplete",
                    }
                )
            else:
                uncovered = self._parts_missing_checkpoints()
                if uncovered:
                    status = "infeasible"
                    termination_cause = "missing_required_checkpoint"
                    self.violations.append(
                        {
                            "type": "missing_required_checkpoint",
                            "checkpoint_ids": sorted(
                                {
                                    checkpoint_id
                                    for row in uncovered
                                    for checkpoint_id in row["checkpoint_ids"]
                                }
                            ),
                            "parts": uncovered,
                            "outcome": "incomplete",
                        }
                    )

        return self._result(status, termination_cause, limits_reached, unfinished)

    def _apply_reporting_choice(self) -> None:
        operating = dict(self.scenario.get("operating_rules") or {})
        choice = self.policy.get("reporting_time_s")
        nested = self.policy.get("reporting") or {}
        if choice is None and isinstance(nested, dict):
            choice = nested.get("required_reporting_s") or nested.get("reporting_time_s")
        rule = operating.get("attendance_response_rule") or self.policy.get("attendance_response_rule") or {}
        rule_type = rule.get("type") if isinstance(rule, dict) else rule
        for unit in self.scenario.get("source_units") or []:
            if unit.get("required_reporting_s") is None and choice is not None:
                unit["required_reporting_s"] = float(choice)
            if str(rule_type or "fixed") == "report_at_instruction":
                required = unit.get("required_reporting_s")
                if required is None:
                    required = unit.get("actual_reporting_s") or 0
                availability = unit.get("availability_s")
                if availability is None:
                    availability = 0
                unit["actual_reporting_s"] = max(float(availability), float(required))

    def _load_calendars(self) -> None:
        for raw in self.scenario.get("calendars") or []:
            calendar_id = raw["id"]
            self.calendars[calendar_id] = raw
            self.calendar_open[calendar_id] = False
            self.wait_calendar[calendar_id] = []
            self.calendar_open_at[calendar_id] = to_ms(raw["open_time_s"])

    def _load_resources(self) -> None:
        for vehicle in self.scenario["initial_state"]["vehicles"]:
            type_fields = dict(vehicle.get("_type_fields") or {})
            resource = Resource(
                resource_id=vehicle["id"],
                kind=vehicle["type"],
                place_id=vehicle["place_id"],
                home_place_id=vehicle["place_id"],
                capacity_students=int(vehicle["capacity_students"]),
                calendar_id=vehicle.get("calendar_id"),
                earliest_available_ms=to_ms(vehicle["available_time_s"]),
                return_travel_s=_first_present(
                    vehicle.get("return_travel_s"), type_fields.get("return_travel_s")
                ),
                turnaround_s=_first_present(
                    vehicle.get("turnaround_s"), type_fields.get("turnaround_s")
                ),
                usable_doors=_first_present(
                    vehicle.get("usable_doors"), type_fields.get("usable_doors")
                ),
                boarding_setup_s=_first_present(
                    vehicle.get("boarding_setup_s"), type_fields.get("boarding_setup_s")
                ),
                boarding_s_per_passenger_per_door=_first_present(
                    vehicle.get("boarding_s_per_passenger_per_door"),
                    type_fields.get("boarding_s_per_passenger_per_door"),
                ),
                alighting_setup_s=_first_present(
                    vehicle.get("alighting_setup_s"), type_fields.get("alighting_setup_s")
                ),
                alighting_s_per_passenger_per_door=_first_present(
                    vehicle.get("alighting_s_per_passenger_per_door"),
                    type_fields.get("alighting_s_per_passenger_per_door"),
                ),
                outages=list(vehicle.get("outages") or []),
                seated_capacity_students=_first_present(
                    vehicle.get("seated_capacity_students"),
                    type_fields.get("seated_capacity_students"),
                ),
            )
            self.resources[resource.resource_id] = resource
            self.wait_resource[resource.resource_id] = []
        v_rule = self.policy.get("vehicle_dispatch_rule") or {}
        policy_berths = (
            v_rule.get("simultaneous_boarding_berths")
            if v_rule.get("simultaneous_boarding_berths") is not None
            else self.policy.get("simultaneous_boarding_berths")
        )
        for fleet in self.scenario.get("fleets") or []:
            fleet_id = fleet["id"]
            fleet_dict = dict(fleet)
            if policy_berths is not None:
                fleet_dict["boarding_berth_capacity"] = min(4, max(1, int(policy_berths)))
            self.fleets[fleet_id] = fleet_dict
            self.fleet_berths_busy[fleet_id] = 0
            self.fleet_dropoff_busy[fleet_id] = 0
            self.max_simultaneous_boarding_berths_used[fleet_id] = 0
            self.peak_berth_ppsl_workers[fleet_id] = 0
            self.wait_resource.setdefault(fleet_id, [])
            for vehicle_id in fleet["vehicle_ids"]:
                self.resources[vehicle_id].fleet_id = fleet_id

    def _load_shared_resources(self) -> None:
        for raw in self.scenario.get("shared_resources") or []:
            self.shared_resources[raw["id"]] = dict(raw)

    def _load_destination(self) -> None:
        dest = dict(self.scenario.get("destination") or {})
        self.destination = dest
        if not dest or dest.get("available_seats") is None:
            return
        initial = int(dest.get("initial_occupants") or 0)
        reserved = int(dest.get("reserved_seating") or 0)
        self.effective_seats = int(dest["available_seats"]) - initial - reserved
        self.seating_place_id = dest.get("seating_place_id")

    def _walk_occupancy_rule(self) -> dict | None:
        operating = self.scenario.get("operating_rules") or {}
        rule = operating.get("walk_occupancy_rule")
        return rule if isinstance(rule, dict) else None

    def _occupancy_ahead_for_walk(self, part: Part | None, leg: dict) -> int:
        self_id = part.part_id if part is not None else None
        shared_ids = [
            resource_id
            for resource_id in (leg.get("shared_resource_ids") or [])
            if resource_id in self.shared_resources
        ]
        counted: set[str] = set()
        ahead = 0
        for other in self.parts.values():
            if self_id and other.part_id == self_id:
                continue
            if other.status != "travelling":
                continue
            same_leg = other.leg_id == leg.get("id")
            held = self.shared_held_by_part.get(other.part_id) or {}
            same_shared = bool(shared_ids) and any(resource_id in held for resource_id in shared_ids)
            if not same_leg and not same_shared:
                continue
            if other.part_id in counted:
                continue
            counted.add(other.part_id)
            ahead += int(other.student_count)
        return ahead

    def _walk_congested_threshold(self, leg: dict, rule: dict) -> int | None:
        limits: list[int] = []
        use_operating = rule.get("congested_at") != "capacity"
        for resource_id in leg.get("shared_resource_ids") or []:
            resource = self.shared_resources.get(resource_id) or {}
            if use_operating and resource.get("operating_limit_students") is not None:
                limits.append(int(resource["operating_limit_students"]))
            elif resource.get("capacity_students") is not None:
                limits.append(int(resource["capacity_students"]))
        if not limits:
            return None
        return min(limits)

    def _leg_timing(
        self, leg: dict, part: Part | None = None
    ) -> tuple[float, int, float, float]:
        unique = float(leg["duration_s"])
        extra = 0.0
        exit_path_extra = 0.0
        for resource_id in leg.get("shared_resource_ids") or []:
            resource = self.shared_resources.get(resource_id) or {}
            if resource.get("duration_s") is not None:
                dur = float(resource["duration_s"])
                is_streaming = resource.get("continuous_streaming") is True or resource_id in (
                    "path_carpark_single_file",
                    "path_north_plaza_single_file",
                    "path_south_plaza_single_file",
                )
                if not is_streaming:
                    extra += dur
                else:
                    exit_path_extra += dur
        occupancy_ahead = 0
        factor = 1.0
        extra_applied = extra
        rule = self._walk_occupancy_rule()
        if rule and leg.get("mode") == "walk":
            occupancy_ahead = self._occupancy_ahead_for_walk(part, leg)
            empty_factor = float(rule.get("empty_duration_factor") or 1.0)
            congested_factor = float(rule.get("congested_duration_factor") or 1.0)
            limit = self._walk_congested_threshold(leg, rule)
            if occupancy_ahead <= 0:
                factor = empty_factor
                extra_applied = exit_path_extra if unique <= 0 else 0.0
            elif limit is not None and occupancy_ahead >= limit:
                factor = congested_factor
                extra_applied = extra
            else:
                factor = empty_factor
                extra_applied = extra
            duration = unique * factor + extra_applied * factor
            if exit_path_extra > 0 and duration <= 0:
                duration = exit_path_extra * factor
                extra_applied = exit_path_extra
        else:
            duration = unique + extra
        if leg.get("mode") == "walk" and self.walking_rate_factor not in (0, None):
            duration = duration / float(self.walking_rate_factor)
        return duration, occupancy_ahead, factor, extra_applied

    def _leg_duration_s(self, leg: dict, part: Part | None = None) -> float:
        duration, _, _, _ = self._leg_timing(leg, part)
        return duration

    def _leg_event_resource_ids(self, leg: dict, part: Part) -> list[str]:
        ids = list(part.resource_ids)
        for resource_id in leg.get("shared_resource_ids") or []:
            if resource_id not in ids:
                ids.append(resource_id)
        return ids

    def _destination_summary(self) -> dict | None:
        dest = self.destination
        if not dest:
            return None
        doors = list(dest.get("doors") or [])
        available = dest.get("available_seats")
        initial = int(dest.get("initial_occupants") or 0)
        reserved = int(dest.get("reserved_seating") or 0)
        summary = {
            "available_seats": available,
            "initial_occupants": initial,
            "reserved_seating": reserved,
            "effective_seats": self.effective_seats,
            "door_count": len(doors),
            "seating_rate_s_per_person": dest.get("seating_rate_s_per_person"),
            "exterior_storage_students": dest.get("exterior_storage_students"),
            "foyer_storage_students": dest.get("foyer_storage_students"),
            "shared_internal_path_ids": list(dest.get("shared_internal_path_ids") or []),
            "seated_students": self.seated_count,
        }
        return summary

    def _load_workers(self) -> None:
        self.worker_pool = WorkerPool.from_scenario(self.scenario, self.policy)
        self.workers = self.worker_pool.workers
        self.workers_by_id = self.worker_pool.by_id
        if self.worker_pool.permanently_understaffed():
            self.violations.append(
                {
                    "type": "insufficient_staff",
                    "message": self.worker_pool.understaffed_reason(),
                }
            )

    def _load_counting(self) -> None:
        for raw in self.scenario.get("checkpoints") or []:
            self.checkpoints[raw["id"]] = dict(raw)
        assumptions = list(self.scenario.get("count_error_assumptions") or [])
        self.error_assumption = dict(assumptions[0]) if assumptions else {
            "id": "implicit_no_error",
            "exposure_unit": "checkpoint_pass",
            "relationship_to_load": "none",
            "p_mismatch": 0.0,
        }

    def _load_service_places(self) -> None:
        for stage in self.stages:
            if stage["kind"] != "queue_service":
                continue
            place_id = stage["place_id"]
            self.queues[place_id] = []
            self.servers_busy[place_id] = 0
            self.server_count[place_id] = int(stage["server_count"])
            self.service_duration_ms[place_id] = to_ms(stage["service_duration_s"])

    def _load_parts(self) -> None:
        for raw in self.scenario["initial_state"]["students"]:
            members = list(raw["members"])
            composition = dict(raw.get("hostel_composition") or {})
            hostel_id = raw.get("hostel_id")
            if not hostel_id and len(composition) == 1:
                hostel_id = next(iter(composition))
            if not hostel_id:
                hostel_id = raw["source_unit_id"]
            if not composition:
                composition = {hostel_id: len(members)}
            source_unit_ids = list(raw.get("source_unit_ids") or [raw["source_unit_id"]])
            membership = dict(
                raw.get("source_unit_membership") or {raw["source_unit_id"]: len(members)}
            )
            occupancy = raw.get("estimated_occupancy")
            if occupancy is None:
                unit = next(
                    (
                        row
                        for row in self.scenario["source_units"]
                        if row["id"] == raw["source_unit_id"]
                    ),
                    None,
                )
                if unit is not None:
                    occupancy = unit.get("estimated_occupancy")
            q_prio = raw.get("queue_priority")
            if q_prio is None:
                unit = next(
                    (
                        row
                        for row in self.scenario.get("source_units") or []
                        if row["id"] == raw["source_unit_id"]
                    ),
                    None,
                )
                if unit is not None:
                    q_prio = unit.get("queue_priority")
            if q_prio is None:
                if hostel_id == "tekun":
                    q_prio = -2
                elif hostel_id == "saujana":
                    q_prio = -1
                elif hostel_id == "restu":
                    q_prio = 1
                else:
                    q_prio = 0
            part = Part(
                part_id=raw["part_id"],
                group_id=raw["group_id"],
                parent_part_id=raw.get("parent_part_id"),
                source_unit_id=raw["source_unit_id"],
                hostel_id=hostel_id,
                hostel_composition=composition,
                student_count=len(members),
                members=members,
                queue_tie_key=str(members[0]["queue_tie_key"]),
                stage_index=0,
                place_id=raw["place_id"],
                leg_id=raw.get("leg_id"),
                resource_ids=list(raw.get("resource_ids") or []),
                status=str(raw.get("status") or "pending"),
                arrival_ms=0,
                parent_group_id=raw.get("parent_group_id") or raw["group_id"],
                source_unit_ids=source_unit_ids,
                source_unit_membership=membership,
                count_record_ids=list(raw.get("count_record_ids") or []),
                required_supervision=dict(raw.get("required_supervision") or {}),
                internal_calculation=bool(raw.get("internal_calculation")),
                covered_checkpoint_ids=list(raw.get("covered_checkpoint_ids") or []),
                estimated_occupancy=int(occupancy) if occupancy is not None else len(members),
                escort_ids=list(raw.get("escort_ids") or []),
                aboard=bool(raw.get("aboard")),
                root_part_id=raw.get("root_part_id") or raw.get("parent_part_id") or raw["part_id"],
                version=int(raw.get("version") or 1),
                queue_priority=int(q_prio),
            )
            c_id = raw.get("cohort_id")
            if not c_id and raw.get("cohort_ids"):
                c_id = raw["cohort_ids"][0]
            if not c_id and members and members[0].get("cohort_id"):
                c_id = members[0]["cohort_id"]
            part.cohort_id = c_id
            if raw.get("arrival_s") is not None:
                part.arrival_ms = to_ms(raw["arrival_s"])
            if part.part_id in self.parts:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"duplicate part id {part.part_id!r}",
                    field="scenario.initial_state.students.part_id",
                )
            self.parts[part.part_id] = part
            if part.status == "travelling":
                token = (
                    f"aboard:{part.resource_ids[0]}"
                    if part.resource_ids
                    else f"leg:{part.leg_id or 'in_motion'}"
                )
                self.space.locate_members(part, token, 0)
                if part.resource_ids:
                    part.aboard = True
                    resource = self.resources.get(part.resource_ids[0])
                    if resource is not None:
                        resource.aboard_students = part.student_count
                        resource.busy = True
                        resource.available = False
                        resource.assigned_part_id = part.part_id
            elif part.place_id:
                if not self.space.occupy(part.place_id, part, 0):
                    self.violations.append(
                        {
                            "type": "physical_capacity",
                            "place_id": part.place_id,
                            "occupancy": self.space.committed(part.place_id)
                            + part.student_count,
                            "capacity_students": self.space.physical_students(
                                part.place_id
                            ),
                            "part_id": part.part_id,
                        }
                    )

    def _validate_behavior_response(self) -> None:
        scenario_behavior = self.scenario.get("behavior")
        active_triggers: set[str] = set()
        if isinstance(scenario_behavior, Mapping):
            for event in scenario_behavior.get("events") or []:
                if isinstance(event, Mapping):
                    phenom = event.get("phenomenon")
                    if phenom:
                        active_triggers.add(phenom)
            for phenom, cfg in (scenario_behavior.get("phenomena") or {}).items():
                if isinstance(cfg, Mapping) and cfg:
                    if any(v for v in cfg.values() if v not in (0, 0.0, None, False, [], {})):
                        active_triggers.add(phenom)
        active_triggers.discard("no_show")

        br = self.policy.get("behavior_response") or (self.policy.get("grouping") or {}).get("behavior_response")
        claims_to_handle = (
            br is not None
            or bool(self.policy.get("handles_case"))
            or bool(self.policy.get("behavior_case_id"))
            or bool(self.policy.get("claims_to_handle"))
            or (
                isinstance(scenario_behavior, Mapping)
                and scenario_behavior.get("case_id")
                and str(self.policy.get("policy_id", "")).startswith(str(scenario_behavior.get("case_id", "")))
            )
        )

        if claims_to_handle and br is None:
            raise SimulationError(
                "missing_input",
                "policy claims to handle named behavior case but does not specify behavior_response",
                field="policy.behavior_response",
            )

        if br is not None and active_triggers:
            covered = self._covered_behavior_triggers(br)
            for act_trig in sorted(active_triggers):
                if act_trig not in covered:
                    raise SimulationError(
                        "missing_input",
                        f"missing behavior_response for active case trigger {act_trig!r}",
                        field=f"policy.behavior_response.{act_trig}",
                    )

    def _covered_behavior_triggers(self, br: Any) -> set[str]:
        covered: set[str] = set()
        rules = []
        if isinstance(br, Mapping):
            rules = list(br.get("rules") or [])
            if br.get("by_trigger"):
                for t, r in br["by_trigger"].items():
                    covered.add(t)
                    if isinstance(r, Mapping):
                        rules.append(r)
            if br.get("by_location"):
                for loc, r in br["by_location"].items():
                    covered.add(loc)
                    if isinstance(r, Mapping):
                        rules.append(r)
        elif isinstance(br, list):
            rules = br

        for rule in rules:
            act = rule.get("action")
            trig = rule.get("trigger") or rule.get("phenomenon")
            if trig:
                covered.add(trig)
            loc = rule.get("place_id") or rule.get("location")
            if loc:
                covered.add(loc)
            if act:
                act_norm = act.replace("-", "_")
                covered.add(act_norm)
            if act:
                act_norm = act.replace("-", "_")
                if act_norm in ("refuse_queue_jump", "allow_queue_jump"):
                    covered.add("queue_jump")
                if act_norm == "intercept_at_station":
                    covered.add("late_reporting")
                    covered.add("queue_jump")
                    covered.add("catch_up_walk")
                    covered.add("mixed_readiness")
                if act_norm in ("wait", "wait_for_stragglers", "split_and_go", "hold_bus", "bump_next_vehicle", "bump_to_next_vehicle"):
                    covered.add("late_reporting")
                    covered.add("mixed_readiness")
                if act_norm == "refuse_unescorted_walk":
                    covered.add("route_deviation")
                    covered.add("schedule_departure")
                    covered.add("catch_up_walk")
                if act_norm in ("deny", "deny_onward_service"):
                    covered.add("stage_skip")
                    covered.add("route_deviation")
                    covered.add("withdrawal")
        return covered

    def _get_behavior_rule(self, trigger: str, place_id: str | None = None) -> dict | None:
        br = self.policy.get("behavior_response") or (self.policy.get("grouping") or {}).get("behavior_response")
        if not br:
            return None
        if isinstance(br, Mapping):
            by_loc = br.get("by_location")
            if by_loc and place_id and place_id in by_loc:
                return dict(by_loc[place_id])
            by_trig = br.get("by_trigger")
            if by_trig and trigger in by_trig:
                return dict(by_trig[trigger])
            rules = br.get("rules") or []
        elif isinstance(br, list):
            rules = br
        else:
            return None

        for rule in rules:
            if not isinstance(rule, Mapping):
                continue
            r_loc = rule.get("place_id") or rule.get("location")
            r_trig = rule.get("trigger") or rule.get("phenomenon")
            if r_loc and place_id and r_loc == place_id:
                return dict(rule)
            if r_trig and r_trig == trigger:
                return dict(rule)
        return None

    def _composition_from_members(self, members: list[dict]) -> dict[str, int]:
        comp: dict[str, int] = {}
        for m in members:
            h = m.get("hostel_id") or "unknown"
            comp[h] = comp.get(h, 0) + 1
        return comp

    def _su_membership_from_members(self, members: list[dict]) -> dict[str, int]:
        mem: dict[str, int] = {}
        for m in members:
            su = m.get("source_unit_id") or "unknown"
            mem[su] = mem.get(su, 0) + 1
        return mem

    def _next_late_part_id(self, part: Part, event_id: str | None = None) -> str:
        root = part.root_part_id or part.part_id
        first_candidate = f"{part.part_id}_late"
        if first_candidate not in self.parts and not part.part_id.endswith("_late"):
            return first_candidate
        tag = event_id or f"split_{self.event_n + 1}"
        candidate = f"{root}_late_{tag}"
        suffix = 1
        while candidate in self.parts:
            candidate = f"{root}_late_{tag}_{suffix}"
            suffix += 1
        return candidate

    def _split_part(
        self,
        part: Part,
        on_time_members: list[dict],
        late_members: list[dict],
        cutoff_s: float | None = None,
        cause: str = "assembly_cutoff",
        event_id: str | None = None,
    ) -> Part:
        parent_id = part.part_id
        root_id = part.root_part_id or part.part_id
        part.version += 1

        late_id = self._next_late_part_id(part, event_id)
        late_part = copy.deepcopy(part)
        late_part.part_id = late_id
        late_part.parent_part_id = parent_id
        late_part.root_part_id = root_id
        late_part.version = 1
        late_part.members = late_members
        late_part.student_count = len(late_members)
        late_part.queue_tie_key = str(late_members[0]["queue_tie_key"])
        late_part.hostel_composition = self._composition_from_members(late_members)
        late_part.source_unit_membership = self._su_membership_from_members(late_members)
        late_part.source_unit_ids = sorted(late_part.source_unit_membership.keys())
        if len(late_part.hostel_composition) == 1:
            late_part.hostel_id = next(iter(late_part.hostel_composition))
        if len(late_part.source_unit_ids) == 1:
            late_part.source_unit_id = late_part.source_unit_ids[0]
        late_part.escort_ids = []
        late_part.pending_escort_ids = []
        late_part.station_worker_id = None
        late_part.resource_ids = []
        late_part.aboard = False
        late_part.shared_held = {}
        late_part.status = "pending"

        part.members = on_time_members
        part.student_count = len(on_time_members)
        part.queue_tie_key = str(on_time_members[0]["queue_tie_key"])
        part.hostel_composition = self._composition_from_members(on_time_members)
        part.source_unit_membership = self._su_membership_from_members(on_time_members)
        part.source_unit_ids = sorted(part.source_unit_membership.keys())
        if len(part.hostel_composition) == 1:
            part.hostel_id = next(iter(part.hostel_composition))
        if len(part.source_unit_ids) == 1:
            part.source_unit_id = part.source_unit_ids[0]
        part.root_part_id = root_id

        self.parts[late_id] = late_part

        if late_part.place_id:
            token = f"place:{late_part.place_id}"
            self.space.locate_members(late_part, token, self.now)

        self.emit(
            "part_split",
            part,
            parent_part_id=parent_id,
            child_part_ids=[part.part_id, late_part.part_id],
            cause=cause,
            cutoff_s=cutoff_s,
            place_id=part.place_id,
            counts={part.part_id: part.student_count, late_part.part_id: late_part.student_count},
        )
        return late_part

    def _check_station_intercept(
        self,
        part: Part,
        place_id: str,
        trigger_name: str,
        fallback_action: str | None = None,
    ) -> tuple[bool, list[str]]:
        rule = self._get_behavior_rule(trigger_name, place_id) or self._get_behavior_rule("intercept_at_station", place_id)
        min_staff = 1
        fallback = fallback_action
        if rule:
            if rule.get("min_station_staff") is not None:
                min_staff = int(rule["min_station_staff"])
            if rule.get("fallback"):
                fallback = rule["fallback"]

        present_workers = [
            w for w in self.workers
            if w.place_id == place_id
            and w.traveling_to is None
            and self.worker_pool.time_available(w, self.now, self.calendar_open)
            and ("station" in (w.roles or {w.role}) or "station" in w.duties or w.role == "station")
        ]
        worker_ids = [w.worker_id for w in present_workers]

        if len(present_workers) >= min_staff:
            part.station_worker_id = present_workers[0].worker_id
            self.emit(
                "station_intercept",
                part,
                place_id=place_id,
                worker_ids=worker_ids,
                min_station_staff=min_staff,
                student_count=part.student_count,
                trigger=trigger_name,
            )
            return True, worker_ids
        else:
            self.emit(
                "station_miss",
                part,
                place_id=place_id,
                worker_ids=worker_ids,
                min_station_staff=min_staff,
                student_count=part.student_count,
                trigger=trigger_name,
                fallback=fallback,
            )
            return False, worker_ids

    def _part_matches_target(self, part: Part, target: Any) -> bool:
        if not target:
            return False
        if isinstance(target, str):
            if part.part_id == target or part.group_id == target or part.source_unit_id == target:
                return True
            if target in part.source_unit_ids:
                return True
            if any(m.get("cohort_id") == target for m in part.members):
                return True
            if any(m.get("student_key") == target for m in part.members):
                return True
            return False
        if isinstance(target, list):
            target_set = set(target)
            return any(m.get("student_key") in target_set for m in part.members)
        if isinstance(target, Mapping):
            if target.get("part_id") and part.part_id == target["part_id"]:
                return True
            if target.get("cohort_id") and any(m.get("cohort_id") == target["cohort_id"] for m in part.members):
                return True
            if target.get("member_keys"):
                keys = set(target["member_keys"])
                return any(m.get("student_key") in keys for m in part.members)
            if target.get("place_id") and part.place_id == target["place_id"]:
                return True
        return False

    def _find_target_parts(self, target: Any, part_hint: Part | None = None) -> list[Part]:
        if part_hint is not None and self._part_matches_target(part_hint, target):
            return [part_hint]
        matched = []
        for part in self.parts.values():
            if part.status not in ("completed", "split", "withdrawn"):
                if self._part_matches_target(part, target):
                    matched.append(part)
        return matched

    def _filter_target_members(self, members: list[dict], target: Any) -> list[dict]:
        if not target:
            return list(members)
        if isinstance(target, str):
            matched = [m for m in members if m.get("cohort_id") == target or m.get("source_unit_id") == target or m.get("student_key") == target]
            return matched if matched else list(members)
        if isinstance(target, list):
            target_set = set(target)
            return [m for m in members if m.get("student_key") in target_set]
        if isinstance(target, Mapping):
            if target.get("member_keys"):
                keys = set(target["member_keys"])
                return [m for m in members if m.get("student_key") in keys]
            if target.get("cohort_id"):
                cid = target["cohort_id"]
                return [m for m in members if m.get("cohort_id") == cid]
            if target.get("source_unit_id"):
                su = target["source_unit_id"]
                return [m for m in members if m.get("source_unit_id") == su]
        return list(members)

    def _on_behavior_queue_jump(self, event: dict) -> None:
        eid = event.get("event_id")
        if eid and eid in self.executed_behavior_events:
            return
        place_id = event.get("place_id")
        if not place_id and isinstance(event.get("target"), Mapping):
            place_id = event["target"].get("place_id")
        target = event.get("target")

        target_parts = self._find_target_parts(target)
        candidates = [p for p in target_parts if p.place_id == place_id and p.status in ("queued", "ready", "waiting_for_server", "holding", "blocked")]
        if not candidates and place_id in self.wait_entry:
            entry_parts = [self.parts[pid] for pid in self.wait_entry[place_id] if pid in self.parts]
            candidates = [p for p in entry_parts if self._part_matches_target(p, target)]
        if not candidates and place_id in self.queues:
            q_parts = [self.parts[pid] for pid in self.queues[place_id] if pid in self.parts]
            candidates = [p for p in q_parts if self._part_matches_target(p, target)]

        if not candidates:
            if event not in self.pending_queue_jumps:
                self.pending_queue_jumps.append(event)
            return

        part = candidates[0]

        queue_list = None
        if place_id in self.wait_entry and part.part_id in self.wait_entry[place_id]:
            queue_list = self.wait_entry[place_id]
        elif place_id in self.queues and part.part_id in self.queues[place_id]:
            queue_list = self.queues[place_id]

        from_rank = (queue_list.index(part.part_id) + 1) if queue_list else 1
        to_rank = 1

        rule = self._get_behavior_rule("queue_jump", place_id)
        action = rule.get("action", "refuse_queue_jump").replace("-", "_") if rule else "refuse_queue_jump"

        intercepted = False
        w_ids: list[str] = []

        if action == "intercept_at_station":
            success, w_ids = self._check_station_intercept(part, place_id, "queue_jump", fallback_action=rule.get("fallback"))
            if success:
                intercepted = True
                enacted = False
            else:
                intercepted = False
                fallback = (rule.get("fallback") or "allow_queue_jump").replace("-", "_")
                enacted = (fallback in ("allow_queue_jump",))
        elif action == "allow_queue_jump":
            enacted = True
            station_workers = [
                w for w in self.workers
                if w.place_id == place_id and w.traveling_to is None
                and self.worker_pool.time_available(w, self.now, self.calendar_open)
                and ("station" in (w.roles or {w.role}) or "station" in w.duties or w.role == "station")
            ]
            w_ids = [w.worker_id for w in station_workers]
        else:
            enacted = False
            station_workers = [
                w for w in self.workers
                if w.place_id == place_id and w.traveling_to is None
                and self.worker_pool.time_available(w, self.now, self.calendar_open)
                and ("station" in (w.roles or {w.role}) or "station" in w.duties or w.role == "station")
            ]
            w_ids = [w.worker_id for w in station_workers]
            if station_workers:
                intercepted = True
                self.emit(
                    "station_intercept",
                    part,
                    place_id=place_id,
                    worker_ids=w_ids,
                    min_station_staff=1,
                    student_count=part.student_count,
                    trigger="queue_jump",
                )

        self.emit(
            "queue_jump_attempt",
            part,
            place_id=place_id,
            from_rank=from_rank,
            to_rank=to_rank,
            worker_ids=w_ids,
            intercepted=intercepted,
            student_count=part.student_count,
            event_id=eid,
        )

        if eid:
            self.executed_behavior_events.add(eid)
        if enacted:
            part.queue_priority = -1
            if queue_list is not None and part.part_id in queue_list:
                queue_list.remove(part.part_id)
                queue_list.insert(0, part.part_id)
            self.emit(
                "queue_jump_enacted",
                part,
                place_id=place_id,
                from_rank=from_rank,
                to_rank=to_rank,
                worker_ids=w_ids,
                intercepted=intercepted,
                student_count=part.student_count,
                event_id=eid,
            )
            self._try_admit_waiters(place_id)
            self.try_start_service(place_id)

    def _maybe_execute_pending_queue_jump(self, part: Part, place_id: str) -> None:
        for event in list(self.pending_queue_jumps):
            tgt_place = event.get("place_id")
            if not tgt_place and isinstance(event.get("target"), Mapping):
                tgt_place = event["target"].get("place_id")
            if tgt_place == place_id and self._part_matches_target(part, event.get("target")):
                self.pending_queue_jumps.remove(event)
                self._on_behavior_queue_jump(event)
                break

    def _on_behavior_withdrawal(self, event: dict, part_hint: Part | None = None) -> None:
        eid = event.get("event_id")
        target = event.get("target")
        if eid and eid in self.executed_behavior_events:
            return
        matching_parts = self._find_target_parts(target, part_hint)
        for part in matching_parts:
            if part.status == "pending" and self.now < part.arrival_ms:
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"pre-start withdrawal is invalid for event {eid!r}; use no-show",
                    field="scenario.behavior.events",
                )
            if part.status == "completed":
                raise SimulationError(
                    "invalid_value_or_unit",
                    f"withdrawal after completion is invalid for event {eid!r}",
                    field="scenario.behavior.events",
                )
            if part.status == "travelling":
                part.pending_withdrawal = {
                    "event": event,
                    "requested_time_ms": self.now,
                }
                continue
            if eid:
                self.executed_behavior_events.add(eid)
            self._execute_withdrawal(part, event, requested_time_ms=self.now)

    def _execute_withdrawal(self, part: Part, event: dict, requested_time_ms: int) -> None:
        target = event.get("target")
        withdrawing_members = self._filter_target_members(part.members, target)
        if not withdrawing_members:
            return

        if len(withdrawing_members) < len(part.members):
            continuing = [m for m in part.members if m not in withdrawing_members]
            withdrawn_part = self._split_part(part, continuing, withdrawing_members, cause="withdrawal", event_id=event.get("event_id"))
            target_part = withdrawn_part
        else:
            target_part = part

        target_part.status = "withdrawn"
        target_part.version += 1

        if target_part.place_id and target_part.place_id in self.queues:
            if target_part.part_id in self.queues[target_part.place_id]:
                self.queues[target_part.place_id].remove(target_part.part_id)
        if target_part.place_id and target_part.place_id in self.wait_entry:
            if target_part.part_id in self.wait_entry[target_part.place_id]:
                self.wait_entry[target_part.place_id].remove(target_part.part_id)
        if target_part.part_id in self.wait_workers:
            self.wait_workers.remove(target_part.part_id)
        if target_part.part_id in self.wait_policy:
            self.wait_policy.remove(target_part.part_id)
        if target_part.part_id in self.wait_shared:
            self.wait_shared.remove(target_part.part_id)
        for dest, waiters in self.wait_reserve.items():
            if target_part.part_id in waiters:
                waiters.remove(target_part.part_id)

        self._end_wait(target_part)
        self._release_escorts(target_part, "withdrawn")
        self._release_station_worker(target_part)
        self._vacate_place(target_part.place_id, target_part)

        self.emit(
            "withdrawal",
            target_part,
            event_id=event.get("event_id"),
            requested_time_s=ms_to_s(requested_time_ms),
            actual_time_s=ms_to_s(self.now),
            place_id=target_part.place_id,
            student_count=target_part.student_count,
            member_keys=[m["student_key"] for m in target_part.members],
        )

    def _check_stage_behavior_events(self, part: Part, trigger_kind: str, stage_id: str) -> None:
        behavior = self.scenario.get("behavior") or {}
        for event in behavior.get("events") or []:
            if not isinstance(event, Mapping):
                continue
            trig = event.get("trigger") or {}
            if isinstance(trig, Mapping) and trig.get(trigger_kind) == stage_id:
                if self._part_matches_target(part, event.get("target")):
                    phenom = event.get("phenomenon")
                    if phenom == "withdrawal":
                        self._on_behavior_withdrawal(event, part_hint=part)
                    elif phenom == "queue_jump":
                        self._on_behavior_queue_jump(event)

    def _schedule_initial(self) -> None:
        for calendar in self.calendars.values():
            open_ms = to_ms(calendar["open_time_s"])
            if open_ms <= self.simulation_end_ms:
                self.schedule(
                    open_ms,
                    PHASE_ARRIVAL_EXTERNAL,
                    "calendar_open",
                    None,
                    calendar_id=calendar["id"],
                )
            if calendar.get("close_time_s") is not None:
                close_ms = to_ms(calendar["close_time_s"])
                if close_ms <= self.simulation_end_ms:
                    self.schedule(
                        close_ms,
                        PHASE_ARRIVAL_EXTERNAL,
                        "calendar_close",
                        None,
                        calendar_id=calendar["id"],
                    )
        for vehicle in self.scenario["initial_state"]["vehicles"]:
            self.schedule(
                to_ms(vehicle["available_time_s"]),
                PHASE_ARRIVAL_EXTERNAL,
                "resource_available",
                None,
                resource_id=vehicle["id"],
            )
            for outage in vehicle.get("outages") or []:
                self.schedule(
                    to_ms(outage["end_s"]),
                    PHASE_ARRIVAL_EXTERNAL,
                    "resource_available",
                    None,
                    resource_id=vehicle["id"],
                )
        unit_by_id = {unit["id"]: unit for unit in self.scenario["source_units"]}
        grouping_pol = self.policy.get("grouping") or {}
        for part in list(self.parts.values()):
            if getattr(part, "_is_initial_queue", False):
                continue
            if part.status == "travelling" and part.leg_id:
                leg = self.legs[part.leg_id]
                arrival_ms = part.arrival_ms if part.arrival_ms else to_ms(self._leg_duration_s(leg, part))
                self.schedule(
                    arrival_ms,
                    PHASE_ARRIVAL_EXTERNAL,
                    "arrival",
                    part,
                    to_place_id=leg["to_place_id"],
                    leg_id=leg["id"],
                )
                continue

            attending = [m for m in part.members if m.get("attendance_state") != "no_show"]
            if not attending:
                part.status = "withdrawn"
                continue
            if len(attending) != len(part.members):
                part.members = attending
                part.student_count = len(attending)
                part.hostel_composition = self._composition_from_members(attending)
                part.source_unit_membership = self._su_membership_from_members(attending)
                part.source_unit_ids = sorted(part.source_unit_membership.keys())

            max_assembly_wait_s = grouping_pol.get("maximum_assembly_wait_s")
            if max_assembly_wait_s is None and self.policy.get("maximum_assembly_wait_s") is not None:
                max_assembly_wait_s = self.policy.get("maximum_assembly_wait_s")
            adapt = grouping_pol.get("adaptation_rule") or self.adaptation_rule or {}
            if (
                adapt.get("type") == "release_ready"
                and adapt.get("permitted_place_id")
                and adapt.get("permitted_place_id") == part.place_id
            ):
                max_assembly_wait_s = 0

            b_rule = (
                self._get_behavior_rule("mixed_readiness", part.place_id)
                or self._get_behavior_rule("late_reporting", part.place_id)
            )
            if b_rule and max_assembly_wait_s is None and b_rule.get("wait_limit_s") is not None:
                max_assembly_wait_s = b_rule.get("wait_limit_s")

            assembly_wait_anchor = (
                (b_rule.get("assembly_wait_anchor") if b_rule else None)
                or grouping_pol.get("assembly_wait_anchor")
                or self.policy.get("assembly_wait_anchor")
                or (self.scenario.get("operating_rules") or {}).get("assembly_wait_anchor")
                or "earliest_ready"
            )

            curr_part = part
            while max_assembly_wait_s is not None and curr_part.student_count > 1:
                member_times = []
                for m in curr_part.members:
                    su_id = m.get("source_unit_id") or curr_part.source_unit_id or (curr_part.source_unit_ids[0] if curr_part.source_unit_ids else None)
                    u = unit_by_id.get(su_id)
                    act = m.get("actual_reporting_s") if m.get("actual_reporting_s") is not None else (u.get("actual_reporting_s", 0.0) if u else 0.0)
                    rdy = m.get("readiness_s") if m.get("readiness_s") is not None else (u.get("readiness_s", 0.0) if u else 0.0)
                    eff = max(float(act), float(rdy))
                    req = float(m.get("required_reporting_s") or (u.get("required_reporting_s") if u else 0.0) or 0.0)
                    member_times.append((m, eff, req))

                if assembly_wait_anchor == "required_reporting":
                    anchor_s = min(t[2] for t in member_times)
                else:
                    anchor_s = min(t[1] for t in member_times)

                cutoff_s = anchor_s + float(max_assembly_wait_s)
                cutoff_ms = to_ms(cutoff_s)

                on_time = [m for m, eff, req in member_times if to_ms(eff) <= cutoff_ms]
                late = [m for m, eff, req in member_times if to_ms(eff) > cutoff_ms]

                if on_time and late:
                    late_part = self._split_part(curr_part, on_time, late, cutoff_s=cutoff_s, cause="assembly_cutoff")
                    on_time_eff = [eff for m, eff, req in member_times if to_ms(eff) <= cutoff_ms]
                    ready_s = max(on_time_eff)
                    assembly = grouping_pol.get("physical_assembly") or {}
                    if assembly.get("duration_s") is not None:
                        curr_part.pending_assembly_s = float(assembly["duration_s"])
                    self.schedule(to_ms(ready_s), PHASE_ARRIVAL_EXTERNAL, "part_ready", curr_part, part_version=curr_part.version)
                    curr_part = late_part
                else:
                    break

            member_effs = []
            for m in curr_part.members:
                su_id = m.get("source_unit_id") or curr_part.source_unit_id or (curr_part.source_unit_ids[0] if curr_part.source_unit_ids else None)
                u = unit_by_id.get(su_id)
                act = m.get("actual_reporting_s") if m.get("actual_reporting_s") is not None else (u.get("actual_reporting_s", 0.0) if u else 0.0)
                rdy = m.get("readiness_s") if m.get("readiness_s") is not None else (u.get("readiness_s", 0.0) if u else 0.0)
                member_effs.append(max(float(act), float(rdy)))
            ready_s = max(member_effs) if member_effs else 0.0
            assembly = grouping_pol.get("physical_assembly") or {}
            if assembly.get("duration_s") is not None:
                curr_part.pending_assembly_s = float(assembly["duration_s"])
            self.schedule(to_ms(ready_s), PHASE_ARRIVAL_EXTERNAL, "part_ready", curr_part, part_version=curr_part.version)

        for event in (self.scenario.get("behavior") or {}).get("events") or []:
            if not isinstance(event, Mapping):
                continue
            phenom = event.get("phenomenon")
            trig = event.get("trigger") or {}
            if isinstance(trig, Mapping) and "time_s" in trig:
                t_ms = to_ms(trig["time_s"])
                self.schedule(
                    t_ms,
                    PHASE_REPORT_DECISION,
                    f"behavior_{phenom}",
                    None,
                    event=dict(event),
                )
        for worker in self.workers:
            if worker.available_from_ms > 0:
                self.schedule(
                    worker.available_from_ms,
                    PHASE_ARRIVAL_EXTERNAL,
                    "worker_available",
                    None,
                    worker_id=worker.worker_id,
                )
        for place_id in list(self.queues):
            self.try_start_service(place_id)

    def schedule(
        self,
        time_ms: int,
        phase: int,
        event_type: str,
        part: Part | None,
        **payload,
    ) -> None:
        if time_ms == self.now and phase < self.current_phase:
            phase = self.current_phase
        self.seq += 1
        part_id = part.part_id if part is not None else None
        heapq.heappush(
            self.heap,
            (int(time_ms), int(phase), self.seq, event_type, part_id, payload),
        )

    def _dispatch(self, event_type: str, part_id: str | None, payload: dict) -> None:
        part = self.parts.get(part_id) if part_id else None
        if part is not None:
            if payload.get("part_version") is not None and part.version != payload["part_version"]:
                return
            if part.status in {"split", "withdrawn", "completed"} and event_type not in {
                "part_split", "withdrawal", "station_intercept", "station_miss"
            }:
                return
        if event_type == "part_ready":
            if part is None or part.status in {"split", "withdrawn", "completed"}:
                return
            self._on_part_ready(part)
        elif event_type == "calendar_open":
            self._on_calendar_open(payload["calendar_id"])
        elif event_type == "calendar_close":
            self._on_calendar_close(payload["calendar_id"])
        elif event_type == "report_delivered":
            self._on_report_delivered(payload)
        elif event_type == "condition_change":
            self._on_condition_change(payload)
        elif event_type == "resource_available":
            self._on_resource_available(payload["resource_id"])
        elif event_type == "departure":
            self._on_departure(part)
        elif event_type == "arrival":
            self._on_arrival(part, payload)
        elif event_type == "service_start":
            self._on_service_start(part)
        elif event_type == "service_complete":
            self._on_service_complete(part)
        elif event_type == "batch_start":
            self._on_batch_start(part, payload)
        elif event_type == "batch_complete":
            self._on_batch_complete(part, payload)
        elif event_type == "resource_release":
            self._on_resource_release(payload["resource_id"], part)
        elif event_type == "vehicle_return_complete":
            self._on_vehicle_return_complete(payload["resource_id"])
        elif event_type == "vehicle_turnaround_complete":
            self._on_vehicle_turnaround_complete(payload["resource_id"])
        elif event_type == "count_complete":
            self._on_count_complete(part, payload)
        elif event_type == "recount_complete":
            self._on_count_complete(part, payload)
        elif event_type == "worker_available":
            self._on_worker_available(payload.get("worker_id"))
        elif event_type == "escort_ready":
            self._on_escort_ready(part, payload)
        elif event_type == "worker_travel_complete":
            self._on_worker_travel_complete(payload)
        elif event_type == "assembly_complete":
            self._on_assembly_complete(part)
        elif event_type == "assembly_travel_complete":
            self._on_assembly_travel_complete(part, payload)
        elif event_type == "check_fleet_dispatch":
            self._fleet_dispatch_scheduled[payload["fleet_id"]] = False
            self.try_start_fleet(payload["fleet_id"])
        elif event_type == "regroup_complete":
            self._on_regroup_complete(part, payload.get("group_id"))
        elif event_type == "destination_delayed_complete":
            self._complete_part(part)
        elif event_type == "behavior_queue_jump":
            self._on_behavior_queue_jump(payload["event"])
        elif event_type == "behavior_withdrawal":
            self._on_behavior_withdrawal(payload["event"])
        elif event_type == "hold_duration_complete":
            self._on_hold_duration_complete(part, payload)
        elif event_type == "check_hostels_departed_hold":
            self._check_hostels_departed_waits()
        else:
            self.emit(event_type, part, **payload)

    def _on_hold_duration_complete(self, part: Part | None, payload: dict) -> None:
        if part is None or part.status in {"completed", "split", "withdrawn"}:
            return
        cause = payload.get("primary_cause", "headcount_staging")
        self._end_wait(part)
        self.emit("hold_end", part, place_id=part.place_id, primary_cause=cause)
        part.status = "ready"
        part.stage_index += 1
        self.begin_stage(part)

    def _on_part_ready(self, part: Part) -> None:
        part.status = "ready"
        part.arrival_ms = self.now
        self._record_origin_wait(part)
        if part.place_id and (part.parent_part_id or any(m.get("late_assembly_s") for m in part.members)):
            rule = self._get_behavior_rule("late_reporting", part.place_id)
            if rule and rule.get("action") in ("intercept_at_station", "intercept-at-station"):
                self._check_station_intercept(part, part.place_id, "late_reporting")
        self.emit("part_ready", part, place_id=part.place_id, primary_cause="initial_presence")
        if part.pending_assembly_s:
            if not self._start_assembly(part):
                return
            return
        self.begin_stage(part)

    def _on_assembly_complete(self, part: Part) -> None:
        duration_s = float(part.pending_assembly_s or 0)
        part.pending_assembly_s = None
        part.assembly_finish_ms = self.now
        self.assembly_student_ms += part.student_count * to_ms(duration_s)
        self._release_assembly_workers(part)
        self.emit(
            "assembly_complete",
            part,
            place_id=part.place_id,
            primary_cause="physical_assembly",
        )
        part.status = "ready"
        self.begin_stage(part)

    def _assembly_place(self, part: Part) -> str | None:
        assembly = (self.policy.get("grouping") or {}).get("physical_assembly") or {}
        return assembly.get("place_id") or part.place_id

    def _assembly_need(self) -> int:
        assembly = (self.policy.get("grouping") or {}).get("physical_assembly") or {}
        return int(assembly.get("worker_count") or 0)

    def _start_assembly(self, part: Part) -> bool:
        if part.assembly_start_ms is not None:
            return True
        if not self._ensure_assembly_location(part):
            return False
        if not self._reserve_assembly_workers(part):
            return False
        need = self._assembly_need()
        if need > 0 and len(part.assembly_worker_ids) < need:
            self._wait_for_assembly(part)
            return False
        place_id = self._assembly_place(part) or part.place_id
        part.assembly_start_ms = self.now
        part.status = "assembling"
        self.emit(
            "assembly_start",
            part,
            place_id=place_id,
            primary_cause="physical_assembly",
            worker_ids=list(part.assembly_worker_ids),
        )
        self.schedule(
            self.now + to_ms(part.pending_assembly_s),
            PHASE_COMPLETION_RELEASE,
            "assembly_complete",
            part,
        )
        return True

    def _ensure_assembly_location(self, part: Part) -> bool:
        dest = self._assembly_place(part)
        if not dest or dest == part.place_id:
            return True
        if part.assembly_arrive_pending:
            return False
        travel_ms = self._place_travel_ms(part.place_id, dest)
        if travel_ms is None:
            raise SimulationError(
                "missing_input",
                (
                    "assembly at "
                    f"{dest!r} needs travel from {part.place_id!r}"
                ),
                field="policy.grouping.physical_assembly.place_id",
            )
        if part.place_id:
            self._vacate_place(part.place_id, part)
        from_place = part.place_id
        part.assembly_arrive_pending = True
        part.status = "assembly_travel"
        self.emit(
            "departure",
            part,
            place_id=from_place,
            primary_cause="physical_assembly",
        )
        if travel_ms <= 0:
            part.assembly_arrive_pending = False
            if dest:
                self._admit_to_place(part, dest)
                part.place_id = dest
            return True
        self.schedule(
            self.now + travel_ms,
            PHASE_ARRIVAL_EXTERNAL,
            "assembly_travel_complete",
            part,
            to_place_id=dest,
        )
        return False

    def _on_assembly_travel_complete(self, part: Part, payload: dict) -> None:
        dest = payload.get("to_place_id") or self._assembly_place(part)
        part.assembly_arrive_pending = False
        if dest:
            self._admit_to_place(part, dest)
            part.place_id = dest
        self.emit(
            "arrival",
            part,
            place_id=dest,
            primary_cause="physical_assembly",
        )
        self._start_assembly(part)

    def _place_travel_ms(self, src: str | None, dest: str | None) -> int | None:
        if not src or not dest or src == dest:
            return 0
        for leg in self.legs.values():
            if leg.get("from_place_id") == src and leg.get("to_place_id") == dest:
                return to_ms(self._leg_duration_s(leg))
            if leg.get("from_place_id") == dest and leg.get("to_place_id") == src:
                return to_ms(self._leg_duration_s(leg))
        found = self.worker_pool.travel_lookup(src, dest)
        return found

    def _record_origin_wait(self, part: Part) -> None:
        unit_by_id = {unit["id"]: unit for unit in self.scenario.get("source_units") or []}
        membership = dict(part.source_unit_membership or {})
        if not membership:
            membership = {part.source_unit_id: part.student_count}
        starts: list[int] = []
        waiting_n = 0
        for unit_id, count in membership.items():
            unit = unit_by_id.get(unit_id) or {}
            present_s = float(unit.get("actual_reporting_s") or 0.0)
            required = unit.get("required_reporting_s")
            if required is None:
                required = present_s
            required_s = float(required)
            external_s = unit.get("external_readiness_s")
            if external_s is None:
                external_s = 0.0
            external_s = float(external_s)
            wait_start_s = max(required_s, present_s, external_s)
            wait_start_ms = to_ms(wait_start_s)
            if wait_start_ms >= self.now:
                continue
            n = int(count or 0)
            if n <= 0:
                continue
            starts.append(wait_start_ms)
            waiting_n += n
        if not starts or waiting_n <= 0:
            return
        self.wait_intervals.append(
            WaitInterval(
                part_id=part.part_id,
                student_count=part.student_count,
                cause="waiting_for_release",
                place_id=part.place_id,
                start_ms=min(starts),
                end_ms=self.now,
            )
        )

    def _wait_for_assembly(self, part: Part) -> None:
        part.status = "waiting_assembly"
        if part.part_id not in self.wait_workers:
            self.wait_workers.append(part.part_id)
        if part.part_id not in self.open_waits:
            self._begin_wait(part, "waiting_for_worker")

    def _try_waiting_assembly(self) -> None:
        waiting = [
            part_id
            for part_id in list(self.wait_workers)
            if self.parts.get(part_id) is not None
            and self.parts[part_id].status == "waiting_assembly"
        ]
        for part_id in waiting:
            part = self.parts[part_id]
            if self._start_assembly(part):
                self.wait_workers = [
                    item for item in self.wait_workers if item != part_id
                ]
                self._end_wait(part)

    def _reserve_assembly_workers(self, part: Part) -> bool:
        need = self._assembly_need()
        if need <= 0:
            return True
        if part.assembly_worker_ids and len(part.assembly_worker_ids) >= need:
            return True
        place_id = self._assembly_place(part) or part.place_id
        present = [
            worker
            for worker in self.worker_pool.workers
            if worker.place_id == place_id
            and worker.assigned_part_id == part.part_id
            and worker.worker_id not in part.assembly_worker_ids
        ]
        if present and len(part.assembly_worker_ids) + len(present) >= need:
            ids = [worker.worker_id for worker in present[:need]]
            part.assembly_worker_ids.extend(
                worker_id
                for worker_id in ids
                if worker_id not in part.assembly_worker_ids
            )
            self.emit(
                "worker_reserved",
                part,
                worker_ids=list(ids),
                resource_ids=list(ids),
                place_id=place_id,
                primary_cause="physical_assembly",
            )
            return True
        idle = self.worker_pool.idle_now(
            place_id, "escort", self.now, self.calendar_open
        )
        if len(idle) >= need:
            ids = self.worker_pool.reserve_now(
                idle[:need], "escort", place_id, self.now, part.part_id
            )
            part.assembly_worker_ids = list(ids)
            if len(ids) < need:
                self._wait_for_assembly(part)
                return False
            self.emit(
                "worker_reserved",
                part,
                worker_ids=list(ids),
                resource_ids=list(ids),
                place_id=place_id,
                primary_cause="physical_assembly",
            )
            return True
        offer = self.worker_pool.pick_free(
            need,
            "escort",
            place_id,
            self.now,
            self.calendar_open,
            self.calendars,
        )
        if offer is None:
            if self.worker_pool.capable_count("escort") < need:
                self.violations.append(
                    {
                        "type": "insufficient_staff",
                        "part_id": part.part_id,
                        "need": need,
                        "primary_cause": "physical_assembly",
                    }
                )
            self._wait_for_assembly(part)
            return False
        chosen, start_ms = offer
        remote = [
            worker
            for worker in chosen
            if worker.place_id not in {None, place_id}
        ]
        if remote:
            ids = self.worker_pool.commit_travel(
                chosen, "escort", place_id, self.now, start_ms, part.part_id
            )
            for worker_id in ids:
                worker = self.workers_by_id.get(worker_id)
                arrive_ms = worker.free_at_ms if worker is not None else start_ms
                if arrive_ms > self.now:
                    self.schedule(
                        arrive_ms,
                        PHASE_START_DEPART,
                        "worker_travel_complete",
                        None,
                        worker_id=worker_id,
                        to_place_id=place_id,
                    )
            self._wait_for_assembly(part)
            return False
        if start_ms > self.now:
            self._wait_for_assembly(part)
            return False
        ids = self.worker_pool.reserve_now(
            chosen, "escort", place_id, self.now, part.part_id
        )
        part.assembly_worker_ids = list(ids)
        if len(ids) < need:
            self._wait_for_assembly(part)
            return False
        self.emit(
            "worker_reserved",
            part,
            worker_ids=list(ids),
            resource_ids=list(ids),
            place_id=place_id,
            primary_cause="physical_assembly",
        )
        return True

    def _release_assembly_workers(self, part: Part) -> None:
        ids = list(part.assembly_worker_ids)
        if not ids:
            return
        self.emit(
            "worker_released",
            part,
            worker_ids=ids,
            resource_ids=ids,
            place_id=part.place_id,
            primary_cause="physical_assembly",
        )
        self.worker_pool.release(ids, self.now)
        part.assembly_worker_ids = []
        self._try_waiting_assembly()
        self._try_waiting_escorts()

    def _on_calendar_open(self, calendar_id: str) -> None:
        planned = self.calendar_open_at.get(calendar_id)
        if planned is not None and self.now < planned:
            return
        calendar = self.calendars[calendar_id]
        self.calendar_open[calendar_id] = True
        waiters = [self.parts[pid] for pid in self.wait_calendar.get(calendar_id, [])]
        student_count = sum(part.student_count for part in waiters)
        composition = _merge_compositions(waiters)
        self.emit(
            "calendar_open",
            None,
            calendar_id=calendar_id,
            place_id=calendar.get("place_id"),
            student_count=student_count,
            hostel_composition=composition,
            imposed_input=bool(calendar.get("imposed")),
            prediction_role="input" if calendar.get("imposed") else "external",
            primary_cause="imposed_calendar" if calendar.get("imposed") else "external_condition",
        )
        waiting_ids = list(self.wait_calendar.get(calendar_id, []))
        self.wait_calendar[calendar_id] = []
        for pid in waiting_ids:
            part = self.parts[pid]
            self._end_wait(part)
            if part.release_ms is None:
                part.release_ms = self.now
            self.emit("hold_end", part, place_id=part.place_id, calendar_id=calendar_id)
            part.stage_index += 1
            self.begin_stage(part)
        for resource in self.resources.values():
            if resource.calendar_id == calendar_id and not resource.busy:
                self._on_resource_available(resource.resource_id)
        self._try_waiting_escorts()
        self._try_waiting_counts()
        for place_id in list(self.queues):
            self.try_start_service(place_id)

    def _on_calendar_close(self, calendar_id: str) -> None:
        calendar = self.calendars[calendar_id]
        self.calendar_open[calendar_id] = False
        self.emit(
            "calendar_close",
            None,
            calendar_id=calendar_id,
            place_id=calendar.get("place_id"),
            primary_cause="door_closure",
        )

    def _on_resource_available(self, resource_id: str) -> None:
        resource = self.resources[resource_id]
        if self.now < resource.earliest_available_ms:
            return
        if not self._vehicle_service_ok(resource):
            return
        if resource.busy:
            return
        resource.available = True
        waiters = [self.parts[pid] for pid in self.wait_resource.get(resource_id, [])]
        hold_waiters = [
            part
            for part in self.parts.values()
            if part.status == "holding"
            and part.current_stage_id
            and self._stage(part).get("until", {}).get("resource_available") == resource_id
        ]
        student_count = sum(part.student_count for part in hold_waiters)
        self.emit(
            "resource_available",
            None,
            resource_ids=[resource_id],
            place_id=resource.place_id,
            student_count=student_count,
            primary_cause="vehicle_available",
        )
        released = [
            pid
            for pid, part in self.parts.items()
            if part.status == "holding"
            and self._stage(part).get("until", {}).get("resource_available") == resource_id
        ]
        for pid in released:
            part = self.parts[pid]
            self._end_wait(part)
            self.emit("hold_end", part, place_id=part.place_id, resource_ids=[resource_id])
            part.stage_index += 1
            self.begin_stage(part)
        if resource.fleet_id:
            released_fleet = [
                pid
                for pid, held in self.parts.items()
                if held.status == "holding"
                and self._stage(held).get("until", {}).get("fleet_available")
                == resource.fleet_id
            ]
            for pid in released_fleet:
                held = self.parts[pid]
                self._end_wait(held)
                self.emit(
                    "hold_end",
                    held,
                    place_id=held.place_id,
                    resource_ids=list(self.fleets[resource.fleet_id]["vehicle_ids"]),
                )
                held.stage_index += 1
                self.begin_stage(held)
        self.try_start_batch(resource_id)
        if resource.fleet_id:
            self.try_start_fleet(resource.fleet_id)

    def _on_departure(self, part: Part) -> None:
        if part is None or part.status in {"completed", "split", "withdrawn"}:
            return
        stage = self._stage(part)
        if stage.get("kind") not in {"travel", "vehicle_travel"} or not stage.get("leg_id"):
            return
        leg = self.legs[stage["leg_id"]]
        if not self._acquire_shared_for_leg(part, leg):
            self._hold_for_shared_capacity(part, leg)
            return
        if part.place_id:
            self._vacate_place(part.place_id, part)
        part.leg_id = leg["id"]
        part.status = "travelling"
        cause = "vehicle_travel" if stage["kind"] == "vehicle_travel" else "walk"
        if stage["kind"] == "vehicle_travel":
            resource_id = None
            if part.resource_ids:
                resource_id = part.resource_ids[0]
            elif stage.get("resource_id"):
                resource_id = stage["resource_id"]
                if resource_id not in part.resource_ids:
                    part.resource_ids.append(resource_id)
            if resource_id and resource_id in self.resources:
                resource = self.resources[resource_id]
                resource.busy = True
                resource.available = False
                resource.assigned_part_id = part.part_id
                resource.aboard_students = part.student_count
                part.aboard = True
                self._set_vehicle_state(resource, "busy", "vehicle_travel")
                self.space.locate_members(part, f"aboard:{resource_id}", self.now)
            else:
                self.space.locate_members(part, f"leg:{leg['id']}", self.now)
        else:
            self.space.locate_members(part, f"leg:{leg['id']}", self.now)
        event_resources = self._leg_event_resource_ids(leg, part)
        duration_s, occupancy_ahead, occupancy_factor, extra_applied = self._leg_timing(leg, part)
        occupancy_payload = {}
        if self._walk_occupancy_rule() and leg.get("mode") == "walk":
            occupancy_payload = {
                "walk_occupancy_ahead": occupancy_ahead,
                "walk_occupancy_factor": occupancy_factor,
                "walk_shared_extra_s": extra_applied,
                "walk_duration_s": duration_s,
            }
        self.emit(
            "departure",
            part,
            place_id=leg["from_place_id"],
            leg_id=leg["id"],
            resource_ids=event_resources,
            escort_ids=list(part.escort_ids),
            worker_ids=list(part.escort_ids),
            primary_cause=cause,
            **occupancy_payload,
        )
        self.schedule(
            self.now + to_ms(duration_s),
            PHASE_ARRIVAL_EXTERNAL,
            "arrival",
            part,
            to_place_id=leg["to_place_id"],
            leg_id=leg["id"],
        )
        self._check_hostels_departed_waits()

    def _on_arrival(self, part: Part, payload: dict) -> None:
        if part is None or part.status in {"completed", "split", "withdrawn"}:
            return
        self._release_shared_for_part(part)
        dest = payload["to_place_id"]
        stage = self._stage(part)
        is_vehicle = stage.get("kind") == "vehicle_travel"
        for resource_id in part.resource_ids:
            if resource_id in self.resources:
                self.resources[resource_id].place_id = dest
        if is_vehicle:
            self._arrive_vehicle(part, dest, payload)
            return
        if self._admit_to_place(part, dest):
            self._finish_arrival(part, dest, payload)
            return
        wait_place = self._wait_place_for(dest, payload)
        if wait_place and self._admit_to_place(part, wait_place):
            self._block_part(part, wait_place, dest, payload, aboard=False)
            return
        self._fail_no_waiting_space(part, dest)

    def _arrive_vehicle(self, part: Part, dest: str, payload: dict) -> None:
        resource_id = part.resource_ids[0] if part.resource_ids else None
        resource = self.resources.get(resource_id) if resource_id else None
        if resource is not None:
            resource.place_id = dest
            resource.aboard_students = part.student_count
            part.aboard = True
        dest_place = self.places.get(dest) or {}
        queue_place = dest_place.get("vehicle_queue_place_id")
        can_alight = self.space.can_enter(dest, part.student_count) and self._dropoff_free(part)
        if can_alight and self._admit_to_place(part, dest):
            if resource is not None:
                resource.aboard_students = 0
            part.aboard = False
            self._finish_arrival(part, dest, payload)
            return
        wait_place = queue_place or dest
        parked = True
        if resource is not None:
            parked = self.space.park_vehicle(wait_place, resource.resource_id)
            resource.place_id = wait_place
        if parked or self.space.unbounded(wait_place):
            self._block_part(part, wait_place, dest, payload, aboard=True)
            return
        self._fail_no_waiting_space(part, dest)

    def _finish_arrival(self, part: Part, place_id: str, payload: dict) -> None:
        part.place_id = place_id
        part.leg_id = None
        part.arrival_ms = self.now
        part.blocked_for_place_id = None
        if part.escort_ids:
            self.worker_pool.colocate(part.escort_ids, place_id)
        completion_event = self._stage(part).get("completion_event")
        leg = self.legs.get(payload.get("leg_id")) or {}
        self.emit(
            "arrival",
            part,
            place_id=place_id,
            leg_id=payload.get("leg_id"),
            resource_ids=self._leg_event_resource_ids(leg, part) if leg else list(part.resource_ids),
            escort_ids=list(part.escort_ids),
            primary_cause="physical_arrival",
            passengers_aboard=bool(part.aboard),
        )
        self._maybe_handover(part, place_id)
        if completion_event == "hall_area_arrival":
            self.emit(
                "hall_area_arrival",
                part,
                place_id=place_id,
                primary_cause="hall_approach_complete",
            )
        elif completion_event == "seated_completion":
            self.seated_count += part.student_count
            self.seated_count_by_place[place_id] = (
                self.seated_count_by_place.get(place_id, 0) + part.student_count
            )
            self.emit(
                "seated_completion",
                part,
                place_id=place_id,
                primary_cause="seated_completion",
            )
        part.stage_index += 1
        if getattr(part, "pending_withdrawal", None):
            pw = part.pending_withdrawal
            part.pending_withdrawal = None
            self._execute_withdrawal(part, pw["event"], requested_time_ms=pw["requested_time_ms"])
            if part.status == "withdrawn":
                return
        if part.stage_index - 1 < len(self._stage_list(part)):
            stage_completed = self._stage_list(part)[part.stage_index - 1]
            self._check_stage_behavior_events(part, "after_stage", stage_completed["id"])
            if part.status in {"split", "withdrawn"}:
                return
        if part.place_id and (part.parent_part_id or any(m.get("late_assembly_s") for m in part.members)):
            rule = self._get_behavior_rule("late_reporting", place_id)
            if rule and rule.get("action") in ("intercept_at_station", "intercept-at-station"):
                self._check_station_intercept(part, place_id, "late_reporting")
        if not part.resource_ids and self.regroup_policy.get("required") and self.regroup_policy.get("place_id") == place_id:
            if not getattr(part, "_regrouped", False):
                part._regrouped = True
                self._start_hold(part, {"group_assembled": True})
                return
        self.begin_stage(part)

    def _block_part(
        self,
        part: Part,
        wait_place: str,
        dest: str,
        payload: dict,
        *,
        aboard: bool,
    ) -> None:
        part.place_id = wait_place
        part.leg_id = None
        part.arrival_ms = self.now
        part.status = "blocked"
        part.aboard = aboard
        self.wait_entry.setdefault(dest, []).append(part.part_id)
        self._maybe_execute_pending_queue_jump(part, dest)
        if aboard and part.resource_ids:
            self.space.locate_members(part, f"aboard:{part.resource_ids[0]}", self.now)
            resource = self.resources.get(part.resource_ids[0])
            if resource is not None:
                self._set_vehicle_state(resource, "held", "waiting_to_alight")
        cause = "physical_blocking"
        self._begin_wait(part, cause, resource_id=part.resource_ids[0] if part.resource_ids else None)
        self.emit(
            "arrival",
            part,
            place_id=wait_place,
            leg_id=payload.get("leg_id"),
            resource_ids=list(part.resource_ids),
            primary_cause="physical_arrival",
            passengers_aboard=aboard,
        )
        self.emit(
            "physical_block",
            part,
            place_id=wait_place,
            blocked_for_place_id=dest,
            primary_cause="physical_blocking",
            passengers_aboard=aboard,
        )
        self.emit(
            "hold_start",
            part,
            place_id=wait_place,
            primary_cause="physical_blocking",
        )
        if part.escort_ids:
            self.worker_pool.colocate(part.escort_ids, wait_place)

    def _wait_place_for(self, dest: str, payload: dict) -> str | None:
        dest_place = self.places.get(dest) or {}
        if "preceding_place_id" in dest_place:
            return dest_place.get("preceding_place_id")
        preceding = self.space.preceding_place_id(dest)
        if preceding:
            return preceding
        leg = self.legs.get(payload.get("leg_id")) or {}
        return leg.get("from_place_id")

    def _dropoff_free(self, part: Part) -> bool:
        stage = self._stage(part)
        # Next stage is alighting after this travel stage.
        stages = self._stage_list(part)
        nxt = stages[part.stage_index + 1] if part.stage_index + 1 < len(stages) else None
        fleet_id = None
        if nxt and nxt.get("kind") == "batch_service":
            fleet_id = nxt.get("fleet_id")
        if stage.get("kind") == "batch_service":
            fleet_id = stage.get("fleet_id")
        if not fleet_id:
            return True
        fleet = self.fleets.get(fleet_id) or {}
        cap = int(fleet.get("dropoff_space_capacity") or 0)
        if cap <= 0:
            self.violations.append(
                {
                    "type": "physical_capacity",
                    "fleet_id": fleet_id,
                    "occupancy": part.student_count,
                    "capacity_students": cap,
                    "resource": "dropoff_space",
                }
            )
            return False
        return self.fleet_dropoff_busy.get(fleet_id, 0) < cap

    def _on_service_start(self, part: Part) -> None:
        place_id = part.place_id
        self._end_wait(part)
        part.status = "in_service"
        self.emit(
            "service_start",
            part,
            place_id=place_id,
            primary_cause="single_server_available",
        )
        duration_ms = (
            part.service_duration_ms
            if part.service_duration_ms is not None
            else self.service_duration_ms[place_id]
        )
        self.service_student_ms += part.student_count * duration_ms
        self._update_starvation(place_id)
        session = self.count_sessions.get(part.count_session_id) if part.count_session_id else None
        if session and not session.related_event_ids:
            self._open_count_session(session, part)
        self.schedule(
            self.now + duration_ms,
            PHASE_COMPLETION_RELEASE,
            "service_complete",
            part,
        )

    def _on_service_complete(self, part: Part) -> None:
        place_id = part.place_id
        stage = self._stage(part)
        extra = stage.get("completion_event")
        if getattr(part, "_is_initial_queue", False):
            self.emit(
                "service_complete",
                part,
                place_id=place_id,
                primary_cause="service_duration_elapsed",
            )
            self.servers_busy[place_id] -= 1
            self._update_starvation(place_id)
            self._release_station_worker(part)
            if place_id:
                self._vacate_place(place_id, part)
            part.status = "completed"
            self.try_start_service(place_id)
            return
        self.emit(
            "service_complete",
            part,
            place_id=place_id,
            primary_cause="service_duration_elapsed",
        )
        if extra in {"entrance_completion", "seated_completion"}:
            if extra == "seated_completion":
                self.seated_count += part.student_count
                self.seated_count_by_place[place_id] = (
                    self.seated_count_by_place.get(place_id, 0) + part.student_count
                )
            self.emit(
                extra,
                part,
                place_id=place_id,
                primary_cause=extra,
            )
        self.servers_busy[place_id] -= 1
        self._update_starvation(place_id)
        self._release_station_worker(part)
        session = self.count_sessions.get(part.count_session_id) if part.count_session_id else None
        if session and not session.is_recount and session.method == "pass_through" and session.batch_action is None:
            session.remaining -= 1
            part.stage_index += 1
            session.already_advanced = True
            self.begin_stage(part)
            self.try_start_service(place_id)
            if session.remaining <= 0:
                self._resolve_count_session(session, advance=False)
            return
        if session and not session.is_recount:
            part.status = "count_pending"
            session.remaining -= 1
            self.try_start_service(place_id)
            if session.remaining <= 0:
                self._resolve_count_session(session)
            return
        part.stage_index += 1
        self.begin_stage(part)
        self.try_start_service(place_id)

    def _on_batch_start(self, part: Part, payload: dict) -> None:
        if part.status == "in_service":
            return
        stage = self._stage(part)
        if stage.get("kind") != "batch_service":
            return
        resource_id = payload["resource_id"]
        resource = self.resources[resource_id]
        if not self._has_idle_passthrough_workers(part, stage):
            resource.busy = False
            resource.available = True
            resource.assigned_part_id = None
            if resource.fleet_id and stage.get("action") == "board":
                self.fleet_berths_busy[resource.fleet_id] = max(
                    0, self.fleet_berths_busy.get(resource.fleet_id, 0) - 1
                )
                w_rel = self.berth_active_workers.pop(part.part_id, [])
                if w_rel and self.worker_pool.workers:
                    self.worker_pool.release(w_rel, self.now)
            part.status = "waiting_count"
            if part.part_id not in self.wait_workers:
                self.wait_workers.append(part.part_id)
            self._begin_wait(part, "waiting_for_counter")
            return
        if not self._ensure_cohort_escorts(part):
            resource.busy = False
            resource.available = True
            resource.assigned_part_id = None
            if resource.fleet_id and stage.get("action") == "board":
                self.fleet_berths_busy[resource.fleet_id] = max(
                    0, self.fleet_berths_busy.get(resource.fleet_id, 0) - 1
                )
                w_rel = self.berth_active_workers.pop(part.part_id, [])
                if w_rel and self.worker_pool.workers:
                    self.worker_pool.release(w_rel, self.now)
            return
        self._end_wait(part)
        part.status = "in_service"
        if resource_id not in part.resource_ids:
            part.resource_ids.append(resource_id)
        resource.busy = True
        resource.available = False
        resource.assigned_part_id = part.part_id
        action = stage.get("action") or "batch"
        if action == "alight":
            self._set_vehicle_state(resource, "busy", "alighting")
        else:
            self._set_vehicle_state(resource, "busy", action)
        self.emit(
            "batch_start",
            part,
            place_id=part.place_id,
            resource_ids=[resource_id],
            escort_ids=list(part.escort_ids),
            worker_ids=list(part.escort_ids),
            primary_cause=action,
        )
        duration_ms = self._batch_duration_ms(stage, part, resource)
        session = self._maybe_start_attached_passthrough(
            part, stage, flow_total_s=ms_to_s(duration_ms)
        )
        if session is not None:
            duration_ms = to_ms(session.duration_s)
        self.service_student_ms += part.student_count * duration_ms
        self.schedule(
            self.now + duration_ms,
            PHASE_COMPLETION_RELEASE,
            "batch_complete",
            part,
            resource_id=resource_id,
            action=action,
        )

    def _on_batch_complete(self, part: Part, payload: dict) -> None:
        if part.status not in {"in_service", "count_pending"}:
            return
        stage = self._stage(part)
        if stage.get("kind") != "batch_service":
            return
        resource_id = payload["resource_id"]
        action = payload.get("action")
        resource = self.resources[resource_id]
        self.emit(
            "batch_complete",
            part,
            place_id=part.place_id,
            resource_ids=[resource_id],
            primary_cause=action or "batch_complete",
        )
        if action == "board" and resource.fleet_id:
            self.fleet_berths_busy[resource.fleet_id] = max(
                0, self.fleet_berths_busy.get(resource.fleet_id, 0) - 1
            )
            w_rel = self.berth_active_workers.pop(part.part_id, [])
            if w_rel and self.worker_pool.workers:
                self.worker_pool.release(w_rel, self.now)
            self.try_start_fleet(resource.fleet_id)
        session = self.count_sessions.get(part.count_session_id) if part.count_session_id else None
        if session is not None:
            session.resource_ids = list(part.resource_ids)
            session.batch_action = action
            part.status = "count_pending"
            session.remaining = 0
            self._resolve_count_session(session)
            return
        if action == "alight":
            part.resource_ids = [rid for rid in part.resource_ids if rid != resource_id]
            self.schedule(
                self.now,
                PHASE_COMPLETION_RELEASE,
                "resource_release",
                part,
                resource_id=resource_id,
            )
            resource.place_id = part.place_id
            resource.aboard_students = 0
            self.space.leave_vehicle(resource.place_id, resource.resource_id)
            if resource.fleet_id:
                self.fleet_dropoff_busy[resource.fleet_id] = max(
                    0, self.fleet_dropoff_busy.get(resource.fleet_id, 0) - 1
                )
                self._try_start_waiting_alight(resource.fleet_id)
            self._start_vehicle_cycle_or_release(resource)
            merged_subs = getattr(part, "_merged_parts", None)
            if merged_subs:
                part.status = "split"
                part.members = []
                part.student_count = 0
                for sub in merged_subs:
                    self.parts[sub.part_id] = sub
                    sub.status = "ready"
                    sub.place_id = part.place_id
                    sub.stage_index = part.stage_index + 1
                    sub.resource_ids = []
                    if self.regroup_policy.get("required") and self.regroup_policy.get("place_id") == sub.place_id:
                        if not getattr(sub, "_regrouped", False):
                            sub._regrouped = True
                            self._start_hold(sub, {"group_assembled": True})
                            continue
                    self.begin_stage(sub)
                return
        part.stage_index += 1
        if self.regroup_policy.get("required") and self.regroup_policy.get("place_id") == part.place_id:
            if not getattr(part, "_regrouped", False):
                part._regrouped = True
                self._start_hold(part, {"group_assembled": True})
                return
        self.begin_stage(part)

    def _on_resource_release(self, resource_id: str, part: Part | None) -> None:
        resource = self.resources[resource_id]
        self.emit(
            "resource_release",
            part,
            resource_ids=[resource_id],
            place_id=resource.place_id,
            primary_cause="resource_released",
        )

    def begin_stage(self, part: Part) -> None:
        self._begin_depth += 1
        try:
            if self._begin_depth > 32:
                self.violations.append(
                    {
                        "type": "engine_loop",
                        "message": "stage chain exceeded bound",
                        "part_id": part.part_id,
                    }
                )
                return
            if part.stage_index >= len(self._stage_list(part)):
                d_rule = self.policy.get("destination_rule") or {}
                if d_rule.get("type") == "wait_for_imposed_opening":
                    cal_id = d_rule.get("calendar_id")
                    if not cal_id:
                        cal_id = next(
                            (
                                cid
                                for cid, cal in self.calendars.items()
                                if (cal.get("kind") in {"opening", "hall", "hall_opening"})
                            ),
                            None,
                        )
                    if cal_id and not self.calendar_open.get(cal_id, False):
                        if not getattr(part, "_destination_hold_started", False):
                            part._destination_hold_started = True
                            self._start_hold(part, {"calendar_id": cal_id})
                            return
                delay_s = float(d_rule.get("coordination_delay_s") or 0)
                if delay_s > 0 and not getattr(part, "_destination_delayed", False):
                    part._destination_delayed = True
                    self.schedule(self.now + to_ms(delay_s), PHASE_COMPLETION_RELEASE, "destination_delayed_complete", part)
                    return
                self._complete_part(part)
                return
            stage = self._stage(part)
            if stage.get("id") in {"final_hall_approach_north", "final_hall_approach_south"}:
                self.dtsp_allocated_students += part.student_count
            elif (
                stage.get("id") == "final_hall_approach"
                and part.place_id == "dtsp_exterior_gathering"
                and "g03_seating" in self.places
                and not getattr(part, "_dtsp_allocated", False)
            ):
                dtsp_cap = self.effective_seats if self.effective_seats is not None else 3000
                carpark_cap = (
                    max(0, dtsp_cap - self.expected_walking_students)
                    if self.expected_walking_students > 0
                    else dtsp_cap
                )
                if self.dtsp_carpark_allocated_students >= carpark_cap or self.dtsp_allocated_students >= dtsp_cap:
                    self.g03_allocated_students += part.student_count
                    self.emit(
                        "cohort_diverted",
                        part,
                        from_place_id="dtsp_exterior_gathering",
                        to_place_id="g03_foyer_entrance",
                        primary_cause="overflow_diversion",
                    )
                    part.stages = [
                        self.stages_by_id[sid]
                        for sid in ("carpark_to_g03", "g03_foyer_to_seating", "g03_seating")
                    ]
                    part.stage_index = 0
                    stage = self._stage(part)
                elif self.dtsp_carpark_allocated_students + part.student_count > carpark_cap:
                    remaining = carpark_cap - self.dtsp_carpark_allocated_students
                    if remaining > 0 and part.student_count > remaining:
                        self.dtsp_carpark_allocated_students += remaining
                        self.dtsp_allocated_students += remaining
                        self.g03_allocated_students += (part.student_count - remaining)
                        part_fit = Part(
                            part_id=f"{part.part_id}_dtsp",
                            group_id=part.group_id,
                            parent_part_id=part.part_id,
                            source_unit_id=part.source_unit_id,
                            hostel_id=part.hostel_id,
                            hostel_composition=_composition_from_members(part.members[:remaining], part.hostel_id),
                            student_count=remaining,
                            members=part.members[:remaining],
                            queue_tie_key=part.queue_tie_key,
                            stage_index=part.stage_index,
                            place_id=part.place_id,
                            leg_id=part.leg_id,
                            resource_ids=list(part.resource_ids),
                            status="ready",
                            arrival_ms=self.now,
                            current_stage_id=part.current_stage_id,
                            parent_group_id=part.parent_group_id or part.group_id,
                            source_unit_ids=sorted(_membership_from_members(part.members[:remaining]).keys()),
                            source_unit_membership=_membership_from_members(part.members[:remaining]),
                            count_record_ids=list(part.count_record_ids),
                            required_supervision=dict(part.required_supervision),
                            internal_calculation=True,
                            covered_checkpoint_ids=list(part.covered_checkpoint_ids),
                            estimated_occupancy=remaining,
                            escort_ids=list(part.escort_ids),
                            root_part_id=part.root_part_id or part.part_id,
                            version=1,
                            stages=getattr(part, "stages", None),
                            cohort_id=getattr(part, "cohort_id", None),
                        )
                        part_fit._dtsp_allocated = True
                        part_div = Part(
                            part_id=f"{part.part_id}_g03",
                            group_id=part.group_id,
                            parent_part_id=part.part_id,
                            source_unit_id=part.source_unit_id,
                            hostel_id=part.hostel_id,
                            hostel_composition=_composition_from_members(part.members[remaining:], part.hostel_id),
                            student_count=part.student_count - remaining,
                            members=part.members[remaining:],
                            queue_tie_key=part.queue_tie_key,
                            stage_index=0,
                            place_id=part.place_id,
                            leg_id=part.leg_id,
                            resource_ids=list(part.resource_ids),
                            status="ready",
                            arrival_ms=self.now,
                            current_stage_id=part.current_stage_id,
                            parent_group_id=part.parent_group_id or part.group_id,
                            source_unit_ids=sorted(_membership_from_members(part.members[remaining:]).keys()),
                            source_unit_membership=_membership_from_members(part.members[remaining:]),
                            count_record_ids=list(part.count_record_ids),
                            required_supervision=dict(part.required_supervision),
                            internal_calculation=True,
                            covered_checkpoint_ids=list(part.covered_checkpoint_ids),
                            estimated_occupancy=part.student_count - remaining,
                            escort_ids=list(part.escort_ids),
                            root_part_id=part.root_part_id or part.part_id,
                            version=1,
                            stages=[
                                self.stages_by_id[sid]
                                for sid in ("carpark_to_g03", "g03_foyer_to_seating", "g03_seating")
                            ],
                            cohort_id=getattr(part, "cohort_id", None),
                        )
                        self.parts[part_fit.part_id] = part_fit
                        self.parts[part_div.part_id] = part_div
                        part.status = "split"
                        part.version += 1
                        self.emit(
                            "cohort_diverted",
                            part_div,
                            from_place_id="dtsp_exterior_gathering",
                            to_place_id="g03_foyer_entrance",
                            primary_cause="overflow_diversion",
                        )
                        self.begin_stage(part_fit)
                        self.begin_stage(part_div)
                        return
                    else:
                        self.g03_allocated_students += part.student_count
                        self.emit(
                            "cohort_diverted",
                            part,
                            from_place_id="dtsp_exterior_gathering",
                            to_place_id="g03_foyer_entrance",
                            primary_cause="overflow_diversion",
                        )
                        part.stages = [
                            self.stages_by_id[sid]
                            for sid in ("carpark_to_g03", "g03_foyer_to_seating", "g03_seating")
                        ]
                        part.stage_index = 0
                        stage = self._stage(part)
                else:
                    self.dtsp_carpark_allocated_students += part.student_count
                    self.dtsp_allocated_students += part.student_count
            self._check_stage_behavior_events(part, "before_stage", stage["id"])
            if part.status in {"split", "withdrawn"}:
                return
            part.current_stage_id = stage["id"]
            if not self._ensure_cohort_escorts(part):
                return
            if part.status == "waiting_escort":
                part.status = "ready"
                if part.part_id in self.wait_workers:
                    self.wait_workers = [
                        item for item in self.wait_workers if item != part.part_id
                    ]
                self._end_wait(part)
            kind = stage["kind"]
            if kind in {"travel", "vehicle_travel"}:
                if kind == "vehicle_travel" and stage.get("resource_id"):
                    if stage["resource_id"] not in part.resource_ids:
                        part.resource_ids.append(stage["resource_id"])
                if self._policy_blocks_release(part, stage):
                    self._hold_for_policy(part)
                    return
                if self._leg_is_closed(stage):
                    self._hold_for_path(part, stage)
                    return
                dest = self.legs[stage["leg_id"]]["to_place_id"]
                if self.space_policy.reserves_before_departure():
                    if not self._try_reserve_destination(part, dest):
                        self._hold_for_space(part, dest)
                        return
                self.schedule(self.now, PHASE_START_DEPART, "departure", part)
                return
            if kind == "hold":
                until = stage.get("until") or {}
                if self._condition_met(until, part):
                    part.stage_index += 1
                    self.begin_stage(part)
                    return
                self._start_hold(part, until)
                return
            if kind == "queue_service":
                self._enqueue_service(part)
                return
            if kind == "batch_service":
                if stage.get("action") == "board" and self._policy_blocks_release(part, stage):
                    self._hold_for_policy(part)
                    return
                self._enqueue_batch(part, stage)
                return
            if kind == "manual_count":
                self._start_manual_count(part, stage)
                return
        finally:
            self._begin_depth -= 1

    def _start_hold(self, part: Part, until: dict) -> None:
        part.status = "holding"
        if "duration_s" in until or "dwell_s" in until:
            duration_s = float(until.get("duration_s") or until.get("dwell_s"))
            cause = until.get("cause", "headcount_staging")
            self._begin_wait(part, cause)
            self.emit(
                "hold_start",
                part,
                place_id=part.place_id,
                primary_cause=cause,
            )
            self.schedule(
                self.now + to_ms(duration_s),
                PHASE_COMPLETION_RELEASE,
                "hold_duration_complete",
                part,
                primary_cause=cause,
            )
            return
        if "calendar_id" in until:
            cal_id = until["calendar_id"]
            cal = self.calendars.get(cal_id) or {}
            cause = cal.get("cause") or cal.get("delay_cause") or cal.get("primary_cause")
            if not cause:
                cal_kind = cal.get("kind")
                if cal_kind == "release":
                    cause = "waiting_for_release"
                elif cal_kind in {"opening", "hall", "hall_opening"}:
                    cause = "waiting_for_hall_open"
                else:
                    cause = "waiting_for_opening"
            self.wait_calendar.setdefault(cal_id, []).append(part.part_id)
            self._begin_wait(part, cause)
            self.emit(
                "hold_start",
                part,
                place_id=part.place_id,
                calendar_id=cal_id,
                primary_cause=cause,
            )
            return
        if "resource_available" in until:
            resource_id = until["resource_available"]
            cause = "waiting_for_vehicle"
            self._begin_wait(part, cause)
            self.emit(
                "hold_start",
                part,
                place_id=part.place_id,
                resource_ids=[resource_id],
                primary_cause=cause,
            )
            if self.resources[resource_id].available and self._vehicle_service_ok(
                self.resources[resource_id]
            ):
                self._end_wait(part)
                self.emit("hold_end", part, place_id=part.place_id, resource_ids=[resource_id])
                part.stage_index += 1
                self.begin_stage(part)
            return
        if "fleet_available" in until:
            fleet_id = until["fleet_available"]
            cause = "waiting_for_vehicle"
            self._begin_wait(part, cause)
            self.emit(
                "hold_start",
                part,
                place_id=part.place_id,
                resource_ids=list(self.fleets[fleet_id]["vehicle_ids"]),
                primary_cause=cause,
            )
            if self._fleet_has_available(fleet_id):
                self._end_wait(part)
                self.emit(
                    "hold_end",
                    part,
                    place_id=part.place_id,
                    resource_ids=list(self.fleets[fleet_id]["vehicle_ids"]),
                )
                part.stage_index += 1
                self.begin_stage(part)
            return
        if until.get("group_assembled"):
            cause = "waiting_for_regroup"
            self.wait_group.setdefault(part.group_id, []).append(part.part_id)
            self._begin_wait(part, cause)
            self.emit(
                "hold_start",
                part,
                place_id=part.place_id,
                primary_cause=cause,
            )
            self._try_release_assembled_group(part.group_id)
            return
        if "hostels_departed" in until or "hold_until_hostels_departed" in until:
            target_hostels = list(until.get("hostels_departed") or until.get("hold_until_hostels_departed"))
            min_dispatch_s = float(until.get("min_dispatch_s") or 0.0)
            cause = until.get("cause", "imposed_sequencing_wait")
            self._begin_wait(part, cause)
            self.emit(
                "hold_start",
                part,
                place_id=part.place_id,
                primary_cause=cause,
            )
            min_ms = to_ms(min_dispatch_s)
            self.wait_hostels_departed.append((part.part_id, target_hostels, min_ms, cause))
            if min_ms > self.now:
                self.schedule(
                    min_ms,
                    PHASE_COMPLETION_RELEASE,
                    "check_hostels_departed_hold",
                    None,
                )
            else:
                self._check_hostels_departed_waits()
            return
        self._begin_wait(part, "waiting")
        self.emit("hold_start", part, place_id=part.place_id, primary_cause="waiting")

    def _enqueue_service(self, part: Part) -> None:
        stage = self._stage(part)
        place_id = stage["place_id"]
        parts = self._split_if_needed(part)
        session = self._maybe_prepare_queue_passthrough(part, parts, stage)
        for sub in parts:
            sub.place_id = place_id
            sub.arrival_ms = self.now
            sub.status = "queued"
            if session is not None:
                sub.count_session_id = session.session_id
            self.queues[place_id].append(sub.part_id)
            self._maybe_execute_pending_queue_jump(sub, place_id)
            self._begin_wait(sub, "waiting_for_server")
        self._note_queue_peak(place_id)
        self.try_start_service(place_id)

    def _split_if_needed(self, part: Part) -> list[Part]:
        if part.student_count <= 1:
            return [part]
        self._end_wait(part)
        subs: list[Part] = []
        for member in sorted(part.members, key=lambda item: (str(item["queue_tie_key"]), item["student_key"])):
            sub = Part(
                part_id=f"{part.part_id}~{member['student_key']}",
                group_id=part.group_id,
                parent_part_id=part.part_id,
                source_unit_id=member.get("source_unit_id") or part.source_unit_id,
                hostel_id=part.hostel_id,
                hostel_composition={part.hostel_id: 1},
                student_count=1,
                members=[member],
                queue_tie_key=str(member["queue_tie_key"]),
                stage_index=part.stage_index,
                place_id=part.place_id,
                leg_id=None,
                resource_ids=list(part.resource_ids),
                status="queued",
                arrival_ms=self.now,
                current_stage_id=part.current_stage_id,
                parent_group_id=part.parent_group_id or part.group_id,
                source_unit_ids=[member.get("source_unit_id") or part.source_unit_id],
                source_unit_membership={
                    member.get("source_unit_id") or part.source_unit_id: 1
                },
                count_record_ids=list(part.count_record_ids),
                required_supervision=dict(part.required_supervision),
                internal_calculation=True,
                covered_checkpoint_ids=list(part.covered_checkpoint_ids),
                estimated_occupancy=part.estimated_occupancy,
                escort_ids=list(part.escort_ids),
                root_part_id=part.root_part_id or part.part_id,
                version=1,
                stages=getattr(part, "stages", None),
                cohort_id=member.get("cohort_id") or getattr(part, "cohort_id", None),
            )
            self.parts[sub.part_id] = sub
            subs.append(sub)
        part.status = "split"
        part.version += 1
        return subs

    def try_start_service(self, place_id: str) -> None:
        queue = self.queues[place_id]
        queue.sort(key=self._queue_sort_key)
        min_n = self.worker_pool.min_station_for(place_id)
        if min_n and self.worker_pool.capable_count("station") < min_n:
            return
        while self.servers_busy[place_id] < self.server_count[place_id] and queue:
            if (
                self.seating_place_id
                and place_id == self.seating_place_id
                and self.effective_seats is not None
                and self.seated_count_by_place.get(place_id, 0) + self.servers_busy[place_id] >= self.effective_seats
            ):
                break
            if (
                place_id == "g03_seating"
                and (self.places.get("g03_seating") or {}).get("capacity_students") is not None
                and self.seated_count_by_place.get(place_id, 0) + self.servers_busy[place_id] >= int((self.places.get("g03_seating") or {})["capacity_students"])
            ):
                pass
            pid = queue[0]
            part = self.parts[pid]
            if not self._ensure_count_workers(part):
                break
            if self.worker_pool.uses_station_staff(place_id):
                if not self._reserve_station_worker(part, place_id):
                    break
            queue.pop(0)
            self.servers_busy[place_id] += 1
            self._note_queue_peak(place_id)
            self.schedule(self.now, PHASE_START_DEPART, "service_start", part)
        self._update_starvation(place_id)

    def _enqueue_batch(self, part: Part, stage: dict) -> None:
        action = stage.get("action")
        fleet_id = stage.get("fleet_id")
        if fleet_id:
            if action == "alight" and part.resource_ids:
                self._enqueue_alight(part, part.resource_ids[0], fleet_id)
                return
            self.wait_resource.setdefault(fleet_id, []).append(part.part_id)
            self._begin_wait(part, "waiting_for_vehicle")
            if not self._fleet_dispatch_scheduled.get(fleet_id):
                self._fleet_dispatch_scheduled[fleet_id] = True
                self.schedule(
                    self.now,
                    PHASE_START_DEPART,
                    "check_fleet_dispatch",
                    None,
                    fleet_id=fleet_id,
                )
            return
        resource_id = stage["resource_id"]
        resource = self.resources[resource_id]
        if resource.assigned_part_id is not None and resource.assigned_part_id in {
            part.part_id,
            part.parent_part_id,
        }:
            if part.student_count > resource.capacity_students:
                self.violations.append(
                    {
                        "type": "physical_capacity",
                        "resource_id": resource_id,
                        "occupancy": part.student_count,
                        "capacity_students": resource.capacity_students,
                    }
                )
                return
            if action == "alight" and resource.fleet_id:
                self._enqueue_alight(part, resource_id, resource.fleet_id)
                return
            resource.assigned_part_id = part.part_id
            if not self._has_idle_passthrough_workers(part, stage):
                part.status = "waiting_count"
                if part.part_id not in self.wait_workers:
                    self.wait_workers.append(part.part_id)
                self._begin_wait(part, "waiting_for_counter")
                return
            if not self._ensure_cohort_escorts(part):
                return
            self.schedule(
                self.now,
                PHASE_START_DEPART,
                "batch_start",
                part,
                resource_id=resource_id,
            )
            return
        self.wait_resource.setdefault(resource_id, []).append(part.part_id)
        self._begin_wait(part, "waiting_for_vehicle")
        if resource.available and not resource.busy and self._vehicle_service_ok(resource):
            self.try_start_batch(resource_id)

    def try_start_batch(self, resource_id: str) -> None:
        resource = self.resources[resource_id]
        if not resource.available or resource.busy or not self._vehicle_service_ok(resource):
            return
        waiters = self.wait_resource.get(resource_id, [])
        waiters.sort(key=self._queue_sort_key)
        if not waiters:
            return
        pid = waiters.pop(0)
        part = self.parts[pid]
        if part.student_count > resource.capacity_students:
            subs = self._split_for_vehicle(part, resource.capacity_students)
            if not subs:
                self.violations.append(
                    {
                        "type": "physical_capacity",
                        "resource_id": resource_id,
                        "occupancy": part.student_count,
                        "capacity_students": resource.capacity_students,
                    }
                )
                waiters.insert(0, pid)
                self.wait_resource[resource_id] = waiters
                return
            part = subs[0]
            pid = part.part_id
            for extra in subs[1:]:
                extra.status = "queued"
                extra.arrival_ms = part.arrival_ms
                waiters.append(extra.part_id)
                self._begin_wait(extra, "waiting_for_vehicle")
            for sub in subs:
                self._ensure_part_escorts(sub)
        if not self._has_idle_passthrough_workers(part, self._stage(part)):
            waiters.insert(0, pid)
            self.wait_resource[resource_id] = waiters
            part.status = "waiting_count"
            if part.part_id not in self.wait_workers:
                self.wait_workers.append(part.part_id)
            if part.part_id not in self.open_waits:
                self._begin_wait(part, "waiting_for_counter")
            return
        if not self._ensure_cohort_escorts(part):
            waiters.insert(0, pid)
            self.wait_resource[resource_id] = waiters
            return

        self.wait_resource[resource_id] = waiters
        resource.busy = True
        resource.available = False
        resource.assigned_part_id = pid
        self.schedule(
            self.now,
            PHASE_START_DEPART,
            "batch_start",
            part,
            resource_id=resource_id,
        )

    def _method_for(self, checkpoint: dict) -> str:
        asg = assignment_for(checkpoint, self.policy)
        methods = checkpoint.get("permitted_methods") or ["column"]
        return asg.get("method") or checkpoint.get("method") or methods[0]

    def _passthrough_checkpoint(self, stage: dict) -> dict | None:
        for checkpoint in checkpoints_attached_to_stage(self.scenario, stage["id"]):
            if self._method_for(checkpoint) == "pass_through":
                return checkpoint
        return None

    def _passthrough_workers_needed(self, stage: dict) -> int:
        checkpoint = self._passthrough_checkpoint(stage)
        if checkpoint is None:
            return 0
        return int((checkpoint.get("pass_through") or {}).get("workers_required") or 1)

    def _has_idle_passthrough_workers(self, part: Part, stage: dict) -> bool:
        need = self._passthrough_workers_needed(stage)
        if need <= 0:
            return True
        if (
            self.worker_pool.combined_permitted(part.place_id)
            and len(part.escort_ids) >= need
        ):
            return True
        return len(self._idle_count_workers(part.place_id)) >= need

    def _ensure_count_workers(self, part: Part) -> bool:
        if not part.count_session_id:
            return True
        session = self.count_sessions.get(part.count_session_id)
        if session is None or session.workers:
            return True
        checkpoint = self.checkpoints.get(session.checkpoint_id) or {}
        need = int((checkpoint.get("pass_through") or {}).get("workers_required") or 1)
        reserved = self._reserve_workers(need, part.place_id, session.session_id, part)
        if reserved is None:
            return False
        session.workers = reserved
        return True

    def _new_session(
        self,
        parent: Part,
        members: list[Part],
        checkpoint: dict,
        method: str,
    ) -> CountSession:
        self.session_n += 1
        session_id = f"cs_{self.session_n:04d}"
        occupancy = parent.estimated_occupancy
        if occupancy is None:
            occupancy = parent.student_count
        attendance = parent.student_count
        session = CountSession(
            session_id=session_id,
            checkpoint_id=checkpoint["id"],
            parent_part_id=parent.part_id,
            group_id=parent.group_id,
            source_unit_ids=list(parent.source_unit_ids or [parent.source_unit_id]),
            member_part_ids=[member.part_id for member in members],
            remaining=len(members),
            expected=attendance,
            estimated_occupancy=int(occupancy),
            actual_attendance=attendance,
            method=method,
            workers=[],
            attempt=1,
            max_retries=int(checkpoint.get("max_retries") or 0),
            related_event_ids=[],
            started_ms=self.now,
            place_id=parent.place_id or checkpoint.get("location_id"),
        )
        self.count_sessions[session_id] = session
        parent.count_session_id = session_id
        for member in members:
            member.count_session_id = session_id
        return session

    def _idle_count_workers(self, place_id: str | None) -> list:
        return self.worker_pool.idle_now(place_id, "count", self.now, self.calendar_open)

    def _reserve_workers(
        self,
        n: int,
        place_id: str | None,
        session_id: str | None,
        part: Part,
    ) -> list[str] | None:
        if n <= 0:
            return []
        if self.worker_pool.combined_permitted(place_id) and part.escort_ids:
            reusable = [
                worker_id
                for worker_id in part.escort_ids
                if self.worker_pool.can_perform(
                    self.workers_by_id[worker_id], "count", place_id
                )
                and self.worker_pool.duties_compatible(
                    self.workers_by_id[worker_id], "count", place_id
                )
            ]
            if len(reusable) >= n:
                chosen_ids = reusable[:n]
                self.worker_pool.add_duty(chosen_ids, "count", self.now)
                for worker_id in chosen_ids:
                    self.workers_by_id[worker_id].assigned_session_id = session_id
                return chosen_ids
        idle = self._idle_count_workers(place_id)
        if len(idle) < n:
            self._note_impossible_count_staff(part, n, place_id)
            return None
        chosen = idle[:n]
        return self.worker_pool.reserve_now(
            chosen, "count", place_id, self.now, part.part_id, session_id=session_id
        )

    def _usable_count_workers(self, part: Part, place_id: str | None) -> int:
        n = 0
        for worker in self.workers:
            if not self.worker_pool.can_perform(worker, "count", place_id):
                continue
            if worker.worker_id in part.escort_ids and not self.worker_pool.combined_permitted(
                place_id
            ):
                continue
            n += 1
        return n

    def _note_impossible_count_staff(self, part: Part, need: int, place_id: str | None) -> None:
        if self._usable_count_workers(part, place_id) >= need:
            return
        if any(
            row.get("type") == "insufficient_staff" and row.get("part_id") == part.part_id
            for row in self.violations
        ):
            return
        self.violations.append(
            {
                "type": "insufficient_staff",
                "part_id": part.part_id,
                "need": need,
                "message": "count staff cannot be met from declared workers",
            }
        )

    def _emit_part(self, session: CountSession) -> Part:
        part = self.parts[session.parent_part_id]
        if part.status == "split":
            return self.parts[session.member_part_ids[0]]
        return part

    def _emit_worker_reserved(self, session: CountSession, part: Part) -> None:
        if not session.workers:
            return
        self.emit(
            "worker_reserved",
            part,
            worker_ids=list(session.workers),
            resource_ids=list(session.workers),
            checkpoint_id=session.checkpoint_id,
            primary_cause="count_attention",
        )

    def _release_session_workers(self, session: CountSession) -> None:
        if not session.workers:
            return
        part = self._emit_part(session)
        still_escort: list[str] = []
        fully_release: list[str] = []
        for worker_id in session.workers:
            worker = self.workers_by_id.get(worker_id)
            if worker is None:
                continue
            if "escort" in worker.duties:
                self.worker_pool.drop_duty(worker_id, "count", self.now)
                worker.assigned_session_id = None
                still_escort.append(worker_id)
            else:
                fully_release.append(worker_id)
        if fully_release:
            self.emit(
                "worker_released",
                part,
                worker_ids=list(fully_release),
                resource_ids=list(fully_release),
                checkpoint_id=session.checkpoint_id,
                primary_cause="count_attention_end",
            )
            self.worker_pool.release(fully_release, self.now)
        session.workers = []
        self._try_waiting_counts()
        self._try_waiting_escorts()
        for place_id in list(self.queues):
            self.try_start_service(place_id)
        for resource_id in list(self.resources):
            self.try_start_batch(resource_id)
        for fleet_id in list(self.fleets):
            self.try_start_fleet(fleet_id)

    def _try_waiting_counts(self) -> None:
        waiting = list(self.wait_workers)
        self.wait_workers = []
        for part_id in waiting:
            part = self.parts.get(part_id)
            if part is None or part.status not in {"waiting_count", "holding", "ready", "queued"}:
                if part is not None and part.status in {"waiting_count", "waiting_escort"}:
                    self.wait_workers.append(part_id)
                continue
            session = (
                self.count_sessions.get(part.count_session_id)
                if part.count_session_id
                else None
            )
            if session is not None and (session.is_recount or session.pending_recount):
                self._end_wait(part)
                self._start_recount(session)
                continue
            stage = self._stage(part)
            if stage.get("kind") == "manual_count":
                self._end_wait(part)
                self._start_manual_count(part, stage)
            elif stage.get("kind") == "batch_service":
                self._end_wait(part)
                resource_id = stage.get("resource_id")
                fleet_id = stage.get("fleet_id")
                resource_waiters = self.wait_resource.get(resource_id, []) if resource_id else []
                fleet_waiters = self.wait_resource.get(fleet_id, []) if fleet_id else []
                if resource_id and part.part_id in resource_waiters:
                    self.try_start_batch(resource_id)
                elif fleet_id and part.part_id in fleet_waiters:
                    self.try_start_fleet(fleet_id)
                else:
                    self._enqueue_batch(part, stage)
            elif stage.get("kind") == "queue_service" and part.place_id:
                self.try_start_service(part.place_id)

    def _open_count_session(self, session: CountSession, part: Part) -> None:
        if session.related_event_ids and not session.is_recount:
            return
        if not session.workers:
            need = int(session.n_columns or 1)
            reserved = self._reserve_workers(
                need, part.place_id, session.session_id, part
            )
            if reserved:
                session.workers = reserved
        start_id = self.emit(
            "count_start",
            part,
            checkpoint_id=session.checkpoint_id,
            attempt=session.attempt,
            method=session.method,
            n_columns=session.n_columns,
            longest_column=session.longest_column,
            worker_ids=list(session.workers),
            added_student_queue=session.added_student_queue,
            primary_cause="manual_check",
        )
        session.related_event_ids.append(start_id)
        session.started_ms = self.now
        self._emit_worker_reserved(session, part)
        if session.method == "pass_through" and session.duration_s:
            self.count_student_ms += to_ms(session.duration_s)

    def _maybe_prepare_queue_passthrough(
        self, parent: Part, parts: list[Part], stage: dict
    ) -> CountSession | None:
        checkpoint = self._passthrough_checkpoint(stage)
        if checkpoint is None:
            return None
        rate = float((checkpoint.get("pass_through") or {}).get("count_rate_s_per_person") or 0)
        flow_s = ms_to_s(self.service_duration_ms[stage["place_id"]])
        person_s = passthrough_person_duration_s(flow_s, rate)
        person_ms = to_ms(person_s)
        for sub in parts:
            sub.service_duration_ms = person_ms
        session = self._new_session(parent, parts, checkpoint, "pass_through")
        session.duration_s = person_s * parent.student_count
        session.added_student_queue = False
        return session

    def _maybe_start_attached_passthrough(
        self, part: Part, stage: dict, flow_total_s: float
    ) -> CountSession | None:
        checkpoint = self._passthrough_checkpoint(stage)
        if checkpoint is None:
            return None
        rate = float((checkpoint.get("pass_through") or {}).get("count_rate_s_per_person") or 0)
        duration_s = passthrough_batch_duration_s(flow_total_s, part.student_count, rate)
        need = int((checkpoint.get("pass_through") or {}).get("workers_required") or 1)
        reserved = self._reserve_workers(need, part.place_id, None, part)
        if reserved is None:
            return None
        session = self._new_session(part, [part], checkpoint, "pass_through")
        session.duration_s = duration_s
        session.added_student_queue = False
        session.batch_action = stage.get("action")
        session.resource_ids = list(part.resource_ids)
        session.workers = reserved
        for worker_id in reserved:
            self.workers_by_id[worker_id].assigned_session_id = session.session_id
        self._open_count_session(session, part)
        return session

    def _start_manual_count(self, part: Part, stage: dict) -> None:
        checkpoint = self.checkpoints[stage["checkpoint_id"]]
        method = self._method_for(checkpoint)
        if method == "pass_through":
            rate = float((checkpoint.get("pass_through") or {}).get("count_rate_s_per_person") or 0)
            duration_s = rate * part.student_count
            session = self._new_session(part, [part], checkpoint, "pass_through")
            session.duration_s = duration_s
            need = int((checkpoint.get("pass_through") or {}).get("workers_required") or 1)
            reserved = self._reserve_workers(need, part.place_id, session.session_id, part)
            if reserved is None:
                part.status = "waiting_count"
                self.wait_workers.append(part.part_id)
                self._begin_wait(part, "waiting_for_counter")
                return
            session.workers = reserved
            part.status = "counting"
            self._open_count_session(session, part)
            self.schedule(
                self.now + to_ms(duration_s),
                PHASE_COMPLETION_RELEASE,
                "count_complete",
                part,
                session_id=session.session_id,
            )
            return
        self._start_column_attempt(part, checkpoint, attempt=1, is_recount=False)

    def _column_stats(
        self,
        checkpoint: dict,
        student_count: int,
        place_id: str | None,
        part: Part | None = None,
    ) -> dict:
        params = dict(checkpoint.get("column") or {})
        asg = assignment_for(checkpoint, self.policy)
        requested = int(asg.get("requested_columns") or params.get("requested_columns") or 1)
        space = int(params.get("space_columns") or 1)
        per_col = int(params.get("workers_per_column") or 1)
        idle = self._idle_count_workers(place_id)
        extra = 0
        if part is not None and self.worker_pool.combined_permitted(place_id):
            extra = len(part.escort_ids)
        available = len(idle) + extra
        return column_count_duration_s(
            student_count=student_count,
            setup_s=float(params.get("setup_s") or 0),
            cadence_s_per_person=float(params.get("cadence_s_per_person") or 0),
            aggregation_s=float(params.get("aggregation_s") or 0),
            requested_columns=requested,
            space_columns=space,
            available_workers=available,
            workers_per_column=per_col,
        )

    def _start_column_attempt(
        self,
        part: Part,
        checkpoint: dict,
        *,
        attempt: int,
        is_recount: bool,
        session: CountSession | None = None,
    ) -> None:
        stats = self._column_stats(
            checkpoint,
            part.student_count if session is None else session.actual_attendance,
            part.place_id,
            part,
        )
        need = int(stats["workers_required"])
        reserved = self._reserve_workers(need, part.place_id, None, part)
        if reserved is None:
            part.status = "waiting_count"
            if part.part_id not in self.wait_workers:
                self.wait_workers.append(part.part_id)
            self._begin_wait(part, "waiting_for_counter")
            return
        if session is None:
            session = self._new_session(part, [part], checkpoint, "column")
        session.workers = reserved
        session.n_columns = int(stats["n_columns"])
        session.longest_column = int(stats["longest_column"])
        session.duration_s = float(stats["duration_s"])
        session.attempt = attempt
        session.is_recount = is_recount
        session.started_ms = self.now
        for worker_id in reserved:
            self.workers_by_id[worker_id].assigned_session_id = session.session_id
        part.status = "counting"
        if is_recount:
            start_id = self.emit(
                "recount_start",
                part,
                checkpoint_id=checkpoint["id"],
                attempt=attempt,
                method="column",
                n_columns=session.n_columns,
                longest_column=session.longest_column,
                worker_ids=list(session.workers),
                primary_cause="count_disagreement",
            )
            session.related_event_ids.append(start_id)
            self._emit_worker_reserved(session, part)
            event_type = "recount_complete"
        else:
            self._open_count_session(session, part)
            event_type = "count_complete"
        count_ms = session.actual_attendance * to_ms(session.duration_s)
        self.service_student_ms += count_ms
        self.count_student_ms += count_ms
        self.schedule(
            self.now + to_ms(session.duration_s),
            PHASE_COMPLETION_RELEASE,
            event_type,
            part,
            session_id=session.session_id,
        )

    def _on_count_complete(self, part: Part, payload: dict) -> None:
        session = self.count_sessions[payload["session_id"]]
        self._resolve_count_session(session)

    def _attach_record(self, session: CountSession, record_id: str) -> None:
        parent = self.parts[session.parent_part_id]
        targets = [parent]
        for part_id in session.member_part_ids:
            member = self.parts.get(part_id)
            if member is not None:
                targets.append(member)
        for target in targets:
            if record_id not in target.count_record_ids:
                target.count_record_ids.append(record_id)
            if session.checkpoint_id not in target.covered_checkpoint_ids:
                target.covered_checkpoint_ids.append(session.checkpoint_id)

    def _resolve_count_session(self, session: CountSession, advance: bool = True) -> None:
        part = self._emit_part(session)
        self._release_session_workers(session)
        event_type = "recount_complete" if session.is_recount else "count_complete"
        complete_id = self.emit(
            event_type,
            part,
            checkpoint_id=session.checkpoint_id,
            attempt=session.attempt,
            method=session.method,
            n_columns=session.n_columns,
            longest_column=session.longest_column,
            worker_ids=[],
            primary_cause="count_duration_elapsed",
            related_event_ids=list(session.related_event_ids),
        )
        session.related_event_ids.append(complete_id)
        observed, is_error = draw_observed_count(
            self.rng,
            session.expected,
            self.error_assumption,
            session.attempt - 1,
            student_count=session.actual_attendance,
        )
        occupancy = session.estimated_occupancy
        attendance = session.actual_attendance
        attendance_gap = occupancy != attendance
        treat_gap = bool(
            (self.scenario.get("operating_rules") or {}).get("treat_attendance_gap_as_count_error")
        )
        if attendance_gap and treat_gap and observed == attendance and occupancy != observed:
            is_error = True
        disagreement = observed != session.expected
        if is_error:
            outcome = "disagreement"
        elif attendance_gap:
            outcome = "attendance_gap"
        else:
            outcome = "agreed"
        self.count_n += 1
        record_id = f"cnt_{self.count_n:04d}"
        record = {
            "count_record_id": record_id,
            "checkpoint_id": session.checkpoint_id,
            "group_id": session.group_id,
            "part_id": session.parent_part_id,
            "source_unit_ids": list(session.source_unit_ids),
            "estimated_occupancy": occupancy,
            "actual_attendance": attendance,
            "expected_count": session.expected,
            "observed_count": observed,
            "disagreement": disagreement,
            "is_count_error": is_error,
            "retries": max(0, session.attempt - 1),
            "attempt": session.attempt,
            "outcome": outcome,
            "method": session.method,
            "related_event_ids": list(session.related_event_ids),
            "n_columns": session.n_columns,
            "longest_column": session.longest_column,
            "duration_s": session.duration_s,
            "added_student_queue": session.added_student_queue,
            "exposure_unit": self.error_assumption.get("exposure_unit") or "checkpoint_pass",
            "relationship_to_load": self.error_assumption.get("relationship_to_load") or "none",
        }
        self.count_records.append(record)
        self._attach_record(session, record_id)
        if is_error:
            dis_id = self.emit(
                "count_disagreement",
                part,
                checkpoint_id=session.checkpoint_id,
                expected_count=session.expected,
                observed_count=observed,
                attempt=session.attempt,
                primary_cause="count_mismatch",
                related_event_ids=list(session.related_event_ids),
            )
            session.related_event_ids.append(dis_id)
            record["related_event_ids"] = list(session.related_event_ids)
            if session.attempt <= session.max_retries:
                self._retract_session_completions(session)
                for part_id in session.member_part_ids:
                    member = self.parts[part_id]
                    if member.part_id not in self.open_waits:
                        self._begin_wait(member, "count_disagreement")
                self._start_recount(session)
                return
            un_id = self.emit(
                "count_unresolved",
                part,
                checkpoint_id=session.checkpoint_id,
                expected_count=session.expected,
                observed_count=observed,
                retries=session.attempt - 1,
                primary_cause="retry_limit",
                related_event_ids=list(session.related_event_ids),
            )
            session.related_event_ids.append(un_id)
            record["outcome"] = "unresolved"
            record["related_event_ids"] = list(session.related_event_ids)
            self._retract_session_completions(session)
            for part_id in session.member_part_ids:
                member = self.parts[part_id]
                member.status = "count_blocked"
            parent = self.parts[session.parent_part_id]
            if parent.status != "split":
                parent.status = "count_blocked"
            self.violations.append(
                {
                    "type": "unresolved_count",
                    "checkpoint_id": session.checkpoint_id,
                    "part_id": session.parent_part_id,
                    "retries": session.attempt - 1,
                    "outcome": "unresolved",
                }
            )
            return
        for part_id in session.member_part_ids:
            member = self.parts[part_id]
            if member.part_id in self.open_waits:
                self._end_wait(member)
        if session.already_advanced:
            if session.is_recount:
                self._finish_advanced_session(session)
        elif advance:
            self._advance_session_members(session)

    def _start_recount(self, session: CountSession) -> None:
        checkpoint = self.checkpoints[session.checkpoint_id]
        emit_part = self._emit_part(session)
        session.is_recount = True
        recount_method = checkpoint.get("recount_method") or session.method
        if recount_method == "column" or session.method == "column":
            target = self.parts[session.parent_part_id]
            if target.status == "split":
                target = emit_part
            self._start_column_attempt(
                target,
                checkpoint,
                attempt=session.attempt + 1,
                is_recount=True,
                session=session,
            )
            return
        if not session.pending_recount:
            rate = float((checkpoint.get("pass_through") or {}).get("count_rate_s_per_person") or 0)
            session.duration_s = rate * session.actual_attendance
            session.attempt += 1
        need = int((checkpoint.get("pass_through") or {}).get("workers_required") or 1)
        reserved = self._reserve_workers(need, session.place_id, session.session_id, emit_part)
        if reserved is None:
            session.pending_recount = True
            emit_part.status = "waiting_count"
            if emit_part.part_id not in self.wait_workers:
                self.wait_workers.append(emit_part.part_id)
            return
        session.pending_recount = False
        session.workers = reserved
        for part_id in session.member_part_ids:
            self.parts[part_id].status = "counting"
        start_id = self.emit(
            "recount_start",
            emit_part,
            checkpoint_id=session.checkpoint_id,
            attempt=session.attempt,
            method="pass_through",
            worker_ids=list(session.workers),
            primary_cause="count_disagreement",
            related_event_ids=list(session.related_event_ids),
        )
        session.related_event_ids.append(start_id)
        self._emit_worker_reserved(session, emit_part)
        self.schedule(
            self.now + to_ms(session.duration_s),
            PHASE_COMPLETION_RELEASE,
            "recount_complete",
            emit_part,
            session_id=session.session_id,
        )

    def _session_member_parts(self, session: CountSession) -> list[Part]:
        parent = self.parts[session.parent_part_id]
        if parent.status == "split":
            return [self.parts[pid] for pid in session.member_part_ids if pid in self.parts]
        return [parent]

    def _retract_session_completions(self, session: CountSession) -> None:
        members = self._session_member_parts(session)
        keys = {member["student_key"] for part in members for member in part.members}
        self.completions = [row for row in self.completions if row["student_key"] not in keys]
        for part in members:
            if part.status == "completed":
                if part.place_id:
                    self.occupancy[part.place_id] = (
                        self.occupancy.get(part.place_id, 0) + part.student_count
                    )
                part.status = "count_pending"

    def _finish_advanced_session(self, session: CountSession) -> None:
        seen: set[str] = set()
        for part in self._session_member_parts(session):
            if part.part_id in seen:
                continue
            seen.add(part.part_id)
            part.count_session_id = None
            if part.stage_index >= len(self._stage_list(part)):
                self._complete_part(part)

    def _advance_session_members(self, session: CountSession) -> None:
        parent = self.parts[session.parent_part_id]
        members: list[Part] = []
        if parent.status == "split":
            for part_id in session.member_part_ids:
                members.append(self.parts[part_id])
        else:
            members = [parent]
        seen: set[str] = set()
        for part in members:
            if part.part_id in seen:
                continue
            seen.add(part.part_id)
            if session.batch_action == "alight":
                for resource_id in list(part.resource_ids):
                    resource = self.resources[resource_id]
                    part.resource_ids = [rid for rid in part.resource_ids if rid != resource_id]
                    self.schedule(
                        self.now,
                        PHASE_COMPLETION_RELEASE,
                        "resource_release",
                        part,
                        resource_id=resource_id,
                    )
                    resource.place_id = part.place_id
                    if resource.fleet_id:
                        self.fleet_dropoff_busy[resource.fleet_id] = max(
                            0, self.fleet_dropoff_busy.get(resource.fleet_id, 0) - 1
                        )
                        self._try_start_waiting_alight(resource.fleet_id)
                    self._start_vehicle_cycle_or_release(resource)
            part.count_session_id = None
            part.stage_index += 1
            self.begin_stage(part)

    def _queue_sort_key(self, pid: str) -> tuple:
        part = self.parts[pid]
        priority = getattr(part, "queue_priority", 0)
        return (priority, part.arrival_ms, str(part.queue_tie_key), part.part_id)

    def _condition_met(self, until: dict, part: Part) -> bool:
        if not until:
            return True
        if "duration_s" in until or "dwell_s" in until:
            return False
        if "calendar_id" in until:
            return bool(self.calendar_open.get(until["calendar_id"]))
        if "resource_available" in until:
            resource = self.resources[until["resource_available"]]
            return bool(resource.available) and self._vehicle_service_ok(resource)
        if "fleet_available" in until:
            return self._fleet_has_available(until["fleet_available"])
        if until.get("group_assembled"):
            return self._group_is_assembled(part)
        if "hostels_departed" in until or "hold_until_hostels_departed" in until:
            target_hostels = list(until.get("hostels_departed") or until.get("hold_until_hostels_departed"))
            min_dispatch_ms = to_ms(float(until.get("min_dispatch_s") or 0.0))
            if self.now < min_dispatch_ms:
                return False
            return all(self._hostel_has_departed(hid) for hid in target_hostels)
        return False

    def _hostel_has_departed(self, hostel_id: str) -> bool:
        hostel_parts = [
            p for p in self.parts.values()
            if p.hostel_id == hostel_id and getattr(p, "root_part_id", p.part_id) == p.part_id
        ]
        if not hostel_parts:
            return True
        has_transit = any(
            any(st.get("id") == "transit" for st in self._stage_list(p))
            for p in hostel_parts
        )
        if has_transit:
            return all(
                p.status in {"completed", "split"}
                or any(st.get("id") == "transit" and p.stage_index >= idx for idx, st in enumerate(self._stage_list(p)))
                for p in hostel_parts
            )
        return all(p.stage_index > 0 or p.status in {"travelling", "completed", "split"} for p in hostel_parts)
    def _check_hostels_departed_waits(self) -> None:
        if not self.wait_hostels_departed:
            return
        remaining = []
        for pid, target_hostels, min_dispatch_ms, cause in self.wait_hostels_departed:
            part = self.parts.get(pid)
            if part is None or part.status in {"split", "withdrawn", "completed"}:
                continue
            if self.now < min_dispatch_ms:
                remaining.append((pid, target_hostels, min_dispatch_ms, cause))
                continue
            all_departed = all(self._hostel_has_departed(hid) for hid in target_hostels)
            if all_departed:
                self._end_wait(part)
                self.emit("hold_end", part, place_id=part.place_id, primary_cause=cause)
                part.status = "ready"
                part.stage_index += 1
                self.begin_stage(part)
            else:
                remaining.append((pid, target_hostels, min_dispatch_ms, cause))
        self.wait_hostels_departed = remaining

    def _stage_list(self, part: Part) -> list[dict]:
        if getattr(part, "stages", None):
            return part.stages
        cohort_id = getattr(part, "cohort_id", None)
        if cohort_id and cohort_id in self.routes:
            return self.routes[cohort_id]
        source_unit_id = getattr(part, "source_unit_id", None)
        if source_unit_id and source_unit_id in self.routes:
            return self.routes[source_unit_id]
        if part.hostel_id in self.routes:
            return self.routes[part.hostel_id]
        return self.stages

    def _stage(self, part: Part) -> dict:
        return self._stage_list(part)[part.stage_index]

    def _set_vehicle_state(self, resource: Resource, state: str, reason: str | None = None) -> None:
        if resource.state == state and resource.state_reason == reason:
            return
        if resource.state_since_ms < self.now or resource.state != state:
            self.vehicle_intervals.append(
                {
                    "resource_id": resource.resource_id,
                    "state": resource.state,
                    "reason": resource.state_reason,
                    "start_ms": resource.state_since_ms,
                    "end_ms": self.now,
                }
            )
        resource.state = state
        resource.state_reason = reason
        resource.state_since_ms = self.now

    def _close_vehicle_states(self) -> None:
        for resource in self.resources.values():
            self.vehicle_intervals.append(
                {
                    "resource_id": resource.resource_id,
                    "state": resource.state,
                    "reason": resource.state_reason,
                    "start_ms": resource.state_since_ms,
                    "end_ms": self.now,
                }
            )
            resource.state_since_ms = self.now

    def _note_queue_peak(self, place_id: str) -> None:
        queued = sum(
            self.parts[pid].student_count
            for pid in self.queues.get(place_id, [])
            if pid in self.parts
        )
        current = self.peak_queue_students.get(place_id, 0)
        if queued > current:
            self.peak_queue_students[place_id] = queued

    def _update_starvation(self, place_id: str) -> None:
        if place_id not in self.server_count:
            return
        idle = max(0, int(self.server_count[place_id]) - int(self.servers_busy.get(place_id, 0)))
        eligible = bool(self.queues.get(place_id))
        busy = int(self.servers_busy.get(place_id, 0))
        prev = self._starvation_state.pop(place_id, None)
        if prev is not None:
            since, n = prev
            self.unused_service_ms += int(n) * max(0, self.now - int(since))
        if idle > 0 and not eligible and busy > 0:
            self._starvation_state[place_id] = (self.now, idle)

    def _close_starvation(self) -> None:
        for place_id in list(self._starvation_state):
            self._update_starvation(place_id)
            self._starvation_state.pop(place_id, None)

    def _close_over_limit_place(self, place_id: str) -> None:
        open_row = self._over_limit_open.pop(place_id, None)
        if open_row is None:
            return
        limit = int(open_row["limit"])
        max_occ = int(open_row["max_occupancy_students"])
        self.over_limit_intervals.append(
            {
                "place_id": place_id,
                "start_ms": open_row["start_ms"],
                "end_ms": self.now,
                "max_occupancy_students": max_occ,
                "max_excess_students": max(0, max_occ - limit),
            }
        )

    def _close_over_limit(self) -> None:
        for place_id in list(self._over_limit_open):
            self._close_over_limit_place(place_id)

    def _begin_wait(self, part: Part, cause: str, resource_id: str | None = None) -> None:
        existing = self.open_waits.get(part.part_id)
        if existing is not None and existing.cause == cause:
            part.waiting_since_ms = existing.start_ms
            part.wait_cause = cause
            return
        if existing is not None:
            self._end_wait(part)
        part.waiting_since_ms = self.now
        part.wait_cause = cause
        related = [part.last_event_id] if part.last_event_id else []
        self.open_waits[part.part_id] = WaitInterval(
            part_id=part.part_id,
            student_count=part.student_count,
            cause=cause,
            place_id=part.place_id,
            start_ms=self.now,
            resource_id=resource_id,
            related_event_ids=related,
        )

    def _end_wait(self, part: Part) -> None:
        interval = self.open_waits.pop(part.part_id, None)
        if interval is None:
            part.waiting_since_ms = None
            part.wait_cause = None
            return
        interval.end_ms = self.now
        self.wait_intervals.append(interval)
        part.waiting_since_ms = None
        part.wait_cause = None

    def _close_open_waits(self) -> None:
        for part_id, interval in list(self.open_waits.items()):
            interval.end_ms = self.now
            self.wait_intervals.append(interval)
            del self.open_waits[part_id]

    def _complete_part(self, part: Part) -> None:
        if part.status == "completed":
            return
        self._release_escorts(part, "required_endpoint_reached")
        if part.place_id:
            self._vacate_place(part.place_id, part)
        self.space.release_reservation(part)
        part.status = "completed"
        self.emit(
            "stage_complete",
            part,
            place_id=part.place_id,
            primary_cause="required_endpoint_reached",
        )
        existing_keys = {row["student_key"] for row in self.completions}
        for member in part.members:
            if member["student_key"] in existing_keys:
                continue
            late_ms = max(0, self.now - self.deadline_ms)
            self.completions.append(
                {
                    "student_key": member["student_key"],
                    "part_id": part.part_id,
                    "group_id": part.group_id,
                    "source_unit_id": member.get("source_unit_id") or part.source_unit_id,
                    "hostel_id": member.get("hostel_id") or part.hostel_id,
                    "completion_time_ms": self.now,
                    "completion_time_s": ms_to_s(self.now),
                    "late_s": ms_to_s(late_ms),
                    "endpoint": self.required_endpoint,
                    "count_record_ids": list(part.count_record_ids),
                    "covered_checkpoint_ids": list(part.covered_checkpoint_ids),
                }
            )

    def _enforce_capacity(self, place_id: str) -> None:
        place = self.places[place_id]
        if place.get("capacity_constraint") == "unbounded":
            return
        capacity = place.get("capacity_students")
        if capacity is None:
            return
        if self.occupancy.get(place_id, 0) > int(capacity):
            self.violations.append(
                {
                    "type": "physical_capacity",
                    "place_id": place_id,
                    "occupancy": self.occupancy[place_id],
                    "capacity_students": int(capacity),
                }
            )

    def _unfinished_students(self) -> int:
        total = 0
        for part in self.parts.values():
            if part.status in {"completed", "split", "withdrawn"}:
                continue
            total += part.student_count
        return total

    def _active_work(self) -> bool:
        return any(
            part.status in {"in_service", "travelling", "counting"}
            for part in self.parts.values()
        )

    def _unfinished_snapshot(self) -> list[dict]:
        rows = []
        for part in sorted(self.parts.values(), key=lambda item: item.part_id):
            if part.status in {"completed", "split", "withdrawn"}:
                continue
            rows.append(
                {
                    "part_id": part.part_id,
                    "group_id": part.group_id,
                    "student_count": part.student_count,
                    "place_id": part.place_id,
                    "stage_id": part.current_stage_id,
                    "status": part.status,
                    "count_record_ids": list(part.count_record_ids),
                    "covered_checkpoint_ids": list(part.covered_checkpoint_ids),
                    "root_part_id": part.root_part_id or part.part_id,
                    "parent_part_id": part.parent_part_id,
                }
            )
        return rows

    def emit(self, event_type: str, part: Part | None, **fields) -> str:
        self.event_n += 1
        event_id = f"evt_{self.event_n:06d}"
        student_count = fields.pop("student_count", part.student_count if part else 0)
        composition = fields.pop(
            "hostel_composition",
            dict(part.hostel_composition) if part else {},
        )
        record = {
            "time_ms": self.now,
            "time_local": local_iso(self.start_dt, self.now),
            "event_id": event_id,
            "event_type": event_type,
            "affected_group_id": part.group_id if part else fields.get("affected_group_id"),
            "affected_part_id": part.part_id if part else None,
            "student_count": student_count,
            "hostel_composition": composition,
            "place_id": fields.pop("place_id", part.place_id if part else None),
            "leg_id": fields.pop("leg_id", part.leg_id if part else None),
            "resource_ids": fields.pop("resource_ids", list(part.resource_ids) if part else []),
            "primary_cause": fields.pop("primary_cause", event_type),
            "related_event_ids": fields.pop(
                "related_event_ids",
                [part.last_event_id] if part and part.last_event_id else [],
            ),
            "stage_id": part.current_stage_id if part else None,
        }
        record.update(fields)
        self.trace.append(record)
        if part is not None:
            part.last_event_id = event_id
        return event_id

    def _result(
        self,
        status: str,
        termination_cause: str,
        limits_reached: list[str],
        unfinished: list[dict],
    ) -> dict:
        compiled = compile_metrics(self, unfinished)
        compiled["measures"]["imposed_sequencing_wait_student_s"] = (
            compiled["measures"].get("waiting_student_s_by_cause", {}).get("imposed_sequencing_wait", 0.0)
        )
        compiled["measures"]["restu_cafe_wait_student_s"] = (
            compiled["measures"].get("waiting_student_s_by_cause", {}).get("imposed_sequencing_wait", 0.0)
        )
        late_students = [row for row in self.completions if row["late_s"] > 0]
        per_group: dict[str, dict] = {}
        per_unit: dict[str, dict] = {}
        per_hostel: dict[str, dict] = {}
        for row in self.completions:
            group = per_group.setdefault(
                row["group_id"],
                {"group_id": row["group_id"], "completed_students": 0, "late_students": 0},
            )
            group["completed_students"] += 1
            if row["late_s"] > 0:
                group["late_students"] += 1
            unit = per_unit.setdefault(
                row["source_unit_id"],
                {
                    "source_unit_id": row["source_unit_id"],
                    "completed_students": 0,
                    "late_students": 0,
                },
            )
            unit["completed_students"] += 1
            if row["late_s"] > 0:
                unit["late_students"] += 1
            hostel_id = row.get("hostel_id") or "unknown"
            hostel = per_hostel.setdefault(
                hostel_id,
                {"hostel_id": hostel_id, "completed_students": 0, "late_students": 0},
            )
            hostel["completed_students"] += 1
            if row["late_s"] > 0:
                hostel["late_students"] += 1
        for row in compiled["group_records"]:
            group = per_group.setdefault(
                row["group_id"],
                {"group_id": row["group_id"], "completed_students": 0, "late_students": 0},
            )
            group.update(row)
        for row in compiled["source_unit_records"]:
            unit = per_unit.setdefault(
                row["source_unit_id"],
                {"source_unit_id": row["source_unit_id"], "completed_students": 0, "late_students": 0},
            )
            unit.update(row)
        for row in compiled["hostel_records"]:
            hostel = per_hostel.setdefault(
                row["hostel_id"],
                {"hostel_id": row["hostel_id"], "completed_students": 0, "late_students": 0},
            )
            hostel.update(row)
        delay_explanations = compiled["delay_explanations"]

        resource_summaries = [
            {
                "resource_id": resource.resource_id,
                "kind": resource.kind,
                "place_id": resource.place_id,
                "busy": resource.busy,
                "available": resource.available,
                "assigned_part_id": resource.assigned_part_id,
                "capacity_students": resource.capacity_students,
            }
            for resource in sorted(
                self.resources.values(), key=lambda item: item.resource_id
            )
        ]
        queue_summaries = [
            {
                "place_id": place_id,
                "queued_parts": len(queue),
                "queued_students": sum(
                    self.parts[pid].student_count for pid in queue if pid in self.parts
                ),
                "servers_busy": self.servers_busy.get(place_id, 0),
                "server_count": self.server_count.get(place_id, 0),
            }
            for place_id, queue in sorted(self.queues.items())
        ]
        active_holds = [
            {
                "part_id": part.part_id,
                "place_id": part.place_id,
                "stage_id": part.current_stage_id,
                "cause": part.wait_cause,
                "student_count": part.student_count,
                "aboard": part.aboard,
                "blocked_for_place_id": part.blocked_for_place_id,
            }
            for part in sorted(self.parts.values(), key=lambda item: item.part_id)
            if part.status in {"holding", "blocked"}
        ]
        place_occupancy = self.space.snapshot()
        required_ids = required_checkpoint_ids(self.scenario)
        coverage = coverage_report(required_ids, self.count_records)
        headcount_actions = len(self.count_records)
        recounts = sum(1 for row in self.count_records if int(row.get("attempt") or 1) > 1)
        unresolved_counts = sum(1 for row in self.count_records if row.get("outcome") == "unresolved")
        worker_summaries = [
            {
                "worker_id": worker.worker_id,
                "role": worker.role,
                "place_id": worker.place_id,
                "busy": worker.busy,
                "assigned_part_id": worker.assigned_part_id,
            }
            for worker in sorted(self.workers, key=lambda item: item.worker_id)
        ]
        self.worker_pool.close_open(self.now)
        worker_stats = self.worker_pool.summarize(self.now)
        worker_assignment_rows = worker_stats.pop("assignments")
        measures = merge_worker_measures(compiled["measures"], worker_stats)
        measures["max_simultaneous_boarding_berths_used"] = max(
            self.max_simultaneous_boarding_berths_used.values(), default=1
        )
        measures["peak_berth_ppsl_workers"] = max(
            self.peak_berth_ppsl_workers.values(), default=0
        )

        return {
            "result_id": f"{self.scenario['scenario_id']}::{self.policy['policy_id']}::{ENGINE_VERSION}",
            "scenario_id": self.scenario["scenario_id"],
            "policy_id": self.policy["policy_id"],
            "versions": {
                "format_version": self.scenario["format_version"],
                "data_version": self.scenario["data_version"],
                "software_revision": SOFTWARE_REVISION,
                "engine_version": ENGINE_VERSION,
                "policy_version": self.policy.get("policy_version"),
            },
            "status": status,
            "termination_cause": termination_cause,
            "outcomes": {
                "student_completions": self.completions,
                "per_group": [per_group[key] for key in sorted(per_group)],
                "per_source_unit": [per_unit[key] for key in sorted(per_unit)],
                "per_hostel": [per_hostel[key] for key in sorted(per_hostel)],
                "groups": [per_group[key] for key in sorted(per_group)],
                "source_units": [per_unit[key] for key in sorted(per_unit)],
                "campus": {
                    "completed_students": len(self.completions),
                    "late_students": len(late_students),
                    "unfinished_students": sum(row["student_count"] for row in unfinished),
                    "wait_denominator_students": measures["wait_denominator_students"],
                    "mean_wait_s": measures["mean_wait_s"],
                    "p95_wait_s": measures["p95_wait_s"],
                    "max_hostel_mean_wait_s": measures["max_hostel_mean_wait_s"],
                    "worst_hostel_id": measures["worst_hostel_id"],
                },
            },
            "measures": measures,
            "worker_assignments": worker_assignment_rows,
            "count_outcomes": self.count_records,
            "checkpoint_coverage": coverage,
            "reconciliation_status": reconciliation_status(required_ids, self.count_records),
            "group_count_totals": accumulate_group_counts(self.count_records),
            "event_trace": self.trace,
            "limits_reached": limits_reached,
            "violations": self.violations,
            "unfinished_demand": unfinished,
            "delay_explanations": delay_explanations,
            "student_time_intervals": compiled["student_time_intervals"],
            "reporting_assumptions": compiled["reporting_assumptions"],
            "event_trace_retained": True,
            "resource_summaries": resource_summaries,
            "queue_summaries": queue_summaries,
            "active_holds": active_holds,
            "place_occupancy": place_occupancy,
            "occupancy_history": list(self.space.flow) + list(self.shared_flow),
            "occupancy_integrity": self.space.integrity(),
            "reports": list(self.reports),
            "delivered_reports": list(self.space_policy.delivered),
            "policy_decisions": list(self.space_policy.decisions),
            "worker_summaries": worker_summaries,
            "uncertainty_case_id": self.scenario.get("uncertainty_case_id"),
            "random_seed": self.policy.get("random_seed"),
            "visible_assumptions": list(self.scenario.get("uncertain_assumptions") or []),
            "background_demand": self.scenario.get("background_demand"),
            "destination": self._destination_summary(),
        }


    def try_start_fleet(self, fleet_id: str) -> None:
        fleet = self.fleets[fleet_id]
        waiters = self.wait_resource.get(fleet_id, [])
        waiters.sort(key=self._queue_sort_key)
        v_rule = self.policy.get("vehicle_dispatch_rule") or {}
        bus_count = v_rule.get("bus_count")
        headway_s = v_rule.get("headway_s") or v_rule.get("dispatch_interval_s") or v_rule.get("interval_s")
        min_passengers = v_rule.get("min_passengers") or v_rule.get("threshold_students")
        if headway_s is not None:
            last_dispatch = self._fleet_last_dispatch_ms.get(fleet_id)
            min_gap_ms = to_ms(float(headway_s))
            if last_dispatch is not None and self.now < last_dispatch + min_gap_ms:
                if not self._fleet_dispatch_scheduled.get(fleet_id):
                    self._fleet_dispatch_scheduled[fleet_id] = True
                    self.schedule(last_dispatch + min_gap_ms, PHASE_START_DEPART, "check_fleet_dispatch", None, fleet_id=fleet_id)
                return
        v_rule = self.policy.get("vehicle_dispatch_rule") or {}
        simultaneous_berths = (
            v_rule.get("simultaneous_boarding_berths")
            if v_rule.get("simultaneous_boarding_berths") is not None
            else self.policy.get("simultaneous_boarding_berths")
        )
        if simultaneous_berths is not None:
            berth_capacity = min(4, max(1, int(simultaneous_berths)))
        else:
            berth_capacity = min(4, max(1, int(fleet.get("boarding_berth_capacity") or 1)))

        assigned_berth_workers = (
            v_rule.get("berth_workers")
            if v_rule.get("berth_workers") is not None
            else (
                self.policy.get("berth_workers")
                if self.policy.get("berth_workers") is not None
                else (self.policy.get("worker_allocation") or {}).get("berth_workers")
            )
        )
        ppsl_budget = int(
            (self.scenario.get("operating_rules") or {}).get("ppsl_total_reference")
            or self.scenario.get("ppsl_total_reference")
            or (self.scenario.get("operating_rules") or {}).get("worker_budget")
            or 154
        )
        if assigned_berth_workers is not None:
            max_berth_workers = min(int(assigned_berth_workers), ppsl_budget)
        else:
            max_berth_workers = min(berth_capacity * 2, ppsl_budget)

        while waiters:
            busy_berths = self.fleet_berths_busy.get(fleet_id, 0)
            if busy_berths >= berth_capacity:
                break
            if (busy_berths + 1) * 2 > max_berth_workers:
                break
            if bus_count is not None:
                active_buses = sum(1 for vid in fleet["vehicle_ids"] if self.resources[vid].busy)
                if active_buses >= int(bus_count):
                    break
            if min_passengers is not None:
                waiting_students = sum(self.parts[p].student_count for p in waiters if p in self.parts)
                if waiting_students < int(min_passengers) and self._unfinished_students() > waiting_students:
                    break
            vehicle = self._next_free_vehicle(fleet, advance=True)
            if vehicle is None:
                break
            idle_berth_workers: list[str] = []
            if self.worker_pool.workers:
                b_place = fleet.get("boarding_place_id")
                berth_workers_in_pool = [
                    w for w in self.worker_pool.workers
                    if w.place_id == b_place and ("ppsl" in (w.roles or {w.role}) or "berth" in (w.roles or {w.role}))
                ]
                if berth_workers_in_pool:
                    idle_w = [
                        w for w in berth_workers_in_pool
                        if self.worker_pool.time_available(w, self.now, self.calendar_open)
                        and w.worker_id not in self.worker_pool._open
                    ]
                    if len(idle_w) < 2:
                        break
                    idle_berth_workers = [w.worker_id for w in idle_w[:2]]
            dest = fleet.get("alighting_place_id")
            boarding_parts: list[Part] = []
            remaining_cap = vehicle.capacity_students

            while waiters and remaining_cap > 0:
                pid = waiters[0]
                part = self.parts[pid]
                if dest and self.space_policy.reserves_before_departure():
                    if not self._try_reserve_destination(part, dest):
                        break
                if not self._has_idle_passthrough_workers(part, self._stage(part)):
                    if not boarding_parts:
                        waiters.pop(0)
                        part.status = "waiting_count"
                        if part.part_id not in self.wait_workers:
                            self.wait_workers.append(part.part_id)
                        if part.part_id not in self.open_waits:
                            self._begin_wait(part, "waiting_for_counter")
                    break
                if part.student_count > remaining_cap:
                    subs = self._split_for_vehicle(part, remaining_cap)
                    if not subs:
                        if not boarding_parts:
                            self.violations.append(
                                {
                                    "type": "physical_capacity",
                                    "resource_id": vehicle.resource_id,
                                    "occupancy": part.student_count,
                                    "capacity_students": vehicle.capacity_students,
                                }
                            )
                        break
                    waiters.pop(0)
                    part = subs[0]
                    for extra in reversed(subs[1:]):
                        extra.status = "queued"
                        waiters.insert(0, extra.part_id)
                        self._begin_wait(extra, "waiting_for_vehicle")
                    for sub in subs:
                        self._ensure_part_escorts(sub)
                else:
                    waiters.pop(0)

                if not self._ensure_cohort_escorts(part):
                    part.status = "queued"
                    waiters.insert(0, part.part_id)
                    self._begin_wait(part, "waiting_for_vehicle")
                    break

                boarding_parts.append(part)
                remaining_cap -= part.student_count

            if not boarding_parts:
                break

            part = boarding_parts[0]
            pid = part.part_id
            if len(boarding_parts) > 1:
                saved_parts: list[Part] = []
                for bp in boarding_parts:
                    p_copy = Part(
                        part_id=bp.part_id,
                        group_id=bp.group_id,
                        parent_part_id=bp.parent_part_id,
                        source_unit_id=bp.source_unit_id,
                        hostel_id=bp.hostel_id,
                        hostel_composition=dict(bp.hostel_composition),
                        student_count=bp.student_count,
                        members=list(bp.members),
                        queue_tie_key=bp.queue_tie_key,
                        stage_index=bp.stage_index,
                        place_id=bp.place_id,
                        leg_id=bp.leg_id,
                        resource_ids=[],
                        status="ready",
                        arrival_ms=bp.arrival_ms,
                        current_stage_id=bp.current_stage_id,
                        parent_group_id=bp.parent_group_id,
                        source_unit_ids=list(bp.source_unit_ids),
                        source_unit_membership=dict(bp.source_unit_membership),
                        count_record_ids=list(bp.count_record_ids),
                        covered_checkpoint_ids=list(bp.covered_checkpoint_ids),
                        required_supervision=dict(bp.required_supervision),
                        escort_ids=list(bp.escort_ids),
                        root_part_id=bp.root_part_id or bp.part_id,
                        version=bp.version,
                        queue_priority=getattr(bp, "queue_priority", 0),
                        stages=getattr(bp, "stages", None),
                        cohort_id=getattr(bp, "cohort_id", None),
                    )
                    saved_parts.append(p_copy)
                part._merged_parts = saved_parts
                for m in part.members:
                    if "group_id" not in m:
                        m["group_id"] = part.group_id
                for other in boarding_parts[1:]:
                    self._end_wait(other)
                    if other.reserved_place_id:
                        self.space.reserved_parts.pop(other.part_id, None)
                        other.reserved_place_id = None
                    part.student_count += other.student_count
                    for m in other.members:
                        if "group_id" not in m:
                            m["group_id"] = other.group_id
                    part.members.extend(other.members)
                    for h, c in other.hostel_composition.items():
                        part.hostel_composition[h] = part.hostel_composition.get(h, 0) + c
                    for u, c in other.source_unit_membership.items():
                        part.source_unit_membership[u] = part.source_unit_membership.get(u, 0) + c
                    for u in other.source_unit_ids:
                        if u not in part.source_unit_ids:
                            part.source_unit_ids.append(u)
                    for cr in other.count_record_ids:
                        if cr not in part.count_record_ids:
                            part.count_record_ids.append(cr)
                    for cp in other.covered_checkpoint_ids:
                        if cp not in part.covered_checkpoint_ids:
                            part.covered_checkpoint_ids.append(cp)
                    for k, v in other.required_supervision.items():
                        part.required_supervision[k] = max(part.required_supervision.get(k, 0), v)
                    for wid in other.escort_ids:
                        if wid not in part.escort_ids:
                            part.escort_ids.append(wid)
                            worker = self.workers_by_id.get(wid)
                            if worker is not None:
                                worker.assigned_part_id = part.part_id
                    other.escort_ids = []
                    other.members = []
                    other.student_count = 0
                    other.status = "split"

            self.wait_resource[fleet_id] = waiters
            if idle_berth_workers:
                self.worker_pool.reserve_now(
                    [self.workers_by_id[wid] for wid in idle_berth_workers],
                    "ppsl",
                    fleet.get("boarding_place_id"),
                    self.now,
                    pid,
                )
                self.berth_active_workers.setdefault(pid, []).extend(idle_berth_workers)
            self.wait_resource[fleet_id] = waiters
            self.fleet_berths_busy[fleet_id] = busy_berths + 1
            self.max_simultaneous_boarding_berths_used[fleet_id] = max(
                self.max_simultaneous_boarding_berths_used.get(fleet_id, 0),
                self.fleet_berths_busy[fleet_id],
            )
            self.peak_berth_ppsl_workers[fleet_id] = max(
                self.peak_berth_ppsl_workers.get(fleet_id, 0),
                self.fleet_berths_busy[fleet_id] * 2,
            )
            vehicle.available = False
            vehicle.assigned_part_id = pid
            self.schedule(
                self.now,
                PHASE_START_DEPART,
                "batch_start",
                part,
                resource_id=vehicle.resource_id,
            )
            waiters = self.wait_resource.get(fleet_id, [])
            waiters.sort(key=self._queue_sort_key)
            self._fleet_last_dispatch_ms[fleet_id] = self.now
            self._fleet_dispatch_scheduled[fleet_id] = False
        self.wait_resource[fleet_id] = waiters

    def _next_free_vehicle(self, fleet: dict, *, advance: bool = False) -> Resource | None:
        boarding_place = fleet.get("boarding_place_id")
        fleet_id = fleet.get("id") or ""
        vids = fleet["vehicle_ids"]
        start_idx = self._fleet_vehicle_cursor.get(fleet_id, 0)
        n = len(vids)
        for offset in range(n):
            idx = (start_idx + offset) % n
            vehicle_id = vids[idx]
            resource = self.resources[vehicle_id]
            if resource.busy or not resource.available:
                continue
            if not self._vehicle_service_ok(resource):
                continue
            if boarding_place and resource.place_id != boarding_place:
                continue
            if advance:
                self._fleet_vehicle_cursor[fleet_id] = (idx + 1) % n
            return resource
        return None

    def _fleet_has_available(self, fleet_id: str) -> bool:
        fleet = self.fleets[fleet_id]
        return self._next_free_vehicle(fleet) is not None or any(
            not resource.busy
            and resource.available
            and self._vehicle_service_ok(resource)
            for resource in (self.resources[vid] for vid in fleet["vehicle_ids"])
        )

    def _vehicle_service_ok(self, resource: Resource) -> bool:
        if resource.calendar_id and not self.calendar_open.get(resource.calendar_id):
            return False
        now_s = ms_to_s(self.now)
        for outage in resource.outages:
            start_s = float(outage["start_s"])
            end_s = float(outage["end_s"])
            if start_s <= now_s < end_s:
                return False
        return True

    def _enqueue_alight(self, part: Part, resource_id: str, fleet_id: str) -> None:
        fleet = self.fleets[fleet_id]
        wait_key = f"{fleet_id}::alight"
        dropoff_capacity = int(fleet["dropoff_space_capacity"])
        if dropoff_capacity <= 0:
            self.violations.append(
                {
                    "type": "physical_capacity",
                    "fleet_id": fleet_id,
                    "occupancy": part.student_count,
                    "capacity_students": dropoff_capacity,
                    "resource": "dropoff_space",
                }
            )
        if self.fleet_dropoff_busy.get(fleet_id, 0) >= dropoff_capacity:
            part.status = "holding"
            self.wait_resource.setdefault(wait_key, []).append(part.part_id)
            self._begin_wait(part, "waiting_to_alight", resource_id=resource_id)
            resource = self.resources.get(resource_id)
            if resource is not None:
                self._set_vehicle_state(resource, "held", "waiting_to_alight")
            self.emit(
                "hold_start",
                part,
                place_id=part.place_id,
                resource_ids=[resource_id],
                primary_cause="waiting_to_alight",
            )
            return
        self.fleet_dropoff_busy[fleet_id] = self.fleet_dropoff_busy.get(fleet_id, 0) + 1
        resource = self.resources[resource_id]
        resource.assigned_part_id = part.part_id
        self.schedule(
            self.now,
            PHASE_START_DEPART,
            "batch_start",
            part,
            resource_id=resource_id,
        )

    def _try_start_waiting_alight(self, fleet_id: str) -> None:
        wait_key = f"{fleet_id}::alight"
        waiters = self.wait_resource.get(wait_key, [])
        waiters.sort(key=self._queue_sort_key)
        while waiters:
            if self.fleet_dropoff_busy.get(fleet_id, 0) >= int(
                self.fleets[fleet_id]["dropoff_space_capacity"]
            ):
                break
            pid = waiters.pop(0)
            part = self.parts[pid]
            self._end_wait(part)
            resource_id = part.resource_ids[0] if part.resource_ids else None
            if resource_id is None:
                continue
            self.emit(
                "hold_end",
                part,
                place_id=part.place_id,
                resource_ids=[resource_id],
                primary_cause="dropoff_space_available",
            )
            self._enqueue_alight(part, resource_id, fleet_id)
        self.wait_resource[wait_key] = waiters

    def _start_vehicle_cycle_or_release(self, resource: Resource) -> None:
        if resource.aboard_students > 0:
            resource.busy = True
            resource.available = False
            return
        resource.assigned_part_id = None
        resource.busy = True
        resource.available = False
        fleet = self.fleets.get(resource.fleet_id or "")
        return_place = fleet["boarding_place_id"] if fleet else None
        if return_place and resource.place_id != return_place:
            if resource.return_travel_s is None:
                raise SimulationError(
                    "missing_input",
                    (
                        f"Vehicle {resource.resource_id!r} dropped off at {resource.place_id!r} "
                        f"but is missing return_travel_s to return to {return_place!r}"
                    ),
                    field="vehicle.return_travel_s",
                )
        if resource.return_travel_s is None and resource.turnaround_s is None:
            resource.busy = False
            resource.available = True
            self._set_vehicle_state(resource, "idle", "available")
            self.try_start_batch(resource.resource_id)
            if resource.fleet_id:
                self.try_start_fleet(resource.fleet_id)
            return
        delay_ms = to_ms(resource.return_travel_s or 0)
        self._set_vehicle_state(resource, "busy", "return_travel")
        self.schedule(
            self.now + delay_ms,
            PHASE_COMPLETION_RELEASE,
            "vehicle_return_complete",
            None,
            resource_id=resource.resource_id,
        )

    def _on_vehicle_return_complete(self, resource_id: str) -> None:
        resource = self.resources[resource_id]
        fleet = self.fleets.get(resource.fleet_id or "")
        if fleet:
            resource.place_id = fleet["boarding_place_id"]
        elif resource.home_place_id:
            resource.place_id = resource.home_place_id
        self.emit(
            "vehicle_return_complete",
            None,
            resource_ids=[resource_id],
            place_id=resource.place_id,
            primary_cause="return_travel",
        )
        turn_s = resource.turnaround_s
        if turn_s:
            self._set_vehicle_state(resource, "busy", "turnaround")
            self.schedule(
                self.now + to_ms(turn_s),
                PHASE_COMPLETION_RELEASE,
                "vehicle_turnaround_complete",
                None,
                resource_id=resource_id,
            )
            return
        self._on_vehicle_turnaround_complete(resource_id)

    def _on_vehicle_turnaround_complete(self, resource_id: str) -> None:
        resource = self.resources[resource_id]
        resource.busy = False
        self._set_vehicle_state(resource, "idle", "available")
        self.emit(
            "vehicle_turnaround_complete",
            None,
            resource_ids=[resource_id],
            place_id=resource.place_id,
            primary_cause="turnaround",
        )
        self._on_resource_available(resource_id)

    def _batch_duration_ms(self, stage: dict, part: Part, resource: Resource) -> int:
        if stage.get("duration_rule") == "load_dependent":
            return to_ms(self._load_dependent_s(stage.get("action"), part.student_count, resource))
        return to_ms(stage["duration_s"])

    def _load_dependent_s(self, action: str | None, student_count: int, resource: Resource) -> float:
        if resource.usable_doors is None or int(resource.usable_doors) < 1:
            self.violations.append(
                {
                    "type": "missing_door_rule",
                    "resource_id": resource.resource_id,
                    "message": "load-dependent boarding needs usable_doors on this vehicle type",
                }
            )
            return 0.0
        doors = int(resource.usable_doors)
        if action == "alight":
            if resource.alighting_setup_s is None or resource.alighting_s_per_passenger_per_door is None:
                self.violations.append(
                    {
                        "type": "missing_door_rule",
                        "resource_id": resource.resource_id,
                        "message": "load-dependent alighting needs declared door times",
                    }
                )
                return 0.0
            setup = float(resource.alighting_setup_s)
            per = float(resource.alighting_s_per_passenger_per_door)
        else:
            if resource.boarding_setup_s is None or resource.boarding_s_per_passenger_per_door is None:
                self.violations.append(
                    {
                        "type": "missing_door_rule",
                        "resource_id": resource.resource_id,
                        "message": "load-dependent boarding needs declared door times",
                    }
                )
                return 0.0
            setup = float(resource.boarding_setup_s)
            per = float(resource.boarding_s_per_passenger_per_door)
        return setup + student_count * per / doors

    def _split_for_vehicle(self, part: Part, capacity: int) -> list[Part] | None:
        raw = {
            "part_id": part.part_id,
            "group_id": part.group_id,
            "parent_group_id": part.parent_group_id or part.group_id,
            "hostel_id": part.hostel_id,
            "source_unit_id": part.source_unit_id,
            "source_unit_ids": part.source_unit_ids,
            "source_unit_membership": part.source_unit_membership,
            "members": part.members,
            "count_record_ids": part.count_record_ids,
            "covered_checkpoint_ids": part.covered_checkpoint_ids,
            "required_supervision": part.required_supervision,
        }
        chunks = split_part_members(raw, capacity, self.split_policy)
        if chunks is None:
            return None
        if len(chunks) == 1:
            return [part]
        self.emit("part_split", part, primary_cause="capacity_split")
        parent_escorts = list(part.escort_ids)
        part.escort_ids = []
        subs: list[Part] = []
        for chunk in chunks:
            sub = Part(
                part_id=chunk["part_id"],
                group_id=part.group_id,
                parent_part_id=part.part_id,
                source_unit_id=chunk["source_unit_id"],
                hostel_id=part.hostel_id,
                hostel_composition=dict(chunk["hostel_composition"]),
                student_count=chunk["student_count"],
                members=list(chunk["members"]),
                queue_tie_key=str(chunk["members"][0]["queue_tie_key"]),
                stage_index=part.stage_index,
                place_id=part.place_id,
                leg_id=part.leg_id,
                resource_ids=list(part.resource_ids),
                status="queued",
                arrival_ms=part.arrival_ms,
                current_stage_id=part.current_stage_id,
                parent_group_id=part.group_id,
                source_unit_ids=list(chunk["source_unit_ids"]),
                source_unit_membership=dict(chunk["source_unit_membership"]),
                count_record_ids=list(chunk["count_record_ids"]),
                covered_checkpoint_ids=list(
                    chunk.get("covered_checkpoint_ids") or part.covered_checkpoint_ids
                ),
                estimated_occupancy=part.estimated_occupancy,
                required_supervision=dict(chunk["required_supervision"]),
                root_part_id=part.root_part_id or part.part_id,
                version=1,
                stages=getattr(part, "stages", None),
                cohort_id=getattr(part, "cohort_id", None),
            )
            self.parts[sub.part_id] = sub
            subs.append(sub)
        for index, sub in enumerate(subs):
            sub.queue_priority = getattr(part, "queue_priority", 0) - 1
            if index < len(parent_escorts):
                wid = parent_escorts[index]
                sub.escort_ids = [wid]
                worker = self.workers_by_id.get(wid)
                if worker is not None:
                    worker.assigned_part_id = sub.part_id
        leftover = parent_escorts[len(subs):]
        if leftover:
            self.worker_pool.release(leftover, self.now)
        part.status = "split"
        part.version += 1
        self._end_wait(part)
        for sub in subs:
            self._ensure_part_escorts(sub)
        return subs

    def _group_is_assembled(self, part: Part) -> bool:
        siblings = [
            other
            for other in self.parts.values()
            if other.group_id == part.group_id
            and other.status not in {"completed", "split", "withdrawn"}
        ]
        if not siblings:
            return True
        return all(
            other.place_id == part.place_id and other.stage_index == part.stage_index
            for other in siblings
        )

    def _try_release_assembled_group(self, group_id: str) -> None:
        waiting_ids = list(self.wait_group.get(group_id) or [])
        if not waiting_ids:
            return
        parts = [self.parts[pid] for pid in waiting_ids if pid in self.parts]
        if not parts:
            return
        if not self._group_is_assembled(parts[0]):
            return
        regroup = self.regroup_policy
        if regroup.get("required"):
            need_workers = int(regroup.get("worker_count") or 0)
            duration_s = float(
                regroup.get("duration_s")
                if regroup.get("duration_s") is not None
                else (regroup.get("assembly_duration_s") or regroup.get("assembly_time_s") or 0)
            )
            place = parts[0].place_id
            if self._regroup_in_progress.get(group_id):
                return
            if need_workers > 0:
                idle = self.worker_pool.idle_now(place, "escort", self.now, self.calendar_open)
                if len(idle) < need_workers:
                    return
                chosen = idle[:need_workers]
                ids = self.worker_pool.reserve_now(chosen, "escort", place, self.now, parts[0].part_id)
                self.emit("worker_reserved", parts[0], place_id=place, primary_cause="regrouping", worker_ids=ids)
                parts[0].assembly_worker_ids.extend(ids)
            self._regroup_in_progress[group_id] = True
            self.schedule(
                self.now + to_ms(duration_s),
                PHASE_COMPLETION_RELEASE,
                "regroup_complete",
                parts[0],
                group_id=group_id,
            )
            return
        self.wait_group[group_id] = []
        for part in parts:
            self._end_wait(part)
            self.emit("hold_end", part, place_id=part.place_id, primary_cause="group_assembled")
            part.stage_index += 1
            self.begin_stage(part)

    def _on_regroup_complete(self, part: Part | None, group_id: str | None) -> None:
        if not group_id:
            return
        self._regroup_in_progress[group_id] = False
        waiting_ids = list(self.wait_group.get(group_id) or [])
        self.wait_group[group_id] = []
        parts = [self.parts[pid] for pid in waiting_ids if pid in self.parts]
        for p in parts:
            self._end_wait(p)
            self.emit("hold_end", p, place_id=p.place_id, primary_cause="group_assembled")
            p.stage_index += 1
            self.begin_stage(p)
        if parts and parts[0].assembly_worker_ids:
            ids = list(parts[0].assembly_worker_ids)
            self.worker_pool.release(ids, self.now)
            parts[0].assembly_worker_ids = []
            self.emit("worker_released", parts[0], place_id=parts[0].place_id, primary_cause="regrouping", worker_ids=ids)
            self._try_waiting_escorts()
            self._try_waiting_assembly()
            self._try_waiting_regroup()

    def _try_waiting_regroup(self) -> None:
        for group_id in list(self.wait_group):
            self._try_release_assembled_group(group_id)

    def _physical_cohort(self, part: Part) -> list[Part]:
        if part.internal_calculation or not part.parent_part_id:
            return [part]
        sibs = [
            other
            for other in self.parts.values()
            if other.parent_part_id == part.parent_part_id
            and not other.internal_calculation
            and other.status not in {"completed", "split", "withdrawn"}
            and other.stage_index == part.stage_index
            and other.place_id == part.place_id
        ]
        return sibs or [part]

    def _cohort_supervision_ready(self, part: Part) -> bool:
        for sib in self._physical_cohort(part):
            need = self.worker_pool.escorts_needed(sib)
            if need <= 0:
                continue
            if len(sib.escort_ids) < need:
                return False
        return True

    def _ensure_cohort_escorts(self, part: Part) -> bool:
        ready = True
        for sib in self._physical_cohort(part):
            if not self._ensure_part_escorts(sib):
                ready = False
        return ready and self._cohort_supervision_ready(part)

    def _ensure_part_escorts(self, part: Part) -> bool:
        if part.internal_calculation:
            return True
        need = self.worker_pool.escorts_needed(part)
        if need <= 0:
            return True
        have = len(part.escort_ids)
        if have >= need:
            return True
        pending = [wid for wid in part.pending_escort_ids if wid not in part.escort_ids]
        if have + len(pending) >= need:
            self._wait_for_escort(part)
            return False
        missing = need - have - len(pending)
        idle = self.worker_pool.idle_now(
            part.place_id, "escort", self.now, self.calendar_open
        )
        idle = [
            worker
            for worker in idle
            if worker.worker_id not in part.escort_ids
            and worker.worker_id not in part.pending_escort_ids
        ]
        if len(idle) >= missing:
            chosen = idle[:missing]
            ids = self.worker_pool.reserve_now(
                chosen, "escort", part.place_id, self.now, part.part_id
            )
            part.escort_ids.extend(ids)
            self._emit_escort_reserved(part, ids)
            return len(part.escort_ids) >= need
        offer = self.worker_pool.pick_free(
            missing,
            "escort",
            part.place_id,
            self.now,
            self.calendar_open,
            self.calendars,
        )
        if offer is None:
            if self.worker_pool.capable_count("escort") < need:
                self.violations.append(
                    {
                        "type": "insufficient_staff",
                        "part_id": part.part_id,
                        "need": need,
                    }
                )
            self._wait_for_escort(part)
            return False
        chosen, start_ms = offer
        ids = self.worker_pool.commit_travel(
            chosen, "escort", part.place_id, self.now, start_ms, part.part_id
        )
        if start_ms <= self.now:
            self.worker_pool.arrive(ids, part.place_id, self.now, "escort")
            part.escort_ids.extend(ids)
            self._emit_escort_reserved(part, ids)
            return len(part.escort_ids) >= need
        for worker_id in ids:
            if worker_id not in part.pending_escort_ids:
                part.pending_escort_ids.append(worker_id)
        self._wait_for_escort(part)
        self.schedule(
            start_ms,
            PHASE_START_DEPART,
            "escort_ready",
            part,
            worker_ids=ids,
        )
        return False

    def _wait_for_escort(self, part: Part) -> None:
        part.status = "waiting_escort"
        if part.part_id not in self.wait_workers:
            self.wait_workers.append(part.part_id)
        if part.part_id not in self.open_waits:
            self._begin_wait(part, "waiting_for_escort")

    def _emit_escort_reserved(self, part: Part, worker_ids: list[str]) -> None:
        if not worker_ids:
            return
        self.emit(
            "worker_reserved",
            part,
            worker_ids=list(worker_ids),
            resource_ids=list(worker_ids),
            escort_ids=list(part.escort_ids),
            primary_cause="escort",
        )

    def _release_escorts(self, part: Part, cause: str) -> None:
        ids = list(part.escort_ids)
        pending = list(part.pending_escort_ids)
        if not ids and not pending:
            return
        if ids:
            self.emit(
                "worker_released",
                part,
                worker_ids=ids,
                resource_ids=ids,
                escort_ids=ids,
                primary_cause=cause,
            )
            self.worker_pool.release(ids, self.now)
        if pending:
            self.worker_pool.release(pending, self.now)
        part.escort_ids = []
        part.pending_escort_ids = []
        self._try_waiting_escorts()
        self._try_waiting_counts()
        for place_id in list(self.queues):
            self.try_start_service(place_id)
        for resource_id in list(self.resources):
            self.try_start_batch(resource_id)
        for fleet_id in list(self.fleets):
            self.try_start_fleet(fleet_id)

    def _try_waiting_escorts(self) -> None:
        waiting = [
            part_id
            for part_id in list(self.wait_workers)
            if self.parts.get(part_id) is not None
            and self.parts[part_id].status == "waiting_escort"
        ]
        for part_id in waiting:
            part = self.parts[part_id]
            if self._ensure_cohort_escorts(part):
                self.wait_workers = [item for item in self.wait_workers if item != part_id]
                self._end_wait(part)
                self.begin_stage(part)

    def _maybe_handover(self, part: Part, place_id: str | None) -> None:
        if not part.escort_ids or not place_id:
            return
        if place_id not in self.worker_pool.permitted_handover_places:
            return
        if part.stage_index + 1 >= len(self._stage_list(part)):
            return
        need = max(1, self.worker_pool.escorts_needed(part))
        idle = [
            worker
            for worker in self.worker_pool.idle_now(
                place_id, "escort", self.now, self.calendar_open
            )
            if worker.worker_id not in part.escort_ids
        ]
        if len(idle) < need:
            return
        old_ids = list(part.escort_ids)
        new_ids = self.worker_pool.reserve_now(
            idle[:need], "escort", place_id, self.now, part.part_id
        )
        self.emit(
            "handover",
            part,
            place_id=place_id,
            worker_ids=list(new_ids),
            released_worker_ids=list(old_ids),
            primary_cause="permitted_transfer",
        )
        self.emit(
            "worker_released",
            part,
            worker_ids=list(old_ids),
            resource_ids=list(old_ids),
            primary_cause="handover",
        )
        self.worker_pool.release(old_ids, self.now)
        part.escort_ids = list(new_ids)
        self._emit_escort_reserved(part, new_ids)
        self._try_waiting_escorts()

    def _on_escort_ready(self, part: Part, payload: dict) -> None:
        worker_ids = list(payload.get("worker_ids") or [])
        if part.status in {"completed", "split", "withdrawn", "in_service", "travelling"}:
            if worker_ids:
                self.worker_pool.arrive(worker_ids, part.place_id, self.now, "escort")
                extra = [wid for wid in worker_ids if wid not in part.escort_ids]
                if extra:
                    self.worker_pool.release(extra, self.now)
            return
        self.worker_pool.arrive(worker_ids, part.place_id, self.now, "escort")
        for worker_id in worker_ids:
            if worker_id in part.pending_escort_ids:
                part.pending_escort_ids.remove(worker_id)
            if worker_id not in part.escort_ids:
                part.escort_ids.append(worker_id)
        if worker_ids:
            self.emit(
                "worker_travel_complete",
                part,
                worker_ids=list(worker_ids),
                resource_ids=list(worker_ids),
                place_id=part.place_id,
                primary_cause="worker_travel",
            )
            self._emit_escort_reserved(part, worker_ids)
        need = self.worker_pool.escorts_needed(part)
        if need and len(part.escort_ids) < need:
            self._wait_for_escort(part)
            return
        self._end_wait(part)
        if part.part_id in self.wait_workers:
            self.wait_workers = [item for item in self.wait_workers if item != part.part_id]
        if part.status in {"waiting_escort", "ready", "queued", "holding", "waiting_count"}:
            self.begin_stage(part)
        self._try_waiting_escorts()
        for resource_id in list(self.resources):
            self.try_start_batch(resource_id)
        for fleet_id in list(self.fleets):
            self.try_start_fleet(fleet_id)

    def _on_worker_travel_complete(self, payload: dict) -> None:
        worker_id = payload.get("worker_id")
        place_id = payload.get("to_place_id")
        if worker_id:
            self.worker_pool.arrive([worker_id], place_id, self.now, "escort")
        self._try_waiting_escorts()
        self._try_waiting_assembly()
        self._try_waiting_regroup()

    def _on_worker_available(self, worker_id: str | None) -> None:
        self.emit(
            "worker_available",
            None,
            worker_ids=[worker_id] if worker_id else [],
            resource_ids=[worker_id] if worker_id else [],
            primary_cause="worker_shift",
        )
        self._try_waiting_escorts()
        self._try_waiting_assembly()
        self._try_waiting_counts()
        for place_id in list(self.queues):
            self.try_start_service(place_id)
        self._try_waiting_regroup()

    def _reserve_station_worker(self, part: Part, place_id: str) -> bool:
        if part.station_worker_id:
            return True
        idle = self.worker_pool.idle_now(place_id, "station", self.now, self.calendar_open)
        if not idle:
            return False
        ids = self.worker_pool.reserve_now(
            idle[:1], "station", place_id, self.now, part.part_id
        )
        part.station_worker_id = ids[0]
        self.emit(
            "worker_reserved",
            part,
            worker_ids=ids,
            resource_ids=ids,
            primary_cause="station",
        )
        return True

    def _release_station_worker(self, part: Part) -> None:
        if not part.station_worker_id:
            return
        worker_id = part.station_worker_id
        self.emit(
            "worker_released",
            part,
            worker_ids=[worker_id],
            resource_ids=[worker_id],
            primary_cause="station",
        )
        self.worker_pool.release([worker_id], self.now)
        part.station_worker_id = None
        self._try_waiting_escorts()
        for place_id in list(self.queues):
            self.try_start_service(place_id)

    def _load_background_occupancy(self) -> None:
        applied: dict[str, int] = {}
        demand = self.scenario.get("background_demand") or {}
        by_place = demand.get("occupancy_by_place") or {}
        for place_id, count in by_place.items():
            n = int(count or 0)
            if place_id and n:
                self.space.add_background(place_id, n, 0)
                applied[place_id] = n
        for index, row in enumerate(self.scenario["initial_state"].get("queues") or []):
            place_id = row.get("place_id")
            count = int(row.get("student_count") or 0)
            if not place_id or count <= 0:
                continue
            is_permanent = bool(
                row.get("permanent_background")
                or row.get("background")
                or row.get("permanent")
                or row.get("kind") == "background"
            )
            if is_permanent or place_id not in self.queues or place_id in applied:
                extra = count - applied.get(place_id, 0)
                if extra > 0:
                    self.space.add_background(place_id, extra, 0)
                    applied[place_id] = applied.get(place_id, 0) + extra
            else:
                qid = f"init_q_{place_id}_{index}"
                init_part = Part(
                    part_id=qid,
                    group_id=qid,
                    parent_part_id=None,
                    source_unit_id=qid,
                    hostel_id="background",
                    hostel_composition={"background": count},
                    student_count=count,
                    members=[{"student_key": f"{qid}_{m}", "source_unit_id": qid, "hostel_id": "background"} for m in range(count)],
                    queue_tie_key=qid,
                    stage_index=0,
                    place_id=place_id,
                    leg_id=None,
                    resource_ids=[],
                    status="queued",
                    arrival_ms=0,
                    internal_calculation=True,
                )
                init_part._is_initial_queue = True
                self.parts[qid] = init_part
                self.space.occupy(place_id, init_part, 0)
                self.queues.setdefault(place_id, []).append(qid)
                self._begin_wait(init_part, "waiting_for_server")
    def _observe_initial_occupancy(self) -> None:
        if not self.space_policy.tracks_reports():
            return
        for place_id, n in list(self.space.actual.items()):
            if n:
                self._maybe_operating_limit(place_id)
                self._observe_occupancy(place_id)
    def _load_conditions(self) -> None:
        for raw in self.scenario.get("external_conditions") or []:
            at_ms = to_ms(raw.get("at_s") or 0)
            if at_ms > self.simulation_end_ms:
                continue
            self.schedule(
                at_ms,
                PHASE_ARRIVAL_EXTERNAL,
                "condition_change",
                None,
                condition=dict(raw),
            )

    def _admit_to_place(self, part: Part, place_id: str) -> bool:
        if part.reserved_place_id == place_id:
            ok = self.space.convert_reservation(part, self.now)
        else:
            if not self.space.can_enter(place_id, part.student_count):
                return False
            ok = self.space.occupy(place_id, part, self.now)
        if not ok:
            return False
        self._maybe_operating_limit(place_id)
        self._observe_occupancy(place_id)
        self._enforce_capacity(place_id)
        return True

    def _vacate_place(self, place_id: str | None, part: Part) -> None:
        if not place_id:
            return
        self.space.vacate(place_id, part, self.now)
        self._maybe_operating_limit(place_id)
        self._observe_occupancy(place_id)
        self._try_admit_waiters(place_id)
        self._try_release_reserve_waiters(place_id)
        for fleet_id in list(self.fleets):
            self.try_start_fleet(fleet_id)

    def _try_reserve_destination(self, part: Part, dest: str) -> bool:
        cap = self.space.physical_students(dest)
        if self.space_policy.tracks_reports():
            if not self.space_policy.delivered_can_fit(dest, part.student_count, cap):
                return False
        return self.space.reserve(dest, part)

    def _policy_blocks_release(self, part: Part, stage: dict) -> bool:
        if not self.space_policy.hold_active:
            return False
        if part.status == "travelling":
            return False
        return True

    def _leg_is_closed(self, stage: dict) -> bool:
        leg_id = stage.get("leg_id")
        return bool(leg_id and leg_id in self.closed_legs)

    def _hold_for_policy(self, part: Part) -> None:
        part.status = "holding"
        if part.part_id not in self.wait_policy:
            self.wait_policy.append(part.part_id)
        self._begin_wait(part, "policy_hold")
        self.emit(
            "hold_start",
            part,
            place_id=part.place_id,
            primary_cause="policy_hold",
        )

    def _shared_ids_for_leg(self, leg: dict) -> list[str]:
        ids: list[str] = []
        for resource_id in leg.get("shared_resource_ids") or []:
            resource = self.shared_resources.get(resource_id)
            if not resource:
                continue
            if resource.get("capacity_students") is None:
                continue
            ids.append(resource_id)
        return ids

    def _shared_capacity(self, resource_id: str) -> int | None:
        resource = self.shared_resources.get(resource_id) or {}
        cap = resource.get("capacity_students")
        if cap is None:
            return None
        return int(cap)

    def _shared_remaining(self, resource_id: str) -> int:
        cap = self._shared_capacity(resource_id)
        if cap is None:
            return 10**9
        return cap - int(self.shared_occupancy.get(resource_id, 0))

    def _shared_occupy(self, resource_id: str, part: Part, n: int) -> None:
        self.shared_occupancy[resource_id] = self.shared_occupancy.get(resource_id, 0) + n
        held = self.shared_held_by_part.setdefault(part.part_id, {})
        held[resource_id] = held.get(resource_id, 0) + n
        after = self.shared_occupancy[resource_id]
        self.shared_flow.append(
            {
                "time_ms": self.now,
                "place_id": resource_id,
                "resource_id": resource_id,
                "direction": "in",
                "student_count": n,
                "occupancy_after": after,
                "kind": "shared_resource",
                "part_id": part.part_id,
            }
        )

    def _acquire_shared_for_leg(self, part: Part, leg: dict) -> bool:
        if part.part_id in self.shared_held_by_part:
            return True
        ids = self._shared_ids_for_leg(leg)
        if not ids:
            return True
        n = int(part.student_count)
        for resource_id in ids:
            resource = self.shared_resources.get(resource_id) or {}
            is_streaming = (
                resource.get("continuous_streaming") is True
                or resource_id in (
                    "path_carpark_single_file",
                    "path_north_plaza_single_file",
                    "path_south_plaza_single_file",
                )
            )
            cap = self._shared_capacity(resource_id)
            if not is_streaming:
                if cap is not None and n > cap:
                    self.violations.append(
                        {
                            "type": "physical_capacity",
                            "resource_id": resource_id,
                            "occupancy": n,
                            "capacity_students": cap,
                            "part_id": part.part_id,
                        }
                    )
                    return False
                if self._shared_remaining(resource_id) < n:
                    return False
        for resource_id in ids:
            self._shared_occupy(resource_id, part, n)
        return True
    def _release_shared_for_part(self, part: Part) -> None:
        held = self.shared_held_by_part.pop(part.part_id, {})
        if not held:
            return
        for resource_id, n in held.items():
            self.shared_occupancy[resource_id] = max(
                0, self.shared_occupancy.get(resource_id, 0) - int(n)
            )
            self.shared_flow.append(
                {
                    "time_ms": self.now,
                    "place_id": resource_id,
                    "resource_id": resource_id,
                    "direction": "out",
                    "student_count": int(n),
                    "occupancy_after": self.shared_occupancy[resource_id],
                    "kind": "shared_resource",
                    "part_id": part.part_id,
                }
            )
        self._try_waiting_shared()

    def _hold_for_shared_capacity(self, part: Part, leg: dict) -> None:
        part.status = "holding"
        if part.part_id not in self.wait_shared:
            self.wait_shared.append(part.part_id)
        self._begin_wait(part, "waiting_for_path")
        self.emit(
            "hold_start",
            part,
            place_id=part.place_id,
            resource_ids=self._shared_ids_for_leg(leg),
            primary_cause="waiting_for_path",
        )

    def _try_waiting_shared(self) -> None:
        waiting = list(self.wait_shared)
        self.wait_shared = []
        for part_id in waiting:
            part = self.parts.get(part_id)
            if part is None or part.status in {"completed", "split", "withdrawn"}:
                continue
            if part.status != "holding":
                continue
            stage = self._stage(part)
            if stage.get("kind") not in {"travel", "vehicle_travel"}:
                self.wait_shared.append(part_id)
                continue
            leg = self.legs.get(stage.get("leg_id")) or {}
            if self._acquire_shared_for_leg(part, leg):
                self._end_wait(part)
                self.emit(
                    "hold_end",
                    part,
                    place_id=part.place_id,
                    resource_ids=self._shared_ids_for_leg(leg),
                    primary_cause="waiting_for_path",
                )
                self.schedule(self.now, PHASE_START_DEPART, "departure", part)
            else:
                self.wait_shared.append(part_id)

    def _parts_missing_checkpoints(self) -> list[dict]:
        missing_rows: list[dict] = []
        seen_parts: set[str] = set()
        covered_by_part: dict[str, set[str]] = {}
        part_ref: dict[str, object] = {}
        for part in self.parts.values():
            if part.status != "completed":
                continue
            part_ref[part.part_id] = part
            covered_by_part.setdefault(part.part_id, set()).update(part.covered_checkpoint_ids)
        for row in self.completions:
            part_id = row.get("part_id")
            if not part_id:
                continue
            part = self.parts.get(part_id)
            if part is not None:
                part_ref[part_id] = part
            elif part_id not in part_ref:
                part_ref[part_id] = row
            covered_by_part.setdefault(part_id, set()).update(row.get("covered_checkpoint_ids") or [])
            if part is not None:
                covered_by_part[part_id].update(part.covered_checkpoint_ids)
        for part_id, part in part_ref.items():
            if part_id in seen_parts:
                continue
            seen_parts.add(part_id)
            required = required_checkpoints_for_part(self.scenario, part)
            covered = covered_by_part.get(part_id) or set()
            missing = [cid for cid in required if cid not in covered]
            if missing:
                missing_rows.append(
                    {
                        "part_id": part_id,
                        "checkpoint_ids": missing,
                    }
                )
        return missing_rows

    def _hold_for_path(self, part: Part, stage: dict) -> None:
        leg_id = stage.get("leg_id")
        part.status = "holding"
        self.wait_path.setdefault(leg_id or "", []).append(part.part_id)
        self._begin_wait(part, "waiting_for_path")
        self.emit(
            "hold_start",
            part,
            place_id=part.place_id,
            leg_id=leg_id,
            primary_cause="waiting_for_path",
        )

    def _hold_for_space(self, part: Part, dest: str) -> None:
        part.status = "holding"
        part.blocked_for_place_id = dest
        if part.part_id not in self.wait_reserve.get(dest, []):
            self.wait_reserve.setdefault(dest, []).append(part.part_id)
        self._begin_wait(part, "waiting_for_space")
        self.emit(
            "hold_start",
            part,
            place_id=part.place_id,
            primary_cause="waiting_for_space",
        )

    def _resume_policy_waiters(self) -> None:
        waiting = list(self.wait_policy)
        self.wait_policy = []
        for pid in waiting:
            part = self.parts.get(pid)
            if part is None or part.status in {"completed", "split", "withdrawn"}:
                continue
            self._end_wait(part)
            self.emit(
                "hold_end",
                part,
                place_id=part.place_id,
                primary_cause="policy_resume",
            )
            self.begin_stage(part)

    def _resume_path_waiters(self, leg_id: str) -> None:
        waiting = list(self.wait_path.get(leg_id) or [])
        self.wait_path[leg_id] = []
        for pid in waiting:
            part = self.parts.get(pid)
            if part is None or part.status in {"completed", "split", "withdrawn"}:
                continue
            self._end_wait(part)
            self.emit(
                "hold_end",
                part,
                place_id=part.place_id,
                primary_cause="path_reopened",
            )
            self.begin_stage(part)

    def _try_admit_waiters(self, place_id: str) -> None:
        waiters = list(self.wait_entry.get(place_id) or [])
        waiters.sort(key=self._queue_sort_key)
        remaining: list[str] = []
        for pid in waiters:
            part = self.parts.get(pid)
            if part is None or part.status != "blocked":
                continue
            if not self.space.can_enter(place_id, part.student_count):
                remaining.append(pid)
                continue
            wait_place = part.place_id
            vacated_wait = False
            if not part.aboard and wait_place and wait_place != place_id:
                # Occupying the wait place. Vacate without recursively admitting
                # this same destination.
                self.space.vacate(wait_place, part, self.now)
                vacated_wait = True
                self._maybe_operating_limit(wait_place)
                self._observe_occupancy(wait_place)
            was_aboard = part.aboard
            aboard_resource = (
                self.resources.get(part.resource_ids[0])
                if part.aboard and part.resource_ids
                else None
            )
            if aboard_resource is not None:
                aboard_resource.aboard_students = 0
                part.aboard = False
            if not self._admit_to_place(part, place_id):
                if vacated_wait and wait_place:
                    self.space.occupy(wait_place, part, self.now)
                    self._maybe_operating_limit(wait_place)
                    self._observe_occupancy(wait_place)
                if was_aboard and aboard_resource is not None:
                    aboard_resource.aboard_students = part.student_count
                    part.aboard = True
                remaining.append(pid)
                continue
            part.place_id = place_id
            self._end_wait(part)
            self.emit(
                "hold_end",
                part,
                place_id=place_id,
                primary_cause="space_available",
            )
            part.blocked_for_place_id = None
            part.status = "ready"
            if part.current_stage_id and self._stage(part).get("kind") in {
                "travel",
                "vehicle_travel",
            }:
                part.stage_index += 1
            self.begin_stage(part)
        self.wait_entry[place_id] = remaining

    def _try_release_reserve_waiters(self, place_id: str) -> None:
        waiters = list(self.wait_reserve.get(place_id) or [])
        remaining: list[str] = []
        for pid in waiters:
            part = self.parts.get(pid)
            if part is None or part.status in {"completed", "split", "withdrawn"}:
                continue
            if not self._try_reserve_destination(part, place_id):
                remaining.append(pid)
                continue
            self._end_wait(part)
            self.emit(
                "hold_end",
                part,
                place_id=part.place_id,
                primary_cause="space_reserved",
            )
            part.blocked_for_place_id = None
            self.begin_stage(part)
        self.wait_reserve[place_id] = remaining

    def _fail_no_waiting_space(self, part: Part, dest: str) -> None:
        self.hard_infeasible = True
        self.violations.append(
            {
                "type": "no_waiting_space",
                "place_id": dest,
                "part_id": part.part_id,
                "student_count": part.student_count,
                "occupancy": self.space.committed(dest),
                "capacity_students": self.space.physical_students(dest),
            }
        )
        self.emit(
            "denied_entry",
            part,
            place_id=dest,
            primary_cause="denied_entry",
        )
        self._begin_wait(part, "denied_entry")
        part.status = "blocked"
        part.blocked_for_place_id = dest

    def _maybe_operating_limit(self, place_id: str) -> None:
        limit = self.space.operating_limit(place_id)
        if limit is None:
            return
        occ = self.space.actual.get(place_id, 0)
        was = self.space.over_limit.get(place_id, False)
        now_over = occ > limit
        if now_over and not was:
            self._over_limit_open[place_id] = {
                "place_id": place_id,
                "start_ms": self.now,
                "limit": limit,
                "max_occupancy_students": occ,
            }
            self.emit(
                "operating_limit_exceeded",
                None,
                place_id=place_id,
                occupancy_students=occ,
                operating_limit_students=limit,
                primary_cause="operating_limit_exceeded",
            )
        elif now_over:
            open_row = self._over_limit_open.get(place_id)
            if open_row is not None:
                open_row["max_occupancy_students"] = max(int(open_row["max_occupancy_students"]), occ)
        elif was and not now_over:
            self._close_over_limit_place(place_id)
            self.emit(
                "operating_limit_cleared",
                None,
                place_id=place_id,
                occupancy_students=occ,
                operating_limit_students=limit,
                primary_cause="operating_limit_cleared",
            )
        self.space.over_limit[place_id] = now_over

    def _observe_occupancy(self, place_id: str) -> None:
        if not self.space_policy.tracks_reports():
            return
        delay_s = self.space_policy.coordination_delay_s or 0
        self.report_n += 1
        report_id = f"rep_{self.report_n:06d}"
        report = {
            "report_id": report_id,
            "kind": "occupancy",
            "place_id": place_id,
            "occupancy_students": self.space.actual.get(place_id, 0),
            "reserved_students": self.space.reserved.get(place_id, 0),
            "observation_ms": self.now,
            "delivery_ms": self.now + to_ms(delay_s),
            "source": "place_observer",
        }
        self.reports.append(report)
        self.schedule(
            report["delivery_ms"],
            PHASE_REPORT_DECISION,
            "report_delivered",
            None,
            report_id=report_id,
        )

    def _on_report_delivered(self, payload: dict) -> None:
        report_id = payload.get("report_id")
        report = next((row for row in self.reports if row["report_id"] == report_id), None)
        if report is None:
            return
        self.emit(
            "report_delivered",
            None,
            place_id=report.get("place_id"),
            report_id=report_id,
            observation_ms=report.get("observation_ms"),
            delivery_ms=report.get("delivery_ms"),
            occupancy_students=report.get("occupancy_students"),
            primary_cause="report_delivered",
        )
        action = self.space_policy.on_delivered(report, self.now)
        if action == "hold":
            self.emit(
                "policy_hold",
                None,
                place_id=report.get("place_id"),
                primary_cause="policy_hold",
            )
        elif action == "resume":
            self.emit(
                "policy_resume",
                None,
                place_id=report.get("place_id"),
                primary_cause="policy_resume",
            )
            self._resume_policy_waiters()

    def _on_condition_change(self, payload: dict) -> None:
        condition = dict(payload.get("condition") or {})
        effects = dict(condition.get("effects") or {})
        kind = condition.get("kind")
        self.emit(
            "condition_change",
            None,
            condition_id=condition.get("id"),
            condition_kind=kind,
            shared=bool(condition.get("shared")),
            forecast=condition.get("forecast"),
            actual=condition.get("actual", True),
            primary_cause="external_condition",
        )
        factor = effects.get("walking_rate_factor")
        if factor is not None:
            self.walking_rate_factor = float(factor)
        if effects.get("path_closed"):
            for leg_id in condition.get("affects_leg_ids") or []:
                self.closed_legs.add(leg_id)
        if effects.get("path_closed") is False:
            for leg_id in condition.get("affects_leg_ids") or []:
                self.closed_legs.discard(leg_id)
                self._resume_path_waiters(leg_id)
        if effects.get("require_shelter"):
            self.shelter_required = True
        hall_delay = effects.get("hall_open_delay_s")
        if hall_delay is not None:
            for calendar_id, calendar in self.calendars.items():
                if calendar.get("kind") in {"opening", "hall", "hall_opening"}:
                    self.calendar_open_at[calendar_id] = self.calendar_open_at.get(
                        calendar_id, to_ms(calendar["open_time_s"])
                    ) + to_ms(hall_delay)
                    self.schedule(
                        self.calendar_open_at[calendar_id],
                        PHASE_ARRIVAL_EXTERNAL,
                        "calendar_open",
                        None,
                        calendar_id=calendar_id,
                    )
        if effects.get("door_closed") and effects.get("calendar_id"):
            self.calendar_open[effects["calendar_id"]] = False
        for vehicle_id in effects.get("bus_outage_vehicle_ids") or []:
            resource = self.resources.get(vehicle_id)
            if resource is None:
                continue
            resource.outages.append(
                {
                    "start_s": ms_to_s(self.now),
                    "end_s": float(effects.get("bus_outage_end_s") or ms_to_s(self.now) + 3600),
                }
            )
            resource.available = False
        for worker_id in effects.get("workers_unavailable") or []:
            worker = self.worker_pool.by_id.get(worker_id)
            if worker is None:
                continue
            worker.available_from_ms = self.now + to_ms(effects.get("workers_unavailable_s") or 3600)
        if self.space_policy.tracks_reports():
            delay_s = self.space_policy.coordination_delay_s or 0
            self.report_n += 1
            report_id = f"rep_{self.report_n:06d}"
            report = {
                "report_id": report_id,
                "kind": "condition",
                "condition_id": condition.get("id"),
                "condition_kind": kind,
                "observation_ms": self.now,
                "delivery_ms": self.now + to_ms(delay_s),
                "source": "condition_observer",
                "forecast": condition.get("forecast"),
                "actual": condition.get("actual", True),
            }
            self.reports.append(report)
            self.schedule(
                report["delivery_ms"],
                PHASE_REPORT_DECISION,
                "report_delivered",
                None,
                report_id=report_id,
            )


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _merge_compositions(parts: list[Part]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for part in parts:
        for hostel, count in part.hostel_composition.items():
            merged[hostel] = merged.get(hostel, 0) + count
    return merged
