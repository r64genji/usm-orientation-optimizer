from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operator_dashboard.api import Settings, create_app
from operator_dashboard.contracts import DashboardError
from operator_dashboard.runner import build_command, parse_envelope, run_job
from operator_dashboard.store import Store
from tests.dashboard.conftest import INTERPRETER, REPO_ROOT


def test_build_command_defaults_to_full():
    cmd = build_command(interpreter="/venv/bin/python", command="simulate", case="artificial", seed=42)
    assert cmd[:4] == ["/venv/bin/python", "-m", "usm_sim", "simulate"]
    assert "--full" in cmd
    assert "--compact" not in cmd
    assert cmd.count("--seed") == 1


def test_build_command_compact_and_input():
    cmd = build_command(
        interpreter="python",
        command="simulate",
        seed=7,
        output_mode="compact",
        input_path="/tmp/in.json",
    )
    assert "--compact" in cmd
    assert "--input" in cmd
    assert "/tmp/in.json" in cmd


def test_build_command_rejects_search():
    with pytest.raises(DashboardError):
        build_command(interpreter="python", command="search", case="artificial")


def test_parse_envelope_success():
    data = parse_envelope('{"ok": true, "command": "simulate", "result": {"status": "completed"}}')
    assert data["ok"] is True


def test_store_queue_limit(tmp_path: Path):
    store = Store(tmp_path, max_queue=1)
    store.create_job({"case": "artificial", "seed": 1, "command": "simulate", "output_mode": "full"}, source_commit="x")
    with pytest.raises(DashboardError) as err:
        store.create_job({"case": "artificial", "seed": 2, "command": "simulate", "output_mode": "full"}, source_commit="x")
    assert err.value.status_code == 429


def test_recover_interrupted(tmp_path: Path):
    store = Store(tmp_path)
    job = store.create_job({"case": "artificial", "seed": 1, "command": "simulate", "output_mode": "full"}, source_commit="x")
    store.update_job(job["id"], status="running")
    ids = store.recover_interrupted_jobs()
    assert job["id"] in ids
    assert store.get_job(job["id"])["status"] == "interrupted"


def test_run_job_subprocess_artificial(tmp_path: Path):
    store = Store(tmp_path)
    job = store.create_job(
        {"case": "artificial", "seed": 42, "command": "simulate", "output_mode": "compact", "apply_parameters": False, "holdout": False, "group_target_students": None, "hall_seats": None},
        source_commit="test",
    )
    finished = run_job(
        store,
        job["id"],
        interpreter=INTERPRETER,
        repo_root=REPO_ROOT,
        timeout_s=60,
        max_result_bytes=5_000_000,
    )
    assert finished["status"] == "finished"
    envelope = store.load_result(job["id"])
    assert envelope["ok"] is True
    assert "event_trace" not in (envelope.get("result") or {})
    assert envelope["result"]["measures"]["completed_students"] == 4


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        auth_token="secret-token",
        data_dir=tmp_path,
        interpreter=INTERPRETER,
        repo_root=REPO_ROOT,
        job_timeout_s=60,
        max_queue=4,
        max_result_bytes=5_000_000,
        history_limit=20,
        optimizer_dir=tmp_path / "opt",
        source_commit="testcommit",
    )
    app = create_app(settings)
    return TestClient(app)


def test_healthz_no_auth(tmp_path: Path):
    with _client(tmp_path) as client:
        res = client.get("/healthz")
        assert res.status_code == 200
        body = res.json()
        assert body["interpreter_ok"] is True
        assert body["storage_writable"] is True
        assert "commit" in body


def test_api_requires_auth(tmp_path: Path):
    with _client(tmp_path) as client:
        res = client.get("/api/cases")
        assert res.status_code == 401
        res = client.get("/api/cases", headers={"Authorization": "Bearer secret-token"})
        assert res.status_code == 200
        ids = [row["id"] for row in res.json()["cases"]]
        assert "artificial" in ids


def test_csrf_origin_rejected(tmp_path: Path):
    with _client(tmp_path) as client:
        res = client.post(
            "/api/runs",
            headers={
                "Authorization": "Bearer secret-token",
                "Origin": "https://evil.example",
                "Host": "127.0.0.1:8866",
            },
            json={"case": "artificial", "seed": 42},
        )
        assert res.status_code == 403
