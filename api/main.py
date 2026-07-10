"""FastAPI application — the thin HTTP skin over `merlin.services`.

In prod this single process serves both `/api/*` and the built React SPA
(`web/dist`, mounted as static files → same origin, no CORS). In dev the Vite
dev server runs on :5173 and proxies/origins are allowed via CORS.

The OpenAPI schema (`/openapi.json`) is the source for the generated TS client
(`openapi-typescript`), which is what keeps the frontend types from drifting
from the backend (FRONTEND_V3_PLAN.md §2).
"""

from __future__ import annotations

import os
from pathlib import Path
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from merlin.bootstrap import register_plugins
from merlin.config import settings
from merlin.core.logging import logger
from merlin.knowledge_sources.registry import registry
from merlin.rag.embeddings import get_embedder

from .errors import install_error_handlers, not_found
from .routers import chat, inbox, ingest, insights, items, topics
from .schemas import HealthResponse

# Dev origins for the Vite dev server. Override/extend with a comma-separated
# CORS_ORIGINS env var. In prod the SPA is same-origin, so CORS is irrelevant.
_DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    extra = [o.strip() for o in raw.split(",") if o.strip()]
    return [*_DEFAULT_ORIGINS, *extra]


def _start_embedding_self_heal() -> None:
    """Fill missing item vectors in the background, off the boot path.

    Runs once per process start in a daemon thread so it never delays uvicorn or
    the health check. Skipped entirely when auto-heal is off or no embedding
    provider is configured (so it adds nothing under EMBEDDING_PROVIDER=none and
    never fires in tests). Idempotent — a no-op once everything is embedded.
    """
    if not settings.embedding_auto_heal or not get_embedder().enabled:
        return

    def _run() -> None:
        try:
            from merlin.services.embeddings import heal_missing_embeddings

            heal_missing_embeddings()
        except Exception:  # never let self-heal crash anything
            logger.warning("Embedding self-heal failed", exc_info=True)

    threading.Thread(target=_run, name="embedding-self-heal", daemon=True).start()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Merlin API",
        version="3.0.0",
        description="Thin HTTP layer over the Merlin knowledge-base core.",
    )

    # Register knowledge-source plugins once at startup (idempotent).
    register_plugins()

    # Backfill any missing item vectors in the background (no-op without a
    # provider; never blocks boot). New items embed at ingest; this heals the
    # existing backlog and any ingest-time embedding failures.
    _start_embedding_self_heal()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    app.include_router(items.router)
    app.include_router(topics.router)
    app.include_router(ingest.router)
    app.include_router(chat.router)
    app.include_router(insights.router)
    app.include_router(inbox.router)

    @app.get("/api/health", response_model=HealthResponse, tags=["meta"])
    def health():
        return {"status": "ok", "source_types": registry.source_types()}

    # Serve the built SPA when present (prod, same origin → no CORS). A plain
    # StaticFiles(html=True) mount only serves index.html for the *root* request,
    # so a full reload of a deep client route (/feed, /library/:id) would 404.
    # Instead: serve content-addressed assets directly, and fall back to the SPA
    # shell for client-side routes via the catch-all below.
    if _WEB_DIST.is_dir():
        index_html = _WEB_DIST / "index.html"

        # Hashed build assets: StaticFiles 404s a missing file rather than
        # masking it with the shell, and handles content types / range / etags.
        app.mount(
            "/assets",
            StaticFiles(directory=str(_WEB_DIST / "assets")),
            name="assets",
        )

        # Catch-all (registered after the routers + the /assets mount, so both
        # win). include_in_schema=False keeps it out of the generated TS client.
        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            # An unknown /api/* route that fell through → genuine JSON 404,
            # never the HTML shell.
            if full_path == "api" or full_path.startswith("api/"):
                raise not_found()
            # A real root-level file (favicon.svg, icons.svg, …) → serve as-is,
            # guarded against path traversal.
            candidate = (_WEB_DIST / full_path).resolve()
            if (
                full_path
                and candidate.is_file()
                and candidate.is_relative_to(_WEB_DIST)
            ):
                return FileResponse(candidate)
            # A missing path that names a file (has an extension) → real 404, so
            # a broken asset reference surfaces clearly instead of returning the
            # shell with a 200 (which then fails as "Unexpected token <").
            if "." in full_path.rsplit("/", 1)[-1]:
                raise not_found()
            # Anything else (extensionless client route, or "/") → the SPA shell,
            # served uncached so a deploy isn't masked by a stale bundle.
            return FileResponse(index_html, headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
