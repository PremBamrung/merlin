"""
Application startup wiring.

`register_plugins()` registers all knowledge-source plugins into the singleton
registry. Call it once at app startup (from `api.main.create_app()`).
"""

from merlin.core.logging import logger
from merlin.knowledge_sources.plugins.youtube.plugin import YouTubePlugin
from merlin.knowledge_sources.registry import registry


def register_plugins() -> None:
    """Idempotent — safe to call more than once."""
    if not registry.get("youtube"):
        registry.register(YouTubePlugin())
        logger.info(f"Registered plugins: {registry.source_types()}")
