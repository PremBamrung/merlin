"""Unified search — hybrid keyword + meaning over the library (⌘K, Library box).

Calls exactly one `merlin.services.search` function and returns its dict.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from merlin.services import search as search_service

from ..schemas import SearchResponse

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = "",
    limit: int = Query(default=search_service.MAX_RESULTS, ge=1, le=20),
    source_type: str | None = None,
):
    return search_service.search(q, limit=limit, source_type=source_type)
