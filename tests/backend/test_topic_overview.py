"""Topics overview + topic page — real router → services.topic_overview →
temp SQLite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from merlin.services import topics as topics_service

NOW = datetime.now(UTC)
OLD = (NOW - timedelta(days=30)).replace(tzinfo=None)
RECENT = (NOW - timedelta(hours=2)).replace(tzinfo=None)


def _assign(label: str, *item_ids: str) -> dict:
    t = topics_service.create_topic(label)
    for iid in item_ids:
        topics_service.set_item_topics(iid, [t["id"]], t["id"])
    return t


def test_overview_cards(client, make_item):
    a = make_item(
        title="A", source_id="a", ingested_at=RECENT, tags=["grind", "espresso"]
    )
    b = make_item(title="B", source_id="b", ingested_at=OLD, tags=["espresso"])
    c = make_item(
        title="C", source_id="c", ingested_at=RECENT, read_at=RECENT, tags=["espresso"]
    )
    d = make_item(title="D", source_id="d", ingested_at=OLD, tags=["bow"])
    _assign("Coffee", a, b, c)
    _assign("Archery", d)
    topics_service.create_topic("Empty")

    since = (NOW - timedelta(days=1)).isoformat()
    body = client.get("/api/topics/overview", params={"since": since}).json()
    assert body["total"] == 4
    labels = [t["label"] for t in body["topics"]]
    assert labels == ["Coffee", "Archery", "Empty"]  # biggest first
    coffee = body["topics"][0]
    assert coffee["count"] == 3
    assert coffee["new_count"] == 1  # A: new and unread; C is read
    assert coffee["share"] == 0.75
    assert coffee["top_tags"][0] == "espresso"
    assert [p["title"] for p in coffee["preview"]] == ["A", "C", "B"]  # newest first
    assert body["topics"][2]["count"] == 0 and body["topics"][2]["preview"] == []


def test_topic_detail(client, make_item):
    a = make_item(title="A", source_id="a", channel="Hoffmann", ingested_at=RECENT)
    b = make_item(title="B", source_id="b", channel="Hoffmann", ingested_at=OLD)
    c = make_item(title="C", source_id="c", channel="Lance", ingested_at=OLD)
    make_item(title="Other", source_id="o")
    t = _assign("Coffee", a, b, c)

    body = client.get(f"/api/topics/by-slug/{t['slug']}").json()
    assert body["label"] == "Coffee"
    assert body["count"] == 3
    assert body["share"] == 0.75
    assert body["seconds"] == 3 * (16 * 60 + 59)  # make_item's 00:16:59 each
    assert body["channel_count"] == 2
    assert body["channels"][0] == {"name": "Hoffmann", "count": 2}
    assert body["new_count"] == 1
    assert {x["name"] for x in body["tags"]} == {"ai", "python"}


def test_topic_detail_404(client):
    assert client.get("/api/topics/by-slug/nope").status_code == 404
