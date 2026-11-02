"""Settings page — runtime-tunable knobs (env defaults + app_state overrides).

Covers the endpoints (read, override, reset, validation), the proxy model list,
and that each knob actually changes behaviour. No network: the proxy's
/v1/models is stubbed and chat runs on a scripted FunctionModel.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def litellm(monkeypatch):
    """Switch the process to the LiteLLM provider (model cache cleared)."""
    from merlin.rag import model as model_mod

    monkeypatch.setattr("merlin.config.settings.llm_provider", "litellm")
    monkeypatch.setattr("merlin.config.settings.litellm_base_url", "http://omv:4000/v1")
    monkeypatch.setattr("merlin.config.settings.litellm_api_key", "sk-merlin")
    monkeypatch.setattr("merlin.config.settings.chat_model", "")
    model_mod.clear_model_cache()
    yield
    model_mod.clear_model_cache()


_PROXY_MODELS = {
    "data": [
        {"id": "gemini-3.8-flash", "mode": "chat", "max_input_tokens": 1_048_576},
        {"id": "gemini-4-argon", "mode": "chat", "max_input_tokens": 2_000_000},
        {"id": "gemini-web-search", "mode": "chat", "max_input_tokens": 1_048_576},
        {"id": "text-embedder", "mode": "embedding"},
    ]
}


@pytest.fixture
def proxy_models(monkeypatch):
    """Stub the proxy's GET /v1/models; records the URL and headers it got."""
    seen: dict = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"], seen["headers"] = url, headers or {}
        return SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: _PROXY_MODELS
        )

    monkeypatch.setattr("merlin.services.app_settings.httpx.get", fake_get)
    return seen


def _knob(page: dict, key: str) -> dict:
    for section in page["sections"]:
        for item in section["settings"]:
            if item["key"] == key:
                return item
    raise KeyError(key)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


def test_get_settings_defaults_come_from_env(client, monkeypatch):
    monkeypatch.setattr("merlin.config.settings.classify_thinking_level", "minimal")
    monkeypatch.setattr("merlin.config.settings.chat_max_requests", 20)

    page = client.get("/api/settings").json()

    assert [s["id"] for s in page["sections"]] == ["thinking", "chat", "models"]
    classify = _knob(page, "classify_thinking")
    assert classify == {
        "key": "classify_thinking",
        "kind": "thinking",
        "value": "minimal",
        "default": "minimal",
        "overridden": False,
        "min": None,
        "max": None,
        "options": ["minimal", "low", "medium", "high"],
    }
    assert _knob(page, "search_step_thinking")["value"] == "low"
    budget = _knob(page, "chat_max_requests")
    assert (budget["value"], budget["min"], budget["max"]) == (20, 1, 50)
    # The derived context window is not a visible knob.
    with pytest.raises(KeyError):
        _knob(page, "chat_context_window")
    assert page["thinking_supported"] is False  # tests default to OpenRouter


def test_override_then_reset(client):
    page = client.patch(
        "/api/settings", json={"summarize_thinking": "HIGH", "chat_max_requests": 7}
    ).json()
    knob = _knob(page, "summarize_thinking")
    assert (knob["value"], knob["overridden"]) == ("high", True)
    assert _knob(page, "chat_max_requests")["value"] == 7

    # It persists across reads, and a null resets just that knob.
    page = client.patch("/api/settings", json={"summarize_thinking": None}).json()
    knob = _knob(page, "summarize_thinking")
    assert knob["overridden"] is False and knob["value"] == knob["default"]
    assert _knob(client.get("/api/settings").json(), "chat_max_requests")["value"] == 7


@pytest.mark.parametrize(
    "patch",
    [
        {"classify_thinking": "max"},
        {"classify_thinking": 3},
        {"chat_max_requests": 0},
        {"chat_max_requests": 51},
        {"chat_max_requests": "ten"},
        {"chat_model": "   "},
        {"nope": "low"},
        {"chat_context_window": 5},
    ],
)
def test_invalid_patch_is_rejected_and_writes_nothing(client, patch):
    resp = client.patch("/api/settings", json={"summarize_thinking": "high", **patch})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_input"
    # All-or-nothing: the valid key in the same patch was not saved either.
    page = client.get("/api/settings").json()
    assert _knob(page, "summarize_thinking")["overridden"] is False


# --------------------------------------------------------------------------- #
# Proxy model list + the chat model's context window
# --------------------------------------------------------------------------- #


def test_models_list_filters_web_search_and_non_chat(client, litellm, proxy_models):
    body = client.get("/api/settings/models").json()
    assert body == {
        "available": True,
        "models": [
            {"id": "gemini-3.8-flash", "context_window": 1_048_576},
            {"id": "gemini-4-argon", "context_window": 2_000_000},
        ],
    }
    assert proxy_models["url"] == "http://omv:4000/v1/models"
    assert proxy_models["headers"] == {"Authorization": "Bearer sk-merlin"}


