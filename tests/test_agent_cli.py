from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from usm_sim import build_artificial_120_hostel_case, build_loop_proposal
from usm_sim.cli import main

EXPECTED_COMMANDS = [
    "schema",
    "cases",
    "check",
    "simulate",
    "resolve",
    "search",
    "loop",
    "replay",
    "benchmark",
]


def run_cli(argv: list[str]) -> tuple[int, dict]:
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        code = main(argv)
    finally:
        sys.stdout = old_stdout
    raw = captured.getvalue()
    payload = json.loads(raw)
    return code, payload


def test_schema_lists_all_commands():
    code, payload = run_cli(["schema"])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "schema"
    assert "result" in payload
    commands = payload["result"]["commands"]
    for cmd in EXPECTED_COMMANDS:
        assert cmd in commands
    assert "error_categories" in payload["result"]
    assert "exit_codes" in payload["result"]


def test_cases_lists_required_cases():
    code, payload = run_cli(["cases"])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "cases"
    cases = payload["result"]["cases"]
    case_ids = {c["id"] for c in cases}
    assert "artificial" in case_ids
    assert "restu-17sep" in case_ids
    assert "artificial-120-floor" in case_ids
    assert "rst-shared-fleet" in case_ids


def test_simulate_compact_omits_event_trace():
    code, payload = run_cli(["simulate", "--case", "artificial", "--compact"])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "simulate"
    assert "event_trace" not in payload["result"]
    assert "input_snapshot" not in payload["result"]
    assert payload["result"]["status"] == "completed"


def test_simulate_full_includes_event_trace():
    code, payload = run_cli(["simulate", "--case", "artificial", "--full"])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "simulate"
    assert "event_trace" in payload["result"]
    assert isinstance(payload["result"]["event_trace"], list)
    assert len(payload["result"]["event_trace"]) > 0


def test_check_valid_floor_proposal_accepts(tmp_path: Path):
    _, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)
    prop_path = tmp_path / "proposal.json"
    prop_path.write_text(json.dumps(proposal))

    code, payload = run_cli(["check", "--case", "artificial-120-floor", "--proposal", str(prop_path)])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "check"
    assert payload["result"]["accepted"] is True


def test_check_change_occupancy_returns_accepted_false_exit_0(tmp_path: Path):
    _, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)
    proposal["fixed_choices"]["resident_occupancy"] = 1
    prop_path = tmp_path / "bad_proposal.json"
    prop_path.write_text(json.dumps(proposal))

    code, payload = run_cli(["check", "--case", "artificial-120-floor", "--proposal", str(prop_path)])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "check"
    assert payload["result"]["accepted"] is False
    assert payload["result"]["category"] == "fixed_rule_violation"


def test_simulate_missing_scenario_returns_envelope_error_exit_2():
    code, payload = run_cli(["simulate"])
    assert code == 2
    assert payload["ok"] is False
    assert payload["command"] == "simulate"
    assert payload["error"]["category"] == "missing_input"
    assert payload["error"]["field"] == "scenario"


def test_search_with_tiny_limits_returns_claim(tmp_path: Path):
    _, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)
    prop_path = tmp_path / "proposal.json"
    prop_path.write_text(json.dumps(proposal))

    lim_path = tmp_path / "limits.json"
    lim_path.write_text(json.dumps({"max_candidates": 2, "max_cases_per_candidate": 1}))

    code, payload = run_cli([
        "search",
        "--case",
        "artificial-120-floor",
        "--proposal",
        str(prop_path),
        "--limits",
        str(lim_path),
        "--compact",
    ])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "search"
    claim = payload["result"].get("claim", "")
    assert "best" in claim.lower()
    assert "search" in claim.lower()
    assert "stopping_reason" in payload["result"]
    assert "feasible_plans" in payload["result"]
    assert "pareto_set" in payload["result"]
    assert "failed_cases" in payload["result"]


def test_loop_one_fixture_proposal_returns_json(tmp_path: Path):
    _, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)
    props_path = tmp_path / "proposals.json"
    props_path.write_text(json.dumps([proposal]))

    code, payload = run_cli([
        "loop",
        "--case",
        "artificial-120-floor",
        "--proposals",
        str(props_path),
        "--round-budget",
        "1",
        "--compact",
    ])
    assert code == 0
    assert payload["ok"] is True
    assert payload["command"] == "loop"
    assert payload["result"]["status"] in ("completed", "no_feasible_plan")
    assert "feasible_plan_found" in payload["result"]
    assert "best_plan" in payload["result"]
    assert "event_trace" not in payload["result"]["best_plan"]
    assert "validation_errors" in payload["result"]
    assert "pareto_set" in payload["result"]
    assert "stopping_reason" in payload["result"]
    assert "claim" in payload["result"]


def test_failed_check_stdout_is_valid_json_no_traceback(tmp_path: Path):
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        _, policy = build_artificial_120_hostel_case("floor")
        proposal = build_loop_proposal(policy)
        proposal["fixed_choices"]["resident_occupancy"] = 1
        prop_path = tmp_path / "bad.json"
        prop_path.write_text(json.dumps(proposal))
        code = main(["check", "--case", "artificial-120-floor", "--proposal", str(prop_path)])
    finally:
        sys.stdout = old_stdout

    raw_output = captured.getvalue()
    assert "Traceback" not in raw_output
    parsed = json.loads(raw_output)
    assert parsed["ok"] is True
    assert parsed["result"]["accepted"] is False
    assert code == 0


def test_missing_file_returns_envelope_error_exit_2():
    code, payload = run_cli(["check", "--case", "artificial", "--proposal", "/missing/path/does_not_exist.json"])
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"]["category"] == "missing_input"


def test_invalid_json_returns_envelope_error_exit_2(tmp_path: Path):
    bad_file = tmp_path / "corrupt.json"
    bad_file.write_text("{ this is not valid json")
    code, payload = run_cli(["check", "--case", "artificial", "--proposal", str(bad_file)])
    assert code == 2
    assert payload["ok"] is False
    assert payload["error"]["category"] == "invalid_value_or_unit"


def test_cli_subprocess_invocation():
    res = subprocess.run(
        [sys.executable, "-m", "usm_sim", "schema"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "Traceback" not in res.stderr
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["command"] == "schema"
