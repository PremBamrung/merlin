"""Tracing to local JSONL files: one JSON line per finished span.

Off unless ``settings.traces_dir`` is set (it always is off in tests). When on,
``setup_tracing()`` records:

- every Pydantic AI agent run, with its model calls and tool calls
  (``Agent.instrument_all``, a class-level default, so agents built at import
  and per-call ``Agent(...)`` instances are both covered);
- every outbound HTTP call made through httpx (OpenRouter/LiteLLM, Groq) or
  requests (Jina, OpenRouter ``/generation``, youtube-transcript-api);
- the manual root spans opened through ``root_span()``: ``ingest.task`` in the
  task-queue worker and ``chat.turn`` in the library-chat turn driver.

Spans go through a ``BatchSpanProcessor``, so the writes happen off the request
path, into ``<traces_dir>/YYYY-MM-DD.jsonl`` (UTC, by span end time). Past days
are gzipped and files older than ``traces_retention_days`` deleted, at startup
and whenever the UTC day rolls over. Writing never raises: a broken trace file
must not fail a chat turn or an ingest (same rule as ``services.usage.record``).

Unless ``traces_verbatim`` is on, model spans are slimmed: each keeps only the
input messages that are new at that step, and the tool definitions and request
parameters only on the first model call of a run. The agent span keeps the full
conversation (``pydantic_ai.all_messages``) once.

Read the files with ``scripts/traces.py``. Framework-free: never imports
``fastapi`` (``tests/test_architecture.py``).
"""

from __future__ import annotations

import atexit
from collections import OrderedDict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import gzip
import json
import logging
import os
from pathlib import Path
import re
import shutil
import threading
from typing import Any

from opentelemetry import context as otel_context, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Span, Status, StatusCode

from merlin.config import settings

logger = logging.getLogger("merlin.telemetry")

__all__ = [
    "JsonlSpanExporter",
    "enabled",
    "root_span",
    "set_outcome",
    "setup_tracing",
    "shutdown_tracing",
    "tracer",
]

# Outbound requests not worth a span: YouTube thumbnail downloads.
_REQUESTS_EXCLUDED_URLS = "img.youtube.com,i.ytimg.com"

# Model-span attributes that repeat on every step of a run. Slimming keeps them
# on the first model span of each run only.
_ONCE_PER_RUN = ("gen_ai.tool.definitions", "model_request_parameters")
# Logfire's rendering hints: noise in a JSONL file.
_DROPPED = ("logfire.json_schema",)

_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl(\.gz)?$")

_lock = threading.Lock()
_provider: TracerProvider | None = None
_NOOP_TRACER = trace.NoOpTracer()


# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #


def enabled() -> bool:
    """True once ``setup_tracing()`` has turned tracing on in this process."""
    return _provider is not None


def setup_tracing(
    traces_dir: str | None = None,
    *,
    include_content: bool | None = None,
    verbatim: bool | None = None,
    retention_days: int | None = None,
    processor: str = "batch",
) -> bool:
    """Turn tracing on. Idempotent; a no-op when no traces dir is configured.

    Arguments default to the ``traces_*`` settings; tests pass them directly
    (and ``processor="simple"`` to write synchronously). Returns whether
    tracing is on.
    """
    global _provider
    directory = settings.traces_dir if traces_dir is None else traces_dir
    if not directory:
        return False
    with _lock:
        if _provider is not None:
            return True
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor
            from pydantic_ai import Agent
            from pydantic_ai.models.instrumented import InstrumentationSettings

            exporter = JsonlSpanExporter(
                directory,
                verbatim=settings.traces_verbatim if verbatim is None else verbatim,
                retention_days=(
                    settings.traces_retention_days
                    if retention_days is None
                    else retention_days
                ),
            )
            exporter.housekeep()
            provider = TracerProvider(
                resource=Resource.create({"service.name": "merlin"})
            )
            span_processor = (
                SimpleSpanProcessor(exporter)
                if processor == "simple"
                else BatchSpanProcessor(exporter)
            )
            provider.add_span_processor(span_processor)

            Agent.instrument_all(
                InstrumentationSettings(
                    tracer_provider=provider,
                    include_content=(
                        settings.traces_include_content
                        if include_content is None
                        else include_content
                    ),
                )
            )
            HTTPXClientInstrumentor().instrument(tracer_provider=provider)
            RequestsInstrumentor().instrument(
                tracer_provider=provider, excluded_urls=_REQUESTS_EXCLUDED_URLS
            )
        except Exception:
            logger.warning("Tracing setup failed; continuing without it", exc_info=True)
            return False
        _provider = provider
        atexit.register(shutdown_tracing)
    logger.info("Tracing on: writing spans to %s", directory)
    return True


