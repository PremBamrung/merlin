"""
PluginRegistry — central registry for all KnowledgeSourcePlugin instances.
Register plugins at app startup in merlin/bootstrap.py.
"""

from typing import Optional

from merlin.knowledge_sources.base import KnowledgeSourcePlugin


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, KnowledgeSourcePlugin] = {}

    def register(self, plugin: KnowledgeSourcePlugin) -> None:
        self._plugins[plugin.source_type] = plugin

    def get(self, source_type: str) -> Optional[KnowledgeSourcePlugin]:
        return self._plugins.get(source_type)

    def find_handler(self, raw_input: str) -> Optional[KnowledgeSourcePlugin]:
        """Auto-detect which plugin handles a given raw input."""
        for plugin in self._plugins.values():
            if plugin.can_handle(raw_input):
                return plugin
        return None

    def all(self) -> list[KnowledgeSourcePlugin]:
        return list(self._plugins.values())

    def source_types(self) -> list[str]:
        return list(self._plugins.keys())


# Singleton — imported everywhere
registry = PluginRegistry()
