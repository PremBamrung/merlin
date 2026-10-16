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


def test_search_library_shows_date_and_coverage(make_item):
    from datetime import datetime

    from merlin.rag.agent import ChatDeps, search_library

    for i in range(3):
        make_item(
            title=f"Moat economics {i}",
            source_id=f"moat{i}",
            summary="A deep look at competitive moats.",
            published_at=datetime(2025, 3, 14),
        )

    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    deps = ChatDeps()
    out = search_library(Ctx(deps), query="moat", limit=2)  # type: ignore[arg-type]
    assert "2025-03-14" in out  # publication date surfaced
    assert "3 matches; showing top 2:" in out  # coverage signal


def test_get_item_shows_metadata(make_item):
    from datetime import datetime

    from merlin.rag.agent import ChatDeps, get_item

    item_id = make_item(title="Dated", published_at=datetime(2024, 12, 1))

    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    out = get_item(Ctx(ChatDeps()), item_id)  # type: ignore[arg-type]
    assert "published: 2024-12-01" in out
    assert "duration: 00:16:59" in out
    assert "views: 12,345" in out


def test_get_item_transcript_paging(make_item):
    from merlin.rag.agent import _TRANSCRIPT_EXCERPT_CHARS, ChatDeps, get_item

    body = "A" * _TRANSCRIPT_EXCERPT_CHARS + "TAIL_MARKER end."
    item_id = make_item(title="Long", raw_content=body)

    class Ctx:
        def __init__(self, deps):
            self.deps = deps

    first = get_item(Ctx(ChatDeps()), item_id)  # type: ignore[arg-type]
    assert "chars remain" in first
    assert f"transcript_offset={_TRANSCRIPT_EXCERPT_CHARS}" in first
    assert "TAIL_MARKER" not in first  # tail is past the first window

    rest = get_item(
        Ctx(ChatDeps()), item_id, transcript_offset=_TRANSCRIPT_EXCERPT_CHARS
    )  # type: ignore[arg-type]
    assert "[continued]" in rest
    assert "TAIL_MARKER" in rest


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
        return ModelResponse(parts=[ToolCallPart("search_library", {"query": "moat"})])

    deps = ChatDeps()

    async def run():
        return await agent.run("moat?", model=FunctionModel(model_fn), deps=deps)

    result = asyncio.run(run())
    assert "library" in result.output.lower()
    assert len(deps.cited) >= 1


# --------------------------------------------------------------------------- #
# Discovery filters, batched reads, date sort/bounds, transcript search.
# --------------------------------------------------------------------------- #


class _Ctx:
    """Minimal RunContext stand-in: the tools only touch ctx.deps."""

    def __init__(self):
        from merlin.rag.agent import ChatDeps

        self.deps = ChatDeps()


def _dt(s: str):
    from datetime import datetime

    return datetime.fromisoformat(s)


def test_browse_library_channel_is_case_insensitive(make_item):
    from merlin.rag.agent import browse_library

    make_item(title="Hoffmann V60", channel="James Hoffmann")
    make_item(title="Hedrick espresso", channel="Lance Hedrick")

    out = browse_library(_Ctx(), channel="james hoffmann")  # type: ignore[arg-type]
    assert "1 item(s) match" in out
    assert "Hoffmann V60" in out and "James Hoffmann" in out
    assert "Hedrick" not in out


def test_browse_library_topic_search_and_dates(make_item):
    from merlin.rag.agent import browse_library
    from merlin.services import topics as topics_service

    old = make_item(title="Old grinder video", published_at=_dt("2024-01-10"))
    new = make_item(title="New grinder video", published_at=_dt("2026-05-02"))
    make_item(title="Unrelated cooking", published_at=_dt("2026-05-03"))
    coffee = topics_service.create_topic("Coffee")
    for iid in (old, new):
        topics_service.set_item_topics(iid, [coffee["id"]], coffee["id"])

    out = browse_library(_Ctx(), topic=coffee["slug"])  # type: ignore[arg-type]
    assert "2 item(s) match" in out and "cooking" not in out

    out = browse_library(_Ctx(), search="grinder", after="2025-01-01")  # type: ignore[arg-type]
    assert "1 item(s) match" in out and "New grinder video" in out

    # `before` is inclusive of the whole day.
    out = browse_library(_Ctx(), search="grinder", before="2024-01-10")  # type: ignore[arg-type]
    assert "Old grinder video" in out and "New grinder" not in out

    assert "Invalid date" in browse_library(_Ctx(), after="last year")  # type: ignore[arg-type]
    assert "Invalid sort" in browse_library(_Ctx(), sort="best")  # type: ignore[arg-type]


