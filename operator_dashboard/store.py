from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from operator_dashboard.contracts import DashboardError


class Store:
    def __init__(self, data_dir: Path, *, max_queue: int = 4, history_limit: int = 50) -> None:
        self.data_dir = Path(data_dir)
        self.jobs_dir = self.data_dir / "jobs"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.max_queue = int(max_queue)
        self.history_limit = int(history_limit)
        self.db_path = self.data_dir / "jobs.sqlite"
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    output_mode TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    engine_status TEXT,
                    termination_cause TEXT,
                    exit_code INTEGER,
                    error_json TEXT,
                    started_at REAL,
                    finished_at REAL,
                    wall_s REAL,
                    result_path TEXT,
                    stdout_path TEXT,
                    input_path TEXT,
                    source_commit TEXT,
                    engine_version TEXT
                )
                """
            )
            conn.commit()

    def queued_or_running_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchone()
            return int(row["n"] if row else 0)

    def create_job(self, request: dict[str, Any], *, source_commit: str | None) -> dict[str, Any]:
        with self._lock:
            if self.queued_or_running_count() >= self.max_queue:
                raise DashboardError(
                    "Too many runs are waiting. Wait for one to finish.",
                    field="queue",
                    status_code=429,
                )
            job_id = uuid.uuid4().hex[:12]
            now = time.time()
            job_dir = self.jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            record = {
                "id": job_id,
                "created_at": now,
                "updated_at": now,
                "status": "queued",
                "case_id": request["case"],
                "seed": int(request["seed"]),
                "command": request["command"],
                "output_mode": request["output_mode"],
                "request_json": json.dumps(request),
                "engine_status": None,
                "termination_cause": None,
                "exit_code": None,
                "error_json": None,
                "started_at": None,
                "finished_at": None,
                "wall_s": None,
                "result_path": str(job_dir / "result.json"),
                "stdout_path": str(job_dir / "stdout.json"),
                "input_path": str(job_dir / "input.json"),
                "source_commit": source_commit,
                "engine_version": None,
            }
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, created_at, updated_at, status, case_id, seed, command,
                        output_mode, request_json, engine_status, termination_cause,
                        exit_code, error_json, started_at, finished_at, wall_s,
                        result_path, stdout_path, input_path, source_commit, engine_version
                    ) VALUES (
                        :id, :created_at, :updated_at, :status, :case_id, :seed, :command,
                        :output_mode, :request_json, :engine_status, :termination_cause,
                        :exit_code, :error_json, :started_at, :finished_at, :wall_s,
                        :result_path, :stdout_path, :input_path, :source_commit, :engine_version
                    )
                    """,
                    record,
                )
                conn.commit()
            return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        fields["updated_at"] = time.time()
        assignments = ", ".join(f"{key} = :{key}" for key in fields)
        fields["id"] = job_id
        with self._connect() as conn:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE id = :id", fields)
            conn.commit()
        return self.get_job(job_id)

    def recover_interrupted_jobs(self) -> list[str]:
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM jobs WHERE status IN ('queued', 'running')"
            ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'interrupted', updated_at = ?, finished_at = ?,
                        error_json = ?
                    WHERE status IN ('queued', 'running')
                    """,
                    (
                        now,
                        now,
                        json.dumps({"message": "Server restarted. Start a new run."}),
                    ),
                )
                conn.commit()
        return ids

    def expire_old_runs(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        ids = [row["id"] for row in rows]
        drop = ids[self.history_limit :]
        removed = []
        for job_id in drop:
            job = self.get_job(job_id)
            if job and job["status"] in {"queued", "running"}:
                continue
            self._delete_job(job_id)
            removed.append(job_id)
        return removed

    def _delete_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        with self._connect() as conn:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
        job_dir = self.jobs_dir / job_id
        if job_dir.exists():
            for path in job_dir.iterdir():
                path.unlink(missing_ok=True)
            job_dir.rmdir()
        if job:
            pass

    def save_result(self, job_id: str, payload: dict[str, Any]) -> Path:
        job = self.get_job(job_id)
        if job is None:
            raise DashboardError("Unknown run", field="run_id", status_code=404)
        path = Path(job["result_path"])
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def load_result(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if job is None or not job.get("result_path"):
            return None
        path = Path(job["result_path"])
        if not path.exists():
            fallback = self.jobs_dir / job_id / "result.json"
            if fallback.exists():
                path = fallback
            else:
                return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_input(self, job_id: str, payload: dict[str, Any]) -> Path:
        job = self.get_job(job_id)
        if job is None:
            raise DashboardError("Unknown run", field="run_id", status_code=404)
        path = Path(job["input_path"])
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def load_input(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if job is None or not job.get("input_path"):
            return None
        path = Path(job["input_path"])
        if not path.exists():
            fallback = self.jobs_dir / job_id / "input.json"
            if fallback.exists():
                path = fallback
            else:
                return None
        return json.loads(path.read_text(encoding="utf-8"))

    def public_job(self, job: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        started = job.get("started_at")
        finished = job.get("finished_at")
        wall_s = job.get("wall_s")
        if wall_s is None and started:
            end = finished or now
            wall_s = max(0.0, end - started)
        return {
            "id": job["id"],
            "run_id": job["id"],
            "status": job["status"],
            "case": job["case_id"],
            "seed": job["seed"],
            "command": job["command"],
            "output_mode": job["output_mode"],
            "engine_status": job.get("engine_status"),
            "termination_cause": job.get("termination_cause"),
            "exit_code": job.get("exit_code"),
            "error": json.loads(job["error_json"]) if job.get("error_json") else None,
            "created_at": job["created_at"],
            "started_at": started,
            "finished_at": finished,
            "wall_s": wall_s,
            "source_commit": job.get("source_commit"),
            "engine_version": job.get("engine_version"),
            "holdout": False,
        }

    def _row_to_job(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["request"] = json.loads(data["request_json"])
        return data
