from fastapi.testclient import TestClient

from app.config import load_config
from app.web.server import create_app


def test_healthz_requires_no_credentials(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "DAILY_RUN_LIMIT": "5"})  # no key at all
    app = create_app(config=config, runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
