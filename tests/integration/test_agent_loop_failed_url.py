from app.agent.agent import run_agent_loop
from app.agent.logger import Run, RunLogger
from app.config import load_config
from tests.integration._scripted_llm import ScriptedLLMClient


def test_unreachable_start_url_ends_failed_with_diagnostic(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "MAX_STEPS_PER_RUN": "5"})
    bad_url = "https://this-domain-should-not-resolve.invalid/"
    run = Run.new(goal="anything", start_url=bad_url, provider="anthropic")
    logger = RunLogger(run, runs_root=tmp_path)

    # The LLM must never even be consulted — navigation fails before any decision is requested.
    client = ScriptedLLMClient(script=[])

    run_agent_loop(run, logger, config, llm_client=client)

    assert run.status == "failed"
    assert run.result_summary
    assert len(run.steps) == 0

    for name in ("run.json", "log.jsonl", "report.md", "data.json"):
        assert (logger.run_dir / name).exists()