def shutdown_tracing() -> None:
    """Flush pending spans and undo ``setup_tracing()`` (tests, process exit)."""
    global _provider
    with _lock:
        provider, _provider = _provider, None
        if provider is None:
            return
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
            from pydantic_ai import Agent

            Agent.instrument_all(False)
            HTTPXClientInstrumentor().uninstrument()
            RequestsInstrumentor().uninstrument()
            provider.shutdown()
        except Exception:
            logger.warning("Tracing shutdown failed", exc_info=True)


def tracer() -> trace.Tracer:
    """Tracer for manual spans; a no-op tracer when tracing is off."""
    provider = _provider
    return provider.get_tracer("merlin") if provider is not None else _NOOP_TRACER


@contextmanager
def root_span(name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[Span]:
    """Open ``name`` as the root of a new trace and make it current.

    For work that outlives whatever started it (an ingest in a pool thread, a
    chat turn in its own task), so it is never filed under a caller's trace.
    Exceptions are recorded on the span and re-raised. A non-recording span when
    tracing is off, so callers can set attributes unconditionally.
    """
    with tracer().start_as_current_span(
        name,
        context=otel_context.Context(),
        attributes={k: v for k, v in (attributes or {}).items() if v is not None},
    ) as span:
        yield span


def set_outcome(span: Span, status: str, exc: BaseException | None = None) -> None:
    """Record how a root span's work ended: ``merlin.status`` plus the error."""
    try:
        span.set_attribute("merlin.status", status)
        if exc is not None:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, f"{type(exc).__name__}: {exc}"))
        elif status in ("failed", "error"):
            span.set_status(Status(StatusCode.ERROR, status))
    except Exception:  # tracing must never break the caller
        logger.debug("set_outcome failed", exc_info=True)


# --------------------------------------------------------------------------- #
# Exporter
# --------------------------------------------------------------------------- #


def _iso(ns: int | None) -> str | None:
    if ns is None:
        return None
    return datetime.fromtimestamp(ns / 1e9, tz=UTC).isoformat(timespec="milliseconds")


def _maybe_json(value: Any) -> Any:
    """Pydantic AI stores messages etc. as JSON strings; store them as JSON."""
    if isinstance(value, str) and value[:1] in ("[", "{"):
        try:
            return json.loads(value)
        except ValueError:
            return value
    if isinstance(value, tuple):
        return list(value)
    return value


def _new_messages(messages: list) -> list:
    """The messages a model call adds to its run: those after the last reply.

    Step 1 of a run yields the new user prompt (earlier turns of the thread are
    in the agent span's ``pydantic_ai.all_messages``); later steps yield the
    tool results they send back.
    """
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], dict) and messages[i].get("role") == "assistant":
            return messages[i + 1 :]
    return messages


