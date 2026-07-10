"""Tests for the batch proposal pipeline (§7): propose → validate.

Covers the clustering pipeline (LLM mocked), supersede-on-new-run, and the
accept/merge/reject actions incl. the drift rules (deleted or already-classified
members are skipped silently).
"""

from __future__ import annotations

from merlin.db.engine import SessionFactory
from merlin.db.repositories.topics import TopicRepository
from merlin.services import classify as classify_mod, topics as topics_service


def _insert_proposal(label: str, item_ids: list[str], batch_id="b1") -> str:
    with SessionFactory() as session:
        p = TopicRepository.create_proposal(
            session,
            proposed_label=label,
            item_ids=item_ids,
            rationale="r",
            batch_id=batch_id,
        )
        session.commit()
        return p.id


def _create_topic(client, label: str) -> str:
    r = client.post("/api/topics", json={"label": label})
    return r.json()["id"]


# --- accept / merge / reject -----------------------------------------------


def test_accept_creates_topic_and_assigns(client, make_item):
    a = make_item(title="a")
    b = make_item(title="b")
    pid = _insert_proposal("Cool Stuff", [a, b])

    r = client.post(f"/api/topics/proposals/{pid}/accept", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["topic"]["slug"] == "cool-stuff"
    assert body["assigned"] == 2 and body["requested"] == 2
    # Both items now sit under the new topic.
    got = client.get("/api/items", params={"topics": ["cool-stuff"]}).json()
    assert got["total"] == 2


def test_accept_with_custom_label(client, make_item):
    a = make_item(title="a")
    pid = _insert_proposal("meh label", [a])
    r = client.post(f"/api/topics/proposals/{pid}/accept", json={"label": "Better"})
    assert r.json()["topic"]["slug"] == "better"


def test_accept_tolerates_drift(client, make_item):
    a = make_item(title="a")
    b = make_item(title="b")
    existing = _create_topic(client, "Existing")
    # Pre-classify b so it's already categorised; add a ghost id that doesn't exist.
    client.post(
        f"/api/items/{b}/topics", json={"topic_ids": [existing], "primary_id": existing}
    )
    pid = _insert_proposal("New", [a, b, "ghost-id"])

    r = client.post(f"/api/topics/proposals/{pid}/accept", json={})
    body = r.json()
    assert body["requested"] == 3
    assert body["assigned"] == 1  # only `a`; b already categorised, ghost missing
    # b kept its manual topic, not the new one.
    got = {t["slug"] for t in client.get(f"/api/items/{b}").json()["topics"]}
    assert got == {"existing"}


def test_merge_into_existing_topic(client, make_item):
    a = make_item(title="a")
    dest = _create_topic(client, "Destination")
    pid = _insert_proposal("throwaway", [a])
    r = client.post(f"/api/topics/proposals/{pid}/accept", json={"topic_id": dest})
    assert r.status_code == 200
    assert r.json()["topic"]["slug"] == "destination"
    # No new topic was created (only the destination exists).
    slugs = {t["slug"] for t in client.get("/api/topics").json()}
    assert slugs == {"destination"}
    got = {t["slug"] for t in client.get(f"/api/items/{a}").json()["topics"]}
    assert got == {"destination"}


def test_reject_leaves_uncategorised(client, make_item):
    a = make_item(title="a")
    pid = _insert_proposal("Nope", [a])
    r = client.post(f"/api/topics/proposals/{pid}/reject")
    assert r.status_code == 204
    assert client.get("/api/topics/uncategorised-count").json()["count"] == 1
    # A second action on the now-resolved proposal 404s.
    assert client.post(f"/api/topics/proposals/{pid}/reject").status_code == 404


def test_list_proposals_resolves_members(client, make_item):
    a = make_item(title="Alpha")
    pid = _insert_proposal("Grp", [a, "ghost"])
    listed = client.get("/api/topics/proposals").json()
    assert len(listed) == 1
    p = listed[0]
    assert p["id"] == pid
    assert p["item_count"] == 1  # ghost dropped
    assert p["items"][0]["title"] == "Alpha"


# --- propose pipeline (supersede + write) ----------------------------------


def test_propose_run_supersedes_prior_pending(client, make_item, monkeypatch):
    make_item(title="uncategorised item")  # so the run has data to cluster
    stale = _insert_proposal("Stale", ["x"], batch_id="old")

    # Mock the LLM clustering and run the background callable synchronously.
    monkeypatch.setattr(
        classify_mod,
        "propose_clusters",
        lambda data, report=None, sink=None: [
            {
                "proposed_label": "Fresh",
                "item_ids": [d[0] for d in data],
                "rationale": "r",
            }
        ],
    )
    from merlin.core.task_queue import task_queue

    def fake_submit(work, task_type=None, input_data=None):
        work("t", lambda *a, **k: None)
        return "t"

    monkeypatch.setattr(task_queue, "submit_callable", fake_submit)

    topics_service.propose_topics()

    pending = client.get("/api/topics/proposals").json()
    labels = {p["proposed_label"] for p in pending}
    assert labels == {"Fresh"}  # the stale one was superseded
    with SessionFactory() as session:
        assert TopicRepository.get_proposal(session, stale).status == "superseded"


def test_propose_cancel_preserves_completed_clusters(client, make_item, monkeypatch):
    """Cancelling mid-clustering keeps the batches that already finished: the
    partial clusters are saved as proposals and the task completes (cancelled)."""
    from merlin.core.task_queue import TaskCancelled, task_queue
    from merlin.db.repositories.tasks import BackgroundTaskRepository

    make_item(title="an uncategorised item")  # so the run has data

    # Fake clustering: push one completed cluster into the sink, then cancel
    # (as parallel_map would after a completed chunk when report() cancels).
    def fake_clusters(data, report=None, sink=None):
        if sink is not None:
            sink.append(
                {
                    "proposed_label": "Partial Topic",
                    "item_ids": [d[0] for d in data],
                    "rationale": "done before cancel",
                }
            )
        raise TaskCancelled()

    monkeypatch.setattr(classify_mod, "propose_clusters", fake_clusters)

    def fake_submit(work, task_type=None, input_data=None):
        with SessionFactory() as s:
            BackgroundTaskRepository.create(
                s, task_id="ct", task_type=task_type, input_data=input_data or {}
            )
            s.commit()
        work("ct", lambda *a, **k: None)
        return "ct"

    monkeypatch.setattr(task_queue, "submit_callable", fake_submit)
    topics_service.propose_topics()

    # The completed cluster survived as a pending proposal.
    pending = client.get("/api/topics/proposals").json()
    assert {p["proposed_label"] for p in pending} == {"Partial Topic"}
    # Task recorded as completed-with-cancelled (not failed).
    with SessionFactory() as s:
        task = BackgroundTaskRepository.get(s, "ct")
    import json

    assert task.status == "completed"
    assert json.loads(task.result_data)["cancelled"] is True


def test_propose_run_noop_when_nothing_uncategorised(client, monkeypatch):
    # No items → early return, no proposals, nothing raised.
    from merlin.core.task_queue import task_queue

    monkeypatch.setattr(
        task_queue,
        "submit_callable",
        lambda work, **k: (work("t", lambda *a, **k: None), "t")[1],
    )
    topics_service.propose_topics()
    assert client.get("/api/topics/proposals").json() == []


# --- clustering helper (chunk + consolidate) -------------------------------


def test_propose_clusters_consolidates_labels(monkeypatch):
    from merlin.config import settings

    # Two chunks (>50 items) produce near-duplicate labels; consolidation merges.
    items = [(f"id{i}", f"title {i}", "summary") for i in range(60)]

    class FakeStructured:
        def __init__(self, schema):
            self.schema = schema

        def invoke(self, messages):
            from merlin.services.classify import (
                _Cluster,
                _ClusterResponse,
                _MergeGroup,
                _MergeResponse,
            )

            content = messages[-1]["content"]
            if self.schema is _ClusterResponse:
                # Chunks now run in parallel (non-deterministic order), so pick the
                # label from the chunk's *content*, not a call counter: chunk 2
                # holds items 50-59, chunk 1 holds 0-49.
                label = "Home Automation" if "title 50 " in content else "Smart Home"
                # indices are per-chunk-local
                n = len(content.splitlines()) - 1
                return _ClusterResponse(
                    clusters=[_Cluster(label=label, item_indices=list(range(n)))]
                )
            return _MergeResponse(
                groups=[
                    _MergeGroup(
                        final_label="Smart Home",
                        source_labels=["Smart Home", "Home Automation"],
                    )
                ]
            )

    class FakeLLM:
        def with_structured_output(self, schema, **kwargs):
            return FakeStructured(schema)

    monkeypatch.setattr(type(settings), "llm", property(lambda self: FakeLLM()))
    out = classify_mod.propose_clusters(items)
    assert len(out) == 1
    assert out[0]["proposed_label"] == "Smart Home"
    assert len(out[0]["item_ids"]) == 60  # both chunks unioned
