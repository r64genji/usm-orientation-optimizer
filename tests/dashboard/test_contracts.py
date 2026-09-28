from __future__ import annotations

import pytest

from operator_dashboard.contracts import DTO_VERSION, DashboardError
from operator_dashboard.projections import project_overview
from operator_dashboard.runner import parse_envelope


def test_dto_version_present(artificial_full):
    overview = project_overview(
        "run1",
        artificial_full,
        case="artificial",
        seed=42,
        output_mode="full",
    )
    assert overview["dto_version"] == DTO_VERSION
    assert overview["run_id"] == "run1"
    assert overview["units"]["wait"] == "s"
    assert "measures" in overview["source_fields"]


def test_parse_envelope_requires_ok():
    with pytest.raises(DashboardError):
        parse_envelope("{")
    with pytest.raises(DashboardError):
        parse_envelope('{"result": {}}')
    data = parse_envelope('{"ok": false, "command": "simulate", "error": {"message": "nope"}}')
    assert data["ok"] is False


def test_missing_result_uses_null_not_zero():
    overview = project_overview(
        "runx",
        {"ok": True, "result": None},
        case="artificial",
        seed=42,
        output_mode="full",
    )
    assert overview["mean_wait_s"] is None
    assert overview["completed_students"] is None
    assert overview["missing"] == "No result yet."
