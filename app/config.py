"""Runtime configuration loaded only from environment variables / .env (constitution Principle II)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is a declared dependency
    pass

SUPPORTED_PROVIDERS = ("anthropic", "openai")


@dataclass(frozen=True)
class Configuration:
    llm_provider: str
    anthropic_api_key: Optional[str]
    openai_api_key: Optional[str]
    anthropic_model: str
    openai_model: str
    daily_run_limit: int
    max_steps_per_run: int
    openai_base_url: Optional[str] = None
    """Override for the 'openai' provider's endpoint — lets any OpenAI-compatible API
    (DeepSeek, Together.ai, a local vLLM server, ...) be used under LLM_PROVIDER=openai
    without any code change. None uses the OpenAI SDK's own default endpoint."""
    anthropic_base_url: Optional[str] = None
    """Same idea as openai_base_url, but for Anthropic-compatible proxies/gateways."""

    def is_provider_ready(self) -> bool:
        """FR-017: false when the selected provider's API key is missing."""
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return False

    def active_api_key(self) -> Optional[str]:
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        return None

    def active_model(self) -> str:
        return self.anthropic_model if self.llm_provider == "anthropic" else self.openai_model


def load_config(env: Optional[Mapping[str, str]] = None) -> Configuration:
    source = env if env is not None else os.environ

    provider = (source.get("LLM_PROVIDER") or "anthropic").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported LLM_PROVIDER {provider!r}; must be one of {SUPPORTED_PROVIDERS}"
        )

    def _int(name: str, default: int) -> int:
        raw = source.get(name)
        if raw is None or str(raw).strip() == "":
            return default
        return int(raw)

    return Configuration(
        llm_provider=provider,
        anthropic_api_key=(source.get("ANTHROPIC_API_KEY") or None),
        openai_api_key=(source.get("OPENAI_API_KEY") or None),
        anthropic_model=source.get("ANTHROPIC_MODEL") or "claude-sonnet-5",
        openai_model=source.get("OPENAI_MODEL") or "gpt-4o",
        daily_run_limit=_int("DAILY_RUN_LIMIT", 20),
        max_steps_per_run=_int("MAX_STEPS_PER_RUN", 15),
        openai_base_url=(source.get("OPENAI_BASE_URL") or None),
        anthropic_base_url=(source.get("ANTHROPIC_BASE_URL") or None),
    )
