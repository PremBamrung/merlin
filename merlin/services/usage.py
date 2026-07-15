"""Usage / cost service — record LLM spend and read it back for Insights.

`record()` is the single write seam: every spend site (chat `on_complete`,
ingest `persist_result`) calls it with whatever counts it has. It computes a
cost (preferring a provider-reported `cost_usd`, else the `llm_pricing` map, else
NULL) and writes one `llm_usage` row. **It never raises** — cost tracking must
not break the operation it's measuring (a failed insert is logged and swallowed).

The aggregate readers return plain dicts (never ORM objects) for the API layer.
Spend is **visibility only** — nothing here gates or throttles.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import func

from merlin import llm_pricing
from merlin.config import settings
from merlin.core.logging import logger
from merlin.db.engine import SessionFactory
from merlin.db.models import LlmUsage


def record(
    *,
    surface: str,
    provider: str | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_read_tokens: int | None = None,
    audio_seconds: float | None = None,
    requests: int = 1,
    cost_usd: float | None = None,
    knowledge_item_id: str | None = None,
    meta: dict | None = None,
) -> None:
    """Write one usage row. Computes cost when not supplied. Never raises."""
    try:
        if cost_usd is None:
            cost_usd = llm_pricing.cost(
                provider,
                model,
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
                cache_read_tokens=cache_read_tokens or 0,
                audio_seconds=audio_seconds or 0.0,
            )
        with SessionFactory() as session:
            session.add(
                LlmUsage(
                    id=str(uuid.uuid4()),
                    surface=surface,
                    provider=provider,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read_tokens,
                    audio_seconds=audio_seconds,
                    requests=requests,
                    cost_usd=cost_usd,
                    knowledge_item_id=knowledge_item_id,
                    meta=json.dumps(meta) if meta else None,
                )
            )
            session.commit()
    except Exception:  # pragma: no cover - defensive; tracking is best-effort
        logger.warning(
            "Failed to record llm_usage (surface=%s)", surface, exc_info=True
        )


def fetch_openrouter_cost(generation_id: str | None) -> float | None:
    """Authoritative USD cost for a single OpenRouter generation, or None.

    The chat path's SDK (Pydantic AI) doesn't surface OpenRouter's billed cost,
    but every response carries a `gen-…` id whose exact cost is available from
    the /generation endpoint. The stats lag the stream noticeably — empirically
    ~10-15s for a streamed call (the endpoint 404s until then) — so this polls
    patiently; it runs in a background task, never on the request path. Best-effort
    — returns None on persistent failure (caller stores NULL, which Insights shows
    as "unknown", never a fabricated $0).

    Timing: the 404 wait path is ~30s (15 × 2s). A pathological all-timeout path
    is longer (each attempt also burns the 8s request timeout) but only ever ties
    up a background thread, never the request.
    """
    if not generation_id or not settings.openrouter_api_key:
        return None
    import time

    import requests

    url = f"{settings.openrouter_endpoint}/generation"
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    # ~30s total: stats are usually ready by ~15s; give margin without hanging.
    attempts = 15
    for attempt in range(attempts):
        try:
            resp = requests.get(
                url, headers=headers, params={"id": generation_id}, timeout=8
            )
            if resp.status_code == 404:  # stats not ready yet — wait and retry
                time.sleep(2.0)
                continue
            resp.raise_for_status()
            cost = (resp.json() or {}).get("data", {}).get("total_cost")
            return float(cost) if cost is not None else None
        except Exception:
            if attempt == attempts - 1:
                logger.warning(
                    "OpenRouter cost fetch failed for %s",
                    generation_id,
                    exc_info=True,
                )
            time.sleep(2.0)
    return None


def fetch_openrouter_costs(
    generation_ids: list[str] | None,
) -> tuple[float | None, bool]:
    """Summed authoritative USD cost across *all* of a turn's generations.

    A chat turn can span several model round-trips (the agent's tool loop), each
    with its own generation id — so billing it at only the final generation
    undercounts. We sum every id's reported cost.

    Returns ``(total, complete)``; ``complete`` is False if any id couldn't be
    priced (provider lag / network), so the caller can fall back to an estimate
    rather than persist a misleadingly low partial sum. Earlier generations in a
    loop are already settled by the time the last one is queried, so the patient
    polling cost is ~one lag-wait, not one per id.
    """
    ids = [g for g in (generation_ids or []) if g]
    if not ids or not settings.openrouter_api_key:
        return None, False
    total = 0.0
    complete = True
    for gid in ids:
        c = fetch_openrouter_cost(gid)
        if c is None:
            complete = False
        else:
            total += c
    return total, complete


def record_chat_turn(
    *,
    model: str,
    generation_ids: list[str] | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_tokens: int | None = None,
    requests: int = 1,
    item_id: str | None = None,
    meta: dict | None = None,
) -> None:
    """Record one chat turn, summing OpenRouter's actual cost across the turn.

    Meant to run as a background task (the cost fetch may retry), so it never
    delays the streamed answer. Sums the provider-reported cost over every
    generation in the turn. If the provider can't price all of them, falls back
    to a pricing-map estimate on the turn's aggregate tokens — cache-aware, so
    the cached portion is billed at the discounted rate (flagged in meta as
    ``cost_estimated``) — and NULL when even that is unavailable (unknown model).
    Token counts are always captured regardless.
    """
    cost, complete = fetch_openrouter_costs(generation_ids)
    estimated = False
    if not complete:
        # Don't keep a partial sum — estimate the *whole* turn from its tokens so
        # the recorded cost matches the (aggregate) token counts beside it.
        cost = llm_pricing.cost(
            "openrouter",
            model,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            cache_read_tokens=cache_read_tokens or 0,
        )
        estimated = cost is not None
    ids = [g for g in (generation_ids or []) if g]
    extra: dict = {}
    if ids:
        extra["generation_ids"] = ids
    if estimated:
        extra["cost_estimated"] = True
    merged = {**(meta or {}), **extra}
    record(
        surface="chat",
        provider="openrouter",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        requests=requests,
        cost_usd=cost,
        knowledge_item_id=None,  # reader-chat cost is not the item's ingest cost
        meta=merged or None,
    )


# ------------------------------------------------------------------
# Aggregate reads (Insights). Cost sums treat NULL cost as 0 in the total but
# the row count of priced-vs-unpriced is surfaced separately as needed.
# ------------------------------------------------------------------


def total_spend() -> dict:
    """Library-wide totals across every recorded call."""
    with SessionFactory() as session:
        row = session.query(
            func.coalesce(func.sum(LlmUsage.input_tokens), 0),
            func.coalesce(func.sum(LlmUsage.output_tokens), 0),
            func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
            func.count(LlmUsage.id),
        ).one()
    return {
        "tokens_in": int(row[0]),
        "tokens_out": int(row[1]),
        "cost_usd": float(row[2]),
        "calls": int(row[3]),
    }


def spend_by_day() -> list[dict]:
    """Daily cost split by surface — the stacked Insights chart's source."""
    with SessionFactory() as session:
        rows = (
            session.query(
                func.date(LlmUsage.created_at).label("day"),
                LlmUsage.surface,
                func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
            )
            .group_by("day", LlmUsage.surface)
            .order_by("day")
            .all()
        )
    return [
        {"date": day, "surface": surface, "cost_usd": float(cost)}
        for day, surface, cost in rows
        if day
    ]


def spend_by_surface() -> list[dict]:
    with SessionFactory() as session:
        rows = (
            session.query(
                LlmUsage.surface,
                func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
                func.count(LlmUsage.id),
            )
            .group_by(LlmUsage.surface)
            .all()
        )
    return [
        {"surface": surface, "cost_usd": float(cost), "calls": int(calls)}
        for surface, cost, calls in rows
    ]


def spend_by_model() -> list[dict]:
    with SessionFactory() as session:
        rows = (
            session.query(
                LlmUsage.model,
                func.coalesce(func.sum(LlmUsage.cost_usd), 0.0),
                func.count(LlmUsage.id),
            )
            .group_by(LlmUsage.model)
            .order_by(func.sum(LlmUsage.cost_usd).desc())
            .all()
        )
    return [
        {"model": model or "unknown", "cost_usd": float(cost), "calls": int(calls)}
        for model, cost, calls in rows
    ]


def cost_for_item(item_id: str) -> float | None:
    """Total recorded cost attributable to one knowledge item (ingest spend).

    None when the item has no priced rows — older items predate tracking, so
    "unknown" must not read as "free".
    """
    with SessionFactory() as session:
        row = (
            session.query(
                func.sum(LlmUsage.cost_usd),
                func.count(LlmUsage.id),
            )
            .filter(LlmUsage.knowledge_item_id == item_id)
            .one()
        )
    total, count = row
    if not count or total is None:
        return None
    return float(total)
