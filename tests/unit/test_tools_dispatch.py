import pytest

from app.agent.browser import ElementNotFoundError, NavigationError, NoHistoryError
from app.agent.llm import Action
from app.agent.tools import InvalidActionError, dispatch


class FakeSession:
    """Duck-typed stand-in for BrowserSession so dispatch logic is unit-tested in isolation."""

    def __init__(self):
        self.calls = []
        self.raise_on_click = None
        self.raise_on_navigate = None
        self.raise_on_go_back = None

    def navigate(self, url):
        self.calls.append(("navigate", url))
        if self.raise_on_navigate:
            raise self.raise_on_navigate

    def click(self, agent_id):
        self.calls.append(("click", agent_id))
        if self.raise_on_click:
            raise self.raise_on_click

    def type_text(self, agent_id, text):
        self.calls.append(("type_text", agent_id, text))
        if self.raise_on_click:
            raise self.raise_on_click

    def scroll(self):
        self.calls.append(("scroll",))

    def go_back(self):
        self.calls.append(("go_back",))
        if self.raise_on_go_back:
            raise self.raise_on_go_back


def test_navigate_success():
    session = FakeSession()
    result = dispatch(session, Action(type="navigate", value="https://example.test/"), has_prior_steps=False)
    assert "navigated" in result
    assert session.calls == [("navigate", "https://example.test/")]


def test_navigate_failure_reports_action_result_not_exception():
    session = FakeSession()
    session.raise_on_navigate = NavigationError("boom")
    result = dispatch(session, Action(type="navigate", value="https://bad.test/"), has_prior_steps=False)
    assert "navigation failed" in result


def test_click_missing_target_agent_id_is_invalid():
    session = FakeSession()
    with pytest.raises(InvalidActionError):
        dispatch(session, Action(type="click"), has_prior_steps=True)


def test_click_stale_element_reports_action_result():
    session = FakeSession()
    session.raise_on_click = ElementNotFoundError("gone")
    result = dispatch(session, Action(type="click", target_agent_id=42), has_prior_steps=True)
    assert "element not found" in result


def test_type_text_requires_value_and_target():
    session = FakeSession()
    with pytest.raises(InvalidActionError):
        dispatch(session, Action(type="type_text", target_agent_id=1), has_prior_steps=True)


def test_scroll_read_page_go_back_success():
    session = FakeSession()
    assert "scrolled" in dispatch(session, Action(type="scroll"), has_prior_steps=True)
    assert "re-read" in dispatch(session, Action(type="read_page"), has_prior_steps=True)
    assert "went back" in dispatch(session, Action(type="go_back"), has_prior_steps=True)


def test_go_back_no_history_reports_action_result():
    session = FakeSession()
    session.raise_on_go_back = NoHistoryError("none")
    result = dispatch(session, Action(type="go_back"), has_prior_steps=True)
    assert "cannot go back" in result


def test_finish_requires_prior_steps():
    session = FakeSession()
    with pytest.raises(InvalidActionError):
        dispatch(session, Action(type="finish", finish_summary="done"), has_prior_steps=False)


def test_finish_requires_summary():
    session = FakeSession()
    with pytest.raises(InvalidActionError):
        dispatch(session, Action(type="finish"), has_prior_steps=True)


def test_finish_success_after_prior_steps():
    session = FakeSession()
    result = dispatch(session, Action(type="finish", finish_summary="collected 12 quotes"), has_prior_steps=True)
    assert "finished" in result
    assert "collected 12 quotes" in result