def test_list_channels_and_topics(make_item):
    from merlin.rag.agent import list_channels, list_topics
    from merlin.services import topics as topics_service

    assert "no topics" in list_topics(_Ctx())  # type: ignore[arg-type]
    make_item(title="A", channel="James Hoffmann")
    make_item(title="B", channel="James Hoffmann")
    make_item(title="C", channel="Lance Hedrick")
    t = topics_service.create_topic("Coffee")

    channels = list_channels(_Ctx())  # type: ignore[arg-type]
    assert channels.startswith("James Hoffmann (2)")
    assert "Lance Hedrick (1)" in channels
    assert f"{t['slug']}: Coffee (0)" in list_topics(_Ctx())  # type: ignore[arg-type]


def test_get_items_reads_summaries_only(make_item):
    from merlin.rag.agent import _GET_ITEMS_SUMMARY_CHARS, _MAX_GET_ITEMS, get_items

    a = make_item(title="Alpha", summary="Alpha summary.", raw_content="SECRET " * 50)
    b = make_item(title="Beta", summary="x" * (_GET_ITEMS_SUMMARY_CHARS + 500))
    ctx = _Ctx()

    out = get_items(ctx, [a, b, "missing-id", a])  # type: ignore[arg-type]
    assert "Alpha summary." in out and "title: Beta" in out
    assert "SECRET" not in out  # never the transcript
    assert "[transcript: 349 chars" in out
    assert "summary truncated" in out
    assert "missing-id" in out and "no item found" in out
    assert set(ctx.deps.cited) == {a, b}

    ids = [make_item(title=f"N{i}") for i in range(_MAX_GET_ITEMS + 2)]
    out = get_items(_Ctx(), ids)  # type: ignore[arg-type]
    assert "2 more id(s) not read" in out


def test_search_library_shows_tags_and_sorts_by_date(make_item):
    from merlin.rag.agent import search_library

    tags = ["espresso"]
    make_item(title="Espresso basics", tags=tags, published_at=_dt("2023-03-01"))
    make_item(title="Espresso advanced", tags=tags, published_at=_dt("2026-02-01"))
    make_item(title="Espresso undated", tags=tags)

    out = search_library(_Ctx(), query="espresso", sort="newest")  # type: ignore[arg-type]
    assert "tags: espresso" in out
    assert out.index("advanced") < out.index("basics") < out.index("undated")

    out = search_library(_Ctx(), query="espresso", sort="oldest")  # type: ignore[arg-type]
    assert out.index("basics") < out.index("advanced") < out.index("undated")

    out = search_library(_Ctx(), query="espresso", after="2025-01-01")  # type: ignore[arg-type]
    assert "advanced" in out and "basics" not in out and "undated" not in out

    assert "Invalid sort" in search_library(_Ctx(), query="x", sort="top")  # type: ignore[arg-type]
    assert "Invalid date" in search_library(_Ctx(), query="x", before="soon")  # type: ignore[arg-type]


def test_search_library_tag_filter_ignores_case(make_item):
    from merlin.rag.agent import search_library

    make_item(title="Panel review", tags=["oled"])
    out = search_library(_Ctx(), query="panel review", tags=["OLED"])  # type: ignore[arg-type]
    assert "Panel review" in out


def test_search_transcript_finds_passages(make_item):
    from merlin.rag.agent import get_item, search_transcript

    filler = "lorem ipsum dolor sit amet " * 200  # ~5,400 chars
    transcript = (
        filler
        + "the grinder burr alignment matters most here. "
        + filler
        + "burr geometry and grinder retention again. "
        + filler
    )
    iid = make_item(title="Grinder deep dive", raw_content=transcript)
    ctx = _Ctx()

    out = search_transcript(ctx, iid, "grinder burr")  # type: ignore[arg-type]
    assert "2 passage(s)" in out
    assert "burr alignment" in out and "burr geometry" in out
    assert iid in ctx.deps.cited

    # Offsets are usable with get_item's transcript paging.
    offset = int(out.split("@offset ")[1].split(":")[0].replace(",", ""))
    page = get_item(_Ctx(), iid, transcript_offset=offset)  # type: ignore[arg-type]
    assert "burr alignment" in page

    assert "No passage" in search_transcript(_Ctx(), iid, "espresso")  # type: ignore[arg-type]
    assert "No item found" in search_transcript(_Ctx(), "nope", "x")  # type: ignore[arg-type]
    empty = make_item(title="Empty", raw_content="")
    assert "no transcript" in search_transcript(_Ctx(), empty, "x")  # type: ignore[arg-type]


def test_search_library_include_summaries(make_item):
    from merlin.rag.agent import search_library

    make_item(title="Moat economics", summary="Moats keep competitors out.")
    ctx = _Ctx()

    plain = search_library(ctx, query="moat")  # type: ignore[arg-type]
    assert "Moats keep competitors out." not in plain

    out = search_library(ctx, query="moat", include_summaries=True)  # type: ignore[arg-type]
    assert "SUMMARY:\nMoats keep competitors out." in out
    assert "MATCH:" in out and "title: Moat economics" in out
    assert len(ctx.deps.cited) == 1


