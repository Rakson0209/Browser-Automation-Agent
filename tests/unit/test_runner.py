import json

from app.config import load_config
from app.runner import RunManager, RunRejected


def _config(**overrides):
    base = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "3"}
    base.update(overrides)
    return load_config(base)


def test_start_run_executes_and_releases_slot(tmp_path):
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    calls = []

    def executor(run):
        calls.append(run.run_id)
        assert manager.busy is True

    run = manager.start_run("goal", "https://example.test/", executor)
    assert calls == [run.run_id]
    assert manager.busy is False
    assert manager.runs_started_today == 1


def test_concurrent_run_is_rejected_not_queued(tmp_path):
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    manager._active_run_id = "already-running"  # simulate an in-progress run

    called = False

    def executor(run):
        nonlocal called
        called = True

    try:
        manager.start_run("goal", "https://example.test/", executor)
        assert False, "expected RunRejected"
    except RunRejected as exc:
        assert "already in progress" in str(exc)
    assert called is False


def test_daily_quota_exhausted_is_rejected(tmp_path):
    manager = RunManager(config=_config(DAILY_RUN_LIMIT="0"), runs_root=tmp_path / "runs")

    called = False

    def executor(run):
        nonlocal called
        called = True

    try:
        manager.start_run("goal", "https://example.test/", executor)
        assert False, "expected RunRejected"
    except RunRejected as exc:
        assert "quota" in str(exc).lower() or "limit" in str(exc).lower()
    assert called is False


def test_provider_not_ready_is_rejected_before_any_execution(tmp_path):
    config = load_config({"LLM_PROVIDER": "openai", "DAILY_RUN_LIMIT": "3"})  # no OPENAI_API_KEY
    manager = RunManager(config=config, runs_root=tmp_path / "runs")

    called = False

    def executor(run):
        nonlocal called
        called = True

    try:
        manager.start_run("goal", "https://example.test/", executor)
        assert False, "expected RunRejected"
    except RunRejected as exc:
        assert "api key" in str(exc).lower()
    assert called is False, "executor (browser/LLM calls) must never run when provider is not ready"


def test_status_reflects_busy_quota_and_provider_ready(tmp_path):
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    status = manager.status()
    assert status["busy"] is False
    assert status["provider_ready"] is True
    assert status["daily_run_limit"] == 3


def test_seeded_sample_is_injected_into_runs_dir(tmp_path):
    samples_root = tmp_path / "samples"
    sample_run_dir = samples_root / "seed-run-1"
    sample_run_dir.mkdir(parents=True)
    (sample_run_dir / "run.json").write_text(
        json.dumps({"run_id": "seed-run-1", "status": "completed", "created_at": "2026-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )

    manager = RunManager(config=_config(), runs_root=tmp_path / "runs", samples_root=samples_root)

    runs = manager.list_runs()
    assert any(r["run_id"] == "seed-run-1" for r in runs)


def test_seeding_is_idempotent_and_does_not_overwrite_existing_run(tmp_path):
    samples_root = tmp_path / "samples"
    sample_run_dir = samples_root / "seed-run-1"
    sample_run_dir.mkdir(parents=True)
    (sample_run_dir / "run.json").write_text(json.dumps({"run_id": "seed-run-1", "status": "completed"}), encoding="utf-8")

    runs_root = tmp_path / "runs"
    RunManager(config=_config(), runs_root=runs_root, samples_root=samples_root)
    # A second RunManager instance (e.g. a restart) must not blow away an already-seeded run
    RunManager(config=_config(), runs_root=runs_root, samples_root=samples_root)

    assert (runs_root / "seed-run-1" / "run.json").exists()
