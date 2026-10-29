"""Freshness (surfaced_at) vs. the real ingest date — real router → service →
temp SQLite path.

- "Bring to top" on a duplicate ingest makes an item fresh: top of "Newest",
  back in the Feed, its summary and ingested_at untouched
- a redo (resummarize) does the same without moving ingested_at
"""

from __future__ import annotations

from datetime import datetime

from tests.backend.test_description import _wait_for_task

OLD = datetime(2026, 1, 1, 12, 0, 0)
NEWER = datetime(2026, 2, 1, 12, 0, 0)


def test_surface_brings_item_to_top_and_back_into_feed(client, make_item):
    old = make_item(
        title="Old", source_id="old", ingested_at=OLD, read_at=NEWER, summary="keep"
    )
    make_item(title="Newer", source_id="newer", ingested_at=NEWER)
    assert client.get("/api/items").json()["items"][0]["title"] == "Newer"

    body = client.post(f"/api/items/{old}/surface").json()
    assert body["id"] == old
    assert body["read_at"] is None
    assert body["ingested_at"] == OLD.isoformat()
    assert body["surfaced_at"] > NEWER.isoformat()

    listed = client.get("/api/items", params={"sort": "newest"}).json()["items"]
    assert [i["title"] for i in listed] == ["Old", "Newer"]
    unread = client.get("/api/items", params={"read": "false"}).json()["items"]
    assert "Old" in [i["title"] for i in unread]
    assert client.get(f"/api/items/{old}").json()["summary"] == "keep"


def test_surface_oldest_sort_still_uses_ingest_date(client, make_item):
    old = make_item(title="Old", source_id="old", ingested_at=OLD)
    make_item(title="Newer", source_id="newer", ingested_at=NEWER)
    client.post(f"/api/items/{old}/surface")

    listed = client.get("/api/items", params={"sort": "oldest"}).json()["items"]
    assert [i["title"] for i in listed] == ["Old", "Newer"]


def test_surface_missing_item_is_404(client):
    res = client.post("/api/items/nope/surface")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_resummarize_surfaces_without_moving_ingest_date(
    client, make_item, monkeypatch
):
    from merlin.knowledge_sources.registry import registry
    from merlin.services import ingest, library

    item_id = make_item(ingested_at=OLD, read_at=NEWER, description="present")
    monkeypatch.setattr(
        registry.get("youtube"),
        "resummarize",
        lambda **kwargs: ("## Overview\nfresh", {}, {}),
    )

    task = _wait_for_task(ingest.resummarize(item_id))
    assert task["status"] == "completed"

    item = library.get_item(item_id)
    assert item["ingested_at"] == OLD.isoformat()
    assert item["surfaced_at"] > NEWER.isoformat()
    assert item["read_at"] is None
