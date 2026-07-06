import json

from fastapi.testclient import TestClient

from app.config import load_config
from app.web.server import create_app


def _config():
    return load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "DAILY_RUN_LIMIT": "5"})


def test_fresh_instance_lists_seeded_sample_run(tmp_path):
    samples_root = tmp_path / "samples"
    sample_dir = samples_root / "seed-1"
    sample_dir.mkdir(parents=True)
    (sample_dir / "run.json").write_text(
        json.dumps({"run_id": "seed-1", "goal": "seed goal", "status": "completed", "created_at": "2026-01-01T00:00:00+00:00", "is_seeded_sample": True}),
        encoding="utf-8",
    )

    app = create_app(config=_config(), runs_root=tmp_path / "runs", samples_root=samples_root)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "seed goal" in response.text


def test_preset_buttons_render_with_data_attributes_not_inline_onclick(tmp_path):
    from app.tasks import PRESETS

    app = create_app(
        config=_config(), runs_root=tmp_path / "runs", samples_root=None, presets=list(PRESETS)
    )
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    for preset in PRESETS:
        assert f'data-goal="{preset.goal}"' in response.text
        assert f'data-start-url="{preset.start_url}"' in response.text
    assert "onclick=" not in response.text
    assert "addEventListener" in response.text
