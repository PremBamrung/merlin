"""Vector search — embedder backends, RRF fusion, and the retriever's hybrid arm.

The Jina HTTP boundary is monkeypatched (no live calls). The retriever runs
against the real migrated temp DB; the embedder is injected per-test.
"""

from __future__ import annotations

import json

from merlin.db.engine import get_db
from merlin.db.repositories.knowledge import EmbeddingRepository
from merlin.rag import embeddings as emb
from merlin.rag.embeddings import (
    JinaEmbedder,
    NullEmbedder,
    item_embed_text,
)
from merlin.rag.retriever import HybridRetriever, RetrievedChunk

_r = HybridRetriever()


# --------------------------------------------------------------------------- #
# item_embed_text
# --------------------------------------------------------------------------- #
def test_item_embed_text_joins_present_parts():
    assert item_embed_text("Title", "A summary.", ["ai", "ml"]) == (
        "Title\nai ml\nA summary."
    )


def test_item_embed_text_drops_empty_parts():
    assert item_embed_text(None, "Only summary", None) == "Only summary"
    assert item_embed_text("", "", []) == ""


# --------------------------------------------------------------------------- #
# NullEmbedder
# --------------------------------------------------------------------------- #
def test_null_embedder_is_inert():
    n = NullEmbedder()
    assert n.enabled is False
    assert n.embed(["x"]) == []
    assert n.rerank("q", ["d"]) is None


