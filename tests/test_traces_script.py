"""scripts/traces.py, the viewer, run against traces written by the real
exporter (merlin/core/telemetry.py) for TestModel agent runs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import gzip
import importlib.util
from pathlib import Path
import shutil
import sys

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
import pytest

from merlin.core import telemetry

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "traces.py"
_spec = importlib.util.spec_from_file_location("traces_script", _SCRIPT)
traces = importlib.util.module_from_spec(_spec)
sys.modules["traces_script"] = traces  # dataclasses look the module up
_spec.loader.exec_module(traces)


def _agent(name: str) -> Agent:
    agent = Agent(TestModel(), instructions="Be brief.", name=name)

    @agent.tool_plain
    def lookup(q: str) -> str:
        return f"result for {q}"

    return agent


@pytest.fixture
def recorded(tmp_path) -> dict[str, str]:
    """Three traces: a chat turn, a failed ingest, a bare title agent run."""
    assert telemetry.setup_tracing(str(tmp_path), processor="simple")
    ids = {}
    try:
        with telemetry.root_span("chat.turn", {"thread_id": "thr-1"}) as span:
            _agent("library").run_sync("what about sleep?")
            telemetry.set_outcome(span, "completed")
            ids["chat"] = f"{span.get_span_context().trace_id:032x}"
        with telemetry.root_span(
            "ingest.task",
            {"task_id": "task-1", "raw_input": "https://youtu.be/abc"},
        ) as span:
            Agent(TestModel(), name="summarize").run_sync("transcript")
            telemetry.set_outcome(span, "failed", RuntimeError("no transcript"))
            ids["ingest"] = f"{span.get_span_context().trace_id:032x}"
        with telemetry.tracer().start_as_current_span("x") as span:
            pass
        Agent(TestModel(), name="title_agent").run_sync("name this")
    finally:
        telemetry.shutdown_tracing()
    return ids


def _run(capsys, *argv: str) -> tuple[int, str, str]:
    code = traces.main(list(argv))
    out, err = capsys.readouterr()
    return code, out, err


def test_list_shows_one_line_per_trace(tmp_path, recorded, capsys):
    code, out, _ = _run(capsys, "--dir", str(tmp_path))
    assert code == 0
    lines = out.splitlines()
    assert len(lines) == 4  # chat, ingest, the bare "x" span, the title run
    chat = next(line for line in lines if "chat.turn" in line)
    assert "thread thr-1" in chat
    assert "2 calls" in chat and "1 tool" in chat
    assert chat.endswith(recorded["chat"][:8])
    ingest = next(line for line in lines if "ingest.task" in line)
    assert "failed" in ingest and "✗1" in ingest and "https://youtu.be/abc" in ingest
    assert any("agent title_agent" in line for line in lines)


def test_list_errors_only(tmp_path, recorded, capsys):
    _, out, _ = _run(capsys, "--dir", str(tmp_path), "list", "--errors")
    assert out.splitlines() == [
        line for line in out.splitlines() if "ingest.task" in line
    ]
    assert len(out.splitlines()) == 1


def test_list_day_filter(tmp_path, recorded, capsys):
    _, out, _ = _run(capsys, "--dir", str(tmp_path), "list", "--day", "today")
    assert len(out.splitlines()) == 4
    _, out, err = _run(capsys, "--dir", str(tmp_path), "list", "--day", "2020-01-01")
    assert out == "" and "No matching traces" in err


def test_show_tree_and_full(tmp_path, recorded, capsys):
    prefix = recorded["chat"][:6]
    code, out, _ = _run(capsys, "--dir", str(tmp_path), "show", prefix)
    assert code == 0
    assert "chat.turn" in out and "thread=thr-1" in out
    assert "└─ agent run" in out and "[library]" in out
    assert "lookup" in out and "→ result for a" in out
    assert "what about sleep?" not in out  # prompts only with --full

    _, full, _ = _run(capsys, "--dir", str(tmp_path), "show", prefix, "--full")
    assert "what about sleep?" in full
    assert "── instructions ──" in full and "Be brief." in full
    assert "── result ──" in full


def test_show_last_is_the_newest_trace(tmp_path, recorded, capsys):
    _, out, _ = _run(capsys, "--dir", str(tmp_path), "show", "last")
    assert "[title_agent]" in out.splitlines()[2]


def test_show_failed_root_reports_the_exception(tmp_path, recorded, capsys):
    prefix = recorded["ingest"][:6]
    _, out, _ = _run(capsys, "--dir", str(tmp_path), "show", prefix)
    assert "status=failed" in out and "✗ RuntimeError: no transcript" in out
    _, full, _ = _run(capsys, "--dir", str(tmp_path), "show", prefix, "--full")
    assert "── exception RuntimeError ──" in full


def test_unknown_and_ambiguous_prefixes(tmp_path, recorded, capsys):
    code, _, err = _run(capsys, "--dir", str(tmp_path), "show", "zzzz")
    assert code == 2 and "no trace matches 'zzzz'" in err
    code, _, err = _run(capsys, "--dir", str(tmp_path), "show", "")
    assert code == 2 and "matches 4 traces" in err


def test_html_page_is_self_contained(tmp_path, recorded, capsys):
    code, out, _ = _run(capsys, "--dir", str(tmp_path), "html", recorded["ingest"])
    assert code == 0
    page = Path(out.strip())
    assert page == tmp_path / "html" / f"{recorded['ingest'][:8]}.html"
    text = page.read_text()
    assert text.startswith("<!doctype html>")
    assert "http://" not in text and "https://cdn" not in text
    assert "<title>Trace " in text
    assert "prefers-color-scheme: dark" in text
    # The failed root is marked; the agent run under it is not an error.
    assert '<details class="err" open>' in text


def test_reads_gzipped_days_and_midnight_crossing(tmp_path, recorded, capsys):
    # Move today's file to "yesterday.jsonl.gz": the viewer reads it the same.
    today = datetime.now(UTC).date()
    yesterday = (today - timedelta(days=1)).isoformat()
    src = tmp_path / f"{today.isoformat()}.jsonl"
    with open(src, "rb") as f, gzip.open(tmp_path / f"{yesterday}.jsonl.gz", "wb") as g:
        shutil.copyfileobj(f, g)
    src.unlink()
    _, out, _ = _run(capsys, "--dir", str(tmp_path), "show", recorded["chat"][:8])
    assert "chat.turn" in out and "lookup" in out


def test_missing_dir(tmp_path, capsys):
    code, _, err = _run(capsys, "--dir", str(tmp_path / "nope"))
    assert code == 1 and "No trace files" in err
