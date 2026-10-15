"""LiteLLM provider switch — model selection, the chat thinking level, the
`web_search` tool, and chat cost capture without OpenRouter's /generation.

No network: models are built but never called, chat runs on a scripted
FunctionModel, and the web-search client is a stub.
"""

from __future__ import annotations

from types import SimpleNamespace

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
# Thinking level
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "level,effort",
    [
        ("minimal", "minimal"),
        ("low", "low"),
        ("medium", "medium"),
        ("HIGH", "high"),
    ],
)
def test_thinking_level_maps_to_reasoning_effort(litellm, level, effort):
    from merlin.services.chat import model_settings_from_filters

    assert model_settings_from_filters({"thinking": level}) == {
        "openai_reasoning_effort": effort
    }


def test_thinking_level_ignored_when_invalid_or_unsupported(litellm, monkeypatch):
    from merlin.services.chat import model_settings_from_filters

    assert model_settings_from_filters({"thinking": "max"}) is None
    # No "off": Gemini can't disable thinking, so the floor is "minimal".
    assert model_settings_from_filters({"thinking": "off"}) is None
    assert model_settings_from_filters({}) is None
    assert model_settings_from_filters(None) is None
    monkeypatch.setattr("merlin.config.settings.llm_provider", "openrouter")
    assert model_settings_from_filters({"thinking": "high"}) is None


def test_library_chat_sends_thinking_level(client, monkeypatch, litellm):
    captured: dict = {}
    _patch_model(monkeypatch, _capturing_model(captured))

    resp = client.post("/api/chat", json=_chat_body("hi", {"thinking": "low"}))
    assert resp.status_code == 200
    assert captured["model_settings"].get("openai_reasoning_effort") == "low"


def test_item_chat_sends_thinking_level(client, monkeypatch, litellm):
    monkeypatch.setattr(
        "merlin.services.library.get_item",
        lambda _id: {"id": "item-1", "title": "T", "raw_content": "words"},
    )
    captured: dict = {}
    _patch_model(monkeypatch, _capturing_model(captured))

    resp = client.post(
        "/api/chat",
        json=_chat_body("hi", {"item_id": "item-1", "thinking": "minimal"}),
    )
    assert resp.status_code == 200
    assert captured["model_settings"].get("openai_reasoning_effort") == "minimal"


def test_health_reports_thinking_support(client, monkeypatch):
    assert client.get("/api/health").json()["chat_thinking"] is False
    monkeypatch.setattr("merlin.config.settings.llm_provider", "litellm")
    assert client.get("/api/health").json()["chat_thinking"] is True


# --------------------------------------------------------------------------- #
# web_search tool
# --------------------------------------------------------------------------- #


def test_web_search_offered_only_on_litellm(client, monkeypatch, litellm):
    captured: dict = {}
    _patch_model(monkeypatch, _capturing_model(captured))
    client.post("/api/chat", json=_chat_body("news?"))
    assert "web_search" in captured["tools"]
    assert "web_search" in captured["instructions"]

    monkeypatch.setattr("merlin.config.settings.llm_provider", "openrouter")
    client.post("/api/chat", json=_chat_body("news?"))
    assert "web_search" not in captured["tools"]
    assert "web_search" not in captured["instructions"]
    assert "search_library" in captured["tools"]


def test_item_chat_never_gets_web_search(client, monkeypatch, litellm):
    monkeypatch.setattr(
        "merlin.services.library.get_item",
        lambda _id: {"id": "item-1", "title": "T", "raw_content": "words"},
    )
    captured: dict = {}
    _patch_model(monkeypatch, _capturing_model(captured))
    client.post("/api/chat", json=_chat_body("hi", {"item_id": "item-1"}))
    assert captured["tools"] == []


class _FakeCompletions:
    def __init__(self, response, calls):
        self._response = response
        self._calls = calls

    def create(self, **kwargs):
        self._calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _fake_client(monkeypatch, response):
    calls: list[dict] = []
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=_FakeCompletions(response, calls))
    )
    monkeypatch.setattr("merlin.rag.agent._web_search_client", lambda: fake)
    return calls


