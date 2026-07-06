import json
from types import SimpleNamespace

from app.agent.llm import (
    Action,
    AnthropicAdapter,
    AssistantTurn,
    OpenAIAdapter,
    PageSnapshot,
    ToolResultsTurn,
    UserTurn,
    adapter_for_provider,
)


def _snapshot(url="https://example.test/"):
    return PageSnapshot(url=url, title="Example", visible_text_excerpt="hello", elements=[])


def test_adapter_for_provider_resolution():
    assert isinstance(adapter_for_provider("anthropic"), AnthropicAdapter)
    assert isinstance(adapter_for_provider("openai"), OpenAIAdapter)
    try:
        adapter_for_provider("gemini")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_anthropic_round_trip_preserves_decision_and_action():
    adapter = AnthropicAdapter()
    user_turn = UserTurn(goal="find the pricing page", snapshot=_snapshot())
    messages = adapter.build_initial_messages(user_turn)

    action = Action(type="navigate", value="https://example.test/pricing")
    assistant_turn = AssistantTurn(action=action, decision="Navigating to the pricing link")
    messages = adapter.append_assistant_turn(messages, assistant_turn)

    tool_use_block = messages[-1]["content"][0]
    assert tool_use_block["type"] == "tool_use"
    assert tool_use_block["input"]["decision"] == "Navigating to the pricing link"
    assert tool_use_block["input"]["value"] == "https://example.test/pricing"

    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=tool_use_block["input"])]
    )
    parsed = adapter.parse_response(fake_response)
    assert parsed.decision == assistant_turn.decision
    assert parsed.action.type == "navigate"
    assert parsed.action.value == "https://example.test/pricing"

    tool_results = ToolResultsTurn(action_result="navigated ok", snapshot=_snapshot("https://example.test/pricing"))
    messages = adapter.append_tool_results_turn(messages, tool_results)
    result_block = messages[-1]["content"][0]
    assert result_block["type"] == "tool_result"
    assert result_block["tool_use_id"] == tool_use_block["id"]


def test_openai_round_trip_preserves_decision_and_action():
    adapter = OpenAIAdapter()
    user_turn = UserTurn(goal="find the pricing page", snapshot=_snapshot())
    messages = adapter.build_initial_messages(user_turn)

    action = Action(type="click", target_agent_id=3)
    assistant_turn = AssistantTurn(action=action, decision="Clicking the pricing link")
    messages = adapter.append_assistant_turn(messages, assistant_turn)

    tool_call = messages[-1]["tool_calls"][0]
    arguments = json.loads(tool_call["function"]["arguments"])
    assert arguments["decision"] == "Clicking the pricing link"
    assert arguments["target_agent_id"] == 3

    fake_message = SimpleNamespace(
        tool_calls=[
            SimpleNamespace(
                function=SimpleNamespace(arguments=tool_call["function"]["arguments"])
            )
        ]
    )
    fake_response = SimpleNamespace(choices=[SimpleNamespace(message=fake_message)])
    parsed = adapter.parse_response(fake_response)
    assert parsed.decision == assistant_turn.decision
    assert parsed.action.type == "click"
    assert parsed.action.target_agent_id == 3

    tool_results = ToolResultsTurn(action_result="clicked ok", snapshot=_snapshot())
    messages = adapter.append_tool_results_turn(messages, tool_results)
    assert messages[-1]["role"] == "tool"
    assert messages[-1]["tool_call_id"] == tool_call["id"]


def test_tool_schemas_expose_all_seven_actions():
    anthropic_schema = AnthropicAdapter().tool_schema()[0]["input_schema"]
    openai_schema = OpenAIAdapter().tool_schema()[0]["function"]["parameters"]
    expected = {"navigate", "click", "type_text", "scroll", "read_page", "go_back", "finish"}
    assert set(anthropic_schema["properties"]["type"]["enum"]) == expected
    assert set(openai_schema["properties"]["type"]["enum"]) == expected
