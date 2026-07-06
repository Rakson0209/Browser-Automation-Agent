"""Provider-agnostic LLM abstraction (constitution Principle IV).

Defines a neutral turn/action representation and vendor adapters that translate it
to/from the Anthropic tool-use and OpenAI function-calling wire formats. The agent
loop (agent.py) only ever imports the neutral types and ``LLMClient`` — never a
vendor SDK type directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from app.config import Configuration

ActionType = Literal[
    "navigate", "click", "type_text", "scroll", "read_page", "go_back", "finish"
]

ACTION_TYPES: tuple = (
    "navigate",
    "click",
    "type_text",
    "scroll",
    "read_page",
    "go_back",
    "finish",
)


# --------------------------------------------------------------------------- #
# Neutral data model (data-model.md: Action, PageSnapshot, ElementSnapshot,
# UserTurn/AssistantTurn/ToolResultsTurn)
# --------------------------------------------------------------------------- #


@dataclass
class ElementSnapshot:
    agent_id: int
    tag: str
    label: str


@dataclass
class PageSnapshot:
    url: str
    title: str
    visible_text_excerpt: str
    elements: List[ElementSnapshot] = field(default_factory=list)


@dataclass
class Action:
    type: ActionType
    target_agent_id: Optional[int] = None
    value: Optional[str] = None
    finish_summary: Optional[str] = None


@dataclass
class UserTurn:
    goal: str
    snapshot: PageSnapshot


@dataclass
class AssistantTurn:
    action: Action
    decision: str
    provider_extra: Optional[Dict[str, Any]] = None
    """Opaque, provider-specific data that MUST be round-tripped back to that same
    provider on the next turn but has no neutral meaning (e.g. DeepSeek's reasoning
    models require their prior `reasoning_content` to be echoed back in "thinking
    mode," or the next call is rejected). Anthropic's adapter never populates this."""


@dataclass
class ToolResultsTurn:
    action_result: str
    snapshot: PageSnapshot


# --------------------------------------------------------------------------- #
# Shared neutral tool schema (contracts/agent-tools.md)
# --------------------------------------------------------------------------- #

_TOOL_NAME = "browser_action"
_TOOL_DESCRIPTION = (
    "Choose the next browser action to take. Exactly one action type per call."
)
_TOOL_PARAMETERS: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": list(ACTION_TYPES)},
        "target_agent_id": {
            "type": "integer",
            "description": "Required for click/type_text: the numbered element to act on.",
        },
        "value": {
            "type": "string",
            "description": "URL for navigate; text to type for type_text.",
        },
        "finish_summary": {
            "type": "string",
            "description": "Required for finish: a summary of what was accomplished.",
        },
        "decision": {
            "type": "string",
            "description": "Brief reasoning for why this action was chosen.",
        },
    },
    "required": ["type", "decision"],
}


def _page_snapshot_text(snapshot: PageSnapshot) -> str:
    lines = [f"URL: {snapshot.url}", f"Title: {snapshot.title}", "", snapshot.visible_text_excerpt, ""]
    if snapshot.elements:
        lines.append("Interactive elements:")
        for el in snapshot.elements:
            lines.append(f"  [{el.agent_id}] <{el.tag}> {el.label}")
    return "\n".join(lines)


def _action_from_tool_input(tool_input: Dict[str, Any]) -> Action:
    return Action(
        type=tool_input["type"],
        target_agent_id=tool_input.get("target_agent_id"),
        value=tool_input.get("value"),
        finish_summary=tool_input.get("finish_summary"),
    )


def _tool_input_from_action(action: Action, decision: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": action.type, "decision": decision}
    if action.target_agent_id is not None:
        payload["target_agent_id"] = action.target_agent_id
    if action.value is not None:
        payload["value"] = action.value
    if action.finish_summary is not None:
        payload["finish_summary"] = action.finish_summary
    return payload


class ProviderAdapter:
    """Base interface both vendor adapters implement."""

    provider_name = "base"

    def tool_schema(self) -> Any:
        raise NotImplementedError

    def build_initial_messages(self, user_turn: UserTurn) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def append_assistant_turn(
        self, messages: List[Dict[str, Any]], turn: AssistantTurn
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def append_tool_results_turn(
        self, messages: List[Dict[str, Any]], turn: ToolResultsTurn
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def parse_response(self, response: Any) -> AssistantTurn:
        raise NotImplementedError


class AnthropicAdapter(ProviderAdapter):
    """Translates neutral turns to/from Anthropic's tool-use format."""

    provider_name = "anthropic"

    def tool_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": _TOOL_NAME,
                "description": _TOOL_DESCRIPTION,
                "input_schema": _TOOL_PARAMETERS,
            }
        ]

    def build_initial_messages(self, user_turn: UserTurn) -> List[Dict[str, Any]]:
        text = f"Goal: {user_turn.goal}\n\n{_page_snapshot_text(user_turn.snapshot)}"
        return [{"role": "user", "content": text}]

    def append_assistant_turn(
        self, messages: List[Dict[str, Any]], turn: AssistantTurn
    ) -> List[Dict[str, Any]]:
        tool_use_id = f"toolu_{len(messages)}"
        messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": _TOOL_NAME,
                        "input": _tool_input_from_action(turn.action, turn.decision),
                    }
                ],
            }
        )
        return messages

    def append_tool_results_turn(
        self, messages: List[Dict[str, Any]], turn: ToolResultsTurn
    ) -> List[Dict[str, Any]]:
        last_tool_use_id = None
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                for block in msg["content"]:
                    if block.get("type") == "tool_use":
                        last_tool_use_id = block["id"]
                break
        result_text = f"{turn.action_result}\n\n{_page_snapshot_text(turn.snapshot)}"
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": last_tool_use_id,
                        "content": result_text,
                    }
                ],
            }
        )
        return messages

    def parse_response(self, response: Any) -> AssistantTurn:
        for block in response.content:
            block_type = block.type if hasattr(block, "type") else block.get("type")
            if block_type == "tool_use":
                tool_input = block.input if hasattr(block, "input") else block.get("input")
                decision = tool_input.get("decision", "")
                return AssistantTurn(action=_action_from_tool_input(tool_input), decision=decision)
        raise ValueError("Anthropic response contained no tool_use block")


