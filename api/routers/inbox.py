"""Inbox / Digest endpoints (Tier 1) — the triage queue over recent ingests.

Thin adapter over `merlin.services.digest`: list the queue, record a review
decision, and retry/clear failed tasks. A `ValueError` from the service (bad
action) maps to 400; a missing item to 404 — both via the shared error layer.
"""

from __future__ import annotations

from fastapi import APIRouter

from merlin.services import digest

from ..errors import not_found
from ..schemas import (
    ClearFailedResponse,
    DigestActionRequest,
    DigestActionResponse,
    InboxResponse,
    RetryFailedResponse,
)

router = APIRouter(prefix="/api/digest", tags=["inbox"])


@router.get("", response_model=InboxResponse)
def inbox(limit: int = 50):
    return digest.list_inbox(limit)


@router.post("/retry-failed", response_model=RetryFailedResponse)
def retry_failed():
    return digest.retry_failed()


@router.post("/clear-failed", response_model=ClearFailedResponse)
def clear_failed():
    return digest.clear_failed()


@router.post("/{item_id}/action", response_model=DigestActionResponse)
def record_action(item_id: str, body: DigestActionRequest):
    # service raises ValueError on a bad action → 400 invalid_input (global handler)
    result = digest.record_action(item_id, body.action)
    if result is None:
        raise not_found("Item not found.")
    return result
