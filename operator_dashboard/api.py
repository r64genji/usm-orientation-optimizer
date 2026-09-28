from __future__ import annotations

import os
import subprocess
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from operator_dashboard.contracts import (
    DEFAULT_GROUP_TARGET,
    GUIDE_TEXT,
    HALL_SEAT_CHOICES,
    LOCKED_FLEET,
    DashboardError,
)
from operator_dashboard.geometry import load_restu_overlay
from operator_dashboard.inputs import is_holdout_case, list_cases, validate_run_request
from operator_dashboard.projections import (
    project_bottlenecks,
    project_legs,
    project_map_for_run,
    project_optimizer,
    project_overview,
    project_replay,
    read_optimizer_records,
)
from operator_dashboard.runner import Worker, run_job
from operator_dashboard.store import Store

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
WEB_DIST = PACKAGE_DIR / "web" / "dist"


@dataclass
class Settings:
    auth_token: str
    data_dir: Path
    interpreter: Path
    repo_root: Path
    job_timeout_s: float = 600.0
    max_queue: int = 4
    max_result_bytes: int = 80_000_000
    history_limit: int = 50
    optimizer_dir: Path | None = None
    source_commit: str | None = None
    access_email: str | None = None


def settings_from_env() -> Settings:
    token = os.environ.get("DASHBOARD_AUTH_TOKEN") or ""
    data_dir = Path(os.environ.get("DASHBOARD_DATA_DIR") or (Path.home() / ".local/share/usm-operator-dashboard"))
    interpreter = Path(os.environ.get("DASHBOARD_PYTHON") or sys.executable)
    if not interpreter.exists():
        interpreter = Path(sys.executable)
    optimizer = os.environ.get("DASHBOARD_OPTIMIZER_DIR")
    timeout = float(os.environ.get("DASHBOARD_JOB_TIMEOUT_S") or 600)
    max_queue = int(os.environ.get("DASHBOARD_MAX_QUEUE") or 4)
    max_bytes = int(os.environ.get("DASHBOARD_MAX_RESULT_BYTES") or 80_000_000)
    history = int(os.environ.get("DASHBOARD_HISTORY_LIMIT") or 50)
    return Settings(
        auth_token=token,
        data_dir=data_dir,
        interpreter=interpreter,
        repo_root=REPO_ROOT,
        job_timeout_s=timeout,
        max_queue=max_queue,
        max_result_bytes=max_bytes,
        history_limit=history,
        optimizer_dir=Path(optimizer) if optimizer else None,
        source_commit=os.environ.get("SOURCE_COMMIT") or _git_commit(REPO_ROOT),
        access_email=os.environ.get("DASHBOARD_ACCESS_EMAIL"),
    )