def _completion(content: str, grounding=None):
    """A real openai ChatCompletion carrying LiteLLM's grounding passthrough."""
    from openai.types.chat import ChatCompletion

    payload = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 0,
        "model": "gemini-web-search",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    if grounding is not None:
        payload["vertex_ai_grounding_metadata"] = grounding
    return ChatCompletion.model_validate(payload)


class _Ctx:
    def __init__(self):
        from merlin.rag.agent import ChatDeps

        self.deps = ChatDeps()


def test_web_search_returns_answer_and_sources(monkeypatch, litellm):
    from merlin.rag.agent import web_search

    grounding = [
        {
            "webSearchQueries": ["gemini 3.8 release"],
            "groundingChunks": [
                {"web": {"uri": "https://a.example/x", "title": "a.example"}},
                {"web": {"uri": "https://b.example/y", "title": "b.example"}},
                {"web": {"uri": "https://a.example/x", "title": "dup"}},
            ],
        }
    ]
    calls = _fake_client(monkeypatch, _completion("It shipped in May.", grounding))

    ctx = _Ctx()
    out = web_search(ctx, query="When did Gemini 3.8 ship?")  # type: ignore[arg-type]

    assert calls[0]["model"] == "gemini-web-search"
    assert calls[0]["messages"][0]["content"] == "When did Gemini 3.8 ship?"
    assert "It shipped in May." in out
    assert "- a.example: https://a.example/x" in out
    assert "- b.example: https://b.example/y" in out
    assert out.count("https://a.example/x") == 1  # de-duplicated
    # Web results never enter the library Sources list.
    assert ctx.deps.cited == {}


def test_web_search_resolves_vertex_redirects(monkeypatch, litellm):
    """Opaque Vertex redirect links become the real page URLs; an unresolvable
    one is kept as-is, and two links landing on one page collapse to one."""
    from merlin.rag import agent as agent_mod

    redirect = agent_mod._GROUNDING_REDIRECT
    targets = {
        f"{redirect}aaa": "https://docs.python.org/3/whatsnew/3.15.html",
        f"{redirect}bbb": "https://docs.python.org/3/whatsnew/3.15.html",
    }

    def fake_head(url, allow_redirects, timeout):
        assert allow_redirects is False
        if url not in targets:
            raise RuntimeError("timeout")
        return SimpleNamespace(is_redirect=True, headers={"Location": targets[url]})

    monkeypatch.setattr("requests.head", fake_head)
    grounding = [
        {
            "groundingChunks": [
                {"web": {"uri": f"{redirect}aaa", "title": "python.org"}},
                {"web": {"uri": f"{redirect}bbb", "title": "python.org"}},
                {"web": {"uri": f"{redirect}ccc", "title": "blog.example"}},
            ]
        }
    ]
    _fake_client(monkeypatch, _completion("3.15 is out.", grounding))

    out = agent_mod.web_search(_Ctx(), query="q")  # type: ignore[arg-type]
    assert "- python.org: https://docs.python.org/3/whatsnew/3.15.html" in out
    assert out.count("docs.python.org") == 1
    assert f"- blog.example: {redirect}ccc" in out


def test_web_search_without_grounding_metadata(monkeypatch, litellm):
    from merlin.rag.agent import web_search

    _fake_client(monkeypatch, _completion("Plain answer."))
    out = web_search(_Ctx(), query="q")  # type: ignore[arg-type]
    assert "no source links returned" in out
    assert "Plain answer." in out


def test_web_search_failure_is_a_tool_message(monkeypatch, litellm):
    from merlin.rag.agent import web_search

    _fake_client(monkeypatch, RuntimeError("proxy down"))
    out = web_search(_Ctx(), query="q")  # type: ignore[arg-type]
    assert out.startswith("web_search failed")
    assert "proxy down" in out


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
