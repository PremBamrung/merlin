"""
In-process background task queue.

Uses asyncio + ThreadPoolExecutor so heavy blocking work (video processing,
LLM calls, ffmpeg) runs off the event loop without extra infrastructure.

Task status is persisted to the SQLite background_tasks table — survives
server restarts and is queryable via GET /api/tasks/{task_id}.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
import uuid

from merlin.core.logging import logger
from merlin.db.engine import SessionFactory
from merlin.db.repositories.tasks import BackgroundTaskRepository
from merlin.knowledge_sources.base import IngestRequest, IngestResult


class TaskCancelled(Exception):
    """Raised inside a worker when the task has been cancelled by the user.

    Surfaced at a progress checkpoint (cooperative cancellation) so the worker
    unwinds cleanly and records the task as ``cancelled`` rather than ``failed``.
    """


class TaskQueue:
    def __init__(self, max_workers: int = 3):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="merlin"
        )
        # task_ids the user has asked to cancel; checked at progress checkpoints.
        self._cancelled: set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue_ingest(
        self,
        plugin,
        raw_input: str,
        options: dict,
        on_complete: Callable[[str, IngestResult], None],
    ) -> str:
        """
        Schedule an ingestion job.

        1. Creates a background_tasks row (queued)
        2. Submits the work to the thread pool (non-blocking)
        3. Returns task_id immediately

        on_complete(task_id, result) is called from the worker thread
        after successful ingestion — use it to persist the IngestResult.
        """
        task_id = str(uuid.uuid4())

        # Persist queued task
        with SessionFactory() as session:
            BackgroundTaskRepository.create(
                session,
                task_id=task_id,
                task_type=f"ingest_{plugin.source_type}",
                input_data={"raw_input": raw_input, **options},
            )
            session.commit()

        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            self._executor,
            self._run_ingest,
            task_id,
            plugin,
            raw_input,
            options,
            on_complete,
        )
        return task_id

    def submit_ingest(
        self,
        plugin,
        raw_input: str,
        options: dict,
        on_complete: Callable[[str, IngestResult], None],
    ) -> str:
        """
        Synchronous variant of enqueue_ingest for non-async callers.

        Same semantics — persists a queued task row and submits the blocking work
        to the thread pool — but without requiring a running asyncio event loop in
        the calling thread.
        """
        task_id = str(uuid.uuid4())

        with SessionFactory() as session:
            BackgroundTaskRepository.create(
                session,
                task_id=task_id,
                task_type=f"ingest_{plugin.source_type}",
                input_data={"raw_input": raw_input, **options},
            )
            session.commit()

        self._executor.submit(
            self._run_ingest,
            task_id,
            plugin,
            raw_input,
            options,
            on_complete,
        )
        return task_id

    def submit_callable(
        self,
        work: Callable[[str, Callable[[int, str], None]], None],
        task_type: str,
        input_data: dict,
    ) -> str:
        """Run an arbitrary blocking job as a tracked background task.

        Persists a queued `background_tasks` row, then runs `work(task_id,
        report)` off-thread — `report(percent, message)` updates progress. The
        `work` callable owns its own persistence and must mark the task
        completed (e.g. via `BackgroundTaskRepository.set_completed`); failures
        are caught here and recorded as `failed`.
        """
        task_id = str(uuid.uuid4())

        with SessionFactory() as session:
            BackgroundTaskRepository.create(
                session,
                task_id=task_id,
                task_type=task_type,
                input_data=input_data,
            )
            session.commit()

        self._executor.submit(self._run_callable, task_id, work)
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Request cancellation of a queued/running task. Cooperative.

        Flags the id so the worker stops at its next `report()` checkpoint and
        records the task as `cancelled`. Returns False if the task is unknown or
        already terminal (completed/failed/cancelled). Work already in flight
        between checkpoints (e.g. an LLM call) finishes before the stop takes.
        """
        with SessionFactory() as s:
            task = BackgroundTaskRepository.get(s, task_id)
            if task is None or task.status in ("completed", "failed", "cancelled"):
                return False
        self._cancelled.add(task_id)
        return True

    def _check_cancelled(self, task_id: str) -> None:
        """Raise TaskCancelled if the user has cancelled this task."""
        if task_id in self._cancelled:
            raise TaskCancelled()

    def _mark_cancelled(self, task_id: str) -> None:
        logger.info(f"Task {task_id} cancelled")
        with SessionFactory() as s:
            BackgroundTaskRepository.set_cancelled(s, task_id)
            s.commit()

    # ------------------------------------------------------------------
    # Worker (runs in thread pool)
    # ------------------------------------------------------------------

    def _run_callable(
        self,
        task_id: str,
        work: Callable[[str, Callable[[int, str], None]], None],
    ) -> None:
        logger.info(f"Task {task_id} started — callable job")

        def report(percent: int, message: str):
            self._check_cancelled(task_id)
            try:
                with SessionFactory() as s:
                    BackgroundTaskRepository.update_progress(
                        s, task_id, percent, message
                    )
                    s.commit()
            except Exception as e:
                logger.warning(f"Progress update failed for {task_id}: {e}")

        with SessionFactory() as s:
            BackgroundTaskRepository.set_processing(s, task_id)
            s.commit()

        try:
            self._check_cancelled(task_id)
            work(task_id, report)
            logger.info(f"Task {task_id} completed successfully")
        except TaskCancelled:
            self._mark_cancelled(task_id)
        except Exception as exc:
            logger.exception(f"Task {task_id} failed: {exc}")
            with SessionFactory() as s:
                BackgroundTaskRepository.set_failed(s, task_id, str(exc))
                s.commit()
        finally:
            self._cancelled.discard(task_id)

    def _run_ingest(
        self,
        task_id: str,
        plugin,
        raw_input: str,
        options: dict,
        on_complete: Callable,
    ) -> None:
        logger.info(f"Task {task_id} started — {plugin.source_type}: {raw_input[:80]}")

        def progress_callback(percent: int, message: str):
            self._check_cancelled(task_id)
            try:
                with SessionFactory() as s:
                    BackgroundTaskRepository.update_progress(
                        s, task_id, percent, message
                    )
                    s.commit()
            except Exception as e:
                logger.warning(f"Progress update failed for {task_id}: {e}")

        def title_callback(title: str):
            try:
                with SessionFactory() as s:
                    BackgroundTaskRepository.set_title(s, task_id, title)
                    s.commit()
            except Exception as e:
                logger.warning(f"Title update failed for {task_id}: {e}")

        # Mark as processing
        with SessionFactory() as s:
            BackgroundTaskRepository.set_processing(s, task_id)
            s.commit()

        try:
            self._check_cancelled(task_id)
            request = IngestRequest(
                raw_input=raw_input,
                options=options,
                task_id=task_id,
                progress_callback=progress_callback,
                title_callback=title_callback,
            )
            result: IngestResult = plugin.ingest(request)

            # Call the on_complete hook (persists result to DB)
            on_complete(task_id, result)
            logger.info(f"Task {task_id} completed successfully")

        except TaskCancelled:
            self._mark_cancelled(task_id)
        except Exception as exc:
            logger.exception(f"Task {task_id} failed: {exc}")
            with SessionFactory() as s:
                BackgroundTaskRepository.set_failed(s, task_id, str(exc))
                s.commit()
        finally:
            self._cancelled.discard(task_id)


# Module-level singleton — imported by the API routers
task_queue = TaskQueue(max_workers=3)
