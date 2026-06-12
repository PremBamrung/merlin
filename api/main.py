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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from merlin.bootstrap import register_plugins
from merlin.knowledge_sources.registry import registry

from .errors import install_error_handlers
from .routers import chat, inbox, ingest, insights, items
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Merlin API",
        version="3.0.0",
        description="Thin HTTP layer over the Merlin knowledge-base core.",
    )

    # Register knowledge-source plugins once at startup (idempotent). Replaces
    # the Streamlit app's register_plugins() call.
    register_plugins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    app.include_router(items.router)
    app.include_router(ingest.router)
    app.include_router(chat.router)
    app.include_router(insights.router)
    app.include_router(inbox.router)

    @app.get("/api/health", response_model=HealthResponse, tags=["meta"])
    def health():
        return {"status": "ok", "source_types": registry.source_types()}

    # Serve the built SPA when present (prod). Mounted last so /api/* wins.
    # `html=True` makes client-side routes fall back to index.html.
    if _WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="web")

    return app


app = create_app()
