"""Classification service — assign topics + tags to an item with one LLM call.

Source-agnostic (works off `title` + `summary`, not the transcript), so it lives
in the service layer, not the YouTube plugin: any future source type gets it for
free, and the plugin stays DB-agnostic (the classifier needs the current
vocabulary from the DB). `merlin/` may import langchain; no fastapi import, so
tests/test_architecture.py stays green.

The classifier NEVER invents a topic — it picks from the active taxonomy or
leaves the item uncategorised (new topics are born only via the batch proposal
pipeline, services.topics). It never clobbers a user-assigned topic (§10.4):
if the item has any `assigned_by="user"` row, topic writes are skipped entirely
(so it can't even write a competing secondary), leaving the user's choice intact.

Best-effort: `classify_and_persist` swallows its own errors (like
`_index_for_search`) so it can never fail an otherwise-good ingest.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from merlin.config import settings
from merlin.core.logging import logger
from merlin.db.engine import SessionFactory
from merlin.db.repositories.knowledge import KnowledgeItemRepository
from merlin.db.repositories.topics import TopicRepository

# Cap the vocabulary fed into the prompt so it can't grow unbounded (§10).
_MAX_TAGS_IN_PROMPT = 40
_MAX_SECONDARY = 2
_MAX_TAGS_OUT = 4


class ClassifyResult(BaseModel):
    """Structured output of one classification call."""

    primary: str | None = Field(
        default=None,
        description="Slug of the single best-fit topic from the provided list, "
        "or null if none genuinely fits.",
    )
    secondary: list[str] = Field(
        default_factory=list,
        description="0-2 additional topic slugs the item also clearly spans "
        "(from the provided list). Prefer fewer; do not fill slots.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="2-4 specific tags. Reuse an existing tag when close; "
        "only invent when genuinely new. Keep them specific, not broad.",
    )


_SYSTEM = (
    "You organise a personal knowledge base. You assign each item to the "
    "existing topic taxonomy and give it a few specific tags.\n\n"
    "Rules:\n"
    "- Choose the smallest honest set of topics: one primary, and only add a "
    "secondary (max 2) when the item genuinely spans it. Fewer is better — do "
    "NOT fill slots.\n"
    "- Pick topics ONLY from the EXISTING TOPICS list, by their slug. If "
    "NOTHING fits, return primary=null and no secondary. Never force a bad fit; "
    "never invent a topic that isn't in the list.\n"
    "- Tags: reuse an existing tag when close; keep them specific, not broad; "
    "2-4 max."
)


def _build_prompt(
    title: str, summary: str, active_topics: list[dict], top_tags: list[str]
) -> str:
    if active_topics:
        topic_lines = "\n".join(
            f"- {t['slug']}: {t['label']}"
            + (f" — {t['description']}" if t.get("description") else "")
            for t in active_topics
        )
    else:
        topic_lines = "(none yet — return primary=null)"
    tag_line = ", ".join(top_tags) if top_tags else "(none yet)"
    # Guard the prompt size — a very long summary adds nothing over the gist.
    summary = (summary or "")[:4000]
    return (
        f"EXISTING TOPICS (choose from these by slug — do not invent):\n"
        f"{topic_lines}\n\n"
        f"EXISTING TAGS (reuse when close; specific, not broad; max 4):\n"
        f"{tag_line}\n\n"
        f"TITLE: {title}\n"
        f"SUMMARY: {summary}"
    )


def classify_item(
    title: str,
    summary: str,
    active_topics: list[dict],
    top_tags: list[str],
) -> ClassifyResult:
    """One structured LLM call. Returns a primary slug (or None), up to 2
    secondary slugs, and 2-4 tags. Chooses topics only from `active_topics`;
    the caller still validates the slugs against the live taxonomy."""
    llm = settings.llm.with_structured_output(ClassifyResult)
    prompt = _build_prompt(title, summary, active_topics, top_tags)
    result = llm.invoke(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ]
    )
    # with_structured_output may return the model or a dict depending on backend.
    if isinstance(result, ClassifyResult):
        return result
    return ClassifyResult.model_validate(result)


def _clean_tags(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for t in tags:
        if isinstance(t, str):
            t = t.strip()
            if t and t.lower() not in {s.lower() for s in seen}:
                seen.append(t)
    return seen[:_MAX_TAGS_OUT]


def classify_and_persist(item_id: str) -> None:
    """Classify one item and write its topics + tags. Best-effort.

    - Topics: skipped entirely if the item has any user-assigned topic (never
      clobbers a manual choice, never writes a competing primary). Otherwise the
      item's LLM-assigned rows are replaced with the fresh classification. No
      primary ⇒ nothing written ⇒ the item stays uncategorised.
    - Tags: written only when the item currently has none (introduces tags for
      fresh/backlog items without ever clobbering hand-curated tags — there is
      no tag provenance column to distinguish them).
    """
    try:
        with SessionFactory() as session:
            item = KnowledgeItemRepository.get_by_id(session, item_id)
            if not item or not (item.summary or "").strip():
                return
            title = item.title or ""
            summary = item.summary or ""
            existing_tags = _parse_tags(item.tags)
            has_user = TopicRepository.has_user_assignment(session, item_id)
            active = TopicRepository.list_active(session)
            slug_to_id = {t.slug: t.id for t in active}
            active_vocab = [
                {"slug": t.slug, "label": t.label, "description": t.description}
                for t in active
            ]
        # No active topics AND the item already has tags → nothing to do.
        if not active_vocab and existing_tags:
            return

        from merlin.services import library

        top_tags = [t["name"] for t in library.list_tags()][:_MAX_TAGS_IN_PROMPT]
        result = classify_item(title, summary, active_vocab, top_tags)

        with SessionFactory() as session:
            item = KnowledgeItemRepository.get_by_id(session, item_id)
            if not item:
                return
            if not has_user:
                TopicRepository.clear_assignments(session, item_id, assigned_by="llm")
                primary = result.primary if result.primary in slug_to_id else None
                if primary:
                    TopicRepository.add_assignment(
                        session,
                        item_id,
                        slug_to_id[primary],
                        is_primary=True,
                        assigned_by="llm",
                    )
                    secondary = [
                        s
                        for s in dict.fromkeys(result.secondary)
                        if s in slug_to_id and s != primary
                    ][:_MAX_SECONDARY]
                    for s in secondary:
                        TopicRepository.add_assignment(
                            session,
                            item_id,
                            slug_to_id[s],
                            is_primary=False,
                            assigned_by="llm",
                        )
            # Tags: only when the item has none (never clobber curated tags).
            if not existing_tags:
                cleaned = _clean_tags(result.tags)
                if cleaned:
                    item.tags = json.dumps(cleaned)
            session.commit()
    except Exception:
        logger.warning("Classification failed for item %s", item_id, exc_info=True)


# ---------------------------------------------------------------------------
# Batch topic discovery (the proposal pipeline, §7)
# ---------------------------------------------------------------------------

# Summaries/items per clustering call. The uncategorised pile can be ~1,200 at
# cold start — too many summaries for one prompt — so we chunk, then do a cheap
# second-pass consolidation over the round-1 labels to merge near-duplicates.
_CLUSTER_CHUNK = 50


class _Cluster(BaseModel):
    label: str = Field(description="Short topic label, e.g. 'Coding' or 'Gaming'.")
    item_indices: list[int] = Field(
        default_factory=list, description="Indices of the member items in this batch."
    )
    rationale: str | None = Field(
        default=None, description="One line: what these items have in common."
    )


class _ClusterResponse(BaseModel):
    clusters: list[_Cluster] = Field(default_factory=list)


class _MergeGroup(BaseModel):
    final_label: str = Field(description="Canonical label for the merged cluster.")
    source_labels: list[str] = Field(
        default_factory=list, description="Round-1 labels this absorbs (near-dups)."
    )


class _MergeResponse(BaseModel):
    groups: list[_MergeGroup] = Field(default_factory=list)


_CLUSTER_SYSTEM = (
    "You organise a personal knowledge base. You are given a batch of items that "
    "have no topic yet. Group them into a SMALL number of broad navigation "
    "buckets (like 'Coding', 'Gaming', 'Healthcare', 'Finance') — the kind of "
    "high-level category someone browses by. For each cluster give a short label, "
    "the member item indices, and a one-line rationale. Leave an item out of all "
    "clusters if it fits no coherent group. Prefer few broad clusters over many "
    "narrow ones."
)

_MERGE_SYSTEM = (
    "You are consolidating candidate topic labels produced from different batches "
    "of the same library. Merge duplicates and near-duplicates (e.g. 'Smart Home' "
    "and 'Home Automation') into a final set of canonical labels. Return one group "
    "per final label listing the source labels it absorbs. Every source label must "
    "appear in exactly one group."
)


def _cluster_chunk(items: list[tuple[str, str, str]]) -> list[dict]:
    """One clustering call over a chunk of (id, title, summary). Returns
    [{proposed_label, item_ids, rationale}] with ids resolved from indices."""
    lines = "\n".join(
        f"{idx}: {title} — {summary[:300]}"
        for idx, (_id, title, summary) in enumerate(items)
    )
    llm = settings.llm.with_structured_output(_ClusterResponse)
    resp = llm.invoke(
        [
            {"role": "system", "content": _CLUSTER_SYSTEM},
            {"role": "user", "content": f"ITEMS:\n{lines}"},
        ]
    )
    resp = (
        resp
        if isinstance(resp, _ClusterResponse)
        else _ClusterResponse.model_validate(resp)
    )
    out: list[dict] = []
    for c in resp.clusters:
        ids = [items[i][0] for i in c.item_indices if 0 <= i < len(items)]
        if ids and c.label.strip():
            out.append(
                {
                    "proposed_label": c.label.strip(),
                    "item_ids": ids,
                    "rationale": (c.rationale or "").strip() or None,
                }
            )
    return out


def _consolidate(round1: list[dict]) -> list[dict]:
    """Second pass: merge near-duplicate labels across chunks into final
    proposals (unions the member ids). Falls back to round1 on any LLM error."""
    labels = sorted({c["proposed_label"] for c in round1})
    if len(labels) <= 1:
        return _merge_by_label(round1)
    try:
        llm = settings.llm.with_structured_output(_MergeResponse)
        resp = llm.invoke(
            [
                {"role": "system", "content": _MERGE_SYSTEM},
                {"role": "user", "content": "LABELS:\n" + "\n".join(labels)},
            ]
        )
        resp = (
            resp
            if isinstance(resp, _MergeResponse)
            else _MergeResponse.model_validate(resp)
        )
    except Exception:
        logger.warning(
            "Label consolidation failed; keeping round-1 labels", exc_info=True
        )
        return _merge_by_label(round1)

    # source label -> final label
    canonical: dict[str, str] = {}
    for g in resp.groups:
        final = g.final_label.strip()
        if not final:
            continue
        for src in g.source_labels:
            canonical[src.strip()] = final
    # Relabel round-1 clusters, then union by final label.
    relabelled = [
        {**c, "proposed_label": canonical.get(c["proposed_label"], c["proposed_label"])}
        for c in round1
    ]
    return _merge_by_label(relabelled)


def _merge_by_label(clusters: list[dict]) -> list[dict]:
    """Union member ids of clusters that share a (final) label."""
    by_label: dict[str, dict] = {}
    for c in clusters:
        label = c["proposed_label"]
        if label not in by_label:
            by_label[label] = {
                "proposed_label": label,
                "item_ids": [],
                "rationale": c.get("rationale"),
            }
        merged = by_label[label]
        for i in c["item_ids"]:
            if i not in merged["item_ids"]:
                merged["item_ids"].append(i)
        if not merged["rationale"] and c.get("rationale"):
            merged["rationale"] = c["rationale"]
    return list(by_label.values())


def propose_clusters(items: list[tuple[str, str, str]], report=None) -> list[dict]:
    """Cluster + label a set of (id, title, summary) items into topic proposals.

    Chunks over `_CLUSTER_CHUNK` items per call, then consolidates near-duplicate
    labels in a cheap second pass. Steady-state (a handful of items) is a single
    call. Returns [{proposed_label, item_ids, rationale}]. `report(pct, msg)` is
    an optional progress callback (the background task's reporter)."""
    if not items:
        return []
    chunks = [
        items[i : i + _CLUSTER_CHUNK] for i in range(0, len(items), _CLUSTER_CHUNK)
    ]
    logger.info("propose_clusters: %d items in %d chunk(s)", len(items), len(chunks))
    round1: list[dict] = []
    for n, chunk in enumerate(chunks, 1):
        if report:
            report(
                10 + int(70 * n / len(chunks)), f"Clustering batch {n}/{len(chunks)}…"
            )
        round1.extend(_cluster_chunk(chunk))
    if len(chunks) == 1:
        return _merge_by_label(round1)
    if report:
        report(85, "Consolidating labels…")
    return _consolidate(round1)


def _parse_tags(raw) -> list[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
        return [t for t in val if isinstance(t, str)] if isinstance(val, list) else []
    except Exception:
        return []