class OpenAIAdapter(ProviderAdapter):
    """Translates neutral turns to/from OpenAI's function-calling format."""

    provider_name = "openai"

    def tool_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": _TOOL_NAME,
                    "description": _TOOL_DESCRIPTION,
                    "parameters": _TOOL_PARAMETERS,
                },
            }
        ]

    def build_initial_messages(self, user_turn: UserTurn) -> List[Dict[str, Any]]:
        text = f"Goal: {user_turn.goal}\n\n{_page_snapshot_text(user_turn.snapshot)}"
        return [{"role": "user", "content": text}]

    def append_assistant_turn(
        self, messages: List[Dict[str, Any]], turn: AssistantTurn
    ) -> List[Dict[str, Any]]:
        import json

        call_id = f"call_{len(messages)}"
        message: Dict[str, Any] = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": _TOOL_NAME,
                        "arguments": json.dumps(
                            _tool_input_from_action(turn.action, turn.decision)
                        ),
                    },
                }
            ],
        }
        # DeepSeek's reasoning models (thinking mode) require reasoning_content to be
        # echoed back verbatim on the next turn or the API rejects the request with
        # "The reasoning_content in the thinking mode must be passed back to the API."
        if turn.provider_extra and turn.provider_extra.get("reasoning_content") is not None:
            message["reasoning_content"] = turn.provider_extra["reasoning_content"]
        messages.append(message)
        return messages

    def append_tool_results_turn(
        self, messages: List[Dict[str, Any]], turn: ToolResultsTurn
    ) -> List[Dict[str, Any]]:
        last_call_id = None
        for msg in reversed(messages):
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                last_call_id = msg["tool_calls"][0]["id"]
                break
        result_text = f"{turn.action_result}\n\n{_page_snapshot_text(turn.snapshot)}"
        messages.append(
            {"role": "tool", "tool_call_id": last_call_id, "content": result_text}
        )
        return messages

    def parse_response(self, response: Any) -> AssistantTurn:
        import json

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or message.get("tool_calls")
        if not tool_calls:
            raise ValueError("OpenAI response contained no tool_calls")
        call = tool_calls[0]
        func = call.function if hasattr(call, "function") else call["function"]
        arguments = func.arguments if hasattr(func, "arguments") else func["arguments"]
        tool_input = json.loads(arguments)
        decision = tool_input.get("decision", "")

        # DeepSeek-compatible reasoning models attach a non-standard reasoning_content
        # field to the message; capture it (if present) so it can be echoed back on the
        # next turn (see append_assistant_turn) — required by DeepSeek's thinking mode.
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content is None and isinstance(message, dict):
            reasoning_content = message.get("reasoning_content")
        provider_extra = {"reasoning_content": reasoning_content} if reasoning_content is not None else None

        return AssistantTurn(
            action=_action_from_tool_input(tool_input),
            decision=decision,
            provider_extra=provider_extra,
        )


def adapter_for_provider(provider: str) -> ProviderAdapter:
    if provider == "anthropic":
        return AnthropicAdapter()
    if provider == "openai":
        return OpenAIAdapter()
    raise ValueError(f"Unsupported provider: {provider!r}")


class LLMClient:
    """Facade the agent loop calls; owns the live SDK client for the configured provider."""

    def __init__(self, config: Configuration):
        self.config = config
        self.adapter = adapter_for_provider(config.llm_provider)
        self._sdk_client = None

    def _sdk(self):
        if self._sdk_client is not None:
            return self._sdk_client
        if self.config.llm_provider == "anthropic":
            import anthropic

            self._sdk_client = anthropic.Anthropic(
                api_key=self.config.anthropic_api_key, base_url=self.config.anthropic_base_url
            )
        else:
            import openai

            self._sdk_client = openai.OpenAI(
                api_key=self.config.openai_api_key, base_url=self.config.openai_base_url
            )
        return self._sdk_client

    def decide(
        self, messages: List[Dict[str, Any]], system_prompt: Optional[str] = None
    ) -> AssistantTurn:
        """Send the current message history to the live provider and parse the next Action."""
        if self.config.llm_provider == "anthropic":
            response = self._sdk().messages.create(
                model=self.config.active_model(),
                max_tokens=1024,
                system=system_prompt,
                tools=self.adapter.tool_schema(),
                messages=messages,
            )
        else:
            oa_messages = messages
            if system_prompt:
                oa_messages = [{"role": "system", "content": system_prompt}] + messages
            response = self._sdk().chat.completions.create(
                model=self.config.active_model(),
                tools=self.adapter.tool_schema(),
                messages=oa_messages,
            )
        return self.adapter.parse_response(response)
