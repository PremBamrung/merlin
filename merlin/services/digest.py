"""
Digest / Inbox service — the triage queue over recently-ingested content.

The Inbox surfaces two things: items **awaiting review** (recently ingested,
not yet acted on) and **failed** ingest tasks. Review decisions (keep / dismiss)
are recorded in `digest_actions`; acting on an item removes it from the queue
without deleting it from the Library. Failed tasks can be **retried**
(re-enqueued) or **cleared** (deleted).

Like every service module this is framework-agnostic and returns plain dicts.
"""

import json

from merlin.db.engine import SessionFactory
from merlin.db.repositories.digest import DigestActionRepository
from merlin.db.repositories.knowledge import KnowledgeItemRepository
from merlin.db.repositories.tasks import BackgroundTaskRepository
from merlin.services import ingest
from merlin.services.library import serialize_item

VALID_ACTIONS = ("keep", "dismiss")


def list_inbox(limit: int = 50) -> dict:
    """The Inbox payload: pending review items, failed tasks, and header counts."""
    with SessionFactory() as session:
        pending = [
            serialize_item(item)
            for item in DigestActionRepository.list_pending(session, limit)
        ]
        failed = [
            ingest._serialize_task(t)
            for t in BackgroundTaskRepository.list_by_status(session, "failed", limit)
        ]
        counts = {
            "pending": DigestActionRepository.count_pending(session),
            "processing": BackgroundTaskRepository.count_by_status(
                session, "queued", "processing"
            ),
            "failed": BackgroundTaskRepository.count_by_status(session, "failed"),
            "reviewed": DigestActionRepository.count(session),
        }
    return {"pending": pending, "failed": failed, "counts": counts}


def record_action(item_id: str, action: str) -> dict | None:
    """Record a review decision (keep/dismiss). Returns None if the item is gone."""
    if action not in VALID_ACTIONS:
        raise ValueError(f"action must be one of {VALID_ACTIONS}")
    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        if not item:
            return None
        DigestActionRepository.record(session, item_id, action)
        session.commit()
    return {"item_id": item_id, "action": action}


def retry_failed() -> dict:
    """Re-enqueue every failed task, then drop the superseded failed rows.

    A failed task is retried via its knowledge item when one exists, otherwise
    by re-submitting the original URL captured in `input_data`. Returns the new
    task ids.
    """
    with SessionFactory() as session:
        targets = [
            (t.id, t.knowledge_item_id, _parse_json(t.input_data, {}))
            for t in BackgroundTaskRepository.list_by_status(session, "failed", 500)
        ]

    started: list[str] = []
    retried_ids: list[str] = []
    for old_id, item_id, input_data in targets:
        try:
            if item_id:
                started.append(ingest.retry(item_id))
            elif input_data.get("raw_input"):
                started.append(
                    ingest.submit_youtube(
                        input_data["raw_input"],
                        input_data.get("languages") or ["en"],
                        input_data.get("summary_length", "short"),
                        force=True,
                    )["task_id"]
                )
            else:
                continue
            retried_ids.append(old_id)
        except ValueError:
            continue  # leave un-retryable rows in place

    if retried_ids:
        with SessionFactory() as session:
            for old_id in retried_ids:
                BackgroundTaskRepository.delete(session, old_id)
            session.commit()

    return {"task_ids": started}


def clear_failed() -> dict:
    """Delete all failed task rows. Returns the number cleared."""
    with SessionFactory() as session:
        cleared = BackgroundTaskRepository.delete_by_status(session, "failed")
        session.commit()
    return {"cleared": cleared}


def _parse_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default
