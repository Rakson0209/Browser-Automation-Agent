"""RunLogger: manages the run.json / log.jsonl / screenshots/ / report.md / data.json
artifact lifecycle for a single Run (data-model.md ArtifactSet; constitution Principle V).

Also hosts the ``Run``/``StepRecord`` state containers (data-model.md Run/Step) since they
exist primarily to be serialized to these artifacts.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agent.llm import Action, PageSnapshot

VALID_STATUSES = ("pending", "in_progress", "completed", "failed", "incomplete")


@dataclass
class StepRecord:
    index: int
    observation: PageSnapshot
    decision: str
    action: Action
    action_result: str
    screenshot_path: Optional[str] = None


@dataclass
class Run:
    run_id: str
    goal: str
    start_url: str
    provider: str
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None
    steps: List[StepRecord] = field(default_factory=list)
    result_summary: Optional[str] = None
    is_seeded_sample: bool = False

    @staticmethod
    def new(goal: str, start_url: str, provider: str, run_id: Optional[str] = None) -> "Run":
        return Run(run_id=run_id or uuid.uuid4().hex, goal=goal, start_url=start_url, provider=provider)


def _redact(text: Optional[str], secrets: List[str]) -> Optional[str]:
    if text is None:
        return None
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***REDACTED***")
    return redacted


class RunLogger:
    """Owns the on-disk artifact set for exactly one Run.

    ``secrets`` lists every credential value that must never appear verbatim in any
    artifact (SC-007) — every piece of free-form text passed through this logger is
    scanned and redacted before being written to disk.
    """

    def __init__(self, run: Run, runs_root: Path, secrets: Optional[List[str]] = None):
        self.run = run
        self.run_dir = Path(runs_root) / run.run_id
        self.screenshots_dir = self.run_dir / "screenshots"
        self._secrets = [s for s in (secrets or []) if s]
        self.run_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.run_dir / "log.jsonl"
        if not log_path.exists():
            log_path.touch()

    def screenshot_path_for_step(self, index: int) -> Path:
        return self.screenshots_dir / f"step-{index:02d}.png"

    def mark_in_progress(self) -> None:
        self.run.status = "in_progress"
        self._write_run_json()

    def record_step(self, step: StepRecord) -> None:
        step.decision = _redact(step.decision, self._secrets) or ""
        step.action_result = _redact(step.action_result, self._secrets) or ""
        step.observation.visible_text_excerpt = (
            _redact(step.observation.visible_text_excerpt, self._secrets) or ""
        )
        self.run.steps.append(step)
        self._append_log_line(step)
        self._write_run_json()

    def _append_log_line(self, step: StepRecord) -> None:
        entry = {
            "index": step.index,
            "decision": step.decision,
            "action": asdict(step.action),
            "action_result": step.action_result,
            "observation": {
                "url": step.observation.url,
                "title": step.observation.title,
                "visible_text_excerpt": step.observation.visible_text_excerpt,
                "elements": [asdict(e) for e in step.observation.elements],
            },
            "screenshot_path": step.screenshot_path,
        }
        with open(self.run_dir / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def finish(self, status: str, result_summary: Optional[str] = None) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")
        self.run.status = status
        self.run.result_summary = _redact(result_summary, self._secrets)
        self.run.finished_at = datetime.now(timezone.utc).isoformat()
        self._write_run_json()
        self._write_report_md()
        self._write_data_json()

    def _run_as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run.run_id,
            "goal": self.run.goal,
            "start_url": self.run.start_url,
            "provider": self.run.provider,
            "status": self.run.status,
            "created_at": self.run.created_at,
            "finished_at": self.run.finished_at,
            "result_summary": self.run.result_summary,
            "is_seeded_sample": self.run.is_seeded_sample,
            "steps": [
                {
                    "index": s.index,
                    "decision": s.decision,
                    "action": asdict(s.action),
                    "action_result": s.action_result,
                    "screenshot_path": s.screenshot_path,
                }
                for s in self.run.steps
            ],
        }

    def _write_run_json(self) -> None:
        payload = self._run_as_dict()
        (self.run_dir / "run.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_report_md(self) -> None:
        lines = [
            f"# Run Report: {self.run.goal}",
            "",
            f"- Start URL: {self.run.start_url}",
            f"- Status: **{self.run.status}**",
            f"- Provider: {self.run.provider}",
            f"- Steps taken: {len(self.run.steps)}",
            "",
        ]
        if self.run.result_summary:
            lines += ["## Result", "", self.run.result_summary, ""]
        lines.append("## Steps")
        for s in self.run.steps:
            lines.append(f"\n### Step {s.index}")
            lines.append(f"- Decision: {s.decision}")
            lines.append(f"- Action: `{s.action.type}`")
            lines.append(f"- Result: {s.action_result}")
            if s.screenshot_path:
                lines.append(f"- Screenshot: `{s.screenshot_path}`")
        (self.run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_data_json(self) -> None:
        data = {
            "run_id": self.run.run_id,
            "goal": self.run.goal,
            "start_url": self.run.start_url,
            "status": self.run.status,
            "result_summary": self.run.result_summary,
            "step_count": len(self.run.steps),
        }
        (self.run_dir / "data.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
