"""The root spans: ``ingest.task`` and ``chat.turn``.

Tracing context does not cross into a ``ThreadPoolExecutor`` on its own, so the
queue opens the ``ingest.task`` root span inside the worker; a library-chat turn
runs in its own asyncio task, so ``chat.turn`` opens in its driver. These guard
that the LLM calls land in the same trace, under that root.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
import pytest

from merlin.core import telemetry
from merlin.core.task_queue import TaskQueue
from merlin.knowledge_sources.base import IngestResult
from merlin.services import chat_turns
from tests.test_telemetry import read_spans


class _FakePlugin:
    source_type = "fake"

    def __init__(self, fail: bool = False):
        self.fail = fail

    def ingest(self, request):
        Agent(TestModel(), name="summarise").run_sync(request.raw_input)
        if self.fail:
            raise RuntimeError("transcript unavailable")
        return IngestResult(source_type="fake", source_id="x", title="Fake")


@pytest.fixture
def traced(tmp_path):
    assert telemetry.setup_tracing(str(tmp_path), processor="simple")
    yield tmp_path
    telemetry.shutdown_tracing()


def _run(plugin, on_complete=lambda task_id, result: None) -> str:
    q = TaskQueue(max_workers=1)
    task_id = q.submit_ingest(plugin, "https://youtu.be/abc", {}, on_complete)
    q._executor.shutdown(wait=True)  # the span is written when the worker ends
    return task_id


def test_ingest_task_is_the_root_of_its_llm_calls(_migrate_temp_db, traced):
    task_id = _run(_FakePlugin())

    spans = read_spans(traced)
    (root,) = [s for s in spans if s["name"] == "ingest.task"]
    assert root["parent_id"] is None
    assert root["attributes"] == {
        "task_id": task_id,
        "task_type": "ingest_fake",
        "source_type": "fake",
        "raw_input": "https://youtu.be/abc",
        "merlin.status": "completed",
    }
    # Every span of the ingest shares the root's trace...
    assert {s["trace_id"] for s in spans} == {root["trace_id"]}
    # ...and the agent run hangs directly off the root.
    (agent_span,) = [s for s in spans if s["name"] == "agent run"]
    assert agent_span["parent_id"] == root["span_id"]


def test_failed_ingest_marks_the_root_span(_migrate_temp_db, traced):
    _run(_FakePlugin(fail=True))

    (root,) = [s for s in read_spans(traced) if s["name"] == "ingest.task"]
    assert root["attributes"]["merlin.status"] == "failed"
    assert root["status"] == "ERROR"
    assert "transcript unavailable" in root["status_message"]


def test_callable_job_gets_a_root_span(_migrate_temp_db, traced):
    q = TaskQueue(max_workers=1)
    task_id = q.submit_callable(
        lambda tid, report: Agent(TestModel()).run_sync("classify"),
        task_type="topic_backfill",
        input_data={},
    )
    q._executor.shutdown(wait=True)

    spans = read_spans(traced)
    (root,) = [s for s in spans if s["name"] == "ingest.task"]
    assert root["attributes"]["task_id"] == task_id
    assert root["attributes"]["task_type"] == "topic_backfill"
    assert {s["trace_id"] for s in spans} == {root["trace_id"]}


# --------------------------------------------------------------------------- #
# chat.turn
# --------------------------------------------------------------------------- #

_STREAMS = Path(__file__).parent / "fixtures" / "chat_streams"


async def _agent_stream(fixture: str):
    """A chunk stream whose iteration runs an agent, as the Vercel adapter's
    does: the agent's spans must nest under the turn iterating it."""
    await Agent(TestModel(), name="library").run("what about moats?")
    for line in (_STREAMS / f"{fixture}.chunks.jsonl").read_text().splitlines():
        if line.strip():
            yield line


async def _turn(thread_id: str, fixture: str) -> None:
    question = [{"id": "u1", "role": "user", "parts": [{"type": "text", "text": "q"}]}]
    turn = await chat_turns.start_turn(thread_id, question, _agent_stream(fixture))
    await asyncio.wait_for(turn.task, 5)


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_chat_turn_is_the_root_of_its_agent_run(
    _migrate_temp_db, traced, anyio_backend
):
    await _turn("trace-t1", "plain")

    spans = read_spans(traced)
    (root,) = [s for s in spans if s["name"] == "chat.turn"]
    assert root["parent_id"] is None
    assert root["attributes"] == {
        "thread_id": "trace-t1",
        "merlin.status": "completed",
    }
    (agent_span,) = [s for s in spans if s["name"] == "agent run"]
    assert agent_span["trace_id"] == root["trace_id"]
    assert agent_span["parent_id"] == root["span_id"]


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_errored_chat_turn_is_marked(_migrate_temp_db, traced, anyio_backend):
    await _turn("trace-t2", "error")

    (root,) = [s for s in read_spans(traced) if s["name"] == "chat.turn"]
    assert root["attributes"]["merlin.status"] == "error"
    assert root["status"] == "ERROR"
