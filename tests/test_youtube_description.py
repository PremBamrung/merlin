"""Unit tests for video-description grounding (no DB, no network, no LLM).

Covers the three pure building blocks:
- the per-item chat context includes the description as its own section
- the summariser prompt carries the description block (and omits it when blank)
- the self-heal gap detector reports which grounding fields are missing
"""

from types import SimpleNamespace

from merlin.knowledge_sources.plugins.youtube.summarizer import VideoSummarizer
from merlin.rag.prompts import format_item_context
from merlin.services.ingest import _missing_youtube_fields

# --- per-item chat context -------------------------------------------------- #


def test_chat_context_includes_description():
    ctx = format_item_context(
        {
            "title": "T",
            "summary": "S",
            "description": "Links and chapters live here.",
            "raw_content": "transcript",
        }
    )
    assert "VIDEO DESCRIPTION:" in ctx
    assert "Links and chapters live here." in ctx
    # Ordered: description sits between summary and the transcript.
    assert (
        ctx.index("SUMMARY:")
        < ctx.index("VIDEO DESCRIPTION:")
        < ctx.index("FULL TRANSCRIPT:")
    )


def test_chat_context_omits_blank_description():
    for desc in (None, "", "   "):
        ctx = format_item_context(
            {"title": "T", "summary": "S", "description": desc, "raw_content": "x"}
        )
        assert "VIDEO DESCRIPTION:" not in ctx


# --- summariser prompt ------------------------------------------------------ #


def _render(summarizer, length, description):
    tpl = summarizer.templates[length]
    return tpl.format(
        subtitles="subs",
        lang="english",
        title="T",
        channel="C",
        description_block=summarizer._build_description_block(description),
    )


def test_prompt_includes_description_block_both_lengths():
    s = VideoSummarizer(model=object())  # llm never touched by .format()
    for length in ("short", "long"):
        rendered = _render(s, length, "Sponsored by Acme. See chapters below.")
        assert "Video description" in rendered
        assert "Sponsored by Acme." in rendered


def test_prompt_omits_block_when_description_blank():
    s = VideoSummarizer(model=object())
    for length in ("short", "long"):
        rendered = _render(s, length, "   ")
        assert "Video description" not in rendered


def test_description_block_is_truncated():
    s = VideoSummarizer(model=object())
    block = s._build_description_block("x" * (s._DESCRIPTION_CHAR_CAP + 500))
    assert "[description truncated]" in block
    # Capped near the limit, not the full oversized input.
    assert len(block) < s._DESCRIPTION_CHAR_CAP + 200


# --- self-heal gap detector ------------------------------------------------- #


def test_missing_fields_when_no_metadata_row():
    assert _missing_youtube_fields(None) == ["description"]


def test_missing_fields_flags_empty_description():
    assert _missing_youtube_fields(SimpleNamespace(description=None)) == ["description"]
    assert _missing_youtube_fields(SimpleNamespace(description="")) == ["description"]


def test_missing_fields_empty_when_present():
    assert _missing_youtube_fields(SimpleNamespace(description="has text")) == []
