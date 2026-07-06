"""Provider-agnostic observe -> decide -> act loop (constitution Principle IV, FR-001/002).

``run_agent_loop`` drives one Run to completion, writing every step's artifacts via
``RunLogger`` as it goes so a crash mid-run still leaves a partial, honest artifact
set behind rather than nothing (constitution Principle V).
"""
from __future__ import annotations

from typing import Optional

from app.agent.browser import BrowserSession, NavigationError
from app.agent.llm import LLMClient, ToolResultsTurn, UserTurn
from app.agent.logger import Run, RunLogger, StepRecord
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import InvalidActionError, dispatch
from app.config import Configuration


def run_agent_loop(
    run: Run,
    logger: RunLogger,
    config: Configuration,
    llm_client: Optional[LLMClient] = None,
) -> None:
    """Execute the full observe->decide->act loop for ``run``.

    On return, ``run.status`` is one of completed/failed/incomplete and
    ``logger.finish(...)`` has already been called — the caller never needs to
    finalize the run itself.
    """
    logger.mark_in_progress()
    client = llm_client if llm_client is not None else LLMClient(config)
    adapter = client.adapter

    try:
        with BrowserSession(headless=True) as session:
            try:
                session.navigate(run.start_url)
            except NavigationError as exc:
                logger.finish(status="failed", result_summary=f"Could not reach start URL: {exc}")
                return

            if session.has_login_form():
                logger.finish(
                    status="failed",
                    result_summary=(
                        "Start page requires login; automation is restricted to "
                        "public, no-login pages."
                    ),
                )
                return

            snapshot = session.snapshot()
            messages = adapter.build_initial_messages(UserTurn(goal=run.goal, snapshot=snapshot))

            step_index = 0
            while step_index < config.max_steps_per_run:
                step_index += 1
                has_prior_steps = len(logger.run.steps) > 0

                assistant_turn = client.decide(messages, system_prompt=SYSTEM_PROMPT)
                messages = adapter.append_assistant_turn(messages, assistant_turn)

                action_valid = True
                try:
                    action_result = dispatch(
                        session, assistant_turn.action, has_prior_steps=has_prior_steps
                    )
                except InvalidActionError as exc:
                    action_result = f"invalid action: {exc}"
                    action_valid = False

                login_detected = session.has_login_form()
                new_snapshot = session.snapshot()
                shot_path = logger.screenshot_path_for_step(step_index)
                session.screenshot(shot_path)
                logger.record_step(
                    StepRecord(
                        index=step_index,
                        observation=new_snapshot,
                        decision=assistant_turn.decision,
                        action=assistant_turn.action,
                        action_result=action_result,
                        screenshot_path=str(shot_path.relative_to(logger.run_dir)),
                    )
                )

                if login_detected:
                    logger.finish(
                        status="failed",
                        result_summary=(
                            "Encountered a page requiring login mid-run; stopping "
                            "per the no-login boundary."
                        ),
                    )
                    return

                if action_valid and assistant_turn.action.type == "finish":
                    logger.finish(
                        status="completed",
                        result_summary=assistant_turn.action.finish_summary,
                    )
                    return

                messages = adapter.append_tool_results_turn(
                    messages,
                    ToolResultsTurn(action_result=action_result, snapshot=new_snapshot),
                )

            logger.finish(
                status="incomplete",
                result_summary=(
                    f"Reached the {config.max_steps_per_run}-step limit before the "
                    "goal was completed."
                ),
            )
    except NavigationError as exc:
        logger.finish(status="failed", result_summary=f"Navigation error: {exc}")
