"""Pydantic AI chat model — OpenRouter, built lazily.

The agentic chat runs on OpenRouter (OpenAI-compatible), **separately** from the
summariser's `settings.llm`. The model is constructed on first use (not at
import) to match `config.py`'s deliberate avoidance of import-time LLM creation:
importing `merlin.rag.agent` must not require an API key, so tests can inject a
`TestModel` instead.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from merlin.config import settings

if TYPE_CHECKING:
    from pydantic_ai.models import Model


@lru_cache(maxsize=1)
def build_chat_model() -> Model:
    """Return the OpenRouter chat model (cached after first construction)."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openrouter import OpenRouterProvider

    if not settings.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is required for the chat agent.")
    if not settings.chat_model_name:
        raise ValueError(
            "No chat model configured — set CHAT_MODEL or "
            "OPENROUTER_MODEL_DEPLOYMENT."
        )

    provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
    return OpenAIChatModel(settings.chat_model_name, provider=provider)
