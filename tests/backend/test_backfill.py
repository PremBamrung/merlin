"""Tests for the parallel LLM helper and the topic-backfill background task.

`parallel_map` is exercised directly (ordering, 429 retry via the limiter's
cooldown, cooperative cancel). `backfill_topics` runs the background callable
synchronously (monkeypatched task queue) with the LLM classifier mocked, and
asserts it fits uncategorised items to *existing* topics while leaving
user-assigned rows untouched.
"""

from __future__ import annotations

import threading

import pytest

from merlin.core.parallel_llm import parallel_map
from merlin.core.rate_limit import MinIntervalRateLimiter
from merlin.core.task_queue import TaskCancelled
from merlin.db.engine import SessionFactory
from merlin.db.repositories.topics import TopicRepository
from merlin.services import classify as classify_mod, topics as topics_service


def _limiter() -> MinIntervalRateLimiter:
    # Fast cooldown so the retry test doesn't sleep long.
    return MinIntervalRateLimiter(0.0, name="test", cooldown_seconds=0.01)


# --- parallel_map ----------------------------------------------------------


def test_parallel_map_preserves_input_order():
    out = parallel_map(
        list(range(20)),
        lambda x: x * 2,
        concurrency=4,
        limiter=_limiter(),
    )
    assert out == [x * 2 for x in range(20)]


def test_parallel_map_empty():
    assert parallel_map([], lambda x: x, concurrency=4, limiter=_limiter()) == []


def test_parallel_map_retries_on_rate_limit():
    calls = {"n": 0}
    lock = threading.Lock()

    def fn(x):
        with lock:
            calls["n"] += 1
            n = calls["n"]
        if n == 1:
            raise RuntimeError("HTTP 429: too many requests")
        return x

    out = parallel_map([7], fn, concurrency=1, limiter=_limiter(), max_retries=3)
    assert out == [7]
    assert calls["n"] == 2  # first raised 429, retry succeeded


def test_parallel_map_failed_item_is_none_not_abort():
    def fn(x):
        if x == 2:
            raise ValueError("boom")  # not a rate-limit → no retry, just drops
        return x

    out = parallel_map([1, 2, 3], fn, concurrency=1, limiter=_limiter())
    assert out == [1, None, 3]


def test_parallel_map_cancel_stops_consumption():
    seen = {"count": 0}

    def report(pct, msg):
        seen["count"] += 1
        raise TaskCancelled()  # cancel at the very first completion checkpoint

    with pytest.raises(TaskCancelled):
        parallel_map(
            list(range(10)),
            lambda x: x,
            concurrency=2,
            limiter=_limiter(),
            report=report,
        )
    assert seen["count"] == 1  # stopped consuming after the first checkpoint


def test_parallel_map_on_result_fires_before_cancel():
    """on_result fires (accumulating partial work) even on the checkpoint that
    then cancels — so the caller keeps what finished."""
    collected: list[int] = []

    calls = {"n": 0}

    def report(pct, msg):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise TaskCancelled()  # cancel on the 2nd completion

    with pytest.raises(TaskCancelled):
        parallel_map(
            list(range(6)),
            lambda x: x,
            concurrency=1,
            limiter=_limiter(),
            report=report,
            on_result=lambda idx, r: collected.append(r),
        )
    # Both completed items were collected before the cancel took effect.
    assert collected == [0, 1]


# --- backfill_topics -------------------------------------------------------


def _run_backfill_synchronously(monkeypatch):
    """Make submit_callable run the work inline; return the completed task row."""
    from merlin.core.task_queue import task_queue
    from merlin.db.repositories.tasks import BackgroundTaskRepository

    captured = {}

    def fake_submit(work, task_type=None, input_data=None):
        # Emulate the queue: create the row, run the work with a real reporter.
        with SessionFactory() as s:
            BackgroundTaskRepository.create(
                s, task_id="bt", task_type=task_type, input_data=input_data or {}
            )
            s.commit()

        def report(pct, msg):
            with SessionFactory() as s:
                BackgroundTaskRepository.update_progress(s, "bt", pct, msg)
                s.commit()

        work("bt", report)
        return "bt"

    monkeypatch.setattr(task_queue, "submit_callable", fake_submit)
    topics_service.backfill_topics()
    with SessionFactory() as s:
        captured["task"] = BackgroundTaskRepository.get(s, "bt")
        captured["result"] = captured["task"].result_data
    return captured


def test_backfill_noop_when_nothing_uncategorised(client, monkeypatch):
    import json

    got = _run_backfill_synchronously(monkeypatch)
    assert got["task"].status == "completed"
    assert json.loads(got["result"]) == {
        "classified": 0,
        "requested": 0,
        "still_uncategorised": 0,
    }


def test_backfill_classifies_against_existing_topics(client, make_item, monkeypatch):
    import json

    from merlin.services.classify import ClassifyResult

    topic_id = client.post("/api/topics", json={"label": "Coding"}).json()["id"]
    a = make_item(title="a", tags=["x"])
    b = make_item(title="b", tags=["y"])

    # Mock the LLM: everything lands under the existing 'coding' slug.
    monkeypatch.setattr(
        classify_mod,
        "classify_item",
        lambda *a, **k: ClassifyResult(primary="coding", secondary=[], tags=["z"]),
    )

    got = _run_backfill_synchronously(monkeypatch)
    assert got["task"].status == "completed"
    result = json.loads(got["result"])
    assert result["requested"] == 2
    assert result["classified"] == 2
    assert result["still_uncategorised"] == 0

    for iid in (a, b):
        with SessionFactory() as s:
            assignments = TopicRepository.get_assignments(s, iid)
        assert [x.topic_id for x in assignments] == [topic_id]


def test_backfill_skips_user_assigned_items(client, make_item, monkeypatch):
    import json

    from merlin.services.classify import ClassifyResult

    client.post("/api/topics", json={"label": "Coding"})
    gaming = client.post("/api/topics", json={"label": "Gaming"}).json()["id"]
    item = make_item(title="pinned")
    # User pins it to Gaming — backfill must never move it.
    topics_service.set_item_topics(item, [gaming], gaming)

    monkeypatch.setattr(
        classify_mod,
        "classify_item",
        lambda *a, **k: ClassifyResult(primary="coding", secondary=[], tags=["z"]),
    )

    got = _run_backfill_synchronously(monkeypatch)
    # The item was never uncategorised, so it isn't even in the work set.
    assert json.loads(got["result"])["requested"] == 0
    with SessionFactory() as s:
        assignments = TopicRepository.get_assignments(s, item)
    assert [x.topic_id for x in assignments] == [gaming]
    assert all(x.assigned_by == "user" for x in assignments)
