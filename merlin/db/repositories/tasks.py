"""
BackgroundTaskRepository — CRUD for the background_tasks table.
"""

from datetime import datetime, timezone
import json
from typing import Optional

from sqlalchemy.orm import Session

from merlin.db.models import BackgroundTask


class BackgroundTaskRepository:
    @staticmethod
    def create(
        session: Session, task_id: str, task_type: str, input_data: dict
    ) -> BackgroundTask:
        task = BackgroundTask(
            id=task_id,
            task_type=task_type,
            status="queued",
            progress=0,
            input_data=json.dumps(input_data),
            created_at=datetime.now(timezone.utc),
        )
        session.add(task)
        session.flush()
        return task

    @staticmethod
    def get(session: Session, task_id: str) -> Optional[BackgroundTask]:
        return session.get(BackgroundTask, task_id)

    @staticmethod
    def set_processing(session: Session, task_id: str) -> None:
        task = session.get(BackgroundTask, task_id)
        if task:
            task.status = "processing"
            task.started_at = datetime.now(timezone.utc)

    @staticmethod
    def update_progress(
        session: Session, task_id: str, progress: int, message: str
    ) -> None:
        task = session.get(BackgroundTask, task_id)
        if task:
            task.progress = progress
            task.message = message

    @staticmethod
    def set_completed(
        session: Session,
        task_id: str,
        result_data: dict,
        knowledge_item_id: Optional[str] = None,
    ) -> None:
        task = session.get(BackgroundTask, task_id)
        if task:
            task.status = "completed"
            task.progress = 100
            task.result_data = json.dumps(result_data)
            task.completed_at = datetime.now(timezone.utc)
            if knowledge_item_id:
                task.knowledge_item_id = knowledge_item_id

    @staticmethod
    def set_failed(session: Session, task_id: str, error: str) -> None:
        task = session.get(BackgroundTask, task_id)
        if task:
            task.status = "failed"
            task.error = error
            task.completed_at = datetime.now(timezone.utc)

    @staticmethod
    def list_recent(session: Session, limit: int = 20) -> list[BackgroundTask]:
        return (
            session.query(BackgroundTask)
            .order_by(BackgroundTask.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def delete(session: Session, task_id: str) -> bool:
        task = session.get(BackgroundTask, task_id)
        if not task:
            return False
        session.delete(task)
        return True

    @staticmethod
    def delete_by_status(session: Session, status: str) -> int:
        """Bulk-delete tasks in a given status (e.g. 'failed'). Returns count."""
        return (
            session.query(BackgroundTask)
            .filter(BackgroundTask.status == status)
            .delete(synchronize_session=False)
        )
