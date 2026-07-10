# Backfill Endpoint + Button — Implementation Plan

Make topic/tag organisation of the existing library reachable entirely from the
frontend (no manual scripts on the NAS), with **parallel, rate-limited,
progress-tracked** LLM calls for every non-ingestion bulk job.

Companion to `docs/TOPICS_AND_TAGS_PLAN.md` (the feature) and
`docs/TOPICS_AND_TAGS_HANDOFF.md` (what shipped). This is the follow-up that
closes the "you still have to SSH in and run a script" gap.

## Constraints

1. **Zero manual scripts on the NAS.** Everything runs from the frontend at
   runtime, or automatically on Docker boot. LLM work must **not** run at Docker
   *build* (no DB/creds at build time, and 1100 LLM calls must not be baked into
   an image). "During build in docker" applies only to migrations, which already
   run via `alembic upgrade head` on the `api` service's boot command.
2. **Non-ingestion LLM calls run in parallel**, with a live progress bar, and are
   safe against provider rate limits.

## Decisions

- **Seed → Option A: rely on Organise, no seed.** For an existing ~1100-item
  library, the batch proposal pipeline (`Organise`) derives topics from the real
  content — strictly better than a hardcoded seed list, and already built. No new
  seed code. `scripts/seed_topics.py` stays as an optional CLI convenience only.
- **`llm_usage` cost tracking → folded in.** A UI-triggered ~1100-call run makes
  invisible cost unacceptable, so classify calls record a `surface="classify"`
  usage row (see Part G).

## What already exists vs. what this adds

- ✅ **Clustering leftovers** (`POST /api/topics/proposals`) — already a button with task polling.
- ✅ **Migrations** — already auto-run on Docker boot.
- ➕ **Backfill** — new endpoint + button (the real gap).
- ➕ **Parallelism + rate limiting** — new shared helper, applied to backfill *and*
  retrofitted onto clustering (its ~24 chunk-calls at cold start are currently sequential).

---

## Part A — shared parallel LLM helper (new)

**New file `merlin/core/parallel_llm.py`** — one bounded, rate-limited,
progress-reporting map used by every non-ingestion bulk LLM job.

```
parallel_map(items, fn, *, concurrency, limiter, report=None, label="Processing",
             should_cancel=None) -> list[result]
```

- `ThreadPoolExecutor(max_workers=concurrency)` submits `fn(item)` per item.
- Each worker calls `limiter.wait()` before its LLM call (process-wide min-interval
  spacing across all threads — `MinIntervalRateLimiter` is already thread-safe).
- **429 handling** via the limiter's circuit breaker: worker catches a rate-limit
  error → `limiter.trip_cooldown()` (returns backoff seconds, doubling on repeat)
  → sleep → retry up to `max_retries`; a clean call `clear_cooldown()`s. Other
  threads see `in_cooldown()` and hold off.
- **Progress**: results consumed with `as_completed` **on the calling (task)
  thread only** — `report(pct, f"{label} {done}/{total}")` is called there, never
  from worker threads, so progress writes stay single-threaded.
- **Cancellation**: `report()` already raises `TaskCancelled` at each completion
  checkpoint; on cancel we stop consuming and `executor.shutdown(cancel_futures=True)`.
  In-flight calls finish (same cooperative semantics as ingest).

## Part B — config knobs (`merlin/config.py`)

```
classify_concurrency: int = 4          # CLASSIFY_CONCURRENCY — parallel LLM calls
classify_min_interval: float = 0.0     # CLASSIFY_MIN_INTERVAL — seconds between calls
classify_cooldown_seconds: float = 20.0  # 429 backoff base
classify_max_retries: int = 4
```

Conservative defaults (concurrency 4, no forced spacing) so it's safe out of the
box; all env-driven, tunable per provider without a redeploy.

## Part C — backfill service (`merlin/services/topics.py`)

New `backfill_topics() -> str`, structured exactly like `propose_topics()`:

```python
def backfill_topics() -> str:
    def work(task_id, report):
        report(2, "Gathering uncategorised items…")
        # collect uncategorised item ids (TopicRepository.uncategorised_items)
        # if none → set_completed({"count": 0}) and return
        # limiter = MinIntervalRateLimiter(classify_min_interval, cooldown_seconds=…)
        # parallel_map(ids, classify_and_persist, concurrency=…, limiter=…,
        #              report=report, label="Classified")
        # set_completed({"classified": n, "still_uncategorised": remaining})
    return task_queue.submit_callable(work, task_type="backfill_topics", input_data={})
```

- `classify_and_persist` is reused **unchanged** — it opens its own short-lived
  sessions, keeps the slow LLM call *outside* the write transaction (small write
  window), skips user-assigned items, and is best-effort. Safe for parallel use.
- `scripts/backfill_topics.py` stays as a CLI fallback (can be reduced to calling
  the service).

## Part D — parallelize clustering (`merlin/services/classify.py`)

`propose_clusters` runs `_cluster_chunk` sequentially over ~24 chunks at cold
start. Swap that loop to `parallel_map(chunks, _cluster_chunk, …)` with the same
limiter; progress reporting moves into the helper. The consolidation second-pass
stays a single call. → cold-start Organise goes from ~24 serial calls to 4-wide.

## Part E — API (`api/routers/topics.py` + `api/schemas.py`)

Mirror the proposals endpoint:

```python
@router.post("/backfill", response_model=TaskIdResponse, status_code=202)
def backfill_topics():
    return {"task_id": topics_service.backfill_topics()}
```

No new schema (reuses `TaskIdResponse`). Regenerate `web/src/lib/api/schema.d.ts`
from the running server afterward.

## Part F — Frontend (`web/src/hooks/useTopics.ts`, `web/src/routes/topics.tsx`)

- `useTopics.ts`: add `useBackfill()` mutation → POST, then poll the task via the
  same task-progress mechanism the proposals use; on completion invalidate
  `keys.topics()` + `keys.uncategorisedCount()` + `keys.items()`.
- `topics.tsx`: a **"Classify N uncategorised →"** button next to "Organise",
  behind a confirm dialog stating *"This makes ~N LLM calls and costs money"*
  (shows the uncategorised count). Show the propose task's progress bar while
  running. Disable both Backfill and Organise while either task runs.
- Keep the conceptual split visible: **Organise** = discover *new* topics;
  **Backfill** = fit items to *existing* topics.

## Part G — cost visibility (folded in)

Add a `surface="classify"` `llm_usage` row inside `classify_item` (reuse the
`record_*` helper the ingest/chat paths use), so Insights reflects backfill spend.

---

## Rollout — fully frontend after deploy

1. `git push` → NAS rebuilds → `alembic upgrade head` runs automatically (009 +
   010). All items = Uncategorised, tags untouched. Nothing else auto-runs.
2. Open **Topics** → **Organise** → review/accept proposals (bootstraps taxonomy
   + assigns most items).
3. **Backfill** → parallel-classifies the remaining uncategorised against the
   now-existing topics, with a progress bar.

No SSH, no scripts.

## Risks & mitigations

- **SQLite write contention** under parallel writes → mitigated by existing
  `busy_timeout=5000` + classify's tiny write window (LLM call outside the
  transaction). Keep concurrency modest (4); lower it if lock warnings appear.
- **Provider 429** → limiter cooldown circuit-breaker + bounded concurrency + retries.
- **Runaway cost** → confirm dialog shows call count; Part G surfaces actual spend.
- **Cancellation** → reuse the task-cancel path; in-flight calls drain.

## Testing

- `parallel_map`: unit test with a fake `fn` (ordering, retry-on-simulated-429 via
  a limiter, cancel stops consumption).
- `backfill_topics`: task completes, respects user-assigned rows, counts correct —
  mock the LLM (like existing `test_classify.py`).
- Clustering still passes `test_topic_proposals.py` after the parallel swap.
- Frontend: typecheck/lint/build; manual screenshot of the Topics page with the
  new button + progress.
