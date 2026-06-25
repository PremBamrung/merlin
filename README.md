# 🧙‍♂️ Merlin

Merlin is a personal knowledge-management app: **ingest** content (currently
YouTube videos), **summarise** it with an LLM, **store** it in SQLite, and
**query** it through hybrid RAG and an agentic chat assistant.

It runs as a **FastAPI backend** that serves a **React single-page app** — paste a
URL, let it transcribe + summarise in the background, then browse, read, and chat
with everything you've saved.

## ✨ What you get

| Surface | What it does |
|---|---|
| **Today** | Omnibox to ingest a URL (or ask a question) + live progress and recent items |
| **Feed** | A swipe-to-read queue of unread items; mark read, ★ save, undo |
| **Library / Reader** | Searchable/filterable grid of everything saved; full reading view per item |
| **Chat** | Agentic assistant that searches and reads your library to answer (with sources) |
| **Insights** | Charts: ingestion timeline, top channels, status breakdown |

**Under the hood:** plugin-based ingestion (YouTube today, more sources pluggable),
LLM summarisation (Azure OpenAI or OpenRouter), and **hybrid retrieval** — SQLite
FTS5 keyword search fused with optional Jina vector search + reranking.

## 🏗️ Architecture

The dependency arrow points one way:

```
api/  →  merlin.services  →  merlin.{core, db, rag, knowledge_sources}
web/  (React SPA, built to web/dist, served by FastAPI at /)
```

- **`merlin/`** — framework-agnostic core: config, the plugin-based ingestion
  pipeline, the SQLite data layer + Alembic migrations, and RAG/agentic chat. It
  never imports `fastapi` or `api/` (enforced by `tests/test_architecture.py`).
- **`api/`** — a thin FastAPI skin: routers validate input, call **one**
  `merlin.services` function, and serialise the dict it returns. Serves `/api/*`
  and mounts the built SPA at `/` (same origin → no CORS in prod).
- **`web/`** — Vite + React 19 + React Router + TanStack Query + Tailwind. Chat
  streams over the Vercel AI SDK protocol; everything else uses a typed client
  generated from the backend's OpenAPI schema.

See `CLAUDE.md` and `docs/FRONTEND_V3_PLAN.md` for the full design.

## 🚀 Quick start (Docker — recommended)

```bash
cp .env.example .env        # then fill in your LLM keys (see Configuration)
docker compose up --build   # → http://localhost:8000
```

The `api` container runs `alembic upgrade head` (DB migrations) on start, then
serves the API and the built React SPA from a single process. OpenAPI docs are at
`http://localhost:8000/docs`. The SQLite DB lives in `./data` (a mounted volume),
so it survives rebuilds.

> Code is baked into the image, not bind-mounted — apply code/dependency changes
> with `docker compose up --build` (a plain restart won't pick them up).

## 🧑‍💻 Local development (without Docker)

Python deps are managed with **[uv](https://docs.astral.sh/uv/)** (Python 3.11+);
the frontend uses **npm**.

```bash
# 1. Backend
uv sync
# Point at the local DB (the .env default uses the Docker path) and run it:
DATABASE_URL="sqlite:///$(pwd)/data/merlin.db" \
  uv run uvicorn api.main:app --reload --port 8000

# 2. Frontend (separate terminal) — Vite dev server proxies /api to :8000
cd web && npm install && npm run dev          # → http://localhost:5173

# DB migrations (env.py migrates settings.database_url)
uv run alembic upgrade head
```

Frontend build/check commands (from `web/`): `npm run build` (→ `web/dist`),
`npm run typecheck`, `npm run lint`, `npm run gen:api` (regenerate the typed API
client against a running server's `/openapi.json`).

## 🔧 Configuration

All configuration is via environment variables in `.env` (see `.env.example` for
the full list with comments). The essentials:

- **`LLM_PROVIDER`** — `openrouter` (default) or `azure`; fill in the matching
  block (`OPENROUTER_*` or `AZURE_OPENAI_*`).
- **`GROQ_API_KEY`** — fallback audio transcriber when no YouTube transcript exists.
- **`EMBEDDING_PROVIDER`** — `none` for pure FTS5 keyword search (no API needed),
  or `jina` to enable vector search + reranking (`JINA_*` keys).
- **`DATABASE_URL`** / **`SQLITE_JOURNAL_MODE`** — SQLite path + journal mode. Use
  `DELETE` on a macOS Docker bind mount (WAL is unsafe there); `WAL` is fine and
  faster on a Linux/NAS volume.

> Keep your API keys out of version control — `.env` is gitignored; commit only
> `.env.example`.

## 🧪 Testing & linting

```bash
uv run pytest                          # full suite
uv run pytest tests/backend            # router → service → temp-SQLite tests
uv run pytest tests/test_architecture.py   # the dependency-boundary guard
uv run pytest -m "not requires_azure"  # skip Azure-dependent tests

uv run ruff check .                    # lint
uv run ruff format .                   # format
```

Markers: `requires_azure`, `integration`, `slow`.

## 📁 Repository layout

```
merlin/      Core library (config, ingestion plugins, DB + migrations, RAG/chat)
api/         FastAPI backend — routers, schemas, error envelope, SSE
web/         React SPA (Vite) — routes, components, hooks, generated API client
tests/       pytest suite (incl. tests/backend/ integration tests)
scripts/     Maintenance utilities (e.g. embedding backfill)
docs/        Architecture & design docs
```

## 📝 License

Apache License 2.0 — see [LICENSE](LICENSE).
