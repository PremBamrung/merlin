"""The home digest — real router → services.home → temp SQLite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from merlin.services import chat_history, topics as topics_service

NOW = datetime.now(UTC)
OLD = (NOW - timedelta(days=30)).replace(tzinfo=None)
RECENT = (NOW - timedelta(hours=2)).replace(tzinfo=None)


def _since(hours: int = 24) -> str:
    return (NOW - timedelta(hours=hours)).isoformat()


def _topic(label: str, *item_ids: str) -> dict:
    t = topics_service.create_topic(label)
    for iid in item_ids:
        topics_service.set_item_topics(iid, [t["id"]], t["id"])
    return t


def test_empty_library(client):
    body = client.get("/api/home").json()
    assert body["unread_count"] == 0
    assert body["new_since_count"] == 0
    assert body["strip"] == []
    assert body["continue_thread"] is None
    assert body["busy_topic"] is None
    assert body["saved_revisit"] is None


def test_new_since_counts_and_busy_topic(client, make_item):
    a = make_item(title="New A", source_id="a", ingested_at=RECENT)
    b = make_item(title="New B", source_id="b", ingested_at=RECENT)
    c = make_item(title="Old C", source_id="c", ingested_at=OLD)
    _topic("Coffee", a, b)
    _topic("Archery", c)

    body = client.get("/api/home", params={"since": _since()}).json()
    assert body["new_since_count"] == 2
    assert body["unread_count"] == 3
    assert body["strip_kind"] == "new"
    assert {i["title"] for i in body["strip"]} == {"New A", "New B"}
    assert body["busy_topic"] == {
        "slug": "coffee",
        "label": "Coffee",
        "count": 2,
        "kind": "new",
    }


def test_nothing_new_falls_back_to_unread(client, make_item):
    a = make_item(title="Old unread", source_id="a", ingested_at=OLD)
    make_item(title="Old read", source_id="b", ingested_at=OLD, read_at=OLD)
    _topic("Archery", a)

    body = client.get("/api/home", params={"since": _since()}).json()
    assert body["new_since_count"] == 0
    assert body["strip_kind"] == "unread"
    assert [i["title"] for i in body["strip"]] == ["Old unread"]
    assert body["busy_topic"]["kind"] == "unread"
    assert body["busy_topic"]["label"] == "Archery"


def test_continue_thread_carries_last_reply_and_sources(client, make_item):
    cite = {
        "type": "data-citations",
        "data": {"items": [{"item_id": "x"}, {"item_id": "y"}]},
    }
    chat_history.save_thread(
        "t1",
        [
            {"id": "u1", "role": "user", "parts": [{"type": "text", "text": "q?"}]},
            {
                "id": "a1",
                "role": "assistant",
                "parts": [{"type": "text", "text": "The   answer\nis here."}, cite],
            },
        ],
    )
    body = client.get("/api/home").json()
    t = body["continue_thread"]
    assert t["id"] == "t1"
    assert t["last_reply"] == "The answer is here."
    assert t["source_count"] == 2


def test_saved_revisit_is_latest_saved(client, make_item):
    make_item(title="Saved first", source_id="a", saved_at=OLD)
    make_item(title="Saved last", source_id="b", saved_at=RECENT)
    body = client.get("/api/home").json()
    assert body["saved_revisit"]["title"] == "Saved last"
