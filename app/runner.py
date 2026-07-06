"""RunManager: single-concurrency lock, daily quota, provider-readiness gate, run
history, and seeded-sample injection at startup (data-model.md RunManager;
constitution Principle VII; FR-012, FR-013, FR-017).
"""
from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional
from datetime import date

from app.agent.logger import Run
from app.config import Configuration


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

    def start_run(self, goal: str, start_url: str, executor: Callable[[Run], None]) -> Run:
        """Reserve a run slot then execute synchronously.

        Raises RunRejected — never queues — if busy, quota exhausted, or the
        configured provider's API key is missing (FR-012, FR-013, FR-017). The
        provider-readiness check runs before ``executor`` is ever invoked, so a
        missing key fails fast with no browser/LLM call attempted.
        """
        with self._lock:
            self._reset_quota_if_new_day()
            if self.busy:
                raise RunRejected("A run is already in progress")
            if self._runs_started_today >= self.config.daily_run_limit:
                raise RunRejected("Daily run limit reached")
            if not self.provider_ready:
                raise RunRejected(
                    f"Configured provider {self.config.llm_provider!r} has no API key set"
                )
            run = Run.new(goal=goal, start_url=start_url, provider=self.config.llm_provider)
            self._active_run_id = run.run_id
            self._runs_started_today += 1

        try:
            executor(run)
        finally:
            with self._lock:
                self._active_run_id = None
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
