"""Insights endpoints — aggregate stats for the dashboard charts (Tier 1).

Thin pass-throughs to `merlin.services.library` aggregate queries.
"""

from __future__ import annotations

from fastapi import APIRouter

from merlin.services import library, usage

from ..schemas import CountResponse, NameCount, TimelinePoint, UsageResponse

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/timeline", response_model=list[TimelinePoint])
def timeline():
    return library.ingest_timeline()


@router.get("/top-channels", response_model=list[NameCount])
def top_channels(limit: int = 12):
    return library.top_channels(limit)


@router.get("/status-counts", response_model=list[NameCount])
def status_counts():
    return library.status_counts()


@router.get("/channel-count", response_model=CountResponse)
def channel_count():
    return {"count": library.count_channels()}


@router.get("/usage", response_model=UsageResponse)
def usage_spend():
    """LLM/transcription spend — totals + daily (by surface) + per-surface/model.

    Visibility only; nothing here gates spend. Cost is provider-reported where
    available, else computed, else omitted (unknown models contribute $0 to sums
    but are visible as calls).
    """
    return {
        "total": usage.total_spend(),
        "by_day": usage.spend_by_day(),
        "by_surface": usage.spend_by_surface(),
        "by_model": usage.spend_by_model(),
    }
