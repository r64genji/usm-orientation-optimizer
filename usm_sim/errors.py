"""Structured failures for the public Simulate operation."""

from __future__ import annotations

from usm_sim.constants import ERROR_CATEGORIES


class SimulationError(Exception):
    """Input or policy error that stops a run before movement starts."""

    def __init__(
        self,
        category: str,
        message: str,
        *,
        field: str | None = None,
        details: dict | None = None,
    ) -> None:
        if category not in ERROR_CATEGORIES:
            raise ValueError(f"unknown error category: {category}")
        self.category = category
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)

    def as_dict(self) -> dict:
        payload = {
            "error": True,
            "category": self.category,
            "message": self.message,
        }
        if self.field is not None:
            payload["field"] = self.field
        if self.details:
            payload["details"] = self.details
        return payload
