from pathlib import Path

from app.agent.agent import run_agent_loop
from app.agent.llm import Action, AssistantTurn
from app.agent.logger import Run, RunLogger
from app.config import load_config
from tests.integration._scripted_llm import ScriptedLLMClient

FIXTURES = Path(__file__).parent / "fixtures"


def _file_url(name: str) -> str:
    return FIXTURES.joinpath(name).absolute().as_uri()


def test_step_limit_reached_without_finish_ends_incomplete(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "MAX_STEPS_PER_RUN": "3"})
    run = Run.new(goal="never finishes", start_url=_file_url("page1.html"), provider="anthropic")
    logger = RunLogger(run, runs_root=tmp_path)

    # Agent keeps re-reading the page and never calls finish
    script = [
        AssistantTurn(action=Action(type="read_page"), decision="still looking")
        for _ in range(3)
    ]
    client = ScriptedLLMClient(script)

    run_agent_loop(run, logger, config, llm_client=client)

    assert run.status == "incomplete"
    assert len(run.steps) == 3
    assert "step limit" in (run.result_summary or "").lower() or "steps" in (run.result_summary or "").lower()

    for name in ("run.json", "log.jsonl", "report.md", "data.json"):
        assert (logger.run_dir / name).exists()
