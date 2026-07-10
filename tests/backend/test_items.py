"""Library endpoints — real router → service → temp SQLite path."""

from __future__ import annotations


def test_list_items_empty(client):
    resp = client.get("/api/items")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0, "page": 1, "per_page": 20}


def test_list_items_returns_seeded_item(client, make_item):
    make_item(title="Attention Is All You Need")
    body = client.get("/api/items").json()
    assert body["total"] == 1
    (item,) = body["items"]
    assert item["title"] == "Attention Is All You Need"
    # JSON-in-text fields arrive parsed, not as strings.
    assert item["tags"] == ["ai", "python"]
    assert item["sections"] == {"Overview": "00:00:00"}
    # List items omit the transcript (contract §6.1).
    assert "raw_content" not in item


def test_list_items_pagination_query(client, make_item):
    for i in range(3):
        make_item(title=f"Video {i}", source_id=f"vid{i}")
    body = client.get("/api/items", params={"per_page": 2, "page": 1}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["per_page"] == 2


def test_get_item_includes_raw_content(client, make_item):
    item_id = make_item()
    resp = client.get(f"/api/items/{item_id}")
    assert resp.status_code == 200
    item = resp.json()
    assert item["id"] == item_id
    assert item["raw_content"] == "Full transcript text here."
    assert item["channel"] == "Test Channel"
    assert item["thumbnail_url"] == "https://img.example/thumb.jpg"


def test_get_item_404(client):
    resp = client.get("/api/items/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_patch_item_updates_tags_and_title(client, make_item):
    item_id = make_item()
    resp = client.patch(
        f"/api/items/{item_id}",
        json={"tags": ["llm", "rag"], "title": "Renamed"},
    )
    assert resp.status_code == 200
    item = resp.json()
    assert item["title"] == "Renamed"
    assert item["tags"] == ["llm", "rag"]
    # Returned shape is the detail shape (with transcript).
    assert item["raw_content"] == "Full transcript text here."


def test_patch_item_404(client):
    resp = client.patch("/api/items/nope", json={"title": "x"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_delete_item(client, make_item):
    item_id = make_item()
    resp = client.delete(f"/api/items/{item_id}")
    assert resp.status_code == 204
    assert client.get(f"/api/items/{item_id}").status_code == 404


def test_delete_item_404(client):
    assert client.delete("/api/items/nope").status_code == 404


def test_clear_summary(client, make_item):
    item_id = make_item()
    resp = client.post(f"/api/items/{item_id}/clear-summary")
    assert resp.status_code == 204
    assert client.get(f"/api/items/{item_id}").json()["summary"] is None


def test_clear_summary_404(client):
    assert client.post("/api/items/nope/clear-summary").status_code == 404


def test_tags_endpoint(client, make_item):
    make_item(tags=["ai", "python"])
    make_item(source_id="vid2", tags=["ai"])
    tags = {t["name"]: t["count"] for t in client.get("/api/tags").json()}
    assert tags["ai"] == 2
    assert tags["python"] == 1


def test_tags_unread_scoped(client, make_item):
    """?unread=true counts tags only on unread items (the Feed Refine chips)."""
    make_item(tags=["ai", "python"])
    read = make_item(source_id="vid2", tags=["ai"])
    assert client.post(f"/api/items/{read}/read").status_code == 200

    unread = {
        t["name"]: t["count"]
        for t in client.get("/api/tags", params={"unread": True}).json()
    }
    # The read item's "ai" no longer counts; "python" (unread) stays.
    assert unread == {"ai": 1, "python": 1}


def test_source_types_endpoint(client, make_item):
    make_item()
    make_item(source_id="a2", source_type="article")
    rows = {r["name"]: r["count"] for r in client.get("/api/source-types").json()}
    assert rows == {"youtube": 1, "article": 1}


# --- search -------------------------------------------------------------- #


def test_search_punctuation_does_not_500(client, make_item):
    """Special chars used to hit the FTS5 MATCH parser → unhandled 500.

    They must now degrade to a clean 200 with no matches.
    """
    make_item(title="Intro to programming")
    for q in ("C++", '"', "react.js", "a:b", "("):
        resp = client.get("/api/items", params={"search": q})
        assert resp.status_code == 200, f"query {q!r} should not 500"
        assert resp.json()["total"] == 0


def test_search_prefix_matches_partial_word(client, make_item):
    """Typing a partial word finds the item (FTS prefix query)."""
    make_item(title="Attention Is All You Need", summary="About transformers.")
    body = client.get("/api/items", params={"search": "transfor"}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Attention Is All You Need"


def test_search_relevance_ranks_title_match_first(client, make_item):
    """With sort=relevance, the title hit outranks a body-only mention."""
    make_item(
        source_id="body",
        title="Cooking basics",
        summary="An aside that mentions transformers once.",
        raw_content="transformers",
    )
    make_item(
        source_id="title",
        title="Transformers explained",
        summary="Deep dive.",
        raw_content="Deep dive into the architecture.",
    )
    body = client.get(
        "/api/items", params={"search": "transformers", "sort": "relevance"}
    ).json()
    assert body["total"] == 2
    assert body["items"][0]["title"] == "Transformers explained"


def test_search_relevance_without_query_falls_back(client, make_item):
    """sort=relevance with no query is meaningless → newest order, no error."""
    make_item(source_id="a", title="First")
    make_item(source_id="b", title="Second")
    resp = client.get("/api/items", params={"sort": "relevance"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_search_excludes_transcripts_by_default(client, make_item):
    """Default scope is title/summary/tags; a transcript-only term is hidden
    unless the search_transcripts toggle is on."""
    make_item(
        title="Cooking basics",
        summary="A nice recipe.",
        raw_content="a deep dive into kubernetes orchestration internals",
    )
    # "kubernetes" only appears in the transcript → no match by default.
    assert (
        client.get("/api/items", params={"search": "kubernetes"}).json()["total"] == 0
    )
    # ...but the toggle opens the transcript up.
    body = client.get(
        "/api/items", params={"search": "kubernetes", "search_transcripts": "true"}
    ).json()
    assert body["total"] == 1


def test_search_prefix_matches_word_start_not_mid_word(client, make_item):
    """Prefix matching hits word starts, not arbitrary substrings.

    "ai" matches the word "AI" / a word starting with it, but not the "ai"
    buried in "again"/"bargain".
    """
    make_item(source_id="a", title="AI fundamentals", summary="Intro.", tags=["tech"])
    make_item(
        source_id="b",
        title="Bargain hunting again",
        summary="Deals.",
        tags=["shopping"],
    )
    body = client.get("/api/items", params={"search": "ai"}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "AI fundamentals"


def test_search_matches_tag(client, make_item):
    """Search also matches an exact tag (e.g. the "ai" tag)."""
    make_item(source_id="a", title="Untagged-word title", tags=["ai", "python"])
    make_item(source_id="b", title="Other", tags=["cooking"])
    body = client.get("/api/items", params={"search": "ai"}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Untagged-word title"


def test_search_fuzzy_rescues_typo_when_no_exact_match(client, make_item):
    """A typo with zero exact hits falls back to fuzzy title matching."""
    make_item(source_id="a", title="ESP32 Dev Board Guide")
    make_item(source_id="b", title="Cooking basics")
    body = client.get("/api/items", params={"search": "ep32"}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "ESP32 Dev Board Guide"


def test_search_no_fuzzy_when_exact_match_exists(client, make_item):
    """Fuzzy only fires on zero exact hits — exact queries stay precise.

    The fuzzy-similar neighbour must NOT be pulled in when an exact prefix hit
    already exists.
    """
    make_item(source_id="a", title="kubernetes guide")
    make_item(source_id="b", title="kubernetidox notes")
    body = client.get("/api/items", params={"search": "kubernetes"}).json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "kubernetes guide"
