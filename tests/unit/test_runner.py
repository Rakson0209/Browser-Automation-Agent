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


def test_custom_key_allows_run_even_when_server_provider_not_ready(tmp_path):
    # Server has no configured key at all.
    config = load_config({"LLM_PROVIDER": "anthropic", "DAILY_RUN_LIMIT": "3"})
    manager = RunManager(config=config, runs_root=tmp_path / "runs")
    assert manager.provider_ready is False

    reserved = manager._reserve(
        "goal", "https://example.test/", override_provider="openai", override_api_key="sk-visitor"
    )
    assert reserved.provider == "openai"
    manager._release()


def test_custom_key_missing_is_rejected(tmp_path):
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    try:
        manager._reserve("goal", "https://example.test/", override_provider="openai", override_api_key="")
        assert False, "expected RunRejected"
    except RunRejected as exc:
        assert "custom api key" in str(exc).lower()


def test_custom_key_unsupported_provider_is_rejected(tmp_path):
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    try:
        manager._reserve("goal", "https://example.test/", override_provider="gemini", override_api_key="sk-x")
        assert False, "expected RunRejected"
    except RunRejected as exc:
        assert "unsupported" in str(exc).lower()


def test_executor_with_override_never_touches_server_config_object(tmp_path):
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    executor = manager._make_executor(override_provider="openai", override_api_key="sk-visitor")

    captured_configs = []
    import app.runner as runner_module

    original_run_agent_loop = runner_module.run_agent_loop

    def spy(run, logger, config):
        captured_configs.append(config)

    runner_module.run_agent_loop = spy
    try:
        from app.agent.logger import Run

        run = Run.new(goal="g", start_url="https://example.test/", provider="openai")
        executor(run)
    finally:
        runner_module.run_agent_loop = original_run_agent_loop

    assert len(captured_configs) == 1
    used_config = captured_configs[0]
    assert used_config.llm_provider == "openai"
    assert used_config.openai_api_key == "sk-visitor"
    # The server's own config object must be untouched (still anthropic/its own key)
    assert manager.config.llm_provider == "anthropic"
    assert used_config is not manager.config


def test_executor_with_override_applies_custom_base_url_and_model(tmp_path):
    """e.g. pointing the 'openai' provider at DeepSeek with a specific model."""
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    executor = manager._make_executor(
        override_provider="openai",
        override_api_key="sk-deepseek-visitor",
        override_base_url="https://api.deepseek.com",
        override_model="deepseek-chat",
    )

    captured_configs = []
    import app.runner as runner_module

    original_run_agent_loop = runner_module.run_agent_loop

    def spy(run, logger, config):
        captured_configs.append(config)

    runner_module.run_agent_loop = spy
    try:
        from app.agent.logger import Run

        run = Run.new(goal="g", start_url="https://example.test/", provider="openai")
        executor(run)
    finally:
        runner_module.run_agent_loop = original_run_agent_loop

    used_config = captured_configs[0]
    assert used_config.openai_base_url == "https://api.deepseek.com"
    assert used_config.openai_model == "deepseek-chat"
    assert used_config.active_model() == "deepseek-chat"
    # Server's own config must remain untouched
    assert manager.config.openai_base_url is None


def test_executor_without_override_base_url_or_model_uses_server_defaults(tmp_path):
    manager = RunManager(config=_config(), runs_root=tmp_path / "runs")
    executor = manager._make_executor(override_provider="openai", override_api_key="sk-visitor")

    captured_configs = []
    import app.runner as runner_module

    original_run_agent_loop = runner_module.run_agent_loop

    def spy(run, logger, config):
        captured_configs.append(config)

    runner_module.run_agent_loop = spy
    try:
        from app.agent.logger import Run

        run = Run.new(goal="g", start_url="https://example.test/", provider="openai")
        executor(run)
    finally:
        runner_module.run_agent_loop = original_run_agent_loop

    used_config = captured_configs[0]
    assert used_config.openai_base_url is None
    assert used_config.openai_model == manager.config.openai_model


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
