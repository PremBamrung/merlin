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
    assert item["topics"] == {"Overview": "00:00:00"}
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


def test_source_types_endpoint(client, make_item):
    make_item()
    make_item(source_id="a2", source_type="article")
    rows = {r["name"]: r["count"] for r in client.get("/api/source-types").json()}
    assert rows == {"youtube": 1, "article": 1}