# --------------------------------------------------------------------------- #
# Message times — each user prompt carries its send time; today's date follows
# the user's timezone.
# --------------------------------------------------------------------------- #


def _ui_user(text: str, ms: int | None = None) -> dict:
    parts: list[dict] = [{"type": "text", "text": text}]
    if ms is not None:
        parts.append({"type": "data-message-time", "data": {"ms": ms}})
    return {"id": text, "role": "user", "parts": parts}


def test_user_message_times_prefers_stamps_then_sent_at():
    from datetime import UTC, datetime

    from merlin.services.chat import user_message_times

    t1 = int(datetime(2026, 10, 12, 0, 28, tzinfo=UTC).timestamp() * 1000)
    t3 = int(datetime(2026, 10, 15, 1, 40, tzinfo=UTC).timestamp() * 1000)
    messages = [
        _ui_user("first", t1),
        {"id": "a", "role": "assistant", "parts": []},
        _ui_user("never stamped"),
        _ui_user("now"),
    ]
    times = user_message_times(messages, t3)
    assert times[0] == datetime(2026, 10, 12, 0, 28, tzinfo=UTC)
    assert times[1] is None  # old, unstamped message — left alone
    assert times[2] == datetime(2026, 10, 15, 1, 40, tzinfo=UTC)

    # A regenerate re-sends an already-stamped last message: its stamp wins.
    assert user_message_times([_ui_user("q", t1)], t3)[0].day == 12
    # No sent_at (old client) → the server clock, never None for the latest.
    assert user_message_times([_ui_user("q")], None)[0] is not None
    assert user_message_times([_ui_user("q")], "junk")[0] is not None


def test_deps_from_request_parses_tz_and_filters():
    from merlin.services.chat import deps_from_request

    deps = deps_from_request(
        {
            "filters": {"tags": ["coffee"]},
            "tz": "America/Toronto",
            "sent_at": 1_760_000_000_000,
            "messages": [_ui_user("hi")],
        }
    )
    assert deps.tags == ["coffee"]
    assert str(deps.tz) == "America/Toronto"
    assert len(deps.user_times) == 1

    assert deps_from_request({"tz": "Not/AZone"}).tz is None
    assert deps_from_request({"tz": 42}).tz is None
    assert deps_from_request(None).user_times == []


def test_agent_stamps_each_user_prompt_once(make_item):
    """Every model request sees each user prompt prefixed with its send time in
    the user's zone — exactly once, even across tool-loop steps — and an old
    unstamped message stays as it was."""
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        ToolCallPart,
        UserPromptPart,
    )
    from pydantic_ai.models.function import FunctionModel

    from merlin.rag.agent import ChatDeps, agent

    make_item(title="Moat video", summary="moat discussion")
    seen: list[list[str]] = []

    def model_fn(messages, info):
        seen.append(
            [
                p.content
                for m in messages
                if isinstance(m, ModelRequest)
                for p in m.parts
                if isinstance(p, UserPromptPart)
            ]
        )
        if len(seen) == 1:
            return ModelResponse(
                parts=[ToolCallPart("search_library", {"query": "moat"})]
            )
        return ModelResponse(parts=[TextPart("done")])

    history = [
        ModelRequest(parts=[UserPromptPart("ancient question")]),
        ModelResponse(parts=[TextPart("ancient answer")]),
        ModelRequest(parts=[UserPromptPart("older question")]),
        ModelResponse(parts=[TextPart("older answer")]),
    ]
    deps = ChatDeps(
        tz=ZoneInfo("America/Toronto"),
        user_times=[
            None,
            datetime(2026, 10, 12, 0, 28, tzinfo=UTC),
            datetime(2026, 10, 15, 1, 40, tzinfo=UTC),
        ],
    )

    async def run():
        return await agent.run(
            "what about now?",
            message_history=history,
            model=FunctionModel(model_fn),
            deps=deps,
        )

    asyncio.run(run())
    assert len(seen) == 2  # search step + answer step
    for prompts in seen:
        assert prompts == [
            "ancient question",
            "[sent Sun 2026-10-11 20:28 EDT]\nolder question",
            "[sent Wed 2026-10-14 21:40 EDT]\nwhat about now?",
        ]


def test_current_date_follows_user_timezone():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from merlin.rag.agent import ChatDeps, current_date

    class Ctx:
        deps = ChatDeps(tz=ZoneInfo("Pacific/Kiritimati"))  # UTC+14

    expected = datetime.now(ZoneInfo("Pacific/Kiritimati")).date().isoformat()
    assert f"Today's date is {expected}." in current_date(Ctx())  # type: ignore[arg-type]
