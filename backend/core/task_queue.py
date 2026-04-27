"""
In-process background task queue.

Uses asyncio + ThreadPoolExecutor so heavy blocking work (video processing,
LLM calls, ffmpeg) runs off the event loop without extra infrastructure.

Task status is persisted to the SQLite background_tasks table — survives
server restarts and is queryable via GET /api/tasks/{task_id}.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable
import uuid

from backend.core.logging import logger
from backend.db.engine import SessionFactory
from backend.db.repositories.tasks import BackgroundTaskRepository
from backend.knowledge_sources.base import IngestRequest, IngestResult


class TaskQueue:
    def __init__(self, max_workers: int = 3):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="merlin"
        )

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

    # ------------------------------------------------------------------
    # Worker (runs in thread pool)
    # ------------------------------------------------------------------

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
            try:
                with SessionFactory() as s:
                    BackgroundTaskRepository.update_progress(
                        s, task_id, percent, message
                    )
                    s.commit()
            except Exception as e:
                logger.warning(f"Progress update failed for {task_id}: {e}")

        # Mark as processing
        with SessionFactory() as s:
            BackgroundTaskRepository.set_processing(s, task_id)
            s.commit()

        try:
            request = IngestRequest(
                raw_input=raw_input,
                options=options,
                task_id=task_id,
                progress_callback=progress_callback,
            )
            result: IngestResult = plugin.ingest(request)

            # Call the on_complete hook (persists result to DB)
            on_complete(task_id, result)
            logger.info(f"Task {task_id} completed successfully")

        except Exception as exc:
            logger.exception(f"Task {task_id} failed: {exc}")
            with SessionFactory() as s:
                BackgroundTaskRepository.set_failed(s, task_id, str(exc))
                s.commit()


# Module-level singleton — imported by the API routers
task_queue = TaskQueue(max_workers=3)
