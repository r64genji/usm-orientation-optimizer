from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable

from operator_dashboard.contracts import DashboardError
from operator_dashboard.inputs import build_input_payload
from operator_dashboard.store import Store

ALLOWED_COMMANDS = frozenset({"simulate"})


class EnvelopeError(DashboardError):
    pass


def build_command(
    *,
    interpreter: str | Path,
    command: str,
    case: str | None = None,
    seed: int = 42,
    output_mode: str = "full",
    input_path: str | Path | None = None,
) -> list[str]:
    if command not in ALLOWED_COMMANDS:
        raise DashboardError(f"Command {command} is not allowed.", field="command")
    cmd = [str(interpreter), "-m", "usm_sim", command]
    if input_path:
        cmd.extend(["--input", str(input_path)])
    elif case:
        cmd.extend(["--case", str(case)])
    else:
        raise DashboardError("Case or input is required.", field="case")
    cmd.extend(["--seed", str(int(seed))])
    if output_mode == "compact":
        cmd.append("--compact")
    else:
        cmd.append("--full")
    return cmd


def parse_envelope(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise EnvelopeError("Simulator wrote no JSON.", field="stdout")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError as inner:
                raise EnvelopeError(f"Simulator JSON is damaged: {inner}", field="stdout") from inner
        else:
            raise EnvelopeError(f"Simulator JSON is damaged: {err}", field="stdout") from err
    if not isinstance(data, dict) or "ok" not in data:
        raise EnvelopeError("Simulator JSON is missing the ok envelope.", field="stdout")
    return data


def run_job(
    store: Store,
    job_id: str,
    *,
    interpreter: str | Path,
    repo_root: Path,
    timeout_s: float,
    max_result_bytes: int,
) -> dict[str, Any]:
    job = store.get_job(job_id)
    if job is None:
        raise DashboardError("Unknown run", field="run_id", status_code=404)
    request = job["request"]
    started = time.time()
    store.update_job(job_id, status="running", started_at=started)
    try:
        payload = build_input_payload(request)
        input_path = store.save_input(job_id, payload)
        cmd = build_command(
            interpreter=interpreter,
            command=request["command"],
            case=request["case"],
            seed=request["seed"],
            output_mode=request["output_mode"],
            input_path=input_path,
        )
        stdout_path = Path(job["stdout_path"])
        stderr_path = stdout_path.with_name("stderr.txt")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        with stdout_path.open("wb") as out_f, stderr_path.open("wb") as err_f:
            proc = subprocess.Popen(
                cmd,
                stdout=out_f,
                stderr=err_f,
                cwd=str(repo_root),
                env=env,
                start_new_session=True,
            )
            deadline = time.time() + float(timeout_s)
            while proc.poll() is None:
                if stdout_path.stat().st_size > max_result_bytes:
                    _kill_process(proc)
                    raise DashboardError(
                        "The run result grew too large and was stopped.",
                        field="result",
                    )
                if time.time() > deadline:
                    _kill_process(proc)
                    wall_s = time.time() - started
                    store.update_job(
                        job_id,
                        status="timed_out",
                        finished_at=time.time(),
                        wall_s=wall_s,
                        exit_code=proc.returncode,
                        error_json=json.dumps({"message": "The run hit the time limit."}),
                    )
                    return store.get_job(job_id)
                time.sleep(0.05)
            exit_code = int(proc.returncode if proc.returncode is not None else 1)
        text = stdout_path.read_text(encoding="utf-8", errors="replace")
        envelope = parse_envelope(text)
        store.save_result(job_id, envelope)
        result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
        engine_status = result.get("status") if envelope.get("ok") else None
        termination = result.get("termination_cause")
        versions = result.get("versions") if isinstance(result.get("versions"), dict) else {}
        engine_version = versions.get("engine_version")
        error_json = None
        if not envelope.get("ok"):
            error_json = json.dumps(envelope.get("error") or {"message": "Command failed."})
            status = "failed"
        else:
            status = "finished"
        wall_s = time.time() - started
        store.update_job(
            job_id,
            status=status,
            finished_at=time.time(),
            wall_s=wall_s,
            exit_code=exit_code,
            engine_status=engine_status,
            termination_cause=termination,
            engine_version=engine_version,
            error_json=error_json,
        )
        return store.get_job(job_id)
    except DashboardError as err:
        wall_s = time.time() - started
        store.update_job(
            job_id,
            status="failed",
            finished_at=time.time(),
            wall_s=wall_s,
            error_json=json.dumps(err.as_dict()),
        )
        return store.get_job(job_id)
    except Exception as exc:
        wall_s = time.time() - started
        store.update_job(
            job_id,
            status="failed",
            finished_at=time.time(),
            wall_s=wall_s,
            error_json=json.dumps({"message": str(exc)}),
        )
        return store.get_job(job_id)


def _kill_process(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()


class Worker:
    def __init__(
        self,
        store: Store,
        *,
        interpreter: str | Path,
        repo_root: Path,
        timeout_s: float,
        max_result_bytes: int,
        run_fn: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.store = store
        self.interpreter = interpreter
        self.repo_root = repo_root
        self.timeout_s = timeout_s
        self.max_result_bytes = max_result_bytes
        self.run_fn = run_fn or run_job
        self.queue: Queue[str] = Queue()
        self._stop = threading.Event()
        self._busy = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="usm-dashboard-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.queue.put("__stop__")
        if self._thread:
            self._thread.join(timeout=2)

    def submit(self, job_id: str) -> None:
        self.queue.put(job_id)

    def busy(self) -> bool:
        return self._busy.is_set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self.queue.get(timeout=0.2)
            except Empty:
                continue
            if job_id == "__stop__":
                break
            self._busy.set()
            try:
                self.run_fn(
                    self.store,
                    job_id,
                    interpreter=self.interpreter,
                    repo_root=self.repo_root,
                    timeout_s=self.timeout_s,
                    max_result_bytes=self.max_result_bytes,
                )
            finally:
                self._busy.clear()
                self.store.expire_old_runs()
