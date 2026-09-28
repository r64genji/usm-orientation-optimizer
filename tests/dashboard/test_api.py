from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from operator_dashboard.api import Settings, create_app
from tests.dashboard.conftest import INTERPRETER, REPO_ROOT

AUTH = {"Authorization": "Bearer secret-token"}


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(
        auth_token="secret-token",
        data_dir=tmp_path,
        interpreter=INTERPRETER,
        repo_root=REPO_ROOT,
        job_timeout_s=60,
        max_queue=4,
        max_result_bytes=8_000_000,
        history_limit=20,
        optimizer_dir=None,
        source_commit="testcommit",
    )
    return TestClient(create_app(settings))


def _wait(client: TestClient, run_id: str, timeout: float = 45.0) -> dict:
    deadline = time.time() + timeout
    body = {}
    while time.time() < deadline:
        res = client.get(f"/api/runs/{run_id}", headers=AUTH)
        assert res.status_code == 200
        body = res.json()
        if body["status"] in {"finished", "failed", "timed_out", "interrupted"}:
            return body
        time.sleep(0.1)
    raise AssertionError(f"run did not finish: {body}")


def test_start_artificial_full_and_conservation(tmp_path: Path):
    with _client(tmp_path) as client:
        res = client.post("/api/runs", headers=AUTH, json={"case": "artificial", "seed": 42})
        assert res.status_code == 202
        run_id = res.json()["id"]
        job = _wait(client, run_id)
        assert job["status"] == "finished"
        assert job["output_mode"] == "full"
        overview = client.get(f"/api/runs/{run_id}/overview", headers=AUTH).json()
        assert overview["completed_students"] + overview["withdrawn_students"] + overview["unfinished_students"] == overview["accounted_students"]
        assert overview["conservation_ok"] is True
        legs = client.get(f"/api/runs/{run_id}/legs", headers=AUTH).json()
        assert legs["detailed_legs_available"] is True
        mmap = client.get(f"/api/runs/{run_id}/map", headers=AUTH).json()
        assert mmap["hostels"]
        bottlenecks = client.get(f"/api/runs/{run_id}/bottlenecks", headers=AUTH).json()
        assert "delays" in bottlenecks


def test_compact_run_disables_detailed_legs(tmp_path: Path):
    with _client(tmp_path) as client:
        res = client.post(
            "/api/runs",
            headers=AUTH,
            json={"case": "artificial", "seed": 42, "output_mode": "compact"},
        )
        run_id = res.json()["id"]
        job = _wait(client, run_id)
        assert job["status"] == "finished"
        legs = client.get(f"/api/runs/{run_id}/legs", headers=AUTH).json()
        assert legs["detailed_legs_available"] is False


def test_holdout_search_rejected_by_api(tmp_path: Path):
    with _client(tmp_path) as client:
        res = client.post(
            "/api/runs",
            headers=AUTH,
            json={"case": "restu-17sep", "seed": 1, "command": "search"},
        )
        assert res.status_code == 400
        assert "holdout" in res.json()["message"].lower()
        res = client.post(
            "/api/runs",
            headers=AUTH,
            json={"case": "restu_18sep_rainy_replay", "seed": 1, "command": "loop"},
        )
        assert res.status_code == 400


def test_optimizer_empty(tmp_path: Path):
    with _client(tmp_path) as client:
        res = client.get("/api/optimizer", headers=AUTH)
        assert res.status_code == 200
        assert res.json()["message"] == "No saved result"


def test_replay_api_endpoint(tmp_path: Path):
    with _client(tmp_path) as client:
        # Auth check
        res = client.get("/api/runs/test_run/replay")
        assert res.status_code == 401

        # 404 on unknown run
        res = client.get("/api/runs/unknown_run/replay", headers=AUTH)
        assert res.status_code == 404

        # Full run replay
        post_res = client.post("/api/runs", headers=AUTH, json={"case": "artificial", "seed": 42})
        assert post_res.status_code == 202
        run_id = post_res.json()["id"]
        job = _wait(client, run_id)
        assert job["status"] == "finished"

        replay_res = client.get(f"/api/runs/{run_id}/replay", headers=AUTH)
        assert replay_res.status_code == 200
        data = replay_res.json()
        assert data["has_trace"] is True
        assert "time_bounds" in data
        assert len(data["sectors"]) >= 18
        assert len(data["student_trajectories"]) > 0
        assert len(data["sector_stats_timeline"]) > 0
