# Merlin — Streamlit Migration Plan (v2)

> Supersedes `PLAN.md`. Corrected against the actual codebase on `develop`
> (verified file/line references throughout) and updated for Streamlit 1.58
> (May 2026) features and practices.

## Decision summary

Migrate the UI back to **Streamlit**, but **do not run the FastAPI web server**.
Instead, run a single **Streamlit (Starlette/Uvicorn) process** that **imports
`backend/` as a Python library** and calls its logic in-process. Add a
file-based **Karpathy wiki layer** for compounding cross-source knowledge.

**Why this over the original `PLAN.md` (Streamlit → HTTP → FastAPI hybrid):**

- The backend's *logic* is not coupled to FastAPI. Verified: only `backend/api/*`
  and `backend/main.py` import FastAPI. The plugin system
  (`knowledge_sources/`), task queue (`core/`), RAG retriever (`rag/`), DB layer
  (`db/`), and config + LLM wiring (`config.py`) are **FastAPI-free, importable
  Python**.
- For a single-user, single-machine tool, an HTTP boundary between two Python
  processes you own buys nothing — it only adds serialization, CORS, Pydantic
  schemas, SSE encode/decode, and an API contract to keep in sync. (The original
  plan's chat snippet already had the contract wrong: it used `GET` with params,
  but `backend/api/chat.py:54` is `POST` with a JSON body.)
- Calling `settings.llm.stream(...)` in-process makes the chat **SSE adapter
  disappear entirely** — `st.write_stream` consumes the token generator directly.
- One process, one port, one container, one language.

**Keep the backend logic as a library — do not delete it.** Drop only the web
layer (`backend/api/*`, `backend/main.py`, uvicorn, the second Docker service).

**Rename + separate concerns.** Once there is no separate backend *service*, the
name `backend/` is misleading. Rename it to **`merlin/`** (reclaiming the name
from the deleted legacy package) — the core, framework-agnostic library — and put
the Streamlit UI **outside** it in **`ui/`**. The dependency rule is one-way:

> `ui/` imports `merlin/`. `merlin/` never imports `ui/` and never imports
> `streamlit`. Orchestration glue that used to live in the FastAPI routers moves
> into a new `merlin/services/` application layer, so the UI stays thin
> (presentation only) and the core stays reusable.

> **Wiki layer is deferred.** This plan targets a working Streamlit app first
> (Steps 0–4, 7). The wiki layer (Steps 5–6) is documented below but is a later
> phase — skip it on the first pass.

---

## Database schema assessment

**No schema changes are required for this migration.** Explicitly:

- The Streamlit app imports the **same `db/models.py`**, uses the **same SQLite
  database** (`settings.database_url`), and runs the **same Alembic migrations**
  that already exist (paths shown post-rename; `backend/db/...` before Step 0):
  - `merlin/db/migrations/versions/001_init_knowledge_base.py` — core tables +
    the `knowledge_fts` FTS5 virtual table and its INSERT/UPDATE/DELETE sync
    triggers (hand-written SQL). The migration body uses only `from alembic import
    op` — it does **not** reference the package name, so the rename leaves its
    contents untouched (only `script_location` in `alembic.ini` changes).
  - `merlin/db/migrations/versions/002_add_share_tokens_digest_actions.py`.
- **No table is coupled to the web layer.** `knowledge_items`, `youtube_metadata`,
  `background_tasks`, `embeddings`, `share_tokens`, `digest_actions` are all
  source/UI-agnostic. The FTS5 triggers stay valid because writes still go
  through the same models/repositories.
- The **wiki layer is markdown files on disk, not the DB** — it adds no tables
  and no migration.
- `embeddings` remains reserved for Phase 3 (unused) — unaffected.

**`engine.py` is already Streamlit-safe.** `engine` and `SessionFactory` are
module-level singletons (`db/engine.py:14,30`) created with
`check_same_thread=False` and `PRAGMA journal_mode=WAL` + `foreign_keys=ON`.
That handles concurrent UI reads (progress polling) alongside worker-thread
writes. Keep WAL.

**Optional, not required:**

- One-time **data backfill** from the legacy `merlin` schema
  (`youtube_video_summary`, a single denormalized table) into `knowledge_items`
  + `youtube_metadata`, if you want old Streamlit-era data visible in the new
  app. This is a standalone script, not a schema change.
