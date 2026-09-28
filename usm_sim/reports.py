"""Delivered reports and occupancy hold/resume. Hidden state is not a policy input."""

from __future__ import annotations

from dataclasses import dataclass, field

from usm_sim.timeutil import to_ms


@dataclass
class SpacePolicy:
    destination_space_rule: str | None = None
    coordination_delay_s: float | None = None
    watch_place_id: str | None = None
    hold_threshold_students: int | None = None
    resume_threshold_students: int | None = None
    min_hold_duration_s: float = 0.0
    hold_active: bool = False
    hold_since_ms: int | None = None
    view: dict[str, int] = field(default_factory=dict)
    delivered: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)

    @classmethod
    def from_policy(cls, policy: dict) -> SpacePolicy:
        control = dict(policy.get("space_control") or {})
        delay = policy.get("coordination_delay_s")
        rule = policy.get("destination_space_rule")
        resume = control.get("resume_threshold_students")
        hold = control.get("hold_threshold_students")
        return cls(
            destination_space_rule=rule,
            coordination_delay_s=None if delay is None else float(delay),
            watch_place_id=control.get("destination_place_id"),
            hold_threshold_students=None if hold is None else int(hold),
            resume_threshold_students=None if resume is None else int(resume),
            min_hold_duration_s=float(control.get("min_hold_duration_s") or 0),
        )

    def tracks_reports(self) -> bool:
        return self.coordination_delay_s is not None

    def reserves_before_departure(self) -> bool:
        return self.destination_space_rule == "reserve_before_departure"

    def allows_approach_wait(self) -> bool:
        return self.destination_space_rule != "reserve_before_departure"

    def delivered_occupancy(self, place_id: str | None) -> int:
        if not place_id:
            return 0
        return int(self.view.get(place_id, 0))

    def delivered_can_fit(self, place_id: str | None, n: int, capacity: int | None) -> bool:
        if capacity is None:
            return True
        return self.delivered_occupancy(place_id) + n <= capacity

    def on_delivered(self, report: dict, now_ms: int) -> str | None:
        self.delivered.append(report)
        if report.get("kind") == "occupancy":
            self.view[report["place_id"]] = int(report.get("occupancy_students") or 0)
        action = self._maybe_toggle(now_ms)
        if action:
            report["requires_action"] = True
            report["action"] = action
        return action

    def _maybe_toggle(self, now_ms: int) -> str | None:
        if self.watch_place_id is None or self.hold_threshold_students is None:
            return None
        occ = self.delivered_occupancy(self.watch_place_id)
        if not self.hold_active:
            if occ >= self.hold_threshold_students:
                self.hold_active = True
                self.hold_since_ms = now_ms
                decision = {
                    "time_ms": now_ms,
                    "action": "hold",
                    "place_id": self.watch_place_id,
                    "delivered_occupancy_students": occ,
                    "hold_threshold_students": self.hold_threshold_students,
                }
                self.decisions.append(decision)
                return "hold"
            return None
        resume_at = self.resume_threshold_students
        if resume_at is None:
            resume_at = self.hold_threshold_students
        if occ > resume_at:
            return None
        held_ms = now_ms - (self.hold_since_ms or now_ms)
        if held_ms < to_ms(self.min_hold_duration_s):
            return None
        self.hold_active = False
        self.hold_since_ms = None
        decision = {
            "time_ms": now_ms,
            "action": "resume",
            "place_id": self.watch_place_id,
            "delivered_occupancy_students": occ,
            "resume_threshold_students": resume_at,
        }
        self.decisions.append(decision)
        return "resume"
