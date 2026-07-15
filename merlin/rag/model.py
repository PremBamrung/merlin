"""Pydantic AI models — OpenRouter, built lazily.

Every LLM path (agentic chat, summarisation, classification) runs on OpenRouter
(OpenAI-compatible) through Pydantic AI. Models are constructed on first use (not
at import) to match `config.py`'s deliberate avoidance of import-time LLM
creation: importing this module must not require an API key, so tests can inject
a `TestModel` instead.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from merlin.config import settings

if TYPE_CHECKING:
    from pydantic_ai.models import Model


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


@lru_cache(maxsize=1)
def build_chat_model() -> Model:
    """The OpenRouter model for the agentic chat agent (cached after first use)."""
    return _build_openrouter_model(settings.chat_model_name)


@lru_cache(maxsize=1)
def build_ingest_model() -> Model:
    """The OpenRouter model for ingest LLM work — summarise + classify (cached)."""
    return _build_openrouter_model(settings.openrouter_model_deployment)
