"""Startup settling of tasks a previous process died holding.

The queue is in-process, so after a restart any queued/processing row is an
orphan. Ingests become failed (retryable from Needs attention); topic jobs
become cancelled; finished rows are left alone.
"""

from __future__ import annotations

from merlin.services import ingest


def test_settles_unfinished_tasks(client, make_task):
    running = make_task(status="processing")
    queued = make_task(status="queued", task_type="resummarize_youtube")
    topic = make_task(status="processing", task_type="propose_topics")
    done = make_task(status="completed", progress=100)

    assert ingest.fail_interrupted_tasks() == 3

    for task_id in (running, queued):
        task = client.get(f"/api/tasks/{task_id}").json()
        assert task["status"] == "failed"
        assert task["error"] == ingest.INTERRUPTED_ERROR
    assert client.get(f"/api/tasks/{topic}").json()["status"] == "cancelled"
    assert client.get(f"/api/tasks/{done}").json()["status"] == "completed"

    # The settled ingests surface in Needs attention.
    failed = {t["id"] for t in client.get("/api/digest").json()["failed"]}
    assert failed == {running, queued}


def test_noop_when_nothing_unfinished(make_task):
    make_task(status="completed", progress=100)
    assert ingest.fail_interrupted_tasks() == 0
