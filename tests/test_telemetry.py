"""Tracing to local JSONL files (merlin/core/telemetry.py).

Each test that turns tracing on writes synchronously (``processor="simple"``)
into its own temp dir and turns it off again, because Pydantic AI's
instrumentation and the HTTP instrumentors are process-wide.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import gzip
import json
from pathlib import Path

from opentelemetry.trace import NoOpTracer
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
import pytest

from merlin.core import telemetry
from merlin.core.telemetry import JsonlSpanExporter


def read_spans(directory: Path) -> list[dict]:
    spans = []
    for path in sorted(directory.glob("*.jsonl*")):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            spans.extend(json.loads(line) for line in f if line.strip())
    return spans


@pytest.fixture
def tracing(tmp_path):
    """Turn tracing on into ``tmp_path``; yields a ``setup(**kw)`` callable."""

    def setup(**kwargs) -> Path:
        assert telemetry.setup_tracing(str(tmp_path), processor="simple", **kwargs)
        return tmp_path

    yield setup
    telemetry.shutdown_tracing()


def _agent() -> Agent:
    agent = Agent(TestModel(), instructions="Be brief.", name="probe")

    @agent.tool_plain
    def lookup(q: str) -> str:
        return f"result for {q}"

    return agent


def _by_op(spans: list[dict], op: str) -> list[dict]:
    return [s for s in spans if s["attributes"].get("gen_ai.operation.name") == op]


def _day(offset: int) -> str:
    return (datetime.now(UTC) + timedelta(days=offset)).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# Off by default
# --------------------------------------------------------------------------- #


def test_off_when_traces_dir_empty(tmp_path):
    assert telemetry.setup_tracing("") is False
    assert not telemetry.enabled()
    assert isinstance(telemetry.tracer(), NoOpTracer)
    assert Agent._instrument_default is False
    # Root spans still work as no-ops, so callers never branch on "enabled".
    with telemetry.root_span("ingest.task", {"task_id": "t"}) as span:
        telemetry.set_outcome(span, "failed", RuntimeError("boom"))
    _agent().run_sync("hello")
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# Agent runs
# --------------------------------------------------------------------------- #


def test_agent_run_writes_agent_model_and_tool_spans(tracing):
    out = tracing()
    _agent().run_sync("hello")

    spans = read_spans(out)
    assert [f.name for f in out.iterdir()] == [f"{_day(0)}.jsonl"]
    (agent_span,) = _by_op(spans, "invoke_agent")
    models = _by_op(spans, "chat")
    (tool,) = _by_op(spans, "execute_tool")
    assert len(models) == 2  # tool call, then the final answer

    # One tree: the agent span is the root, everything else hangs off it.
    assert agent_span["parent_id"] is None
    assert {s["trace_id"] for s in spans} == {agent_span["trace_id"]}
    assert all(m["parent_id"] == agent_span["span_id"] for m in models)

    assert agent_span["attributes"]["gen_ai.agent.name"] == "probe"
    assert agent_span["attributes"]["pydantic_ai.all_messages"][0]["role"] == "user"
    assert agent_span["attributes"]["gen_ai.system_instructions"] == [
        {"type": "text", "content": "Be brief."}
    ]
    assert models[0]["attributes"]["gen_ai.usage.input_tokens"] > 0
    assert tool["attributes"]["gen_ai.tool.name"] == "lookup"
    assert tool["attributes"]["tool_arguments"] == {"q": "a"}
    assert tool["attributes"]["tool_response"] == "result for a"
    assert agent_span["duration_ms"] >= 0
    assert agent_span["status"] == "UNSET"
    # Logfire's rendering hints are dropped.
    assert not any("logfire.json_schema" in s["attributes"] for s in spans)


def test_content_off_keeps_timings_but_no_prompts(tracing):
    out = tracing(include_content=False)
    _agent().run_sync("a secret question")

    spans = read_spans(out)
    assert _by_op(spans, "chat") and _by_op(spans, "execute_tool")
    text = json.dumps(spans)
    assert "a secret question" not in text
    assert "result for a" not in text
    for model in _by_op(spans, "chat"):
        # The message structure stays (roles, part types); the text does not.
        parts = model["attributes"]["gen_ai.input.messages"][-1]["parts"]
        assert all("content" not in p for p in parts)
        assert model["attributes"]["gen_ai.usage.output_tokens"] > 0


def test_slimming_keeps_only_new_messages_and_tool_defs_once(tracing):
    out = tracing(verbatim=False)
    _agent().run_sync("hello")

    first, second = _by_op(read_spans(out), "chat")
    a1, a2 = first["attributes"], second["attributes"]
    # Step 1 sends the user prompt; step 2 only the tool result it adds.
    assert [m["role"] for m in a1["gen_ai.input.messages"]] == ["user"]
    assert a2["gen_ai.input.messages"][0]["parts"][0]["type"] == "tool_call_response"
    assert a2["merlin.input_messages_total"] == 3
    assert a2["merlin.input_messages_omitted"] == 2
    assert "gen_ai.tool.definitions" in a1 and "model_request_parameters" in a1
    assert "gen_ai.tool.definitions" not in a2
    assert "model_request_parameters" not in a2
    # Instructions live on the agent span only.
    assert "gen_ai.system_instructions" not in a1
    # Outputs are never slimmed.
    assert a2["gen_ai.output.messages"]


def test_verbatim_writes_model_spans_as_recorded(tracing):
    out = tracing(verbatim=True)
    _agent().run_sync("hello")

    _, second = _by_op(read_spans(out), "chat")
    a2 = second["attributes"]
    assert len(a2["gen_ai.input.messages"]) == 3
    assert "gen_ai.tool.definitions" in a2
    assert "gen_ai.system_instructions" in a2
    assert "merlin.input_messages_total" not in a2


# --------------------------------------------------------------------------- #
# Root spans
# --------------------------------------------------------------------------- #


def test_root_span_starts_a_new_trace_and_records_failure(tracing):
    out = tracing()
    with telemetry.tracer().start_as_current_span("outer"):
        with telemetry.root_span("ingest.task", {"task_id": "t1", "x": None}) as s:
            _agent().run_sync("hello")
            telemetry.set_outcome(s, "failed", ValueError("bad input"))

    spans = read_spans(out)
    root = next(s for s in spans if s["name"] == "ingest.task")
    outer = next(s for s in spans if s["name"] == "outer")
    assert root["parent_id"] is None
    assert root["trace_id"] != outer["trace_id"]
    assert root["attributes"] == {"task_id": "t1", "merlin.status": "failed"}
    assert root["status"] == "ERROR"
    assert "ValueError: bad input" in root["status_message"]
    assert root["events"][0]["name"] == "exception"
    # The agent run nests under the root span.
    (agent_span,) = _by_op(spans, "invoke_agent")
    assert agent_span["parent_id"] == root["span_id"]


def test_setup_is_idempotent_and_shutdown_uninstruments(tracing, tmp_path):
    tracing()
    assert telemetry.setup_tracing(str(tmp_path / "other")) is True
    assert telemetry.enabled()
    telemetry.shutdown_tracing()
    assert not telemetry.enabled()
    assert Agent._instrument_default is False
    assert not (tmp_path / "other").exists()


# --------------------------------------------------------------------------- #
# Exporter: housekeeping and failure handling
# --------------------------------------------------------------------------- #


def _write(path: Path, *records: dict) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def test_housekeep_gzips_past_days_and_prunes_expired(tmp_path):
    old = tmp_path / f"{_day(-100)}.jsonl.gz"
    with gzip.open(old, "wt") as f:
        f.write("{}\n")
    stale_plain = tmp_path / f"{_day(-91)}.jsonl"
    _write(stale_plain, {"n": 0})
    yesterday = tmp_path / f"{_day(-1)}.jsonl"
    with gzip.open(tmp_path / f"{_day(-1)}.jsonl.gz", "wt") as f:
        f.write(json.dumps({"n": 1}) + "\n")
    _write(yesterday, {"n": 2})  # a late span written after the day was gzipped
    today = tmp_path / f"{_day(0)}.jsonl"
    _write(today, {"n": 3})
    other = tmp_path / "notes.txt"
    other.write_text("keep me")

    JsonlSpanExporter(tmp_path, retention_days=90).housekeep()

    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [f"{_day(-1)}.jsonl.gz", f"{_day(0)}.jsonl", "notes.txt"]
    )
    with gzip.open(tmp_path / f"{_day(-1)}.jsonl.gz", "rt") as f:
        assert [json.loads(line)["n"] for line in f] == [1, 2]


def test_retention_zero_keeps_everything(tmp_path):
    _write(tmp_path / f"{_day(-400)}.jsonl", {"n": 1})
    JsonlSpanExporter(tmp_path, retention_days=0).housekeep()
    assert [p.name for p in tmp_path.iterdir()] == [f"{_day(-400)}.jsonl.gz"]


def test_export_swallows_write_errors(tmp_path, tracing):
    tracing()
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("a file where the traces dir should be")
    exporter = JsonlSpanExporter(blocked)

    with telemetry.tracer().start_as_current_span("x") as span:
        pass
    from opentelemetry.sdk.trace.export import SpanExportResult

    assert exporter.export([span]) is SpanExportResult.FAILURE
    exporter.housekeep()  # not a dir: nothing to do, no error


# --------------------------------------------------------------------------- #
# Thread pools
# --------------------------------------------------------------------------- #


def test_bind_context_nests_pool_work_under_the_caller(tracing):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    out = tracing()
    barrier = threading.Barrier(2, timeout=5)

    def work(i: int) -> int:
        barrier.wait()  # both tasks run at once: each needs its own context copy
        with telemetry.tracer().start_as_current_span(f"work {i}"):
            return i

    def unbound(i: int) -> None:
        with telemetry.tracer().start_as_current_span("unbound"):
            pass

    with telemetry.root_span("ingest.task") as root:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(telemetry.bind_context(work), i) for i in (1, 2)]
            assert [f.result() for f in futures] == [1, 2]
            pool.submit(unbound, 0).result()
        root_id = f"{root.get_span_context().span_id:016x}"

    spans = {s["name"]: s for s in read_spans(out)}
    assert spans["work 1"]["parent_id"] == root_id
    assert spans["work 2"]["parent_id"] == root_id
    assert spans["work 1"]["trace_id"] == spans["ingest.task"]["trace_id"]
    # Without it, the pool thread starts a trace of its own.
    assert spans["unbound"]["parent_id"] is None


def test_bind_context_passes_arguments_and_errors_through():
    def fn(a, *, b):
        if b is None:
            raise ValueError("no b")
        return a + b

    assert telemetry.bind_context(fn)(1, b=2) == 3
    with pytest.raises(ValueError, match="no b"):
        telemetry.bind_context(fn)(1, b=None)
