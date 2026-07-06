"""RunManager: single-concurrency lock, daily quota, provider-readiness gate, run
history, and seeded-sample injection at startup (data-model.md RunManager;
constitution Principle VII; FR-012, FR-013, FR-017).
"""
from __future__ import annotations

import json
import shutil
import threading
from dataclasses import replace
from pathlib import Path
from typing import Callable, Dict, List, Optional
from datetime import date

from app.agent.agent import run_agent_loop
from app.agent.logger import Run, RunLogger
from app.config import SUPPORTED_PROVIDERS, Configuration


class RunRejected(Exception):
    """Raised when a new run request cannot be accepted — never queued, always rejected."""


class RunManager:
    def __init__(
        self,
        config: Configuration,
        runs_root: Path,
        samples_root: Optional[Path] = None,
    ):
        self.config = config
        self.runs_root = Path(runs_root)
        self.samples_root = Path(samples_root) if samples_root else None
        self._lock = threading.Lock()
        self._active_run_id: Optional[str] = None
        self._runs_started_today = 0
        self._quota_day = date.today()
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self._seed_sample_if_needed()

    def _reset_quota_if_new_day(self) -> None:
        today = date.today()
        if today != self._quota_day:
            self._quota_day = today
            self._runs_started_today = 0

    @property
    def busy(self) -> bool:
        return self._active_run_id is not None

    @property
    def runs_started_today(self) -> int:
        self._reset_quota_if_new_day()
        return self._runs_started_today

    @property
    def provider_ready(self) -> bool:
        return self.config.is_provider_ready()

    def status(self) -> Dict[str, object]:
        return {
            "busy": self.busy,
            "provider": self.config.llm_provider,
            "runs_started_today": self.runs_started_today,
            "daily_run_limit": self.config.daily_run_limit,
            "provider_ready": self.provider_ready,
        }

    def _reserve(
        self,
        goal: str,
        start_url: str,
        override_provider: Optional[str] = None,
        override_api_key: Optional[str] = None,
    ) -> Run:
        """Reserve a run slot. Raises RunRejected — never queues — if busy, quota
        exhausted, or there is no usable LLM credential (FR-012, FR-013, FR-017, FR-018).
        This check always runs before any browser/LLM call is attempted.

        If ``override_provider``/``override_api_key`` are supplied (a visitor's "bring
        your own key" — constitution Principle II), readiness is judged on THAT
        credential instead of the server's own configuration, and the resolved Run
        records the effective provider actually used.
        """
        with self._lock:
            self._reset_quota_if_new_day()
            if self.busy:
                raise RunRejected("A run is already in progress")
            if self._runs_started_today >= self.config.daily_run_limit:
                raise RunRejected("Daily run limit reached")

            if override_provider is not None:
                if override_provider not in SUPPORTED_PROVIDERS:
                    raise RunRejected(f"Unsupported LLM provider: {override_provider!r}")
                if not override_api_key:
                    raise RunRejected("A custom API key is required when using your own key")
                effective_provider = override_provider
            else:
                if not self.provider_ready:
                    raise RunRejected(
                        f"Configured provider {self.config.llm_provider!r} has no API "
                        "key set — supply your own key or ask the operator to configure one"
                    )
                effective_provider = self.config.llm_provider

            run = Run.new(goal=goal, start_url=start_url, provider=effective_provider)
            self._active_run_id = run.run_id
            self._runs_started_today += 1
            return run

    def _release(self) -> None:
        with self._lock:
            self._active_run_id = None

    def _make_executor(
        self,
        override_provider: Optional[str] = None,
        override_api_key: Optional[str] = None,
        override_base_url: Optional[str] = None,
        override_model: Optional[str] = None,
    ) -> Callable[[Run], None]:
        def executor(run: Run) -> None:
            if override_provider is not None:
                # Ephemeral, in-memory-only config for this one run — never persisted,
                # never touches self.config (constitution Principle II).
                overrides = {
                    "llm_provider": override_provider,
                    "anthropic_api_key": override_api_key if override_provider == "anthropic" else None,
                    "openai_api_key": override_api_key if override_provider == "openai" else None,
                }
                if override_base_url:
                    if override_provider == "openai":
                        overrides["openai_base_url"] = override_base_url
                    else:
                        overrides["anthropic_base_url"] = override_base_url
                if override_model:
                    if override_provider == "openai":
                        overrides["openai_model"] = override_model
                    else:
                        overrides["anthropic_model"] = override_model
                effective_config = replace(self.config, **overrides)
                secrets = [override_api_key]
            else:
                effective_config = self.config
                secrets = [self.config.anthropic_api_key, self.config.openai_api_key]

            logger = RunLogger(run, runs_root=self.runs_root, secrets=secrets)
            run_agent_loop(run, logger, effective_config)

        return executor

    def start_run(self, goal: str, start_url: str, executor: Callable[[Run], None]) -> Run:
        """Reserve a run slot then execute synchronously (blocks until ``executor`` returns)."""
        run = self._reserve(goal, start_url)
        try:
            executor(run)
        finally:
            self._release()
        return run

    def trigger_run(
        self,
        goal: str,
        start_url: str,
        override_provider: Optional[str] = None,
        override_api_key: Optional[str] = None,
        override_base_url: Optional[str] = None,
        override_model: Optional[str] = None,
    ) -> Run:
        """Synchronous entry point (used by the CLI): drives the run to completion
        before returning. Raises RunRejected under the same conditions as ``start_run``.
        """
        run = self._reserve(goal, start_url, override_provider, override_api_key)
        executor = self._make_executor(
            override_provider, override_api_key, override_base_url, override_model
        )
        try:
            executor(run)
        finally:
            self._release()
        return run

    def trigger_run_background(
        self,
        goal: str,
        start_url: str,
        override_provider: Optional[str] = None,
        override_api_key: Optional[str] = None,
        override_base_url: Optional[str] = None,
        override_model: Optional[str] = None,
    ) -> Run:
        """Asynchronous entry point (used by the web dashboard): reserves the slot
        synchronously (so rejection is immediate) then runs the agent loop on a
        background thread, returning right away so the caller can redirect to a
        live-polling detail page. Supports "bring your own key" the same way as
        ``trigger_run`` (constitution Principle II), including an optional custom
        endpoint (``override_base_url``) and model (``override_model``) — e.g. to point
        the "openai" provider at DeepSeek's OpenAI-compatible API.
        """
        run = self._reserve(goal, start_url, override_provider, override_api_key)
        executor = self._make_executor(
            override_provider, override_api_key, override_base_url, override_model
        )

        def _target() -> None:
            try:
                executor(run)
            finally:
                self._release()

        threading.Thread(target=_target, daemon=True).start()
        return run

    def list_runs(self) -> List[dict]:
        runs = []
        if self.runs_root.exists():
            for run_dir in self.runs_root.iterdir():
                run_json = run_dir / "run.json"
                if run_json.exists():
                    runs.append(json.loads(run_json.read_text(encoding="utf-8")))
        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return runs

    def get_run(self, run_id: str) -> Optional[dict]:
        run_json = self.runs_root / run_id / "run.json"
        if not run_json.exists():
            return None
        return json.loads(run_json.read_text(encoding="utf-8"))

    def _seed_sample_if_needed(self) -> None:
        """FR-006: guarantee at least one viewable run exists on a fresh deployment."""
        if self.samples_root is None or not self.samples_root.exists():
            return
        for sample_dir in self.samples_root.iterdir():
            if not sample_dir.is_dir():
                continue
            target = self.runs_root / sample_dir.name
            if not target.exists():
                shutil.copytree(sample_dir, target)
