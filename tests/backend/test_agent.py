"""Agent + tools layer — the lazy-model invariant and tool behaviour.

These drive the tools directly (and via a scripted model) against the real
migrated temp DB, with no network.
"""

from __future__ import annotations

import asyncio

import pytest


def test_agent_module_imports_without_api_key(monkeypatch):
    """Importing the agent must NOT construct the model (no key required) — the
    model is supplied at run time. Guards config.py's lazy-LLM convention."""
    monkeypatch.setattr("merlin.config.settings.openrouter_api_key", "", raising=False)
    import importlib

    import merlin.rag.agent as agent_mod

    importlib.reload(agent_mod)
    assert agent_mod.agent is not None
    assert agent_mod.item_agent is not None


def test_build_chat_model_requires_key(monkeypatch):
    from merlin.rag import model as model_mod

    model_mod.build_chat_model.cache_clear()
    monkeypatch.setattr("merlin.config.settings.openrouter_api_key", "", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        model_mod.build_chat_model()
    model_mod.build_chat_model.cache_clear()


def test_search_library_tool_accumulates_citations(make_item):
    from pydantic_ai import RunContext  # noqa: F401  (type only)

    from merlin.rag.agent import ChatDeps, search_library

    make_item(title="Moat economics", summary="A deep look at competitive moats.")

    # Minimal RunContext stand-in: the tool only touches ctx.deps.
    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    deps = ChatDeps()
    out = search_library(Ctx(deps), query="moat")  # type: ignore[arg-type]
    assert "Moat economics" in out
    assert len(deps.cited) >= 1


def test_search_library_tool_handles_no_results(make_item):
    from merlin.rag.agent import ChatDeps, search_library

    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    deps = ChatDeps()
    out = search_library(Ctx(deps), query="zzzznonexistentterm")  # type: ignore[arg-type]
    assert "No items" in out
    assert deps.cited == {}


def test_get_item_tool_returns_transcript_excerpt(make_item):
    from merlin.rag.agent import ChatDeps, get_item

    item_id = make_item(
        title="Deep dive",
        summary="Overview.",
        raw_content="UNIQUE_BODY the speaker goes deep on the topic.",
    )

    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    deps = ChatDeps()
    out = get_item(Ctx(deps), item_id)  # type: ignore[arg-type]
    assert "UNIQUE_BODY" in out
    assert item_id in deps.cited


def test_get_item_tool_handles_missing():
    from merlin.rag.agent import ChatDeps, get_item

    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    out = get_item(Ctx(ChatDeps()), "does-not-exist")  # type: ignore[arg-type]
    assert "No item found" in out


def test_browse_and_meta_tools(make_item):
    from merlin.rag.agent import browse_library, list_source_types, list_tags

    make_item(title="One", tags=["ai"], source_type="youtube")
    make_item(title="Two", source_id="x2", tags=["ai", "ml"], source_type="youtube")

    class Ctx:
        def __init__(self, deps):
            from merlin.rag.agent import ChatDeps

            self.deps = ChatDeps()

    out = browse_library(Ctx(None), source_type="youtube")  # type: ignore[arg-type]
    assert "item(s) match" in out
    assert "One" in out and "Two" in out

    # list_tags/list_source_types now take ctx (for the per-turn budget guard).
    assert "ai" in list_tags(Ctx(None))  # type: ignore[arg-type]
    assert "youtube" in list_source_types(Ctx(None))  # type: ignore[arg-type]


def test_full_agent_run_with_scripted_model(make_item):
    """End-to-end agent.run with a streamed FunctionModel: search → answer,
    citations accumulate, no network."""
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    from merlin.rag.agent import ChatDeps, agent

    make_item(title="Scripted moat video", summary="moat discussion")

    def model_fn(messages, info):
        used = any(
            getattr(p, "part_kind", "") == "tool-return"
            for m in messages
            for p in getattr(m, "parts", [])
        )
        if used:
            return ModelResponse(parts=[TextPart("Here is what your library says.")])
        return ModelResponse(
            parts=[ToolCallPart("search_library", {"query": "moat"})]
        )

    deps = ChatDeps()

    async def run():
        return await agent.run("moat?", model=FunctionModel(model_fn), deps=deps)

    result = asyncio.run(run())
    assert "library" in result.output.lower()
    assert len(deps.cited) >= 1