class JsonlSpanExporter(SpanExporter):
    """Append each finished span as one JSON line to a per-UTC-day file."""

    def __init__(
        self,
        directory: str | os.PathLike,
        *,
        verbatim: bool = False,
        retention_days: int = 90,
    ) -> None:
        self.dir = Path(directory)
        self.verbatim = verbatim
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self._last_day: str | None = None
        # Agent runs whose first model span has been written (slimming).
        self._seen_runs: OrderedDict[str, None] = OrderedDict()

    # -- SpanExporter --------------------------------------------------------

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            with self._lock:
                today = datetime.now(UTC).strftime("%Y-%m-%d")
                if self._last_day is not None and today != self._last_day:
                    self._housekeep_locked(today)
                self._last_day = today
                by_file: dict[str, list[str]] = {}
                for span in spans:
                    record = self.to_record(span)
                    day = (record["end"] or record["start"] or today)[:10]
                    by_file.setdefault(day, []).append(
                        json.dumps(record, ensure_ascii=False, default=str)
                    )
                self.dir.mkdir(parents=True, exist_ok=True)
                for day, lines in by_file.items():
                    with open(self.dir / f"{day}.jsonl", "a", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
        except Exception:
            logger.warning("Writing %d trace span(s) failed", len(spans), exc_info=True)
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    # -- serialisation -------------------------------------------------------

    def to_record(self, span: ReadableSpan) -> dict[str, Any]:
        ctx = span.get_span_context()
        start, end = span.start_time, span.end_time
        attrs = {
            k: _maybe_json(v)
            for k, v in (span.attributes or {}).items()
            if k not in _DROPPED
        }
        if not self.verbatim and attrs.get("gen_ai.operation.name") == "chat":
            self._slim_model_span(attrs)
        return {
            "trace_id": f"{ctx.trace_id:032x}",
            "span_id": f"{ctx.span_id:016x}",
            "parent_id": f"{span.parent.span_id:016x}" if span.parent else None,
            "name": span.name,
            "kind": span.kind.name,
            "start": _iso(start),
            "end": _iso(end),
            "duration_ms": (round((end - start) / 1e6, 1) if start and end else None),
            "status": span.status.status_code.name,
            "status_message": span.status.description,
            "attributes": attrs,
            "events": [
                {
                    "name": e.name,
                    "time": _iso(e.timestamp),
                    "attributes": dict(e.attributes or {}),
                }
                for e in span.events
            ],
        }

    def _slim_model_span(self, attrs: dict[str, Any]) -> None:
        messages = attrs.get("gen_ai.input.messages")
        if isinstance(messages, list):
            new = _new_messages(messages)
            attrs["gen_ai.input.messages"] = new
            attrs["merlin.input_messages_total"] = len(messages)
            attrs["merlin.input_messages_omitted"] = len(messages) - len(new)
        # The agent span carries the system instructions once.
        attrs.pop("gen_ai.system_instructions", None)
        run = attrs.get("gen_ai.agent.call.id")
        if not run:
            return
        if run in self._seen_runs:
            for key in _ONCE_PER_RUN:
                attrs.pop(key, None)
        else:
            self._seen_runs[run] = None
            while len(self._seen_runs) > 1000:
                self._seen_runs.popitem(last=False)

    # -- housekeeping --------------------------------------------------------

    def housekeep(self) -> None:
        """Gzip past days and delete expired files. Never raises."""
        with self._lock:
            self._housekeep_locked(datetime.now(UTC).strftime("%Y-%m-%d"))

    def _housekeep_locked(self, today: str) -> None:
        try:
            if not self.dir.is_dir():
                return
            cutoff = None
            if self.retention_days > 0:
                cutoff = (
                    datetime.strptime(today, "%Y-%m-%d")
                    - timedelta(days=self.retention_days)
                ).strftime("%Y-%m-%d")
            for path in sorted(self.dir.iterdir()):
                m = _FILE_RE.match(path.name)
                if not m:
                    continue
                day, is_gz = m.group(1), bool(m.group(2))
                if cutoff is not None and day < cutoff:
                    path.unlink(missing_ok=True)
                elif not is_gz and day < today:
                    _gzip_append(path)
        except Exception:
            logger.warning("Trace housekeeping failed", exc_info=True)


def _gzip_append(path: Path) -> None:
    """Move ``path`` into ``path.gz``, appending a gzip member if it exists.

    A span that ends just before midnight can be written after its day was
    already compressed; appending keeps one file per day (gzip readers read a
    multi-member file as one stream).
    """
    gz = path.with_name(path.name + ".gz")
    with open(path, "rb") as src, gzip.open(gz, "ab") as dst:
        shutil.copyfileobj(src, dst)
    path.unlink()
