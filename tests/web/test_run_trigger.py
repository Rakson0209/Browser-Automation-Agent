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


def test_custom_key_accepted_even_when_server_provider_not_ready(tmp_path, monkeypatch):
    # Prevent the background thread from touching a real browser/network — this test is
    # only about the trigger/reservation logic, not full execution (Principle III).
    monkeypatch.setattr("app.runner.run_agent_loop", lambda run, logger, config: None)

    # Server has no key at all — only a visitor-supplied "bring your own key" should work.
    config = load_config({"LLM_PROVIDER": "anthropic", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app, follow_redirects=False)

    response = client.post(
        "/run",
        data={
            "goal": "g",
            "start_url": "https://example.test/",
            "llm_source": "custom",
            "llm_provider": "openai",
            "llm_api_key": "sk-visitor-key",
        },
    )
    assert response.status_code == 303  # accepted, not rejected — proves the custom
    # key bypassed the server-provider-not-ready rejection that would otherwise apply
    assert "/runs/" in response.headers["location"]


def test_custom_key_missing_value_is_rejected_with_400(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.post(
        "/run",
        data={
            "goal": "g",
            "start_url": "https://example.test/",
            "llm_source": "custom",
            "llm_provider": "openai",
            "llm_api_key": "",
        },
    )
    assert response.status_code == 400
    assert app.state.manager.list_runs() == []


def test_custom_key_invalid_provider_is_rejected_with_400(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.post(
        "/run",
        data={
            "goal": "g",
            "start_url": "https://example.test/",
            "llm_source": "custom",
            "llm_provider": "gemini",
            "llm_api_key": "sk-visitor",
        },
    )
    assert response.status_code == 400
    assert app.state.manager.list_runs() == []


def test_custom_key_with_deepseek_base_url_and_model_reaches_the_agent_loop(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.runner.run_agent_loop",
        lambda run, logger, config: captured.update(
            base_url=config.openai_base_url, model=config.active_model()
        ),
    )

    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app, follow_redirects=False)

    response = client.post(
        "/run",
        data={
            "goal": "g",
            "start_url": "https://example.test/",
            "llm_source": "custom",
            "llm_provider": "openai",
            "llm_api_key": "sk-deepseek-visitor",
            "llm_base_url": "https://api.deepseek.com",
            "llm_model": "deepseek-chat",
        },
    )
    assert response.status_code == 303

    import time

    for _ in range(50):
        if "base_url" in captured:
            break
        time.sleep(0.02)
    assert captured.get("base_url") == "https://api.deepseek.com"
    assert captured.get("model") == "deepseek-chat"


def test_custom_key_with_localhost_base_url_is_rejected(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.post(
        "/run",
        data={
            "goal": "g",
            "start_url": "https://example.test/",
            "llm_source": "custom",
            "llm_provider": "openai",
            "llm_api_key": "sk-visitor",
            "llm_base_url": "http://localhost:11434",
        },
    )
    assert response.status_code == 400
    assert app.state.manager.list_runs() == []


def test_custom_key_with_private_ip_base_url_is_rejected(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.post(
        "/run",
        data={
            "goal": "g",
            "start_url": "https://example.test/",
            "llm_source": "custom",
            "llm_provider": "openai",
            "llm_api_key": "sk-visitor",
            "llm_base_url": "http://192.168.1.10:8080",
        },
    )
    assert response.status_code == 400


def test_default_source_still_uses_server_provider(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.runner.run_agent_loop",
        lambda run, logger, config: captured.update(provider=config.llm_provider),
    )

    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app, follow_redirects=False)

    response = client.post(
        "/run",
        data={"goal": "g", "start_url": "https://example.test/", "llm_source": "default"},
    )
    assert response.status_code == 303

    import time

    for _ in range(50):
        if "provider" in captured:
            break
        time.sleep(0.02)
    assert captured.get("provider") == "anthropic"
