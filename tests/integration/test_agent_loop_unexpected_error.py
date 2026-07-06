from pathlib import Path

from app.agent.agent import run_agent_loop
from app.agent.logger import Run, RunLogger
from app.config import load_config

FIXTURES = Path(__file__).parent / "fixtures"


def _file_url(name: str) -> str:
    return FIXTURES.joinpath(name).absolute().as_uri()


class _ExplodingLLMClient:
    """Simulates an SDK raising an unexpected error (e.g. an invalid/expired
    visitor-supplied key triggering an auth error deep inside the provider SDK)."""

    def __init__(self):
        from app.agent.llm import adapter_for_provider

        self.adapter = adapter_for_provider("anthropic")

    def decide(self, messages, system_prompt=None):
        raise RuntimeError("401 Unauthorized: invalid API key")


def test_unexpected_llm_error_ends_failed_not_stuck_in_progress(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "MAX_STEPS_PER_RUN": "5"})
    run = Run.new(goal="anything", start_url=_file_url("page1.html"), provider="anthropic")
    logger = RunLogger(run, runs_root=tmp_path)

    run_agent_loop(run, logger, config, llm_client=_ExplodingLLMClient())

    assert run.status == "failed"
    assert "unexpected error" in (run.result_summary or "").lower()
    assert "401" in (run.result_summary or "")

    for name in ("run.json", "log.jsonl", "report.md", "data.json"):
        assert (logger.run_dir / name).exists()
