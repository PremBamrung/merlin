"""HybridRetriever — tokenized FTS5 + bm25 + snippet excerpts.

Runs against the real migrated temp DB (FTS triggers live), so these exercise
the actual SQLite FTS5 path, not a mock.
"""

from __future__ import annotations

from merlin.db.engine import get_db
from merlin.rag.retriever import HybridRetriever

_r = HybridRetriever()


def _retrieve(query, **kw):
    with get_db() as db:
        return _r.retrieve(db, query, **kw)


def test_build_fts_query_tokenizes_to_or_of_prefixes():
    assert _r._build_fts_query("What are DJI's moats?") == (
        "what* OR are* OR dji* OR moats*"
    )
    # 1-char letters dropped, single digits kept (version numbers), dedup
    # preserves order.
    assert _r._build_fts_query("a GPT 4 4 model a") == "gpt* OR 4* OR model*"


def test_build_fts_query_empty_when_no_tokens():
    assert _r._build_fts_query("???") == ""
    assert _r._build_fts_query("   ") == ""


def test_empty_query_returns_no_hits(make_item):
    make_item(title="Anything", summary="content")
    assert _retrieve("") == []
    assert _retrieve("!!!") == []


def test_natural_language_question_matches_on_content_words(make_item):
    """The old phrase query returned nothing here; tokenized OR finds it."""
    make_item(
        title="Vision Transformers explained",
        summary="A deep dive into the self-attention mechanism in transformers.",
        raw_content="Attention lets the model weigh tokens against each other.",
    )
    hits = _retrieve("how does attention work in a transformer?")
    assert len(hits) == 1
    assert "Transformers" in hits[0].title


def test_snippet_excerpt_drawn_from_matching_column(make_item):
    """A term that only appears in the transcript yields a transcript excerpt."""
    make_item(
        title="Generic title",
        summary="Generic summary.",
        raw_content="The speaker explains a UNIQUEXYZ concept at length here.",
    )
    hits = _retrieve("UNIQUEXYZ")
    assert len(hits) == 1
    assert "UNIQUEXYZ" in hits[0].excerpt


def test_source_type_filter(make_item):
    make_item(title="A YT moat video", source_type="youtube", summary="moat moat")
    make_item(
        title="A reddit moat post",
        source_type="reddit",
        source_id="rd1",
        summary="moat moat",
    )
    yt = _retrieve("moat", source_types=["youtube"])
    assert [h.source_type for h in yt] == ["youtube"]


def test_tag_filter(make_item):
    make_item(title="Tagged AI", summary="moat", tags=["ai"])
    make_item(title="Tagged cooking", source_id="c1", summary="moat", tags=["cooking"])
    hits = _retrieve("moat", tag_filters=["cooking"])
    assert len(hits) == 1
    assert "cooking" in hits[0].title.lower()


def test_results_ranked_and_capped(make_item):
    for i in range(5):
        make_item(
            title=f"Moat discussion {i}",
            source_id=f"m{i}",
            summary="moat " * (i + 1),
        )
    hits = _retrieve("moat", top_k=3)
    assert len(hits) == 3
    # Scores are descending (larger = more relevant after the bm25 flip).
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
