"""Playwright wrapper with numbered-element-snapshot capture (constitution Principle VI).

Every observation tags visible interactive elements with a stable ``data-agent-id``
attribute so the LLM can target them by number instead of a brittle CSS selector.
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from app.agent.llm import ElementSnapshot, PageSnapshot

_SNAPSHOT_SCRIPT = """
() => {
    const selectors = ['a', 'button', 'input', 'textarea', 'select', '[role]'];
    const seen = new Set();
    const results = [];
    let counter = 1;
    for (const el of document.querySelectorAll(selectors.join(','))) {
        if (seen.has(el)) continue;
        seen.add(el);
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const visible = rect.width > 0 && rect.height > 0
            && style.visibility !== 'hidden' && style.display !== 'none';
        if (!visible) continue;
        el.setAttribute('data-agent-id', String(counter));
        const label = (el.innerText || el.value || el.getAttribute('aria-label')
            || el.getAttribute('placeholder') || '').trim().slice(0, 80);
        results.push({ agent_id: counter, tag: el.tagName.toLowerCase(), label: label });
        counter += 1;
    }
    return results;
}
"""


class ElementNotFoundError(Exception):
    """Raised when an action targets a data-agent-id that no longer exists (stale snapshot)."""


class NoHistoryError(Exception):
    """Raised when go_back is requested but there is no previous page in history."""


class NavigationError(Exception):
    """Raised when navigating to a URL fails (unreachable, timeout, DNS error, ...)."""


class BrowserSession:
    """One Playwright browser + page for the lifetime of a single Run."""

    def __init__(self, headless: bool = True):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._page = self._browser.new_page()

    def close(self) -> None:
        try:
            self._browser.close()
        finally:
            self._playwright.stop()

    def __enter__(self) -> "BrowserSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def navigate(self, url: str) -> None:
        try:
            self._page.goto(url, wait_until="load", timeout=15000)
        except Exception as exc:  # Playwright raises its own Error/TimeoutError types
            raise NavigationError(f"Failed to navigate to {url!r}: {exc}") from exc

    def go_back(self) -> None:
        response = self._page.go_back(wait_until="load", timeout=15000)
        if response is None:
            raise NoHistoryError("No previous page in browser history")

    def scroll(self) -> None:
        self._page.mouse.wheel(0, 800)

    def click(self, agent_id: int) -> None:
        selector = f"[data-agent-id='{agent_id}']"
        if self._page.locator(selector).count() == 0:
            raise ElementNotFoundError(f"No element with data-agent-id={agent_id}")
        self._page.click(selector, timeout=5000)

    def type_text(self, agent_id: int, text: str) -> None:
        selector = f"[data-agent-id='{agent_id}']"
        if self._page.locator(selector).count() == 0:
            raise ElementNotFoundError(f"No element with data-agent-id={agent_id}")
        self._page.fill(selector, text, timeout=5000)

    def screenshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(path))

    def snapshot(self) -> PageSnapshot:
        raw_elements = self._page.evaluate(_SNAPSHOT_SCRIPT)
        elements = [
            ElementSnapshot(agent_id=e["agent_id"], tag=e["tag"], label=e["label"])
            for e in raw_elements
        ]
        body_text = self._page.evaluate(
            "() => document.body ? document.body.innerText : ''"
        )
        excerpt = (body_text or "").strip()[:2000]
        return PageSnapshot(
            url=self._page.url,
            title=self._page.title(),
            visible_text_excerpt=excerpt,
            elements=elements,
        )

    def has_login_form(self) -> bool:
        """Best-effort no-login boundary detection (constitution Principle II)."""
        return self._page.locator("input[type='password']").count() > 0
