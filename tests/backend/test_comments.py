"""Top YouTube comments: the yt-dlp fetcher, storage, the API, the summary
grounding and the chat surfaces — real router → service → temp-SQLite path,
with yt-dlp / the LLM stubbed (conftest turns fetching off; tests here turn it
back on where they need it).
"""

from __future__ import annotations

from datetime import UTC, datetime
import time

import pytest

RAW = [
    {"id": "a", "text": "Decent video", "author": "@a", "like_count": 10,
     "parent": "root", "timestamp": 1_700_000_000},
    {"id": "b", "text": "Great point at 3:00", "author": "@b", "like_count": 900,
     "parent": "root"},
    {"id": "b.r", "text": "a reply", "author": "@r", "like_count": 5000,
     "parent": "b"},
    {"id": "c", "text": "Thanks for watching!", "author": "@creator",
     "like_count": 3, "parent": "root", "is_pinned": True,
     "author_is_uploader": True},
    {"id": "d", "text": "   ", "author": "@blank", "like_count": 99_999,
     "parent": "root"},
]  # fmt: skip


def _fake_ytdl(info: dict | Exception, seen: dict | None = None):
    class FakeYDL:
        def __init__(self, opts):
            if seen is not None:
                seen["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            if isinstance(info, Exception):
                raise info
            return info

    return FakeYDL


@pytest.fixture
def comments_on(monkeypatch):
    from merlin.config import settings

    monkeypatch.setattr(settings, "youtube_comments_limit", 20)


@pytest.fixture
def no_cooldown(monkeypatch):
    from merlin.knowledge_sources.plugins.youtube import comments as mod

    monkeypatch.setattr(mod._subtitle_rate_limiter, "in_cooldown", lambda: False)


def _store(item_id: str, comments: list[dict]) -> None:
    from merlin.db.engine import SessionFactory
    from merlin.db.repositories.knowledge import YouTubeCommentRepository

    with SessionFactory() as session:
        YouTubeCommentRepository.replace(session, item_id, comments)
        session.commit()


def _comment(text: str, likes: int = 1, **kw) -> dict:
    return {"comment_id": text[:8], "author": "@v", "text": text,
            "like_count": likes, **kw}  # fmt: skip


# --------------------------------------------------------------------------- #
# Fetcher
# --------------------------------------------------------------------------- #


def test_fetch_sorts_pinned_then_likes_and_drops_replies(
    comments_on, no_cooldown, monkeypatch
):
    from merlin.knowledge_sources.plugins.youtube import comments as mod

    seen: dict = {}
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", _fake_ytdl({"comments": RAW}, seen))
    out = mod.fetch_top_comments("vid12345678")

    assert [c["comment_id"] for c in out] == ["c", "b", "a"]  # no reply, no blank
    assert out[0]["is_pinned"] and out[0]["is_uploader"]
    assert out[2]["posted_at"] == datetime.fromtimestamp(1_700_000_000, UTC)
    yt = seen["opts"]["extractor_args"]["youtube"]
    assert yt["comment_sort"] == ["top"]
    assert yt["max_comments"] == ["20", "20", "0"]  # top-level only
    assert seen["opts"]["skip_download"] and seen["opts"]["getcomments"]


def test_fetch_is_spaced_by_its_own_limiter(no_cooldown, monkeypatch):
    """Every fetch takes a comments-limiter slot (not the subtitle one) and asks
    yt-dlp to pause between the calls inside the fetch."""
    from merlin.knowledge_sources.plugins.youtube import comments as mod

    waits = []
    monkeypatch.setattr(mod._comments_rate_limiter, "wait", lambda: waits.append(1))
    monkeypatch.setattr(
        mod._subtitle_rate_limiter,
        "wait",
        lambda: (_ for _ in ()).throw(AssertionError("subtitle slot used")),
    )
    seen: dict = {}
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", _fake_ytdl({"comments": RAW}, seen))
    mod.fetch_top_comments("v", limit=5)
    mod.fetch_top_comments("v", limit=5)
    assert waits == [1, 1]
    assert seen["opts"]["sleep_interval_requests"] > 0


def test_fetch_rechecks_cooldown_after_waiting(monkeypatch):
    """A block tripped by another worker while we waited cancels our fetch."""
    from merlin.knowledge_sources.plugins.youtube import comments as mod

    states = iter([False, True])
    monkeypatch.setattr(mod._subtitle_rate_limiter, "in_cooldown", lambda: next(states))
    monkeypatch.setattr(mod._comments_rate_limiter, "wait", lambda: None)
    monkeypatch.setattr(mod, "_cooldown_skip_message", lambda: "blocked meanwhile")
    monkeypatch.setattr(
        mod.yt_dlp, "YoutubeDL", _fake_ytdl(AssertionError("must not fetch"))
    )
    with pytest.raises(mod.CommentsUnavailable, match="blocked meanwhile"):
        mod.fetch_top_comments("v", limit=5)


def test_fetch_respects_limit(no_cooldown, monkeypatch):
    from merlin.knowledge_sources.plugins.youtube import comments as mod

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", _fake_ytdl({"comments": RAW}))
    assert [c["comment_id"] for c in mod.fetch_top_comments("v", limit=2)] == [
        "c",
        "b",
    ]


def test_fetch_off_or_cooled_down_raises(monkeypatch):
    from merlin.knowledge_sources.plugins.youtube import comments as mod

    with pytest.raises(mod.CommentsUnavailable, match="off"):
        mod.fetch_top_comments("v")  # conftest: YOUTUBE_COMMENTS_LIMIT=0

    monkeypatch.setattr(mod._subtitle_rate_limiter, "in_cooldown", lambda: True)
    monkeypatch.setattr(mod, "_cooldown_skip_message", lambda: "cooling down")
    with pytest.raises(mod.CommentsUnavailable, match="cooling down"):
        mod.fetch_top_comments("v", limit=5)


def test_fetch_ip_block_trips_cooldown(no_cooldown, monkeypatch):
    from merlin.knowledge_sources.plugins.youtube import comments as mod

    tripped = []
    monkeypatch.setattr(
        mod._subtitle_rate_limiter, "trip_cooldown", lambda: tripped.append(1) or 60
    )
    monkeypatch.setattr(
        mod.yt_dlp, "YoutubeDL", _fake_ytdl(Exception("HTTP Error 429: Too Many"))
    )
    with pytest.raises(mod.CommentsUnavailable):
        mod.fetch_top_comments("v", limit=5)
    assert tripped == [1]

    # Best-effort wrapper swallows it: None = "not fetched".
    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", _fake_ytdl(Exception("boom")))
    monkeypatch.setattr(mod.settings, "youtube_comments_limit", 5)
    assert mod.try_fetch_top_comments("v") is None


# --------------------------------------------------------------------------- #
# Storage + API
# --------------------------------------------------------------------------- #


def test_list_comments_never_fetched(client, make_item):
    item_id = make_item()
    body = client.get(f"/api/items/{item_id}/comments").json()
    assert body == {
        "item_id": item_id,
        "enabled": False,
        "fetched_at": None,
        "comments": [],
    }
    assert client.get("/api/items/nope/comments").status_code == 404


def test_replace_ranks_and_stamps(client, make_item, comments_on):
    item_id = make_item()
    _store(item_id, [_comment("first", 5), _comment("second", 2)])
    _store(item_id, [_comment("new top", 9, is_pinned=True), _comment("next", 1)])

    body = client.get(f"/api/items/{item_id}/comments").json()
    assert body["enabled"] is True
    assert body["fetched_at"] is not None
    assert [c["text"] for c in body["comments"]] == ["new top", "next"]
    assert body["comments"][0]["is_pinned"] is True


def test_refresh_replaces_stored_set(client, make_item, monkeypatch):
    from merlin.services import comments as svc

    item_id = make_item(source_id="vidREFRESH1")
    _store(item_id, [_comment("stale")])
    calls = []

    def fake_fetch(video_id, limit=None):
        calls.append(video_id)
        return [_comment("fresh", 42, is_uploader=True)]

    monkeypatch.setattr(svc, "fetch_top_comments", fake_fetch)
    res = client.post(f"/api/items/{item_id}/comments/refresh")
    assert res.status_code == 200
    assert calls == ["vidREFRESH1"]
    assert [c["text"] for c in res.json()["comments"]] == ["fresh"]
    assert res.json()["comments"][0]["is_uploader"] is True


def test_refresh_failure_is_400_and_keeps_stored(client, make_item, monkeypatch):
    from merlin.knowledge_sources.plugins.youtube.comments import (
        CommentsUnavailable,
    )
    from merlin.services import comments as svc

    item_id = make_item()
    _store(item_id, [_comment("kept")])

    def boom(video_id, limit=None):
        raise CommentsUnavailable("YouTube said no")

    monkeypatch.setattr(svc, "fetch_top_comments", boom)
    res = client.post(f"/api/items/{item_id}/comments/refresh")
    assert res.status_code == 400
    assert "YouTube said no" in res.json()["error"]["message"]
    kept = client.get(f"/api/items/{item_id}/comments").json()["comments"]
    assert [c["text"] for c in kept] == ["kept"]
    assert client.post("/api/items/nope/comments/refresh").status_code == 404


def test_deleting_item_deletes_comments(client, make_item):
    from sqlalchemy import text

    from merlin.db.engine import engine

    item_id = make_item()
    _store(item_id, [_comment("bye")])
    assert client.delete(f"/api/items/{item_id}").status_code == 204
    with engine.connect() as conn:
        left = conn.execute(text("SELECT COUNT(*) FROM youtube_comments")).scalar()
    assert left == 0


# --------------------------------------------------------------------------- #
# Ingest + re-summarise
# --------------------------------------------------------------------------- #


def _wait_for_task(task_id: str, timeout: float = 10.0) -> dict:
    from merlin.services import ingest

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = ingest.get_task(task_id)
        if task and task["status"] in ("completed", "failed"):
            return task
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} did not finish within {timeout}s")


