"""
GET    /api/tasks/{task_id}  — poll background task status
GET    /api/tasks            — list recent tasks
DELETE /api/tasks/{task_id}  — dismiss a single task
DELETE /api/tasks            — bulk-clear tasks (optionally filtered by ?status=failed)
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.engine import get_db_session
from backend.db.models import BackgroundTask
from backend.db.repositories.tasks import BackgroundTaskRepository

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db_session)):
    task = BackgroundTaskRepository.get(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _serialize(task)


@router.get("")
def list_tasks(limit: int = 20, db: Session = Depends(get_db_session)):
    tasks = BackgroundTaskRepository.list_recent(db, limit=limit)
    return [_serialize(t) for t in tasks]


@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db_session)):
    """Dismiss a single task (e.g. a failed ingestion). Does not touch the
    knowledge item — use DELETE /api/knowledge/{id} for that."""
    ok = BackgroundTaskRepository.delete(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


@router.delete("")
def clear_tasks(status: Optional[str] = None, db: Session = Depends(get_db_session)):
    """Bulk-clear tasks. Pass ?status=failed to clear only failed ingestions."""
    if status:
        if status not in ("queued", "processing", "completed", "failed"):
            raise HTTPException(status_code=422, detail=f"Invalid status '{status}'")
        deleted = BackgroundTaskRepository.delete_by_status(db, status)
    else:
        deleted = BackgroundTaskRepository.delete_by_status(db, "failed")
    return {"deleted": deleted}


def _serialize(task: BackgroundTask) -> dict:
    result_data = None
    if task.result_data:
        try:
            result_data = json.loads(task.result_data)
        except Exception:
            result_data = {"raw": task.result_data}

    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "error": task.error,
        "result": result_data,
        "knowledge_item_id": task.knowledge_item_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
