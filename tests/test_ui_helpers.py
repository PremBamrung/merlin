"""Unit tests for pure UI helpers (no Streamlit runtime needed)."""

from ui.components.omnibox import omnibox_route
from ui.styles import TAG_SWATCHES, tag_color
from ui.util import rel_date, short, ts_to_seconds, youtube_url


def test_omnibox_route_classifies_links_as_ingest():
    for url in [
        "https://www.youtube.com/watch?v=abc123",
        "youtu.be/abc123",
        "www.example.com/post",
        "example.com/article",
    ]:
        kind, payload = omnibox_route(url)
        assert kind == "ingest", url
        assert payload == url


def test_omnibox_route_classifies_text_as_ask():
    kind, payload = omnibox_route("what did I learn about transformers")
    assert kind == "ask"
    assert payload == "what did I learn about transformers"


def test_omnibox_route_empty():
    assert omnibox_route("   ") == (None, "")


def test_ts_to_seconds():
    assert ts_to_seconds("01:02:03") == 3723
    assert ts_to_seconds("02:05") == 125
    assert ts_to_seconds("90") == 90
    assert ts_to_seconds("not-a-time") is None
    assert ts_to_seconds("") is None


def test_youtube_url_with_and_without_timestamp():
    assert youtube_url("xyz") == "https://www.youtube.com/watch?v=xyz"
    assert youtube_url("xyz", 90) == "https://www.youtube.com/watch?v=xyz&t=90s"


def test_tag_color_is_deterministic_and_in_palette():
    assert tag_color("ai") == tag_color("AI")  # case-insensitive
    assert tag_color("ai") in TAG_SWATCHES


def test_short_truncates_with_ellipsis():
    assert short("hello world", 5) == "hello…"
    assert short("hi", 5) == "hi"
    assert short(None, 5) == ""


def test_rel_date_handles_blank():
    assert rel_date(None) == ""
    assert rel_date("") == ""
