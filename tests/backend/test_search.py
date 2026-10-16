"""Unified search — real router → services.search → HybridRetriever → temp
SQLite (FTS5 from the real migrations). The vector arm is faked by patching
`HybridRetriever._vector`, the same seam the retriever tests use; without a
provider it is inert, so the default path is pure keyword search."""

from __future__ import annotations

from merlin.rag.retriever import HybridRetriever, RetrievedChunk


def test_empty_query_returns_nothing(client, make_item):
    make_item(title="Anything")
    body = client.get("/api/search", params={"q": "  "}).json()
    assert body == {"query": "", "items": []}


def test_keyword_hits_are_hydrated_list_items(client, make_item):
    item_id = make_item(
        title="Espresso dialing guide", summary="Grind finer for espresso."
    )
    make_item(title="Unrelated hiking video", source_id="other", summary="Mountains.")
    body = client.get("/api/search", params={"q": "espresso"}).json()
    assert body["query"] == "espresso"
    (hit,) = body["items"]
    assert hit["id"] == item_id
    assert hit["match"] == "fts"
    assert hit["excerpt"]
    # Same shape as a Library card: card fields present, transcript absent.
    assert hit["channel"] == "Test Channel"
    assert hit["thumbnail_url"] == "https://img.example/thumb.jpg"
    assert "raw_content" not in hit


def test_match_reports_the_arm_that_found_each_hit(client, make_item, monkeypatch):
    both = make_item(title="Moats and edges", source_id="m1", summary="moat")
    meaning_only = make_item(
        title="Competitive advantage", source_id="m2", summary="durable"
    )

    def fake_vector(self, session, query, source_types, tag_filters, limit, *_):
        return [
            RetrievedChunk(
                knowledge_item_id=i,
                source_type="youtube",
                source_id=i,
                title="t",
                author=None,
                excerpt="",
            )
            for i in (meaning_only, both)
        ]

    monkeypatch.setattr(HybridRetriever, "_vector", fake_vector)
    body = client.get("/api/search", params={"q": "moat"}).json()
    matches = {h["id"]: h["match"] for h in body["items"]}
    assert matches == {both: "both", meaning_only: "vector"}
    # In both lists → fused to the top.
    assert body["items"][0]["id"] == both


def test_limit_is_capped(client, make_item):
    for i in range(5):
        make_item(title=f"Coffee video {i}", source_id=f"c{i}", summary="coffee")
    body = client.get("/api/search", params={"q": "coffee", "limit": 2}).json()
    assert len(body["items"]) == 2
    assert (
        client.get("/api/search", params={"q": "coffee", "limit": 50}).status_code
        == 422
    )
