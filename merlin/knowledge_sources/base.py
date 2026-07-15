"""
Plugin system base — abstract interface every knowledge source must implement.

To add a new source type:
1. Create merlin/knowledge_sources/plugins/mytype/plugin.py
2. Subclass KnowledgeSourcePlugin and set source_type
3. Implement can_handle(), ingest(), and optionally validate_input()
4. Register in merlin/bootstrap.py: registry.register(MyTypePlugin())

The service layer, task queue, and DB repositories require zero changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


@dataclass
class IngestRequest:
    """Source-agnostic envelope passed into every plugin's ingest() method."""

    raw_input: str  # URL, file path, raw text, etc.
    options: dict[str, Any] = field(default_factory=dict)  # plugin-specific options
    task_id: str = ""
    progress_callback: Optional[Callable[[int, str], None]] = None
    title_callback: Optional[Callable[[str], None]] = None

    def report(self, percent: int, message: str) -> None:
        """Convenience wrapper — safe to call even if no callback is set."""
        if self.progress_callback:
            self.progress_callback(percent, message)

    def set_title(self, title: str) -> None:
        """Record the document title once known. Safe to call with no callback."""
        if self.title_callback and title:
            self.title_callback(title)


@dataclass
class IngestResult:
    """
    Normalised output returned by every plugin's ingest() method.
    Maps directly onto knowledge_items + the source-specific metadata table.
    """

    source_type: str
    source_id: str  # deduplication key (video_id, URL hash, etc.)
    title: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None

    raw_content: str = ""  # full transcript / article text
    summary: str = ""
    summary_length: str = "short"

    tags: list[str] = field(default_factory=list)
    # Per-item section map ({"heading": "12:34"}) for in-summary navigation —
    # NOT the cross-corpus topic taxonomy (see merlin.services.topics).
    sections: dict[str, str] = field(default_factory=dict)

    word_count: int = 0
    llm_model: str = ""

    # Usage / cost tracking (visibility only — see merlin.services.usage). The
    # plugin fills whatever it knows; the service layer writes the llm_usage
    # rows. None ⇒ not measured (older items / providers without passthrough).
    summarize_input_tokens: Optional[int] = None
    summarize_output_tokens: Optional[int] = None
    summarize_cache_read_tokens: Optional[int] = None  # cached subset of input
    summarize_cost_usd: Optional[float] = None  # provider-reported when available
    transcribe_audio_seconds: Optional[float] = None  # set only when audio was used
    transcribe_model: Optional[str] = None

    # Plugin-specific fields stored in the per-source metadata table
    source_metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeSourcePlugin(ABC):
    """
    Abstract base class for all knowledge source plugins.

    Subclasses are synchronous and run inside the thread-pool task queue.
    They can freely block (network I/O, LLM calls, ffmpeg, etc.).
    """

    source_type: str  # e.g. "youtube", "article", "pdf"
    display_name: str  # e.g. "YouTube Video", "Web Article"

    # JSON Schema for the frontend form (drives auto-generated UI)
    input_schema: dict = field(default_factory=dict)

    @abstractmethod
    def can_handle(self, raw_input: str) -> bool:
        """Return True if this plugin can process the given input string."""
        ...

    @abstractmethod
    def ingest(self, request: IngestRequest) -> IngestResult:
        """
        Full ingestion pipeline: extract → transcribe/parse → summarise.
        Must call request.report(percent, message) periodically for progress.
        Runs inside the thread pool — blocking I/O is fine.
        """
        ...

    def validate_input(self, raw_input: str, options: dict) -> list[str]:
        """Return a list of human-readable validation error strings (empty = valid)."""
        return []
