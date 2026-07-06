from pathlib import Path

import pytest

from app.agent.browser import BrowserSession, ElementNotFoundError, NoHistoryError

FIXTURES = Path(__file__).parent / "fixtures"


def _file_url(name: str) -> str:
    return FIXTURES.joinpath(name).absolute().as_uri()


@pytest.fixture()
def session():
    with BrowserSession(headless=True) as s:
        yield s


def test_visible_elements_are_tagged_and_hidden_ones_excluded(session):
    session.navigate(_file_url("page1.html"))
    snap = session.snapshot()

    labels_by_tag = {(e.tag, e.label) for e in snap.elements}
    assert ("a", "Go to Page 2") in labels_by_tag
    assert ("button", "Click Me") in labels_by_tag

    # hidden button and hidden input must never receive a data-agent-id / appear in the snapshot
    tags_present = [e.tag for e in snap.elements]
    all_labels = " ".join(e.label for e in snap.elements)
    assert "Hidden Button" not in all_labels
    assert "secret" not in all_labels
    assert len(snap.elements) == len({e.agent_id for e in snap.elements}), "agent_id values must be unique"


def test_click_by_agent_id_navigates_to_linked_page(session):
    session.navigate(_file_url("page1.html"))
    snap = session.snapshot()
    link = next(e for e in snap.elements if e.label == "Go to Page 2")

    session.click(link.agent_id)
    assert "page2.html" in session.snapshot().url


def test_type_text_by_agent_id_fills_input(session):
    session.navigate(_file_url("page1.html"))
    snap = session.snapshot()
    text_input = next(e for e in snap.elements if e.tag == "input" and "Type here" in e.label)

    session.type_text(text_input.agent_id, "hello world")
    # re-observe: value should be reflected as the field's accessible label/placeholder is unchanged,
    # so assert via evaluate instead
    value = session._page.eval_on_selector(f"[data-agent-id='{text_input.agent_id}']", "el => el.value")
    assert value == "hello world"


def test_stale_agent_id_raises_element_not_found(session):
    session.navigate(_file_url("page1.html"))
    session.snapshot()  # tags elements 1..N
    with pytest.raises(ElementNotFoundError):
        session.click(9999)


def test_go_back_with_no_history_raises(session):
    session.navigate(_file_url("page1.html"))
    with pytest.raises(NoHistoryError):
        session.go_back()


def test_go_back_after_navigation_returns_to_previous_page(session):
    session.navigate(_file_url("page1.html"))
    session.navigate(_file_url("page2.html"))
    session.go_back()
    assert "page1.html" in session.snapshot().url


def test_login_form_detection(session):
    session.navigate(_file_url("login.html"))
    assert session.has_login_form() is True

    session.navigate(_file_url("page1.html"))
    assert session.has_login_form() is False
