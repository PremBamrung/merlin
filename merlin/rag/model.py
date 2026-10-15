"""Pydantic AI models — OpenRouter or the LiteLLM proxy, built lazily.

Every LLM path (agentic chat, summarisation, classification) runs on one
OpenAI-compatible provider through Pydantic AI, picked by `LLM_PROVIDER`:
OpenRouter (default) or the self-hosted LiteLLM proxy (Gemini on Vertex). Models
are constructed on first use (not at import) to match `config.py`'s deliberate
avoidance of import-time LLM creation: importing this module must not require an
API key, so tests can inject a `TestModel` instead.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from merlin.config import settings

if TYPE_CHECKING:
    from pydantic_ai.models import Model


# Chat thinking levels the UI offers → the `reasoning_effort` sent to LiteLLM,
# which maps it onto Gemini's thinking config. There is no "off": Gemini 3.8
# Flash can't disable thinking (even `none` still thinks on a hard question), so
# the floor is "minimal" — the model then thinks only when it has to.
THINKING_EFFORT = {
    "minimal": "minimal",
    "low": "low",
    "medium": "medium",
    "high": "high",
}


def thinking_supported() -> bool:
    """Whether per-message thinking control is available (LiteLLM only)."""
    return settings.is_litellm


def thinking_model_settings(level: str | None) -> dict | None:
    """Per-request model settings for a chat thinking level, or None.

    None (the model's default) for an unknown level or when the provider doesn't
    support the control — an OpenRouter preset decides its own reasoning.
    """
    effort = THINKING_EFFORT.get((level or "").strip().lower())
    if effort is None or not thinking_supported():
        return None
    return {"openai_reasoning_effort": effort}


def _build_openrouter_model(model_name: str) -> Model:
    """Construct an OpenRouter chat model for `model_name` (uncached).

    Asks OpenRouter to bill usage on the response (`extra_body`) so the token
    sub-details (reasoning/cache) are accurate. Note: Pydantic AI does **not**
    surface OpenRouter's per-call cost field, so cost is derived from the pricing
    map (ingest paths) or the /generation endpoint (chat) — this flag only keeps
    the token accounting complete.
    """
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is required.")
    if not model_name:
        raise ValueError("No model configured (OPENROUTER_MODEL_DEPLOYMENT).")

    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    return OpenAIChatModel(
        model_name,
        provider=provider,
        settings=OpenAIChatModelSettings(extra_body={"usage": {"include": True}}),
    )


def _build_litellm_model(
    model_name: str, *, reasoning_effort: str | None = None
) -> Model:
    """Construct a model on the LiteLLM proxy for `model_name` (uncached).

    `reasoning_effort` becomes the model's default; a chat request can override
    it per run via `thinking_model_settings`.
    """
    from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
    from pydantic_ai.providers.litellm import LiteLLMProvider

    if not settings.litellm_base_url:
        raise ValueError("LITELLM_BASE_URL is required when LLM_PROVIDER=litellm.")
    if not model_name:
        raise ValueError("No model configured (LITELLM_MODEL).")

    provider = LiteLLMProvider(
        api_base=settings.litellm_base_url, api_key=settings.litellm_api_key or None
    )
    model_settings = (
        OpenAIChatModelSettings(openai_reasoning_effort=reasoning_effort)
        if reasoning_effort
        else None
    )
    return OpenAIChatModel(model_name, provider=provider, settings=model_settings)


@lru_cache(maxsize=1)
def build_chat_model() -> Model:
    """The model for the agentic chat agent (cached after first use)."""
    if settings.is_litellm:
        return _build_litellm_model(settings.chat_model_name)
    return _build_openrouter_model(settings.chat_model_name)


@lru_cache(maxsize=1)
def build_ingest_model() -> Model:
    """The model for ingest LLM work — summarise + classify (cached)."""
    if settings.is_litellm:
        return _build_litellm_model(
            settings.ingest_model_name,
            reasoning_effort=settings.ingest_thinking_level or None,
        )
    return _build_openrouter_model(settings.ingest_model_name)
