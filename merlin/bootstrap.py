"""
Application startup wiring.

`register_plugins()` registers all knowledge-source plugins into the singleton
registry. Call it once at app startup (from `app.py`). This replaces the plugin
registration that used to live in the FastAPI `lifespan` hook.
"""

from merlin.core.logging import logger
from merlin.knowledge_sources.plugins.youtube.plugin import YouTubePlugin
from merlin.knowledge_sources.registry import registry


def register_plugins() -> None:
    """Idempotent — safe to call on every Streamlit rerun."""
    if not registry.get("youtube"):
        registry.register(YouTubePlugin())
        logger.info(f"Registered plugins: {registry.source_types()}")
