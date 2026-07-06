from fastapi.testclient import TestClient

from app.config import load_config
from app.web.server import create_app


def test_post_run_rejected_while_busy(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    app.state.manager._active_run_id = "already-running"  # simulate an in-progress run
    client = TestClient(app)

    response = client.post("/run", data={"goal": "g", "start_url": "https://example.test/"})
    assert response.status_code == 409
    assert "already in progress" in response.text.lower()
    assert app.state.manager.list_runs() == []


def test_post_run_rejected_when_daily_quota_exhausted(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "0"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.post("/run", data={"goal": "g", "start_url": "https://example.test/"})
    assert response.status_code == 409
    assert "quota" in response.text.lower() or "limit" in response.text.lower()


def test_post_run_rejected_when_provider_api_key_missing(tmp_path):
    config = load_config({"LLM_PROVIDER": "openai", "DAILY_RUN_LIMIT": "5"})  # no OPENAI_API_KEY
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.post("/run", data={"goal": "g", "start_url": "https://example.test/"})
    assert response.status_code == 409
    assert "api key" in response.text.lower()
    assert app.state.manager.list_runs() == []


def test_post_run_rejected_for_malformed_start_url(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.post("/run", data={"goal": "g", "start_url": "not-a-url"})
    assert response.status_code == 400
