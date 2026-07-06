import json

from app.agent.llm import Action, PageSnapshot
from app.agent.logger import Run, RunLogger, StepRecord

SECRET = "sk-super-secret-test-key"


def _make_logger(tmp_path, with_secret=True):
    run = Run.new(goal="collect quotes", start_url="https://example.test/", provider="anthropic")
    secrets = [SECRET] if with_secret else []
    return RunLogger(run, runs_root=tmp_path, secrets=secrets), run


def _artifact_paths(run_dir):
    return {
        "run.json": run_dir / "run.json",
        "log.jsonl": run_dir / "log.jsonl",
        "report.md": run_dir / "report.md",
        "data.json": run_dir / "data.json",
    }


def _add_step(logger, index=1, decision="looking", action_result="ok", secret_in_result=False):
    result = f"observed {SECRET}" if secret_in_result else action_result
    step = StepRecord(
        index=index,
        observation=PageSnapshot(url="https://example.test/", title="Example", visible_text_excerpt="hi"),
        decision=decision,
        action=Action(type="read_page"),
        action_result=result,
        screenshot_path=str(logger.screenshot_path_for_step(index)),
    )
    logger.screenshot_path_for_step(index).parent.mkdir(parents=True, exist_ok=True)
    logger.screenshot_path_for_step(index).write_bytes(b"fake-png-bytes")
    logger.record_step(step)


def test_all_five_artifacts_exist_for_completed_run(tmp_path):
    logger, run = _make_logger(tmp_path)
    logger.mark_in_progress()
    _add_step(logger)
    logger.finish(status="completed", result_summary="collected 12 quotes")

    paths = _artifact_paths(logger.run_dir)
    for name, path in paths.items():
        assert path.exists(), f"{name} missing"
    screenshots = list(logger.screenshots_dir.glob("*.png"))
    assert len(screenshots) == 1


def test_all_five_artifacts_exist_for_failed_run(tmp_path):
    logger, run = _make_logger(tmp_path)
    logger.mark_in_progress()
    logger.finish(status="failed", result_summary="start URL unreachable")
    for path in _artifact_paths(logger.run_dir).values():
        assert path.exists()


def test_all_five_artifacts_exist_for_incomplete_run(tmp_path):
    logger, run = _make_logger(tmp_path)
    logger.mark_in_progress()
    _add_step(logger)
    logger.finish(status="incomplete", result_summary=None)
    for path in _artifact_paths(logger.run_dir).values():
        assert path.exists()


def test_run_json_is_internally_consistent_with_steps(tmp_path):
    logger, run = _make_logger(tmp_path)
    logger.mark_in_progress()
    _add_step(logger, index=1)
    _add_step(logger, index=2)
    logger.finish(status="completed", result_summary="done")

    payload = json.loads((logger.run_dir / "run.json").read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert len(payload["steps"]) == 2
    assert payload["steps"][0]["index"] == 1
    assert payload["steps"][1]["index"] == 2


def test_no_artifact_ever_contains_the_configured_secret(tmp_path):
    """SC-007: zero secrets ever appear in any run artifact."""
    logger, run = _make_logger(tmp_path, with_secret=True)
    logger.mark_in_progress()
    _add_step(logger, index=1, decision=f"my key is {SECRET}", secret_in_result=True)
    logger.finish(status="completed", result_summary=f"succeeded using {SECRET}")

    for path in _artifact_paths(logger.run_dir).values():
        content = path.read_text(encoding="utf-8")
        assert SECRET not in content, f"secret leaked into {path.name}"
        assert "REDACTED" in content or SECRET not in content
