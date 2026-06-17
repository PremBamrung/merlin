"""Feed read/saved state — real router → service → temp SQLite path."""

from __future__ import annotations


def test_new_item_is_unread_and_unsaved(client, make_item):
    item_id = make_item()
    item = client.get(f"/api/items/{item_id}").json()
    assert item["read_at"] is None
    assert item["saved_at"] is None


def test_mark_read_then_unread(client, make_item):
    item_id = make_item()

    read = client.post(f"/api/items/{item_id}/read").json()
    assert read["id"] == item_id
    assert read["read_at"] is not None

    unread = client.post(f"/api/items/{item_id}/unread").json()
    assert unread["read_at"] is None


def test_save_then_unsave(client, make_item):
    item_id = make_item()

    saved = client.post(f"/api/items/{item_id}/save").json()
    assert saved["saved_at"] is not None

    unsaved = client.post(f"/api/items/{item_id}/unsave").json()
    assert unsaved["saved_at"] is None


def test_read_filter_excludes_read_items(client, make_item):
    a = make_item(title="Unread one", source_id="vidA")
    make_item(title="Will be read", source_id="vidB")
    # Read the second item.
    body = client.get("/api/items").json()
    read_target = next(i["id"] for i in body["items"] if i["title"] == "Will be read")
    client.post(f"/api/items/{read_target}/read")

    unread = client.get("/api/items", params={"read": "false"}).json()
    assert unread["total"] == 1
    assert unread["items"][0]["id"] == a

    only_read = client.get("/api/items", params={"read": "true"}).json()
    assert only_read["total"] == 1
    assert only_read["items"][0]["id"] == read_target


def test_saved_filter(client, make_item):
    make_item(title="Plain", source_id="vidA")
    star = make_item(title="Starred", source_id="vidB")
    client.post(f"/api/items/{star}/save")

    saved = client.get("/api/items", params={"saved": "true"}).json()
    assert saved["total"] == 1
    assert saved["items"][0]["id"] == star


def test_unread_count_endpoint(client, make_item):
    make_item(source_id="vidA")
    read_one = make_item(source_id="vidB")
    # Only completed items count; a pending item must be excluded.
    make_item(source_id="vidC", status="pending")
    client.post(f"/api/items/{read_one}/read")

    count = client.get("/api/items/unread-count").json()
    assert count == {"count": 1}


def test_mark_all_read_clears_queue(client, make_item):
    make_item(source_id="vidA")
    make_item(source_id="vidB")
    make_item(source_id="vidC", status="pending")  # not completed → not touched

    resp = client.post("/api/items/read-all")
    assert resp.status_code == 200
    assert resp.json() == {"count": 2}

    assert client.get("/api/items/unread-count").json() == {"count": 0}
    # The pending item is still unread (read filter), just not in the queue.
    assert client.get("/api/items", params={"read": "false"}).json()["total"] == 1


def test_mark_read_404(client):
    assert client.post("/api/items/nope/read").status_code == 404
    assert client.post("/api/items/nope/save").status_code == 404
