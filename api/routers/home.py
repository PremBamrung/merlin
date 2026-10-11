"""The chat-first home's digest — what's new since the client's last visit.

Calls exactly one `merlin.services.home` function and returns its dict.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from merlin.services import home as home_service

from ..schemas import HomeResponse

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/home", response_model=HomeResponse)
def home(since: datetime | None = None):
    """`since` = the client's last visit (ISO 8601); defaults to 24 hours ago."""
    return home_service.digest(since or datetime.now(UTC) - timedelta(hours=24))
