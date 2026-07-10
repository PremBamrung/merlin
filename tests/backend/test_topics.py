"""Backend tests for the topic taxonomy: CRUD, the Feed topic filter (incl. the
uncategorised sentinel and search/relevance interplay), manual assignment, the
one-primary invariant, and the exact-match tag fix.

Real router → service → temp-SQLite path (schema via real Alembic migrations),
so the migration 010 tables + partial unique index are genuinely exercised.
"""

from __future__ import annotations

import pytest


def _create_topic(client, label: str) -> dict:
    r = client.post("/api/topics", json={"label": label})
    assert r.status_code == 201, r.text
    return r.json()


def _assign(client, item_id: str, topic_ids: list[str], primary_id=None) -> None:
    r = client.post(
        f"/api/items/{item_id}/topics",
        json={"topic_ids": topic_ids, "primary_id": primary_id},
    )
    assert r.status_code == 200, r.text


# --- CRUD -------------------------------------------------------------------


def test_create_and_list_topics(client):
    t = _create_topic(client, "Coding")
    assert t["slug"] == "coding"
    assert t["label"] == "Coding"
    assert t["count"] == 0
    listed = client.get("/api/topics").json()
    assert [x["slug"] for x in listed] == ["coding"]


def test_slug_collision_gets_suffixed(client):
    a = _create_topic(client, "Smart Home")
    b = _create_topic(client, "smart home!")  # slugifies to the same base
    assert a["slug"] == "smart-home"
    assert b["slug"] == "smart-home-2"


def test_rename_keeps_slug(client):
    t = _create_topic(client, "Coding")
    r = client.patch(f"/api/topics/{t['id']}", json={"label": "Software"})
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "Software"
    assert body["slug"] == "coding"  # stable for existing links


def test_archive_hides_from_active_list(client):
    t = _create_topic(client, "Coding")
    client.patch(f"/api/topics/{t['id']}", json={"archive": True})
    assert client.get("/api/topics").json() == []
    all_topics = client.get("/api/topics", params={"status": ""}).json()
    # status="" → no filter → the archived topic is still returned
    assert any(x["id"] == t["id"] for x in all_topics)


def test_delete_topic(client, make_item):
    t = _create_topic(client, "Coding")
    item = make_item(title="A coding video")
    _assign(client, item, [t["id"]])
    r = client.delete(f"/api/topics/{t['id']}")
    assert r.status_code == 204
    assert client.get("/api/topics").json() == []
    # The assignment cascaded away — item is uncategorised again.
    assert client.get("/api/topics/uncategorised-count").json()["count"] == 1


# --- manual assignment + invariants ----------------------------------------


def test_assign_sets_primary_and_serializes_on_item(client, make_item):
    coding = _create_topic(client, "Coding")
    ai = _create_topic(client, "AI")
    item = make_item(title="LLM tooling")
    _assign(client, item, [coding["id"], ai["id"]], primary_id=ai["id"])

    got = client.get(f"/api/items/{item}").json()
    topics = {t["slug"]: t["is_primary"] for t in got["topics"]}
    assert topics == {"ai": True, "coding": False}
    # Primary first in the serialized order.
    assert got["topics"][0]["slug"] == "ai"
    # Counts reflect the assignment.
    counts = {t["slug"]: t["count"] for t in client.get("/api/topics").json()}
    assert counts == {"ai": 1, "coding": 1}


def test_unread_scoped_topics_drop_read_and_recount(client, make_item):
    """?unread=true scopes counts to unread items and hides emptied topics."""
    coding = _create_topic(client, "Coding")
    gaming = _create_topic(client, "Gaming")
    a = make_item(title="A")
    b = make_item(title="B")
    c = make_item(title="C")
    _assign(client, a, [coding["id"]])
    _assign(client, b, [coding["id"]])
    _assign(client, c, [gaming["id"]])

    # Unscoped: both topics present with full counts.
    all_counts = {t["slug"]: t["count"] for t in client.get("/api/topics").json()}
    assert all_counts == {"coding": 2, "gaming": 1}

    # Read one Coding item and the only Gaming item.
    assert client.post(f"/api/items/{a}/read").status_code == 200
    assert client.post(f"/api/items/{c}/read").status_code == 200

    unread = client.get("/api/topics", params={"unread": True}).json()
    unread_counts = {t["slug"]: t["count"] for t in unread}
    # Coding drops to its 1 unread item; Gaming (fully read) disappears.
    assert unread_counts == {"coding": 1}


def test_unread_scoped_uncategorised_count(client, make_item):
    """?unread=true on the uncategorised count excludes read items."""
    make_item(title="unread-uncat")
    read = make_item(title="read-uncat")
    assert client.post(f"/api/items/{read}/read").status_code == 200

    total = client.get("/api/topics/uncategorised-count").json()["count"]
    unread = client.get(
        "/api/topics/uncategorised-count", params={"unread": True}
    ).json()["count"]
    assert total == 2
    assert unread == 1


def test_reassign_replaces_previous(client, make_item):
    a = _create_topic(client, "A")
    b = _create_topic(client, "B")
    item = make_item()
    _assign(client, item, [a["id"]])
    _assign(client, item, [b["id"]])  # full replace
    got = client.get(f"/api/items/{item}").json()
    assert [t["slug"] for t in got["topics"]] == ["b"]


