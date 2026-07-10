"""Bounded, rate-limited, progress-reporting parallel map for bulk LLM jobs.

Ingestion runs one LLM call per background task, so it never needed this. Every
*non-ingestion* bulk job does: topic backfill classifies ~1,100 items, and the
clustering pipeline fires ~24 chunk-calls at cold start. Running those serially
is needlessly slow; running them unbounded risks provider 429s. `parallel_map`
is the one place that concurrency + rate-limiting + progress + cooperative
cancellation live, so every such job gets identical, tested behaviour.

Design notes:
- Workers run `fn(item)` on a `ThreadPoolExecutor`; each calls `limiter.wait()`
  before its LLM call so the process-wide min-interval spacing holds across
  threads (`MinIntervalRateLimiter` is already thread-safe).
- 429 handling reuses the limiter's cooldown circuit breaker: a worker that hits
  a rate-limit error trips the cooldown (doubling backoff), sleeps, and retries;
  sibling threads observe `in_cooldown()` and hold off rather than pile on.
- Progress is reported from the **consuming (calling) thread only** — never from
  workers — so progress writes stay single-threaded, matching the task queue's
  `report()` contract.
- Cancellation is cooperative: `report()` raises `TaskCancelled` at each
  completion checkpoint; we stop consuming and shut the pool down. In-flight
  calls drain (same semantics as ingest).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import TypeVar

from merlin.core.logging import logger
from merlin.core.rate_limit import MinIntervalRateLimiter
from merlin.core.task_queue import TaskCancelled

T = TypeVar("T")
R = TypeVar("R")


def _is_rate_limit_error(exc: Exception) -> bool:
    """Best-effort: does this exception look like a provider rate-limit / 429?"""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status == 429:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


def parallel_map(
    items: Iterable[T],
    fn: Callable[[T], R],
    *,
    concurrency: int,
    limiter: MinIntervalRateLimiter,
    report: Callable[[int, str], None] | None = None,
    label: str = "Processing",
    progress_range: tuple[int, int] = (0, 100),
    max_retries: int = 4,
    should_cancel: Callable[[], bool] | None = None,
    on_result: Callable[[int, R | None], None] | None = None,
) -> list[R | None]:
    """Run ``fn`` over ``items`` concurrently, rate-limited and progress-tracked.

    Returns results in **input order** (not completion order). An item whose
    ``fn`` raises after exhausting retries yields ``None`` in its slot (the whole
    map never aborts on one bad item — the caller filters). ``report(pct, msg)``,
    when given, is called on the consuming thread at each completion, mapping
    ``done/total`` into ``progress_range``; it may raise ``TaskCancelled`` to
    cancel, at which point the pool is shut down and the exception re-raised.

    ``on_result(index, result)`` is invoked on the consuming thread as each item
    finishes — **before** the cancel checkpoint — so a caller can accumulate
    partial results that survive a mid-run cancel (the raised ``TaskCancelled``
    otherwise discards the returned list). It fires once per item, in completion
    order, never from a worker thread.
    """
    items = list(items)
    total = len(items)
    if total == 0:
        return []
    lo, hi = progress_range
    concurrency = max(1, concurrency)

    def worker(item: T) -> R:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            # A sibling thread's 429 tripped the cooldown — hold off rather than
            # hammer the upstream and prolong the block.
            while limiter.in_cooldown():
                time.sleep(min(limiter.cooldown_remaining() + 0.05, 5.0))
            limiter.wait()
            try:
                result = fn(item)
                limiter.clear_cooldown()
                return result
            except Exception as exc:  # noqa: BLE001 - retried or re-raised below
                last_exc = exc
                if _is_rate_limit_error(exc) and attempt < max_retries:
                    backoff = limiter.trip_cooldown()
                    logger.warning(
                        "parallel_map: rate-limited (attempt %d/%d), backing off %.1fs",
                        attempt + 1,
                        max_retries,
                        backoff,
                    )
                    time.sleep(backoff or 1.0)
                    continue
                raise
        # Unreachable in practice (loop returns or raises), but keep types happy.
        raise last_exc  # type: ignore[misc]

    results: list[R | None] = [None] * total
    done = 0
    with ThreadPoolExecutor(
        max_workers=concurrency, thread_name_prefix="merlin-llm"
    ) as executor:
        futures = {executor.submit(worker, item): i for i, item in enumerate(items)}
        try:
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception:  # noqa: BLE001 - one bad item ≠ abort the batch
                    logger.warning(
                        "parallel_map: item %d (%s) failed permanently",
                        idx,
                        label,
                        exc_info=True,
                    )
                    results[idx] = None
                done += 1
                if on_result:
                    # Fire before the cancel checkpoint so accumulated partial
                    # results survive a mid-run TaskCancelled.
                    on_result(idx, results[idx])
                if should_cancel and should_cancel():
                    raise TaskCancelled()
                if report:
                    # May raise TaskCancelled — propagate after shutting down.
                    pct = lo + int((hi - lo) * done / total)
                    report(pct, f"{label} {done}/{total}")
        except TaskCancelled:
            executor.shutdown(cancel_futures=True)
            raise
    return results
