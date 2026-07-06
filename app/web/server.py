"""FastAPI dashboard: trigger, live-progress API, history, health check.

(contracts/web-api.md; FR-005, FR-006, FR-012, FR-013, FR-015, FR-017)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import SUPPORTED_PROVIDERS, Configuration, load_config
from app.runner import RunManager, RunRejected
from app.tasks import PRESETS

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def create_app(
    config: Optional[Configuration] = None,
    runs_root: Optional[Path] = None,
    samples_root: Optional[Path] = None,
    presets: Optional[list] = None,
) -> FastAPI:
    config = config or load_config()
    runs_root = Path(runs_root) if runs_root else Path("app/runs")

    manager = RunManager(config=config, runs_root=runs_root, samples_root=samples_root)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="Browser Automation Agent")
    app.state.manager = manager
    app.state.presets = presets or []

    @app.get("/")
    def index(request: Request):
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "runs": manager.list_runs(),
                "presets": app.state.presets,
                "provider_ready": manager.provider_ready,
                "error": None,
            },
        )

    @app.get("/runs/{run_id}")
    def run_detail(request: Request, run_id: str):
        run = manager.get_run(run_id)
        if run is None:
            return JSONResponse({"error": "run not found"}, status_code=404)
        return templates.TemplateResponse(request, "run.html", {"run": run})

    @app.post("/run")
    def trigger_run(
        request: Request,
        goal: str = Form(...),
        start_url: str = Form(...),
        llm_source: str = Form("default"),
        llm_provider: str = Form(""),
        llm_api_key: str = Form(""),
    ):
        def _error(message: str, status_code: int):
            return templates.TemplateResponse(
                request,
                "index.html",
                {
                    "runs": manager.list_runs(),
                    "presets": app.state.presets,
                    "provider_ready": manager.provider_ready,
                    "error": message,
                },
                status_code=status_code,
            )

        if not _looks_like_url(start_url):
            return _error(f"Invalid start URL: {start_url!r}", 400)

        override_provider: Optional[str] = None
        override_api_key: Optional[str] = None
        if llm_source == "custom":
            if llm_provider not in SUPPORTED_PROVIDERS:
                return _error("Please choose a valid LLM provider for your custom key.", 400)
            if not llm_api_key:
                return _error("Please enter your API key, or switch to the server default.", 400)
            override_provider = llm_provider
            override_api_key = llm_api_key

        try:
            run = manager.trigger_run_background(
                goal, start_url, override_provider=override_provider, override_api_key=override_api_key
            )
        except RunRejected as exc:
            return _error(str(exc), 409)
        return RedirectResponse(url=f"/runs/{run.run_id}", status_code=303)

    @app.get("/api/status")
    def api_status():
        return manager.status()

    @app.get("/api/runs")
    def api_runs():
        return manager.list_runs()

    @app.get("/api/runs/{run_id}")
    def api_run_detail(run_id: str):
        run = manager.get_run(run_id)
        if run is None:
            return JSONResponse({"error": "run not found"}, status_code=404)
        return run

    @app.get("/artifacts/{run_id}/{path:path}")
    def artifacts(run_id: str, path: str):
        run_dir = (manager.runs_root / run_id).resolve()
        target = (run_dir / path).resolve()
        if run_dir not in target.parents and target != run_dir:
            return JSONResponse({"error": "not found"}, status_code=404)
        if not target.exists() or not target.is_file():
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(str(target))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


app = create_app(samples_root=Path("app/samples"), presets=list(PRESETS))