# --------------------------------------------------------------------------- #
# JinaEmbedder — request shape + parsing (HTTP mocked)
# --------------------------------------------------------------------------- #
class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_jina_embed_sends_passage_task_and_parses_by_index(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = headers["Authorization"]
        # Return out of order to prove we sort by index.
        return _FakeResp(
            {
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            }
        )

    monkeypatch.setattr(emb.requests, "post", fake_post)
    je = JinaEmbedder("k", "model-x", "rerank-x")
    out = je.embed(["a", "b"], query=False)

    assert out == [[0.1, 0.2], [0.3, 0.4]]  # re-ordered to match input order
    assert captured["url"] == "https://api.jina.ai/v1/embeddings"
    assert captured["json"]["task"] == "retrieval.passage"
    assert captured["json"]["normalized"] is True
    assert captured["json"]["input"] == ["a", "b"]
    assert captured["auth"] == "Bearer k"


def test_jina_embed_waits_on_rate_limiter_before_calling(monkeypatch):
    """The process-wide limiter gates the HTTP call (off by default, but must be
    invoked so a configured interval actually throttles)."""
    calls = []
    monkeypatch.setattr(emb._rate_limiter, "wait", lambda: calls.append("wait"))

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append("post")
        return _FakeResp({"data": [{"index": 0, "embedding": [1.0]}]})

    monkeypatch.setattr(emb.requests, "post", fake_post)
    JinaEmbedder("k", "m", "r").embed(["x"])
    assert calls == ["wait", "post"]  # throttle gate precedes the request


def test_jina_embed_uses_query_task_when_query_true(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return _FakeResp({"data": [{"index": 0, "embedding": [1.0]}]})

    monkeypatch.setattr(emb.requests, "post", fake_post)
    JinaEmbedder("k", "m", "r").embed(["q"], query=True)
    assert captured["json"]["task"] == "retrieval.query"


def test_jina_embed_empty_input_makes_no_call(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("should not be called for empty input")

    monkeypatch.setattr(emb.requests, "post", boom)
    assert JinaEmbedder("k", "m", "r").embed([]) == []


def test_jina_rerank_parses_results(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeResp(
            {
                "results": [
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.5},
                ]
            }
        )

    monkeypatch.setattr(emb.requests, "post", fake_post)
    out = JinaEmbedder("k", "m", "rerank-y").rerank("q", ["a", "b", "c"], top_n=2)

    assert out == [(2, 0.9), (0, 0.5)]
    assert captured["url"] == "https://api.jina.ai/v1/rerank"
    assert captured["json"]["model"] == "rerank-y"
    assert captured["json"]["return_documents"] is False
    assert captured["json"]["top_n"] == 2


# --------------------------------------------------------------------------- #
# get_embedder factory
# --------------------------------------------------------------------------- #
def test_get_embedder_is_null_without_provider(monkeypatch):
    # Backend conftest forces EMBEDDING_PROVIDER=none; confirm the factory honours
    # it even with a key present.
    monkeypatch.setattr(emb.settings, "embedding_provider", "none")
    emb.get_embedder.cache_clear()
    assert isinstance(emb.get_embedder(), NullEmbedder)
    emb.get_embedder.cache_clear()


def test_get_embedder_builds_jina_when_configured(monkeypatch):
    monkeypatch.setattr(emb.settings, "embedding_provider", "jina")
    monkeypatch.setattr(emb.settings, "jina_api_key", "secret")
    emb.get_embedder.cache_clear()
    e = emb.get_embedder()
    assert isinstance(e, JinaEmbedder)
    emb.get_embedder.cache_clear()


# --------------------------------------------------------------------------- #
# RRF — pure function
# --------------------------------------------------------------------------- #
def _chunk(iid, title="t", excerpt="e"):
    return RetrievedChunk(
        knowledge_item_id=iid,
        source_type="youtube",
        source_id=f"src_{iid}",
        title=title,
        author=None,
        excerpt=excerpt,
    )


def test_rrf_single_list_preserves_order():
    """With no vector arm, fusion must reproduce the FTS order exactly."""
    fts = [_chunk("a"), _chunk("b"), _chunk("c")]
    fused = HybridRetriever._rrf(fts, [], top_k=10)
    assert [c.knowledge_item_id for c in fused] == ["a", "b", "c"]
    scores = [c.score for c in fused]
    assert scores == sorted(scores, reverse=True)  # strictly decreasing by rank


def test_rrf_dedupes_and_boosts_items_in_both_lists():
    # 'b' is rank 1 in FTS and rank 0 in vector → highest combined score.
    fts = [_chunk("a"), _chunk("b")]
    vec = [_chunk("b"), _chunk("c")]
    fused = HybridRetriever._rrf(fts, vec, top_k=10)
    ids = [c.knowledge_item_id for c in fused]
    assert ids[0] == "b"  # appears in both → wins
    assert set(ids) == {"a", "b", "c"}  # deduped union
    assert len(ids) == 3


def test_rrf_prefers_fts_chunk_as_representative():
    fts = [_chunk("a", excerpt="lexical-snippet")]
    vec = [_chunk("a", excerpt="vector-summary")]
    fused = HybridRetriever._rrf(fts, vec, top_k=10)
    assert fused[0].excerpt == "lexical-snippet"


def test_rrf_respects_top_k():
    fts = [_chunk(x) for x in "abcde"]
    fused = HybridRetriever._rrf(fts, [], top_k=2)
    assert len(fused) == 2


# --------------------------------------------------------------------------- #
# Retriever vector arm (embedder injected)
# --------------------------------------------------------------------------- #
class _FakeEmbedder:
    """Maps a fixed phrase to a fixed vector; everything else is orthogonal."""

    enabled = True
    model = "fake"

    def __init__(self, query_vec, rerank_result=None):
        self._query_vec = query_vec
        self._rerank_result = rerank_result

    def embed(self, texts, *, query=False):
        return [self._query_vec for _ in texts]

    def rerank(self, query, documents, *, top_n=None):
        return self._rerank_result


def _store_vec(item_id, vector):
    with get_db() as db:
        EmbeddingRepository.upsert(
            db,
            knowledge_item_id=item_id,
            chunk_index=0,
            chunk_text="x",
            embedding=json.dumps(vector),
            embedding_model="fake",
        )
        db.commit()


def test_vector_arm_surfaces_semantic_match_with_no_lexical_overlap(
    make_item, monkeypatch
):
    """A query with zero keyword overlap still finds the nearest vector."""
    a = make_item(title="Alpha", summary="alpha", source_id="a", tags=[])
    b = make_item(title="Beta", summary="beta", source_id="b", tags=[])
    _store_vec(a, [1.0, 0.0])
    _store_vec(b, [0.0, 1.0])

    # Query embeds to [1,0] → cosine 1.0 with A, 0.0 with B. The literal query
    # text ("zzqqxx") matches neither item lexically, so FTS returns nothing.
    fake = _FakeEmbedder([1.0, 0.0])
    monkeypatch.setattr("merlin.rag.retriever.get_embedder", lambda: fake)

    with get_db() as db:
        hits = _r.retrieve(db, "zzqqxx", top_k=5)

    assert [h.knowledge_item_id for h in hits] == [a, b]


def test_null_embedder_keeps_pure_fts(make_item):
    """Regression guard: with the (default) NullEmbedder, a vector exists in the
    table but a non-lexical query still returns nothing."""
    a = make_item(title="Alpha", summary="alpha", source_id="a")
    _store_vec(a, [1.0, 0.0])
    with get_db() as db:
        assert _r.retrieve(db, "zzqqxx", top_k=5) == []


def test_vector_arm_degrades_to_fts_on_embed_error(make_item, monkeypatch):
    """If the embedder raises, the vector arm is skipped and FTS still answers."""
    a = make_item(title="Transformers", summary="attention mechanism", source_id="a")

    class _Boom:
        enabled = True
        model = "boom"

        def embed(self, texts, *, query=False):
            raise RuntimeError("jina down")

        def rerank(self, query, documents, *, top_n=None):
            return None

    monkeypatch.setattr("merlin.rag.retriever.get_embedder", lambda: _Boom())
    with get_db() as db:
        hits = _r.retrieve(db, "transformers attention", top_k=5)
    assert [h.knowledge_item_id for h in hits] == [a]


def test_rerank_reorders_fused_candidates(make_item, monkeypatch):
    """The rerank pass reorders by returned indices."""
    a = make_item(title="Apple", summary="apple fruit moat", source_id="a")
    b = make_item(title="Banana", summary="banana fruit moat", source_id="b")
    # No vector arm (empty query vec) so order comes from FTS, then rerank flips.
    fake = _FakeEmbedder([], rerank_result=None)

    # Capture fused order, then make rerank reverse it.
    def fake_get():
        return fake

    monkeypatch.setattr("merlin.rag.retriever.get_embedder", fake_get)
    with get_db() as db:
        baseline = _r.retrieve(db, "fruit moat", top_k=5)
    base_ids = [h.knowledge_item_id for h in baseline]
    assert set(base_ids) == {a, b}

    # Now return a rerank that puts the last candidate first.
    fake._rerank_result = [(len(base_ids) - 1, 0.9)] + [
        (i, 0.1) for i in range(len(base_ids) - 1)
    ]
    with get_db() as db:
        reranked = _r.retrieve(db, "fruit moat", top_k=5)
    assert reranked[0].knowledge_item_id == base_ids[-1]


# --------------------------------------------------------------------------- #
# store_item_embedding (ingest hook / backfill shared path)
# --------------------------------------------------------------------------- #
def test_store_item_embedding_writes_row(make_item):
    item_id = make_item(title="Stored", summary="content", source_id="s")
    fake = _FakeEmbedder([0.5, 0.5])
    with get_db() as db:
        wrote = emb.store_item_embedding(
            db,
            item_id=item_id,
            title="Stored",
            summary="content",
            tags=["x"],
            embedder=fake,
        )
        db.commit()
    assert wrote is True
    with get_db() as db:
        cands = EmbeddingRepository.candidates_for_search(db)
    assert any(c["knowledge_item_id"] == item_id for c in cands)


def test_store_item_embedding_noop_under_null_embedder(make_item):
    item_id = make_item(title="Skipped", summary="content", source_id="s")
    with get_db() as db:
        wrote = emb.store_item_embedding(
            db,
            item_id=item_id,
            title="Skipped",
            summary="content",
            tags=[],
            embedder=NullEmbedder(),
        )
    assert wrote is False
