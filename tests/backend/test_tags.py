"""Tag normalisation — lowercase on write, case-blind filters, migration 014."""

from __future__ import annotations

import importlib
import json


def test_normalize_tags():
    from merlin.services.library import normalize_tags

    assert normalize_tags([" OLED ", "oled", "Dofus", "", 3, "dofus"]) == [
        "oled",
        "dofus",
    ]


def test_update_item_lowercases_tags(make_item):
    from merlin.services import library

    iid = make_item(tags=["ai"])
    out = library.update_item(iid, tags=["OLED", "oled", " Monitor "])
    assert out["tags"] == ["oled", "monitor"]


def test_classifier_tags_are_lowercased():
    from merlin.services.classify import _clean_tags

    assert _clean_tags(["Eliotrope", "eliotrope", "Cra"]) == ["eliotrope", "cra"]


def test_list_items_tag_filter_ignores_case(make_item):
    from merlin.services import library

    make_item(title="Panel", tags=["oled"])
    result = library.list_items(tags=["OLED"])
    assert [i["title"] for i in result["items"]] == ["Panel"]


def test_migration_014_lowercases_and_dedupes(make_item):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    from merlin.db.engine import engine
    from merlin.services import library

    mixed = make_item(title="Mixed case", tags=["OLED", "oled", "Monitor"])
    clean = make_item(title="Already clean", tags=["ai"])
    mod = importlib.import_module("merlin.db.migrations.versions.014_lowercase_tags")

    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()
        rows = dict(conn.execute(text("SELECT id, tags FROM knowledge_items")).all())

    assert json.loads(rows[mixed]) == ["oled", "monitor"]
    assert json.loads(rows[clean]) == ["ai"]
    # The FTS update trigger resynced the index: the new tag text is searchable.
    hits = library.list_items(search="monitor")["items"]
    assert [i["title"] for i in hits] == ["Mixed case"]
