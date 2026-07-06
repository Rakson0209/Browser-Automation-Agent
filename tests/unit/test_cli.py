import os

from app import cli


class _FakeRun:
    def __init__(self, status="completed", result_summary="done"):
        self.run_id = "fake-run-id"
        self.status = status
        self.result_summary = result_summary


class _FakeManager:
    last_goal = None
    last_start_url = None

    def __init__(self, config, runs_root, samples_root):
        pass

    def trigger_run(self, goal, start_url):
        _FakeManager.last_goal = goal
        _FakeManager.last_start_url = start_url
        return _FakeRun(status="completed")


def test_list_presets_prints_without_triggering_a_run(capsys, monkeypatch):
    monkeypatch.setattr(cli, "RunManager", _FakeManager)
    exit_code = cli.main(["--list-presets"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "quotes_humor" in out
    assert _FakeManager.last_goal is None


def test_preset_dispatches_matching_goal_and_start_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(cli, "RunManager", _FakeManager)

    exit_code = cli.main(["--preset", "quotes_humor"])

    assert exit_code == 0
    assert "quotes.toscrape.com" in _FakeManager.last_start_url


def test_unknown_preset_key_exits_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "RunManager", _FakeManager)
    exit_code = cli.main(["--preset", "does-not-exist"])
    assert exit_code != 0


def test_missing_all_required_args_exits_nonzero(monkeypatch):
    monkeypatch.setattr(cli, "RunManager", _FakeManager)
    exit_code = cli.main([])
    assert exit_code != 0


def test_missing_provider_api_key_is_rejected_with_nonzero_exit(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(cli, "RUNS_ROOT_DEFAULT", tmp_path / "runs")
    monkeypatch.setattr(cli, "SAMPLES_ROOT_DEFAULT", tmp_path / "samples")

    exit_code = cli.main(["--goal", "g", "--start-url", "https://example.test/"])

    assert exit_code != 0
    err = capsys.readouterr().err
    assert "rejected" in err.lower()
