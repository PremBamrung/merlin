"""Cooperative cancellation in the in-process task queue.

The worker runs in a thread pool, so cancellation can't kill it outright — it
flags the task and the worker unwinds at its next `report()` checkpoint, landing
in the `cancelled` (not `failed`) state.
"""

from __future__ import annotations

import threading
import time

from merlin.core.task_queue import TaskQueue
from merlin.db.engine import SessionFactory
from merlin.db.repositories.tasks import BackgroundTaskRepository


def _status(task_id: str) -> str | None:
    with SessionFactory() as s:
        task = BackgroundTaskRepository.get(s, task_id)
        return task.status if task else None


def _wait_for_status(task_id: str, want: str, timeout: float = 3.0) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = _status(task_id)
        if status == want:
            return status
        time.sleep(0.02)
    return _status(task_id)


def test_cancel_stops_at_next_checkpoint(_migrate_temp_db):
    q = TaskQueue(max_workers=1)
    started = threading.Event()
    release = threading.Event()

    def work(task_id, report):
        report(10, "step 1")
        started.set()
        release.wait(3)  # hold here until the test cancels
        report(50, "step 2")  # the checkpoint that should raise once cancelled
        report(90, "step 3")  # never reached

    task_id = q.submit_callable(work, task_type="test_job", input_data={})
    assert started.wait(3), "worker never started"

    assert q.cancel(task_id) is True
    release.set()

    assert _wait_for_status(task_id, "cancelled") == "cancelled"


def test_cancel_unknown_task_returns_false(_migrate_temp_db):
    q = TaskQueue(max_workers=1)
    assert q.cancel("does-not-exist") is False


def test_cancel_completed_task_returns_false(_migrate_temp_db):
    q = TaskQueue(max_workers=1)

    def work(task_id, report):
        report(100, "done")
        # submit_callable's contract: the job marks itself completed.
        with SessionFactory() as s:
            BackgroundTaskRepository.set_completed(s, task_id, {})
            s.commit()

    task_id = q.submit_callable(work, task_type="test_job", input_data={})
    assert _wait_for_status(task_id, "completed") == "completed"
    # Nothing to cancel once it's terminal.
    assert q.cancel(task_id) is False
