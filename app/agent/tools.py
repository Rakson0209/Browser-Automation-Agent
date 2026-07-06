"""Neutral action schema and dispatch-to-browser logic (contracts/agent-tools.md, FR-002)."""
from __future__ import annotations

from app.agent.browser import (
    BrowserSession,
    ElementNotFoundError,
    NavigationError,
    NoHistoryError,
)
from app.agent.llm import Action


class InvalidActionError(Exception):
    """Raised when an Action is structurally invalid (missing required fields, bad ordering)."""


def dispatch(session: BrowserSession, action: Action, has_prior_steps: bool) -> str:
    """Execute the given neutral Action against the browser session.

    Returns an ``action_result`` string. Every action, regardless of type, MUST produce
    one — including on failure (contracts/agent-tools.md) — so the caller never has to
    special-case a missing result.
    """
    if action.type == "navigate":
        if not action.value:
            raise InvalidActionError("navigate requires 'value' (a URL)")
        try:
            session.navigate(action.value)
        except NavigationError as exc:
            return f"navigation failed: {exc}"
        return f"navigated to {action.value}"

    if action.type == "click":
        if action.target_agent_id is None:
            raise InvalidActionError("click requires 'target_agent_id'")
        try:
            session.click(action.target_agent_id)
        except ElementNotFoundError as exc:
            return f"element not found: {exc}"
        return f"clicked element {action.target_agent_id}"

    if action.type == "type_text":
        if action.target_agent_id is None or action.value is None:
            raise InvalidActionError("type_text requires 'target_agent_id' and 'value'")
        try:
            session.type_text(action.target_agent_id, action.value)
        except ElementNotFoundError as exc:
            return f"element not found: {exc}"
        return f"typed into element {action.target_agent_id}"

    if action.type == "scroll":
        session.scroll()
        return "scrolled"

    if action.type == "read_page":
        return "re-read page"

    if action.type == "go_back":
        try:
            session.go_back()
        except NoHistoryError as exc:
            return f"cannot go back: {exc}"
        return "went back"

    if action.type == "finish":
        if not has_prior_steps:
            raise InvalidActionError(
                "finish is not valid as the first action — at least one prior "
                "observation is required (constitution Principle V)"
            )
        if not action.finish_summary:
            raise InvalidActionError("finish requires 'finish_summary'")
        return f"finished: {action.finish_summary}"

    raise InvalidActionError(f"Unknown action type: {action.type!r}")