def _git_commit(repo_root: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _authorized(request: Request, settings: Settings) -> bool:
    token = settings.auth_token
    header = request.headers.get("authorization") or ""
    if token and header == f"Bearer {token}":
        return True
    email = request.headers.get("cf-access-authenticated-user-email")
    if settings.access_email and email and email.lower() == settings.access_email.lower():
        return True
    return False


def _reject_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if not origin:
        return
    host = request.headers.get("host")
    parsed = urlparse(origin)
    if host and parsed.netloc != host:
        raise DashboardError("Cross-site run requests are blocked.", status_code=403)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or settings_from_env()
    store = Store(settings.data_dir, max_queue=settings.max_queue, history_limit=settings.history_limit)
    worker = Worker(
        store,
        interpreter=settings.interpreter,
        repo_root=settings.repo_root,
        timeout_s=settings.job_timeout_s,
        max_result_bytes=settings.max_result_bytes,
        run_fn=run_job,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.recover_interrupted_jobs()
        worker.start()
        yield
        worker.stop()

    app = FastAPI(title="USM operator dashboard", lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.worker = worker

    @app.exception_handler(DashboardError)
    async def dashboard_error_handler(_request: Request, err: DashboardError):
        return JSONResponse(err.as_dict(), status_code=err.status_code)

    @app.middleware("http")
    async def auth_gate(request: Request, call_next):
        path = request.url.path
        if path == "/healthz" or path.startswith("/healthz"):
            return await call_next(request)
        if path == "/" or path.startswith("/assets") or path.endswith(".svg") or path.endswith(".css") or path.endswith(".js"):
            return await call_next(request)
        if path.startswith("/api") or path.startswith("/runs"):
            if not settings.auth_token:
                return JSONResponse({"error": True, "message": "DASHBOARD_AUTH_TOKEN is not set"}, status_code=500)
            if not _authorized(request, settings):
                return JSONResponse({"error": True, "message": "Sign in needed"}, status_code=401)
            try:
                _reject_csrf(request)
            except DashboardError as err:
                return JSONResponse(err.as_dict(), status_code=err.status_code)
        return await call_next(request)

    @app.api_route("/healthz", methods=["GET", "HEAD"])
    def healthz() -> dict[str, Any]:
        interpreter_ok = Path(settings.interpreter).exists()
        probe = settings.data_dir / ".healthz"
        writable = False
        try:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            probe.write_text("ok", encoding="utf-8")
            writable = True
            probe.unlink(missing_ok=True)
        except OSError:
            writable = False
        return {
            "status": "ok" if (interpreter_ok and writable) else "error",
            "ok": interpreter_ok and writable,
            "commit": settings.source_commit,
            "interpreter": str(settings.interpreter),
            "interpreter_ok": interpreter_ok,
            "storage_writable": writable,
            "worker": "busy" if worker.busy() else "idle",
        }

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return {
            "fleet": LOCKED_FLEET,
            "group_target_default": DEFAULT_GROUP_TARGET,
            "hall_seats": [
                {"seats": seats, **choice} for seats, choice in HALL_SEAT_CHOICES.items()
            ],
            "guide": GUIDE_TEXT,
            "default_output_mode": "full",
        }

    @app.get("/api/cases")
    def cases() -> dict[str, Any]:
        return {"cases": list_cases()}

    @app.get("/api/runs")
    def runs() -> dict[str, Any]:
        rows = []
        for job in store.list_jobs():
            public = store.public_job(job)
            public["holdout"] = is_holdout_case(job["case_id"])
            rows.append(public)
        return {"runs": rows}

    @app.post("/api/runs", status_code=202)
    async def start_run(request: Request) -> JSONResponse:
        body = await request.json()
        validated = validate_run_request(body)
        job = store.create_job(validated, source_commit=settings.source_commit)
        worker.submit(job["id"])
        public = store.public_job(job)
        public["holdout"] = is_holdout_case(job["case_id"])
        return JSONResponse(public, status_code=202)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        job = store.get_job(run_id)
        if job is None:
            raise DashboardError("Unknown run", field="run_id", status_code=404)
        public = store.public_job(job)
        public["holdout"] = is_holdout_case(job["case_id"])
        return public

    @app.post("/api/runs/{run_id}/rerun-full", status_code=202)
    def rerun_full(run_id: str) -> JSONResponse:
        job = store.get_job(run_id)
        if job is None:
            raise DashboardError("Unknown run", field="run_id", status_code=404)
        request = dict(job["request"])
        request["output_mode"] = "full"
        validated = validate_run_request(request)
        created = store.create_job(validated, source_commit=settings.source_commit)
        worker.submit(created["id"])
        public = store.public_job(created)
        public["holdout"] = is_holdout_case(created["case_id"])
        return JSONResponse(public, status_code=202)

    def _finished_context(run_id: str) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
        job = store.get_job(run_id)
        if job is None:
            raise DashboardError("Unknown run", field="run_id", status_code=404)
        envelope = store.load_result(run_id)
        saved = store.load_input(run_id) or {}
        scenario = saved.get("scenario") if isinstance(saved, dict) else None
        return job, envelope, scenario

    @app.get("/api/runs/{run_id}/overview")
    def get_overview(run_id: str) -> dict[str, Any]:
        job, envelope, scenario = _finished_context(run_id)
        return project_overview(
            run_id,
            envelope,
            case=job["case_id"],
            seed=job["seed"],
            output_mode=job["output_mode"],
            scenario=scenario,
            request=job["request"],
        )

    @app.get("/api/runs/{run_id}/map")
    def get_map(run_id: str) -> dict[str, Any]:
        job, envelope, scenario = _finished_context(run_id)
        overlay = load_restu_overlay(settings.repo_root)
        return project_map_for_run(
            run_id,
            envelope,
            scenario,
            output_mode=job["output_mode"],
            overlay_geojson=overlay,
        )

    @app.get("/api/runs/{run_id}/legs")
    def get_legs(run_id: str) -> dict[str, Any]:
        job, envelope, scenario = _finished_context(run_id)
        return project_legs(run_id, envelope, scenario, output_mode=job["output_mode"])

    @app.get("/api/runs/{run_id}/bottlenecks")
    def get_bottlenecks(run_id: str) -> dict[str, Any]:
        job, envelope, _scenario = _finished_context(run_id)
        return project_bottlenecks(run_id, envelope, output_mode=job["output_mode"])

    @app.get("/api/runs/{run_id}/replay")
    def get_replay(run_id: str) -> dict[str, Any]:
        job, envelope, scenario = _finished_context(run_id)
        return project_replay(run_id, envelope, scenario, output_mode=job["output_mode"])

    @app.get("/api/optimizer")
    def get_optimizer() -> dict[str, Any]:
        records = read_optimizer_records(settings.optimizer_dir)
        return project_optimizer(records)

    @app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
    def favicon() -> JSONResponse:
        return JSONResponse(status_code=204, content={})

    if WEB_DIST.exists():
        assets = WEB_DIST / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.api_route("/", methods=["GET", "HEAD"])
        def index() -> FileResponse:
            return FileResponse(WEB_DIST / "index.html")

        @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
        def spa_fallback(full_path: str) -> FileResponse:
            candidate = WEB_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(WEB_DIST / "index.html")

    return app