def test_persist_result_stores_comments(client, make_task, monkeypatch):
    from merlin.knowledge_sources.base import IngestResult
    from merlin.services import comments as svc, ingest

    monkeypatch.setattr(ingest, "_classify", lambda item_id: None)
    task_id = make_task(task_type="ingest_youtube")
    result = IngestResult(
        source_type="youtube",
        source_id="vidPERSIST1",
        title="T",
        raw_content="words",
        source_metadata={"video_id": "vidPERSIST1"},
        comments=[_comment("top one", 7), _comment("second", 3)],
    )
    ingest.persist_result(task_id, result)

    item_id = ingest.get_task(task_id)["knowledge_item_id"]
    stored = svc.list_comments(item_id)
    assert [c["text"] for c in stored["comments"]] == ["top one", "second"]
    assert stored["fetched_at"] is not None


def test_resummarize_self_heals_comments(client, make_item, comments_on, monkeypatch):
    from merlin.knowledge_sources.registry import registry
    from merlin.services import comments as svc, ingest

    item_id = make_item(description="has one", source_id="vidHEAL0001")
    fetched = []

    def fake_try(video_id):
        fetched.append(video_id)
        return [_comment("viewers loved it", 120)]

    monkeypatch.setattr(ingest, "try_fetch_top_comments", fake_try)
    captured: dict = {}

    def fake_resummarize(*, comments=None, **kwargs):
        captured["comments"] = comments
        return ("## Overview\nnew", {}, {})

    monkeypatch.setattr(registry.get("youtube"), "resummarize", fake_resummarize)

    assert _wait_for_task(ingest.resummarize(item_id))["status"] == "completed"
    assert fetched == ["vidHEAL0001"]
    assert [c["text"] for c in captured["comments"]] == ["viewers loved it"]
    assert svc.list_comments(item_id)["fetched_at"] is not None

    # Healed: the next redo reuses the stored set without fetching again.
    assert _wait_for_task(ingest.resummarize(item_id))["status"] == "completed"
    assert fetched == ["vidHEAL0001"]
    assert [c["text"] for c in captured["comments"]] == ["viewers loved it"]


