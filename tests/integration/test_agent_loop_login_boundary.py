from pathlib import Path

from app.agent.agent import run_agent_loop
from app.agent.llm import Action, AssistantTurn
from app.agent.logger import Run, RunLogger
from app.config import load_config
from tests.integration._scripted_llm import ScriptedLLMClient

FIXTURES = Path(__file__).parent / "fixtures"


def _file_url(name: str) -> str:
    return FIXTURES.joinpath(name).absolute().as_uri()


def test_start_page_requiring_login_ends_failed_with_no_auth_attempt(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "MAX_STEPS_PER_RUN": "5"})
    run = Run.new(goal="log in and do something", start_url=_file_url("login.html"), provider="anthropic")
    logger = RunLogger(run, runs_root=tmp_path)

    # The LLM must never be consulted — the login boundary is enforced before any decision.
    client = ScriptedLLMClient(script=[])

    run_agent_loop(run, logger, config, llm_client=client)

    assert run.status == "failed"
    assert "login" in (run.result_summary or "").lower()
    assert len(run.steps) == 0  # no action (certainly no credential submission) was ever attempted


def test_login_page_reached_mid_run_stops_the_run(tmp_path):
    config = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test", "MAX_STEPS_PER_RUN": "5"})
    run = Run.new(goal="navigate somewhere then hit a login wall", start_url=_file_url("page1.html"), provider="anthropic")
    logger = RunLogger(run, runs_root=tmp_path)

    script = [
        AssistantTurn(
            action=Action(type="navigate", value=_file_url("login.html")),
            decision="Navigate to the login fixture to simulate hitting a login wall mid-run",
        ),
    ]
    client = ScriptedLLMClient(script)

    run_agent_loop(run, logger, config, llm_client=client)

    assert run.status == "failed"
    assert "login" in (run.result_summary or "").lower()
    assert len(run.steps) == 1  # the navigate step is recorded, but nothing after it