- Per `CLAUDE.md`: any *future* FTS/trigger changes must be hand-written SQL
  (Alembic can't autogenerate them). None needed now.

**Session discipline in Streamlit (important):** cache the *engine/factory* (it's
already a module singleton — importing it is enough), but **never cache a live
`Session`** in `st.session_state` or `st.cache_resource`. Open a short-lived
session per action via `get_db()` (`db/engine.py:33`).

---

## Target architecture

```
   ┌────────────────────────────────────────────────────────────────┐
   │  Single Streamlit process (Starlette/Uvicorn) — port 8501        │
   │  streamlit run app.py                                            │
   │                                                                  │
   │   ui/  (frontend — presentation only)                            │
   │     views/{today,ingest,library,chat}.py                         │
   │            │  collect widget input → call a service → render     │
   │            ▼                                                      │
   │   merlin/services/  (application layer — no streamlit, no http)  │
   │     ingest.submit_ingest()   chat.answer()   library.search()    │
   │            │                                                      │
   │            ▼                                                      │
   │   merlin/  (core library)                                        │
   │     knowledge_sources/registry · core/task_queue · rag/retriever │
   │     db/repositories · config.settings.llm                        │
   │            │                                                      │
   │   ThreadPoolExecutor (3 workers, module singleton)               │
   │            └── progress ──▶ SQLite (data/merlin.db, FTS5)         │
   └────────────────────────────────────────────────────────────────┘

Dependency rule:  ui ──▶ merlin.services ──▶ merlin.{core,db,rag,...}
                  (merlin never imports ui or streamlit)

Storage:
  SQLite  (data/merlin.db)  — items, metadata, tasks, FTS5  (unchanged)
  wiki/*.md                 — deferred (later phase)
```

---

## Streamlit version & practices (target: `streamlit>=1.58`)

`main` currently pins `streamlit>=1.51`. Pin **`>=1.58`** (latest is 1.58.0,
2026-05-28). Use these 2026 features to avoid the classic rerun/threading pain:

| Use case | Feature | Ver |
|---|---|---|
| Page structure (replace `pages/01_*.py` file convention) | `st.navigation` + `st.Page` (code-defined, `expanded` param) | 1.56 |
| Isolate reruns; concurrent background-style UI | `@st.fragment`, **`parallel=True`** | 1.58 |
| Auto-refresh task progress without rerunning the page | `@st.fragment(run_every=2)` | — |
| Pinned chat input / filter toolbar | `st.bottom` | 1.57 |
| Streaming chat output that scrolls | `st.container(autoscroll=True)` + `st.write_stream` | 1.56 |
| Library paging (replaces manual page/page_size) | `st.pagination` | 1.58 |
| Item detail / inbox-review modals | `st.dialog` (`icon`) | 1.53 |
| Per-item action menus | `st.menu_button` | 1.56 |
| Embed the YouTube player | `st.iframe` | 1.56 |
| Deep-linkable filtered Library / wiki pages | widget `bind` to query params | 1.55 |
| Clean shutdown of the executor / engine | `st.cache_resource(on_release=...)` | 1.53 |
| Friendly error surface | `st.App` custom exception handler | 1.58 |
| Public share links in the same process | `st.App` ASGI custom routes (**experimental**) | 1.53 |

**Do not** use the legacy `pages/NN_Name.py` auto-discovery; define navigation in
code with `st.navigation` so the structure is explicit and testable.

---

## Code seams (verified against the repo)

> Paths below are **post-rename** (`merlin/...`); the "today" location under
> `backend/...` is noted where the code already exists. The orchestration glue
> that lived in the deleted FastAPI routers lands in **`merlin/services/`**, never
> in `ui/`.

### 1. Task queue — add a synchronous submit
`task_queue.enqueue_ingest()` is `async` and dispatches via
`asyncio.get_event_loop().run_in_executor(...)`
(today `backend/core/task_queue.py:62`). Streamlit has no always-running event
loop in the script thread. `_run_ingest` itself is already synchronous, so add a
sync entry point:

```python
# merlin/core/task_queue.py  (new method on TaskQueue)
def submit_ingest(self, plugin, raw_input, options, on_complete) -> str:
    task_id = str(uuid.uuid4())
    with SessionFactory() as s:
        BackgroundTaskRepository.create(
            s, task_id=task_id,
            task_type=f"ingest_{plugin.source_type}",
            input_data={"raw_input": raw_input, **options},
        )
        s.commit()
    self._executor.submit(self._run_ingest, task_id, plugin, raw_input, options, on_complete)
    return task_id
```
The `task_queue` module singleton (today `task_queue.py:124`) persists across
Streamlit reruns because it's module-level. Cache it via `@st.cache_resource` in
`ui/state.py` only if you want explicit lifecycle control / `on_release` cleanup.

### 2. Plugin registration at startup
`backend/main.py`'s `lifespan` registers plugins into `registry`. Extract into a
reusable function the Streamlit entry point calls once:

```python
# merlin/bootstrap.py  (new)
from merlin.knowledge_sources.registry import registry
from merlin.knowledge_sources.plugins.youtube.plugin import YouTubePlugin

def register_plugins() -> None:
    if not registry.get("youtube"):
        registry.register(YouTubePlugin())
```

### 3. Ingest service — relocate `_persist_result`, wrap in a service
`backend/api/sources/youtube.py:51` (`_persist_result`) is the `on_complete`
callback — plain Python (no FastAPI) that upserts the item + YouTube metadata and
completes the task. It must not be deleted with the API layer: move it into the
application layer and expose a thin service the UI calls.

```python
# merlin/services/ingest.py
from merlin.core.task_queue import task_queue
from merlin.knowledge_sources.registry import registry
# persist_result moved here verbatim from the old router

def submit_ingest(url: str, languages: list[str], summary_length: str) -> str:
    return task_queue.submit_ingest(
        plugin=registry.get("youtube"),
        raw_input=url,
        options={"languages": languages, "summary_length": summary_length},
        on_complete=persist_result,
    )
```
```python
# ui/views/ingest.py  — presentation only
task_id = merlin.services.ingest.submit_ingest(url, langs, length)
```
The full language list already exists as `LANGUAGE_MAP` (~40 langs) in
`knowledge_sources/plugins/youtube/plugin.py:27` — drive the selectbox from it.
(Fix the pre-existing retry bug at `youtube.py:170`, which hardcodes `["en","fr"]`
and discards the user's language choice — fold the fix into this service.)

### 4. Chat service — direct streaming, no SSE
```python
# merlin/services/chat.py  — no streamlit, no http
from merlin.config import settings
from merlin.db.engine import get_db
from merlin.rag.retriever import HybridRetriever
from merlin.rag.prompts import MERLIN_SYSTEM_PROMPT, format_context

_retriever = HybridRetriever()

def answer(question, history, filters):
    with get_db() as db:
        chunks = _retriever.retrieve(
            db, query=question,
            source_types=filters.get("source_types"),
            tag_filters=filters.get("tags"), top_k=5,
        )
    msgs = [
        {"role": "system", "content": MERLIN_SYSTEM_PROMPT.format(context=format_context(chunks))},
        *history,
        {"role": "user", "content": question},
    ]
    def gen():
        for c in settings.llm.stream(msgs):
            yield c.content if hasattr(c, "content") else str(c)
    return gen(), chunks   # citations from `chunks`, no out-of-band event
```
```python
# ui/views/chat.py  — presentation only
gen, chunks = merlin.services.chat.answer(q, history, filters)
with st.chat_message("assistant"):
    with st.container(autoscroll=True):
        st.write_stream(gen)
    render_citations(chunks)
```

### 5. Progress polling — a self-refreshing fragment (UI side)
```python
# ui/components/task_panel.py
@st.fragment(run_every=2)
def task_panel():
    tasks = merlin.services.ingest.recent_tasks(limit=10)   # service wraps the repo
    for t in tasks:
        st.progress((t["progress"] or 0) / 100, text=t["message"] or t["status"])
```

---

## The Karpathy wiki layer

File-based, git-versionable, Obsidian-compatible markdown under `wiki/`. The LLM
(same `settings.llm`) maintains it. Three operations: **ingest** (automatic),
**query** (chat can load wiki pages as context), **lint** (manual button, or
`cd wiki/ && claude` for interactive work).

**Run it as a separate task after ingest — not inline — and serialize it.**
Two reasons, both verified:
- The pool has **3 workers** (`task_queue.py:124`). Two ingests finishing close
  together would read-modify-write the same `wiki/*.md` page concurrently → lost
  updates / corruption.
- An LLM rewrite per ingest adds latency/cost to the critical path.

```python
# merlin/wiki/updater.py
import threading
_wiki_lock = threading.Lock()      # serialize all wiki writes

def update_wiki(result) -> None:
    with _wiki_lock:
        # 1. read wiki/index.md
        # 2. find relevant pages (keyword match, then LLM)
        # 3. load them; LLM merges new content into existing pages
        # 4. write pages back; update index.md; append wiki/log.md
        # 5. git add/commit the wiki dir  ← every change is a revertible diff
        ...
```
- Trigger it from `persist_result` *after* `session.commit()`, ideally by
  enqueuing a second background task so a wiki failure never fails the ingest.
- **Auto-commit each wiki write** (`wiki/` is a git repo or a tracked subtree) so
  a bad LLM generation is always recoverable. This is the only real protection
  against the model clobbering hand-edited pages.
- Streamlit wiki page: render markdown, parse `[[wikilinks]]` into nav buttons,
  build a backlinks panel, and a graph view. Note there are **two** possible
  graphs — the existing **tag co-occurrence** graph (computable from the tag data
  in the repositories; logic was in the deleted `graph.py` router) and the new
  **wikilink** graph.
  Render either with `streamlit-agraph` (caveat: lightly maintained — fall back
  to a static backlinks list if it breaks).

---

## Project layout

```
app.py                       # entry: register_plugins(); st.navigation([...]).run()

merlin/                      # ── CORE LIBRARY ── never imports streamlit or ui
  config.py                  #   Settings, settings.llm           (was backend/config.py)
  bootstrap.py               #   register_plugins()               (new; from main.py lifespan)
  core/                      #   task_queue (+ submit_ingest), rate_limit, logging
  db/                        #   engine, models, repositories, migrations (FTS5 intact)
  knowledge_sources/         #   plugin system + youtube plugin
  rag/                       #   retriever, prompts
  services/                  #   ── APPLICATION LAYER (new) ── no streamlit, no http
    ingest.py                #     submit_ingest(), persist_result, recent_tasks()
    chat.py                  #     answer(q, history, filters) -> (token_gen, citations)
    library.py               #     list/search/get/update/delete -> plain dicts
  wiki/                      #   (deferred) updater.py

ui/                          # ── FRONTEND ── imports merlin.services, never imported by merlin
  views/
    today.py                 #   recency dashboard (replaces TodayPage + Digest)
    ingest.py                #   YouTube form (port pages/01_Youtube.py UX)
    library.py               #   grid + search + tag/status filter + st.pagination (= Inbox)
    chat.py                  #   st.write_stream, citations, st.bottom input
    wiki.py                  #   (deferred)
  components/                #   item_card, citation_list, task_panel
  state.py                   #   cached resources, session_state helpers

wiki/                        # (deferred) markdown knowledge base, git-tracked
tests/
  test_architecture.py       #   asserts merlin/ never imports streamlit (boundary guard)
```

**Dependency rule (enforced by a test):** `ui/` → `merlin.services` →
`merlin.{core,db,rag,knowledge_sources}`. `merlin/` must never `import streamlit`
nor import from `ui/`. A one-line grep test in `tests/test_architecture.py` keeps
the boundary from rotting.

**Pages are callables, not the `pages/NN_*.py` convention** — `st.navigation`
takes `st.Page(view.render, ...)`, keeping every view importable and testable.

`Inbox` collapses into Library with a `status` filter (there was **no** backend
inbox router — it was always a `GET /api/knowledge?status=...` view). `Digest` is
a placeholder backend (`digest.py:36` hardcodes `match_score=1.0`,
`why="Recently added"`) so it folds into the Today recency view with no real
loss.

---

## Build order

| Step | What | Notes |
|---|---|---|
| 0a | **Rename** `git mv backend merlin`; find/replace `backend.` → `merlin.`; fix `alembic.ini` `script_location = merlin/db/migrations` + `migrations/env.py`; update `pyproject.toml`/`pytest.ini` | Mechanical; tests should still pass |
| 0b | Add `merlin/bootstrap.py`; add `TaskQueue.submit_ingest`; create `merlin/services/` and move `_persist_result` into `services/ingest.py` | Library-ization; no behavior change |
| 1 | `app.py` scaffold — `st.navigation` (callable pages), theme, `register_plugins()`, cached engine/queue in `ui/state.py`; add `tests/test_architecture.py` boundary guard | Foundation |
| 2 | Ingest view — port `pages/01_Youtube.py` UX via `services.ingest`, languages from `LANGUAGE_MAP`, length picker, self-refreshing task panel | Restore what v2 trimmed |
| 3 | Library view — grid + thumbnails + search + tag/status filter + `st.pagination`; `st.dialog` detail (via `services.library`) | |
| 4 | Chat view — `st.write_stream` over `services.chat.answer`, citations, `st.bottom` input, autoscroll | **No SSE** |
| 7 | Single-service Docker; mount `data/`, `.env`, `logs/`; `streamlit run app.py` | NAS-ready |
| — | **Working app reached here.** Everything below is deferred. | |
| 5 | *(deferred)* `merlin/wiki/updater.py` — serialized post-ingest task, git-commit per write | + `services` wrapper |
| 6 | *(deferred)* Wiki view — viewer, wikilinks, backlinks, graph, editor | |
| 8 | *(opt)* Public share links via `st.App` ASGI route | Experimental — gate on maturity |
| 9 | *(opt)* One-time backfill from legacy `youtube_video_summary` | Standalone script |

**Steps 0–4 + 7 = working app.** Wiki (5–6) and share links (8) are later phases.

---

## Deletions / keep / port

**Delete (in this order — the legacy `merlin/` must go *before* `backend/` is renamed to `merlin/`):**
1. `merlin/` (legacy package), `Home.py`, `pages/`, `merlin_cli.py` — legacy Streamlit app
   *(port `pages/01_Youtube.py` UX and backfill data first if wanted)*. This frees the `merlin` name.
2. `backend/api/*`, `backend/main.py` — FastAPI web layer
   *(relocate `_persist_result` into `services/ingest.py` first)*.
3. `frontend/`, `frontend_v2/` — React/Vite app + JSX mockups.

**Keep (becomes the `merlin/` importable library after rename):**
- `backend/config.py`, `backend/core/`, `backend/rag/`, `backend/db/`, `backend/knowledge_sources/`
- `alembic.ini` + `backend/db/migrations/` (FTS5 triggers intact)
- `.env`

**Port (don't delete until ported):**
- `pages/01_Youtube.py` (573 lines) → `ui/views/ingest.py` UX, re-pointed at the v2 pipeline via `services.ingest`

---

## Risks & caveats (stated honestly)

- **`st.App` ASGI custom routes are experimental** (1.53) and `parallel=True`
  fragments are new (1.58). Build the UI on the **stable** set (navigation,
  fragments, `st.bottom`, pagination, dialog) now; treat public share links via
  `st.App` as a later, gated step — validate maturity before betting the feature
  on it. Until then, share links can stay as a tiny standalone FastAPI service or
  be deferred.
- **Wiki corruption** is the main new-failure mode: serialize writes with a lock
  **and** git-commit per write, or the LLM will eventually clobber curated pages.
- **In-flight tasks die on process restart** (true today with FastAPI too — the
  queue is in-process). Records survive as `processing`; add a startup sweep that
  marks stale `processing` rows as `failed` if you want clean recovery.
- **Single process couples UI and ingestion**: a Streamlit hot-reload won't kill
  jobs already submitted to the cached executor, but a full process restart will.
  Acceptable for a personal tool; note it.
- **SQLAlchemy sessions**: open per-action via `get_db()`; never stash a `Session`
  in `st.session_state`.

---

## Open decisions

1. **Share links** — keep the feature (and accept the experimental `st.App`
   route, or run a tiny separate FastAPI just for `/s/{token}`), or drop it?
2. **Legacy data** — backfill `youtube_video_summary` into the v2 schema, or
   start fresh?
3. **Wiki granularity** — pages by topic, by tag, or by source cluster? Decide
   before writing `updater.py`'s "find relevant pages" step.