def test_resummarize_no_fetch_when_off(client, make_item, monkeypatch):
    from merlin.knowledge_sources.registry import registry
    from merlin.services import ingest

    item_id = make_item(description="has one")

    def boom(video_id):
        raise AssertionError("must not fetch comments when they're off")

    monkeypatch.setattr(ingest, "try_fetch_top_comments", boom)
    monkeypatch.setattr(
        registry.get("youtube"),
        "resummarize",
        lambda **kw: ("## Overview\nnew", {}, {}),
    )
    assert _wait_for_task(ingest.resummarize(item_id))["status"] == "completed"


# --------------------------------------------------------------------------- #
# Summariser
# --------------------------------------------------------------------------- #


def test_comments_block_and_prompt():
    from merlin.knowledge_sources.plugins.youtube.summarizer import VideoSummarizer

    s = VideoSummarizer(model=object())
    assert s._build_comments_block(None) == ""
    assert s._build_comments_block([{"text": "  "}]) == ""

    block = s._build_comments_block(
        [_comment("x" * 2000, 50, is_uploader=True), _comment("nice {braces}", 2)]
    )
    assert "## What Viewers Say" in block
    assert "(50 likes [creator])" in block
    assert "x" * 500 + "…" in block and "x" * 501 not in block

    for length in ("short", "long"):
        prompt = s.templates[length].format(
            subtitles="SUBS",
            lang="english",
            title="T",
            channel="C",
            description_block="",
            comments_block=block,
        )
        assert prompt.index("SUBS") < prompt.index("Top viewer comments")
        assert "nice {braces}" in prompt


