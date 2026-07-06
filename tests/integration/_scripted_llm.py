"""Test-only stand-in for LLMClient that returns a pre-scripted sequence of decisions.

Lets the agent-loop tests (T021-T024) exercise the real Playwright browser and the
real dispatch/logging machinery end-to-end, offline, without depending on a live LLM
API call (constitution Principle III: integration tests must not depend on external
services being reachable).
"""
from app.agent.llm import AssistantTurn, adapter_for_provider


class ScriptedLLMClient:
    def __init__(self, script, provider="anthropic"):
        self.adapter = adapter_for_provider(provider)
        self._script = list(script)
        self._calls = 0

    def decide(self, messages, system_prompt=None) -> AssistantTurn:
        if self._calls >= len(self._script):
            raise AssertionError("ScriptedLLMClient script exhausted before agent loop finished")
        turn = self._script[self._calls]
        self._calls += 1
        return turn
