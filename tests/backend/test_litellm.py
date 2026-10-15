"""LiteLLM provider switch — model selection and chat cost capture without
OpenRouter's /generation.

No network: models are built but never called.
"""

from __future__ import annotations

import pytest

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def litellm(monkeypatch):
    """Switch the process to the LiteLLM provider (cached models cleared)."""
    from merlin.rag import model as model_mod

    monkeypatch.setattr("merlin.config.settings.llm_provider", "litellm")
    monkeypatch.setattr("merlin.config.settings.litellm_base_url", "http://omv:4000/v1")
    monkeypatch.setattr("merlin.config.settings.litellm_api_key", "sk-merlin")
    monkeypatch.setattr("merlin.config.settings.chat_model", "")
    model_mod.build_chat_model.cache_clear()
    model_mod.build_ingest_model.cache_clear()
    yield
    model_mod.build_chat_model.cache_clear()
    model_mod.build_ingest_model.cache_clear()


def _chat_body(text: str, filters: dict | None = None) -> dict:
    body = {
        "id": "conv-1",
        "trigger": "submit-message",
        "messages": [
            {"id": "m1", "role": "user", "parts": [{"type": "text", "text": text}]}
        ],
    }
    if filters is not None:
        body["filters"] = filters
    return body


def _capturing_model(captured: dict):
    """A streaming FunctionModel that records what the agent offered it."""
    from pydantic_ai.models.function import FunctionModel

    async def stream_fn(messages, info):
        captured["model_settings"] = dict(info.model_settings or {})
        captured["tools"] = [t.name for t in info.function_tools]
        captured["instructions"] = info.instructions or ""
        yield "ok"

    return FunctionModel(stream_function=stream_fn)


def _patch_model(monkeypatch, model):
    monkeypatch.setattr(
        "merlin.services.chat.build_chat_model", lambda: model, raising=True
    )


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #


def test_litellm_models_use_proxy_and_alias(litellm):
    from merlin.rag.model import build_chat_model, build_ingest_model

    chat = build_chat_model()
    assert chat.model_name == "gemini-3.8-flash"
    assert chat.system == "litellm"
    assert str(chat.client.base_url).startswith("http://omv:4000/v1")
    # Chat has no default effort — the composer picks it per message.
    assert not (chat.settings or {}).get("openai_reasoning_effort")

    ingest = build_ingest_model()
    assert ingest.model_name == "gemini-3.8-flash"
    assert ingest.settings["openai_reasoning_effort"] == "medium"


def test_litellm_requires_base_url(litellm, monkeypatch):
    from merlin.rag.model import build_chat_model

    monkeypatch.setattr("merlin.config.settings.litellm_base_url", "")
    with pytest.raises(ValueError, match="LITELLM_BASE_URL"):
        build_chat_model()


def test_openrouter_stays_the_default():
    from merlin.config import Settings

    s = Settings(_env_file=None)
    assert s.llm_provider == "openrouter"
    assert not s.is_litellm
    assert s.llm_provider_name == "openrouter"


# --------------------------------------------------------------------------- #
# Cost capture
# --------------------------------------------------------------------------- #


def test_chat_turn_on_litellm_skips_openrouter_lookup(monkeypatch, litellm):
    from merlin.services import usage

    def _boom(*_a, **_k):
        raise AssertionError("OpenRouter /generation must not be called")

    monkeypatch.setattr(usage, "fetch_openrouter_costs", _boom)
    recorded: dict = {}
    monkeypatch.setattr(usage, "record", lambda **kw: recorded.update(kw))

    usage.record_chat_turn(
        model="gemini-3.8-flash",
        generation_ids=["chatcmpl-1"],
        input_tokens=100,
        output_tokens=20,
    )
    assert recorded["provider"] == "litellm"
    assert recorded["cost_usd"] is None  # unpriced → "unknown", never fake $0
    assert recorded["input_tokens"] == 100