def test_key_points_parser_stops_at_next_section():
    from merlin.knowledge_sources.plugins.youtube.summarizer import VideoSummarizer

    summary = (
        "## Overview\nIntro.\n\n## Main Key Points\n"
        "1. **Point one** - detail [00:01:00]\n"
        "2. **Point two** - detail [00:02:00]\n\n"
        "## What Viewers Say\n- Viewers - pushed back [00:09:00]\n"
    )
    topics, timestamps = VideoSummarizer(model=object()).extract_topics_and_timestamps(
        summary, "short"
    )
    assert set(timestamps) == {"00:01:00", "00:02:00"}


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #


class _Ctx:
    def __init__(self, deps):
        self.deps = deps


def test_get_comments_tool(make_item):
    from merlin.rag.agent import ChatDeps, get_comments

    item_id = make_item(title="Espresso myths")
    deps = ChatDeps()
    out = get_comments(_Ctx(deps), item_id)  # type: ignore[arg-type]
    assert "never fetched" in out

    _store(item_id, [_comment("Myth 3 is wrong", 300, is_uploader=True)])
    out = get_comments(_Ctx(deps), item_id, limit=5)  # type: ignore[arg-type]
    assert "Myth 3 is wrong" in out
    assert "300 likes [creator]" in out
    assert item_id in deps.cited

    _store(item_id, [])
    assert "has no comments" in get_comments(_Ctx(deps), item_id)  # type: ignore[arg-type]
    assert "No item found" in get_comments(_Ctx(deps), "nope")  # type: ignore[arg-type]


def test_item_chat_context_includes_comments(make_item):
    from merlin.services.chat import item_instructions

    item_id = make_item()
    assert "TOP VIEWER COMMENTS" not in item_instructions(item_id)
    _store(item_id, [_comment("Loved the ending", 12)])
    text = item_instructions(item_id)
    assert "TOP VIEWER COMMENTS" in text
    assert "Loved the ending" in text
