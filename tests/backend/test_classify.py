"""Tests for the classification service + its ingest wiring.

The LLM boundary is monkeypatched (no network). These guard the invariants that
matter: the classifier never clobbers a user-assigned topic, never writes a
competing primary, ignores hallucinated slugs, only fills empty tags, and — the
§4 ordering bug — the item vector is embedded with the classifier's tags, not
the plugin's empty ones.
"""

from __future__ import annotations

import json

import pytest

from merlin.services import classify as classify_mod
from merlin.services.classify import ClassifyResult


def _canned(monkeypatch, primary=None, secondary=None, tags=None):
    """Make classify_item return a fixed result without calling the LLM."""

    def fake(title, summary, active_topics, top_tags):
        return ClassifyResult(
            primary=primary, secondary=secondary or [], tags=tags or []
        )

    monkeypatch.setattr(classify_mod, "classify_item", fake)


def _mk_topic(slug: str, label: str) -> str:
    from merlin.db.engine import SessionFactory
    from merlin.db.repositories.topics import TopicRepository

    with SessionFactory() as session:
        t = TopicRepository.create(session, label=label, slug=slug, origin="seed")
        session.commit()
        return t.id


def _topics_of(item_id: str) -> dict[str, bool]:
    from merlin.db.engine import SessionFactory
    from merlin.db.repositories.topics import TopicRepository

    with SessionFactory() as session:
        return {
            t["slug"]: t["is_primary"]
            for t in TopicRepository.assignments_for_items(session, [item_id]).get(
                item_id, []
            )
        }


def _tags_of(item_id: str) -> list[str]:
    from merlin.db.engine import SessionFactory
    from merlin.db.repositories.knowledge import KnowledgeItemRepository

    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        return json.loads(item.tags) if item.tags else []


def test_classify_writes_primary_secondary_and_tags(client, make_item, monkeypatch):
    _mk_topic("coding", "Coding")
    _mk_topic("ai", "AI")
    item = make_item(tags=[])  # no tags yet
    _canned(monkeypatch, primary="coding", secondary=["ai"], tags=["python", "llm"])

    classify_mod.classify_and_persist(item)

    assert _topics_of(item) == {"coding": True, "ai": False}
    assert _tags_of(item) == ["python", "llm"]


def test_classify_ignores_hallucinated_slugs(client, make_item, monkeypatch):
    _mk_topic("coding", "Coding")
    item = make_item(tags=[])
    _canned(monkeypatch, primary="coding", secondary=["not-a-real-topic"])
    classify_mod.classify_and_persist(item)
    # The bogus secondary is dropped; only the valid primary lands.
    assert _topics_of(item) == {"coding": True}


def test_no_primary_stays_uncategorised(client, make_item, monkeypatch):
    _mk_topic("coding", "Coding")
    item = make_item(tags=[])
    # secondary without a primary must write nothing (uncategorised).
    _canned(monkeypatch, primary=None, secondary=["coding"], tags=["x"])
    classify_mod.classify_and_persist(item)
    assert _topics_of(item) == {}
    # Tags still fill even when no topic fits.
    assert _tags_of(item) == ["x"]


def test_user_assignment_never_clobbered(client, make_item, monkeypatch):
    coding = _mk_topic("coding", "Coding")
    _mk_topic("gaming", "Gaming")
    item = make_item(tags=[])
    # User manually pins the item to coding (primary).
    client.post(
        f"/api/items/{item}/topics",
        json={"topic_ids": [coding], "primary_id": coding},
    )
    # A later classify wants gaming as primary — it must be ignored entirely.
    _canned(monkeypatch, primary="gaming", secondary=[], tags=["a"])
    classify_mod.classify_and_persist(item)

    got = _topics_of(item)
    assert got == {"coding": True}  # user's choice survives; no competing primary


def test_existing_tags_not_clobbered(client, make_item, monkeypatch):
    _mk_topic("coding", "Coding")
    item = make_item(tags=["hand-picked"])
    _canned(monkeypatch, primary="coding", tags=["auto1", "auto2"])
    classify_mod.classify_and_persist(item)
    # Topic still assigned, but curated tags are left intact.
    assert _topics_of(item) == {"coding": True}
    assert _tags_of(item) == ["hand-picked"]


def test_reclassify_replaces_llm_topics(client, make_item, monkeypatch):
    _mk_topic("coding", "Coding")
    _mk_topic("gaming", "Gaming")
    item = make_item(tags=[])
    _canned(monkeypatch, primary="coding")
    classify_mod.classify_and_persist(item)
    assert _topics_of(item) == {"coding": True}
    # Re-run with a different result — the old llm rows are replaced.
    _canned(monkeypatch, primary="gaming")
    classify_mod.classify_and_persist(item)
    assert _topics_of(item) == {"gaming": True}


def test_classify_item_uses_structured_llm(monkeypatch):
    """classify_item drives settings.llm.with_structured_output(...).invoke(...)."""
    from merlin.config import settings

    captured = {}

    class FakeStructured:
        def invoke(self, messages):
            captured["messages"] = messages
            return ClassifyResult(primary="coding", tags=["t"])

    class FakeLLM:
        def with_structured_output(self, schema):
            captured["schema"] = schema
            return FakeStructured()

    monkeypatch.setattr(type(settings), "llm", property(lambda self: FakeLLM()))
    out = classify_mod.classify_item(
        "Title", "Summary", [{"slug": "coding", "label": "Coding"}], ["python"]
    )
    assert out.primary == "coding"
    assert captured["schema"] is ClassifyResult
    # Prompt carries the topic slug and the tag vocabulary.
    user_msg = captured["messages"][-1]["content"]
    assert "coding" in user_msg and "python" in user_msg


def test_ingest_embeds_with_classifier_tags(client, make_item, monkeypatch):
    """§4 ordering: persist_result classifies (writing tags) BEFORE embedding, and
    the embed reads tags from the DB — so the vector never bakes in empty tags."""
    from merlin.knowledge_sources.base import IngestResult
    from merlin.services import ingest

    # Stand-in classifier: writes tags directly to the DB for the new item.
    def fake_classify(item_id):
        from merlin.db.engine import SessionFactory
        from merlin.db.repositories.knowledge import KnowledgeItemRepository

        with SessionFactory() as session:
            it = KnowledgeItemRepository.get_by_id(session, item_id)
            it.tags = json.dumps(["classified-tag"])
            session.commit()

    captured = {}

    def fake_store(session, *, item_id, title, summary, tags, embedder=None):
        captured["tags"] = tags
        return False  # no-op write

    monkeypatch.setattr(ingest, "_classify", fake_classify)
    # get_embedder().enabled must be True to reach store_item_embedding.
    import merlin.rag.embeddings as emb

    monkeypatch.setattr(emb, "store_item_embedding", fake_store)
    monkeypatch.setattr(emb, "get_embedder", lambda: type("E", (), {"enabled": True})())

    result = IngestResult(
        source_type="youtube",
        source_id="vid_order_test",
        title="Ordering test",
        summary="A summary.",
        tags=[],  # plugin emits empty tags
        sections={},
        source_metadata={"video_id": "vid_order_test"},
    )
    ingest.persist_result("task-x", result)

    assert captured["tags"] == ["classified-tag"]


@pytest.mark.usefixtures("client")
def test_classify_swallows_llm_errors(make_item, monkeypatch):
    _mk_topic("coding", "Coding")
    item = make_item(tags=[])

    def boom(*a, **k):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(classify_mod, "classify_item", boom)
    # Must not raise — best-effort.
    classify_mod.classify_and_persist(item)
    assert _topics_of(item) == {}
