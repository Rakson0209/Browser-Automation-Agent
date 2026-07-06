import json
from pathlib import Path

from app.agent.agent import run_agent_loop
from app.agent.llm import Action, AssistantTurn
from app.agent.logger import Run, RunLogger
from app.config import load_config
from tests.integration._scripted_llm import ScriptedLLMClient

FIXTURES = Path(__file__).parent / "fixtures"


def _file_url(name: str) -> str:
    return FIXTURES.joinpath(name).absolute().as_uri()


def test_full_loop_completes_goal_with_consistent_artifacts(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "MAX_STEPS_PER_RUN": "10"})
    run = Run.new(goal="find and follow the link to page 2", start_url=_file_url("page1.html"), provider="anthropic")
    logger = RunLogger(run, runs_root=tmp_path)

    script = [
        AssistantTurn(action=Action(type="click", target_agent_id=1), decision="Click the link to page 2"),
        AssistantTurn(
            action=Action(type="finish", finish_summary="Reached page 2 successfully"),
            decision="Goal achieved: arrived at page 2",
        ),
    ]
    client = ScriptedLLMClient(script)

    run_agent_loop(run, logger, config, llm_client=client)

    assert run.status == "completed"
    run_dir = logger.run_dir
    for name in ("run.json", "log.jsonl", "report.md", "data.json"):
        assert (run_dir / name).exists()
    screenshots = list((run_dir / "screenshots").glob("*.png"))
    assert len(screenshots) == 2

    payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert len(payload["steps"]) == 2
    assert payload["result_summary"] == "Reached page 2 successfully"