def test_models_unavailable_off_litellm_or_when_proxy_fails(client, monkeypatch):
    assert client.get("/api/settings/models").json() == {
        "available": False,
        "models": [],
    }

    monkeypatch.setattr("merlin.config.settings.llm_provider", "litellm")
    monkeypatch.setattr("merlin.config.settings.litellm_base_url", "http://omv:4000/v1")

    def boom(*a, **k):
        raise OSError("unreachable")

    monkeypatch.setattr("merlin.services.app_settings.httpx.get", boom)
    assert client.get("/api/settings/models").json()["available"] is False


def test_picking_chat_model_records_its_context_window(
    client, litellm, proxy_models, monkeypatch
):
    from merlin.core import tunables

    monkeypatch.setattr("merlin.config.settings.chat_context_window", 123)
    client.patch("/api/settings", json={"chat_model": "gemini-4-argon"})
    assert tunables.get("chat_context_window") == 2_000_000

    client.patch("/api/settings", json={"chat_model": None})
    assert tunables.get("chat_context_window") == 123  # back to env


# --------------------------------------------------------------------------- #
# Each knob changes behaviour
# --------------------------------------------------------------------------- #


def test_model_and_summarise_level_overrides_reach_the_builders(client, litellm):
    from merlin.knowledge_sources.plugins.youtube.summarizer import VideoSummarizer
    from merlin.rag.model import build_chat_model, build_ingest_model

    client.patch(
        "/api/settings",
        json={
            "chat_model": "gemini-4-argon",
            "ingest_model": "gemini-4-argon",
            "summarize_thinking": "high",
        },
    )
    assert build_chat_model().model_name == "gemini-4-argon"
    ingest = build_ingest_model()
    assert ingest.model_name == "gemini-4-argon"
    assert ingest.settings["openai_reasoning_effort"] == "high"
    # The summarizer resolves its model per call, so a change applies at once.
    summarizer = VideoSummarizer()
    assert summarizer.model.model_name == "gemini-4-argon"
    client.patch("/api/settings", json={"ingest_model": None})
    assert summarizer.model.model_name == "gemini-3.8-flash"


@pytest.mark.parametrize(
    "surface,key",
    [("classify", "classify_thinking"), ("discover", "discover_thinking")],
)
def test_structured_calls_follow_their_override(client, monkeypatch, surface, key):
    from pydantic import BaseModel
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    from merlin.services import classify

    class Out(BaseModel):
        ok: bool

    levels: list = []

    def fake_build(level=None):
        levels.append(level)
        return FunctionModel(lambda m, i: ModelResponse(parts=[TextPart('{"ok":1}')]))

    monkeypatch.setattr("merlin.rag.model.build_ingest_model", fake_build)
    monkeypatch.setattr("merlin.services.usage.record", lambda **k: None)

    client.patch("/api/settings", json={key: "high"})
    classify._run_structured(Out, "sys", "user", surface=surface)
    assert levels == ["high"]


def _search_then_answer_recording(efforts: list):
    from pydantic_ai.messages import ModelRequest, ToolReturnPart
    from pydantic_ai.models.function import DeltaToolCall, FunctionModel

    async def stream_fn(messages, info):
        efforts.append((info.model_settings or {}).get("openai_reasoning_effort"))
        last = messages[-1]
        if isinstance(last, ModelRequest) and any(
            isinstance(p, ToolReturnPart) for p in last.parts
        ):
            yield "answer"
        else:
            yield {
                0: DeltaToolCall(
                    name="search_library",
                    json_args=json.dumps({"query": "moats"}),
                    tool_call_id="call-1",
                )
            }

    return FunctionModel(stream_function=stream_fn)


def test_search_step_level_override(client, monkeypatch, litellm):
    efforts: list = []
    monkeypatch.setattr(
        "merlin.services.chat.build_chat_model",
        lambda: _search_then_answer_recording(efforts),
    )
    client.patch("/api/settings", json={"search_step_thinking": "minimal"})

    body = {
        "id": "conv-1",
        "trigger": "submit-message",
        "messages": [
            {"id": "m1", "role": "user", "parts": [{"type": "text", "text": "moats?"}]}
        ],
        "filters": {"thinking": "medium"},
    }
    assert client.post("/api/chat", json=body).status_code == 200
    assert efforts == ["minimal", "medium"]


def test_search_budget_override(client):
    from merlin.rag import agent

    client.patch("/api/settings", json={"chat_max_requests": 2})
    assert agent._over_budget(SimpleNamespace(run_step=2)) is False
    assert agent._over_budget(SimpleNamespace(run_step=3)) is True


def test_tunables_fall_back_to_env_without_a_db(monkeypatch):
    from merlin.core import tunables

    def broken():
        raise RuntimeError("no db")

    monkeypatch.setattr("merlin.db.engine.get_db", broken)
    monkeypatch.setattr("merlin.config.settings.chat_max_requests", 9)
    assert tunables.overrides() == {}
    assert tunables.get("chat_max_requests") == 9
