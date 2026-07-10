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


# --- llm_member_ids (re-scan feeder) --------------------------------------


def _llm_assign(item_id: str, topic_id: str, *, primary: bool) -> None:
    with SessionFactory() as s:
        TopicRepository.add_assignment(
            s, item_id, topic_id, is_primary=primary, assigned_by="llm"
        )
        s.commit()


def test_llm_member_ids_covers_primary_and_secondary(client, make_item):
    gaming = client.post("/api/topics", json={"label": "Gaming"}).json()["id"]
    prim = make_item(title="primary member")
    sec = make_item(title="secondary member")
    _llm_assign(prim, gaming, primary=True)
    _llm_assign(sec, gaming, primary=False)

    with SessionFactory() as s:
        ids = set(TopicRepository.llm_member_ids(s, gaming))
    assert ids == {prim, sec}


def test_llm_member_ids_excludes_user_assigned(client, make_item):
    gaming = client.post("/api/topics", json={"label": "Gaming"}).json()["id"]
    pinned = make_item(title="pinned")
    # Gaming is present on the item, but via a user assignment → excluded.
    topics_service.set_item_topics(pinned, [gaming], gaming)

    with SessionFactory() as s:
        ids = TopicRepository.llm_member_ids(s, gaming)
    assert ids == []


# --- reclassify_topic ------------------------------------------------------


def _run_reclassify_synchronously(monkeypatch, topic_id: str):
    """Make submit_callable run the reclassify work inline; return task + result."""
    from merlin.core.task_queue import task_queue
    from merlin.db.repositories.tasks import BackgroundTaskRepository

    captured = {}

    def fake_submit(work, task_type=None, input_data=None):
        with SessionFactory() as s:
            BackgroundTaskRepository.create(
                s, task_id="rt", task_type=task_type, input_data=input_data or {}
            )
            s.commit()

        def report(pct, msg):
            with SessionFactory() as s:
                BackgroundTaskRepository.update_progress(s, "rt", pct, msg)
                s.commit()

        work("rt", report)
        return "rt"

    monkeypatch.setattr(task_queue, "submit_callable", fake_submit)
    topics_service.reclassify_topic(topic_id)
    with SessionFactory() as s:
        captured["task"] = BackgroundTaskRepository.get(s, "rt")
        captured["result"] = captured["task"].result_data
    return captured


def test_reclassify_missing_topic_404s(client):
    assert client.post("/api/topics/nope/reclassify").status_code == 404
    # Service returns None directly for the unknown id.
    assert topics_service.reclassify_topic("nope") is None


def test_reclassify_moves_llm_members_to_better_fit(client, make_item, monkeypatch):
    import json

    from merlin.services.classify import ClassifyResult

    gaming = client.post("/api/topics", json={"label": "Gaming"}).json()["id"]
    dofus = client.post("/api/topics", json={"label": "Dofus"}).json()["id"]

    moved = make_item(title="a dofus video")
    pinned = make_item(title="hand-filed under gaming")
    _llm_assign(moved, gaming, primary=True)  # LLM-filed under the broad topic
    topics_service.set_item_topics(pinned, [gaming], gaming)  # user-pinned

    # The narrower topic now fits better — the classifier re-decides to 'dofus'.
    monkeypatch.setattr(
        classify_mod,
        "classify_item",
        lambda *a, **k: ClassifyResult(primary="dofus", secondary=[], tags=["z"]),
    )

    got = _run_reclassify_synchronously(monkeypatch, gaming)
    assert got["task"].status == "completed"
    result = json.loads(got["result"])
    # Only the LLM member is in the work set (the user-pinned item is excluded).
    assert result == {
        "reclassified": 1,
        "requested": 1,
        "moved": 1,
        "cancelled": False,
    }

    with SessionFactory() as s:
        moved_topics = [x.topic_id for x in TopicRepository.get_assignments(s, moved)]
        pinned_rows = TopicRepository.get_assignments(s, pinned)
    # The LLM member flipped Gaming → Dofus…
    assert moved_topics == [dofus]
    # …and the hand-filed item is untouched.
    assert [x.topic_id for x in pinned_rows] == [gaming]
    assert all(x.assigned_by == "user" for x in pinned_rows)


# --- reclassify_all (full-corpus) ------------------------------------------


def test_classifiable_item_ids_covers_categorised_and_uncategorised(
    client, make_item
):
    gaming = client.post("/api/topics", json={"label": "Gaming"}).json()["id"]
    llm_item = make_item(title="already classified")
    uncat_item = make_item(title="no topic yet")
    pinned = make_item(title="hand-filed")
    _llm_assign(llm_item, gaming, primary=True)
    topics_service.set_item_topics(pinned, [gaming], gaming)

    with SessionFactory() as s:
        ids = set(TopicRepository.classifiable_item_ids(s))
    # Both the LLM-classified and the uncategorised item are in scope; the
    # hand-filed one is excluded.
    assert ids == {llm_item, uncat_item}


def test_reclassify_all_redecides_llm_items_too(client, make_item, monkeypatch):
    import json

    from merlin.core.task_queue import task_queue
    from merlin.db.repositories.tasks import BackgroundTaskRepository
    from merlin.services.classify import ClassifyResult

    client.post("/api/topics", json={"label": "Gaming"})
    dofus = client.post("/api/topics", json={"label": "Dofus"}).json()["id"]

    gaming_id = next(
        t["id"] for t in topics_service.list_topics() if t["slug"] == "gaming"
    )
    already = make_item(title="a dofus video filed under gaming")
    _llm_assign(already, gaming_id, primary=True)

    monkeypatch.setattr(
        classify_mod,
        "classify_item",
        lambda *a, **k: ClassifyResult(primary="dofus", secondary=[], tags=["z"]),
    )

    # Run the full re-scan work inline.
    def fake_submit(work, task_type=None, input_data=None):
        with SessionFactory() as s:
            BackgroundTaskRepository.create(
                s, task_id="ra", task_type=task_type, input_data=input_data or {}
            )
            s.commit()

        def report(pct, msg):
            with SessionFactory() as s:
                BackgroundTaskRepository.update_progress(s, "ra", pct, msg)
                s.commit()

        work("ra", report)
        return "ra"

    monkeypatch.setattr(task_queue, "submit_callable", fake_submit)
    topics_service.reclassify_all()

    with SessionFactory() as s:
        task = BackgroundTaskRepository.get(s, "ra")
        topics_after = [x.topic_id for x in TopicRepository.get_assignments(s, already)]
    assert task.status == "completed"
    assert json.loads(task.result_data)["requested"] == 1
    # An already-LLM-classified item was re-decided (Gaming → Dofus) — the thing
    # backfill can't do.
    assert topics_after == [dofus]
