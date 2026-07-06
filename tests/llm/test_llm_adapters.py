import json
from types import SimpleNamespace

from app.agent.llm import (
    Action,
    AnthropicAdapter,
    AssistantTurn,
    LLMClient,
    OpenAIAdapter,
    PageSnapshot,
    ToolResultsTurn,
    UserTurn,
    adapter_for_provider,
)
from app.config import load_config


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


def test_llm_client_passes_custom_base_url_to_openai_sdk():
    """Confirms an OpenAI-compatible endpoint (e.g. DeepSeek) is actually reachable
    through LLM_PROVIDER=openai, not just accepted at the config layer."""
    config = load_config(
        {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-deepseek-test",
            "OPENAI_BASE_URL": "https://api.deepseek.com",
        }
    )
    client = LLMClient(config)
    sdk_client = client._sdk()
    assert str(sdk_client.base_url).rstrip("/") == "https://api.deepseek.com"


def test_llm_client_uses_openai_default_base_url_when_unset():
    config = load_config({"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"})
    client = LLMClient(config)
    sdk_client = client._sdk()
    assert "api.openai.com" in str(sdk_client.base_url)


def test_openai_adapter_captures_deepseek_reasoning_content_from_response():
    """DeepSeek's reasoning models (thinking mode) attach a non-standard
    reasoning_content field to the message; it must be captured so it can be echoed
    back on the next turn, or DeepSeek rejects the follow-up call with:
    '400 ... reasoning_content in the thinking mode must be passed back to the API.'
    """
    adapter = OpenAIAdapter()
    arguments = json.dumps({"type": "read_page", "decision": "Thinking it over..."})
    fake_message = SimpleNamespace(
        tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=arguments))],
        reasoning_content="Let me consider the page contents step by step...",
    )
    fake_response = SimpleNamespace(choices=[SimpleNamespace(message=fake_message)])

    parsed = adapter.parse_response(fake_response)

    assert parsed.provider_extra == {
        "reasoning_content": "Let me consider the page contents step by step..."
    }


def test_openai_adapter_echoes_reasoning_content_back_on_next_turn():
    adapter = OpenAIAdapter()
    messages = adapter.build_initial_messages(
        UserTurn(goal="anything", snapshot=_snapshot())
    )
    turn = AssistantTurn(
        action=Action(type="read_page"),
        decision="Reading the page",
        provider_extra={"reasoning_content": "step-by-step reasoning trace"},
    )

    messages = adapter.append_assistant_turn(messages, turn)

    assert messages[-1]["reasoning_content"] == "step-by-step reasoning trace"


def test_openai_adapter_omits_reasoning_content_when_absent():
    """Plain OpenAI (and non-thinking-mode DeepSeek) responses never set
    reasoning_content; the resulting message must not include the key at all."""
    adapter = OpenAIAdapter()
    messages = adapter.build_initial_messages(
        UserTurn(goal="anything", snapshot=_snapshot())
    )
    turn = AssistantTurn(action=Action(type="read_page"), decision="Reading the page")

    messages = adapter.append_assistant_turn(messages, turn)

    assert "reasoning_content" not in messages[-1]
