from __future__ import annotations

from typing import Any

DTO_VERSION = "usm-dashboard-v1"

ALLOWED_RUN_FIELDS = frozenset(
    {
        "case",
        "seed",
        "output_mode",
        "group_target_students",
        "hall_seats",
        "command",
        "apply_parameters",
    }
)

OUTPUT_MODES = ("full", "compact")
DEFAULT_OUTPUT_MODE = "full"
DEFAULT_GROUP_TARGET = 25
LOCKED_FLEET = {
    "n_buses": 8,
    "n_coach": 5,
    "n_electric": 3,
    "usable_doors": 1,
    "coach_capacity_students": 80,
    "coach_seated_students": 40,
    "electric_capacity_students": 40,
    "electric_seated_students": 28,
    "capacities_status": "assumed",
}

HALL_SEAT_CHOICES = {
    1338: {
        "label": "paper_main_floor",
        "title": "Paper main floor 1338",
        "note": "Kawsar main-floor model. Not a fire certificate.",
        "status": "paper_main_floor",
    },
    2500: {
        "label": "cited_full_hall",
        "title": "Cited full hall 2500",
        "note": "Cited full-hall range 2500-3500. Not confirmed.",
        "status": "cited_full_hall",
    },
    3500: {
        "label": "cited_full_hall",
        "title": "Cited full hall 3500",
        "note": "Cited full-hall range 2500-3500. Not confirmed.",
        "status": "cited_full_hall",
    },
}

HOLDOUT_CASE_IDS = frozenset(
    {
        "restu-17sep",
        "restu-18sep-rainy",
        "restu_17sep_replay",
        "restu_18sep_rainy_replay",
    }
)

CASE_ALIASES = {
    "restu_17sep_replay": "restu-17sep",
    "restu_18sep_rainy_replay": "restu-18sep-rainy",
}

GUIDE_TEXT = {
    "case": "Case = starting setup.",
    "run": "Run = one test.",
    "seed": "Seed = repeat setting.",
    "unfinished": "Unfinished = students who did not finish before this test stopped.",
    "restu": "Restu moves last.",
    "optimizer": "The optimizer tests plans in the simulator.",
    "route_link": "Route link, not exact road path",
    "restu_overlay": "One phone in one contingent (student group).",
    "fleet": "8 buses. 5 coach and 3 electric. Each bus has one door. Capacities are assumed.",
}

JOB_STATUSES = (
    "queued",
    "running",
    "finished",
    "failed",
    "timed_out",
    "interrupted",
)


class DashboardError(Exception):
    def __init__(self, message: str, *, field: str | None = None, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.field = field
        self.status_code = status_code

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": True, "message": self.message}
        if self.field:
            payload["field"] = self.field
        return payload


def as_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DashboardError(f"{field} must be an integer", field=field)
    return value


def as_optional_positive_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DashboardError(f"{field} must be a positive integer", field=field)
    return value


def labeled_fact(kind: str, text: str, *, source: str | None = None) -> dict[str, Any]:
    return {"kind": kind, "text": text, "source": source}


def dto_base(run_id: str | None, *, units: dict[str, str], source_fields: list[str], missing: str | None = None) -> dict[str, Any]:
    return {
        "dto_version": DTO_VERSION,
        "run_id": run_id,
        "units": units,
        "source_fields": source_fields,
        "missing": missing,
    }
