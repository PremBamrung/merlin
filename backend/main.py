"""
Merlin — FastAPI application factory.

Start with:
    conda run -n merlin uvicorn backend.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.core.logging import logger
from backend.knowledge_sources.registry import registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info("Merlin backend starting up…")

    # Register all knowledge source plugins
    from backend.knowledge_sources.plugins.youtube.plugin import YouTubePlugin
    registry.register(YouTubePlugin())
    logger.info(f"Registered plugins: {registry.source_types()}")

    yield

    logger.info("Merlin backend shutting down.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Merlin",
        description="Personal knowledge management API",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS — allow the Vite dev server (Phase 2) and any local origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount the API
    app.include_router(api_router)

    # Health check
    @app.get("/api/health", tags=["system"])
    def health():
        return {"status": "ok", "version": "2.0.0"}

    # Config endpoint (useful for frontend to know available sources)
    @app.get("/api/config", tags=["system"])
    def config():
        return {
            "source_types": [
                {"type": p.source_type, "display_name": p.display_name, "schema": p.input_schema}
                for p in registry.all()
            ],
        }

    return app


app = create_app()
