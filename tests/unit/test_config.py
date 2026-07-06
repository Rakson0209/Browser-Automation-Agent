from app.config import load_config


def test_defaults_when_only_provider_and_key_set():
    cfg = load_config({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-test"})
    assert cfg.llm_provider == "anthropic"
    assert cfg.daily_run_limit == 20
    assert cfg.max_steps_per_run == 15
    assert cfg.is_provider_ready() is True


def test_missing_key_makes_provider_not_ready():
    cfg = load_config({"LLM_PROVIDER": "openai"})
    assert cfg.openai_api_key is None
    assert cfg.is_provider_ready() is False


def test_wrong_provider_key_present_does_not_help():
    cfg = load_config({"LLM_PROVIDER": "openai", "ANTHROPIC_API_KEY": "sk-test"})
    assert cfg.is_provider_ready() is False


def test_invalid_provider_raises():
    try:
        load_config({"LLM_PROVIDER": "gemini"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_active_api_key_and_model_follow_provider():
    cfg = load_config(
        {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-openai",
            "OPENAI_MODEL": "gpt-4o-mini",
        }
    )
    assert cfg.active_api_key() == "sk-openai"
    assert cfg.active_model() == "gpt-4o-mini"


def test_custom_limits_are_parsed_as_int():
    cfg = load_config(
        {
            "LLM_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": "sk-test",
            "DAILY_RUN_LIMIT": "5",
            "MAX_STEPS_PER_RUN": "8",
        }
    )
    assert cfg.daily_run_limit == 5
    assert cfg.max_steps_per_run == 8


def test_openai_base_url_defaults_to_none():
    cfg = load_config({"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"})
    assert cfg.openai_base_url is None


def test_openai_base_url_can_target_an_openai_compatible_endpoint():
    """e.g. DeepSeek, Together.ai, or a local vLLM server — anything speaking the
    OpenAI chat-completions wire format can be used under LLM_PROVIDER=openai."""
    cfg = load_config(
        {
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "sk-deepseek-test",
            "OPENAI_BASE_URL": "https://api.deepseek.com",
            "OPENAI_MODEL": "deepseek-chat",
        }
    )
    assert cfg.openai_base_url == "https://api.deepseek.com"
    assert cfg.active_model() == "deepseek-chat"
    assert cfg.is_provider_ready() is True
