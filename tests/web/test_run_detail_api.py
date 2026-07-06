import json

from fastapi.testclient import TestClient

from app.config import load_config
from app.web.server import create_app


def _config():
    return load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})


def _seed_one_run(runs_root):
    run_dir = runs_root / "run-abc"
    (run_dir / "screenshots").mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run-abc",
                "goal": "test goal",
                "start_url": "https://example.test/",
                "status": "completed",
                "created_at": "2026-01-01T00:00:00+00:00",
                "steps": [],
                "result_summary": "done",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text("# Report", encoding="utf-8")
    (run_dir / "data.json").write_text("{}", encoding="utf-8")
    (run_dir / "log.jsonl").write_text("", encoding="utf-8")
    (run_dir / "screenshots" / "step-01.png").write_bytes(b"fake-png")
    return run_dir


def test_run_detail_page_and_json_api(tmp_path):
    runs_root = tmp_path / "runs"
    _seed_one_run(runs_root)
    app = create_app(config=_config(), runs_root=runs_root, samples_root=None)
    client = TestClient(app)

    page = client.get("/runs/run-abc")
    assert page.status_code == 200
    assert "test goal" in page.text

    api = client.get("/api/runs/run-abc")
    assert api.status_code == 200
    assert api.json()["status"] == "completed"

    listing = client.get("/api/runs")
    assert listing.status_code == 200
    assert any(r["run_id"] == "run-abc" for r in listing.json())


def test_unknown_run_id_returns_404(tmp_path):
    app = create_app(config=_config(), runs_root=tmp_path / "runs", samples_root=None)
    client = TestClient(app)

    assert client.get("/runs/does-not-exist").status_code == 404
    assert client.get("/api/runs/does-not-exist").status_code == 404


def test_artifacts_are_served_and_path_traversal_is_rejected(tmp_path):
    runs_root = tmp_path / "runs"
    _seed_one_run(runs_root)
    app = create_app(config=_config(), runs_root=runs_root, samples_root=None)
    client = TestClient(app)

    ok = client.get("/artifacts/run-abc/report.md")
    assert ok.status_code == 200
    assert ok.text == "# Report"

    screenshot = client.get("/artifacts/run-abc/screenshots/step-01.png")
    assert screenshot.status_code == 200

    missing = client.get("/artifacts/run-abc/does-not-exist.txt")
    assert missing.status_code == 404

    traversal = client.get("/artifacts/run-abc/../../secret.txt")
    assert traversal.status_code == 404
