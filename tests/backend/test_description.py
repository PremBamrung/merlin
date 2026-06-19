"""Description grounding through the real router → service → DB path.

- the detail endpoint exposes the stored description
- the redo (resummarize) path self-heals a missing description via a cheap
  metadata-only fetch, grounds the new summary with it, and persists it
"""

from __future__ import annotations

import time


def test_item_detail_exposes_description(client, make_item):
    item_id = make_item(description="Chapters: 0:00 intro. Links: example.com")
    body = client.get(f"/api/items/{item_id}").json()
    assert body["description"] == "Chapters: 0:00 intro. Links: example.com"


def _wait_for_task(task_id: str, timeout: float = 10.0) -> dict:
    """Poll the task until it's done; return its final serialized dict."""
    from merlin.services import ingest

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = ingest.get_task(task_id)
        if task and task["status"] in ("completed", "failed"):
            return task
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} did not finish within {timeout}s")


def test_resummarize_self_heals_missing_description(client, make_item, monkeypatch):
    """An old item with no description gets one fetched + grounded on redo."""
    from merlin.knowledge_sources.plugins.youtube.extractors import VideoExtractor
    from merlin.knowledge_sources.registry import registry
    from merlin.services import ingest, library

    item_id = make_item(description=None)

    # The self-heal fetch is metadata-only — stub it to return a description
    # (and assert later that no transcript re-download was needed).
    monkeypatch.setattr(
        VideoExtractor,
        "extract_video_info",
        staticmethod(lambda url: {"description": "HEALED DESCRIPTION", "channel": "C"}),
    )

    # Avoid the real LLM: capture the description handed to the summariser.
    captured: dict = {}
    plugin = registry.get("youtube")

    def fake_resummarize(*, description=None, **kwargs):
        captured["description"] = description
        return ("## Overview\nfresh summary", {}, {})

    monkeypatch.setattr(plugin, "resummarize", fake_resummarize)

    task = _wait_for_task(ingest.resummarize(item_id))
    assert task["status"] == "completed"

    # Grounded: the fetched description reached the summariser.
    assert captured["description"] == "HEALED DESCRIPTION"
    # Persisted: the item is permanently healed and the new summary is stored.
    item = library.get_item(item_id)
    assert item["description"] == "HEALED DESCRIPTION"
    assert item["summary"] == "## Overview\nfresh summary"


def test_resummarize_skips_fetch_when_description_present(
    client, make_item, monkeypatch
):
    """Already-healed items don't trigger the metadata fetch on redo."""
    from merlin.knowledge_sources.plugins.youtube.extractors import VideoExtractor
    from merlin.knowledge_sources.registry import registry
    from merlin.services import ingest

    item_id = make_item(description="already here")

    def boom(url):
        raise AssertionError("extract_video_info must not be called when present")

    monkeypatch.setattr(VideoExtractor, "extract_video_info", staticmethod(boom))

    captured: dict = {}
    plugin = registry.get("youtube")

    def fake_resummarize(*, description=None, **kwargs):
        captured["description"] = description
        return ("## Overview\nx", {}, {})

    monkeypatch.setattr(plugin, "resummarize", fake_resummarize)

    task = _wait_for_task(ingest.resummarize(item_id))
    assert task["status"] == "completed"
    assert captured["description"] == "already here"