def test_assign_defaults_first_as_primary(client, make_item):
    a = _create_topic(client, "A")
    b = _create_topic(client, "B")
    item = make_item()
    _assign(client, item, [a["id"], b["id"]], primary_id=None)
    got = client.get(f"/api/items/{item}").json()
    primary = [t["slug"] for t in got["topics"] if t["is_primary"]]
    assert primary == ["a"]  # exactly one primary, the first assigned


def test_assign_unknown_topic_400(client, make_item):
    item = make_item()
    r = client.post(
        f"/api/items/{item}/topics",
        json={"topic_ids": ["nope"], "primary_id": "nope"},
    )
    assert r.status_code == 400


def test_bad_primary_400(client, make_item):
    a = _create_topic(client, "A")
    item = make_item()
    r = client.post(
        f"/api/items/{item}/topics",
        json={"topic_ids": [a["id"]], "primary_id": "other"},
    )
    assert r.status_code == 400


# --- merge ------------------------------------------------------------------


def test_merge_repoints_and_dedupes(client, make_item):
    src = _create_topic(client, "Home Automation")
    dest = _create_topic(client, "Smart Home")
    only_src = make_item(title="only src")
    both = make_item(title="both")
    _assign(client, only_src, [src["id"]])
    _assign(client, both, [dest["id"], src["id"]], primary_id=dest["id"])

    r = client.patch(f"/api/topics/{src['id']}", json={"merge_into": dest["id"]})
    assert r.status_code == 200
    assert r.json()["id"] == dest["id"]
    # src is gone; dest carries both items exactly once.
    slugs = {t["slug"]: t["count"] for t in client.get("/api/topics").json()}
    assert slugs == {"smart-home": 2}
    # The item that had only src now sits under dest as its primary.
    got = client.get(f"/api/items/{only_src}").json()
    assert [(t["slug"], t["is_primary"]) for t in got["topics"]] == [
        ("smart-home", True)
    ]


# --- the Feed topic filter --------------------------------------------------


def test_filter_by_topic_slug(client, make_item):
    coding = _create_topic(client, "Coding")
    _create_topic(client, "Gaming")
    a = make_item(title="coding one")
    make_item(title="gaming one")
    _assign(client, a, [coding["id"]])

    body = client.get("/api/items", params={"topics": ["coding"]}).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == a


def test_filter_uncategorised_sentinel(client, make_item):
    coding = _create_topic(client, "Coding")
    a = make_item(title="categorised")
    b = make_item(title="uncategorised")
    _assign(client, a, [coding["id"]])

    body = client.get("/api/items", params={"topics": ["uncategorised"]}).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == b


def test_filter_mixes_sentinel_and_slug_or(client, make_item):
    coding = _create_topic(client, "Coding")
    _create_topic(client, "Gaming")
    a = make_item(title="coding")
    b = make_item(title="uncat")
    c = make_item(title="gaming")
    gaming_id = next(
        t["id"] for t in client.get("/api/topics").json() if t["slug"] == "gaming"
    )
    _assign(client, a, [coding["id"]])
    _assign(client, c, [gaming_id])

    body = client.get(
        "/api/items", params={"topics": ["coding", "uncategorised"]}
    ).json()
    got = {i["id"] for i in body["items"]}
    assert got == {a, b}  # coding OR uncategorised, not gaming


def test_topic_filter_holds_with_search(client, make_item):
    coding = _create_topic(client, "Coding")
    a = make_item(title="python tutorial", summary="learn python")
    make_item(title="python cooking", summary="python the snake")
    _assign(client, a, [coding["id"]])
    body = client.get(
        "/api/items", params={"topics": ["coding"], "search": "python"}
    ).json()
    assert [i["id"] for i in body["items"]] == [a]


def test_topic_filter_holds_with_relevance_sort(client, make_item):
    coding = _create_topic(client, "Coding")
    a = make_item(title="python tutorial", summary="python python python")
    make_item(title="python basics", summary="python")
    _assign(client, a, [coding["id"]])
    body = client.get(
        "/api/items",
        params={"topics": ["coding"], "search": "python", "sort": "relevance"},
    ).json()
    assert [i["id"] for i in body["items"]] == [a]


# --- exact-match tag fix ----------------------------------------------------


def test_tag_filter_exact_match_no_substring(client, make_item):
    make_item(title="safety piece", tags=["ai-safety"])
    match = make_item(title="ai piece", tags=["ai"])
    body = client.get("/api/items", params={"tags": ["ai"]}).json()
    # "ai" must NOT match "ai-safety" (the old substring bug).
    assert [i["id"] for i in body["items"]] == [match]


def test_one_primary_invariant_enforced_by_index(client, make_item):
    """A second is_primary row for the same item must violate ux_item_topics_primary."""
    from sqlalchemy.exc import IntegrityError

    from merlin.db.engine import SessionFactory
    from merlin.db.repositories.topics import TopicRepository

    a = _create_topic(client, "A")
    b = _create_topic(client, "B")
    item = make_item()
    with SessionFactory() as session:
        # add_assignment flushes, so the second primary trips the partial unique
        # index at insert time (not deferred to commit).
        with pytest.raises(IntegrityError):
            TopicRepository.add_assignment(
                session, item, a["id"], is_primary=True, assigned_by="user"
            )
            TopicRepository.add_assignment(
                session, item, b["id"], is_primary=True, assigned_by="user"
            )
            session.commit()


@pytest.mark.parametrize("count", [0, 3])
def test_uncategorised_count(client, make_item, count):
    for i in range(count):
        make_item(title=f"item {i}")
    assert client.get("/api/topics/uncategorised-count").json()["count"] == count
