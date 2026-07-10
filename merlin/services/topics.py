"""Topics service — the application layer for the cross-corpus taxonomy.

Framework-agnostic orchestration the UI/API calls; returns plain dicts (never
live ORM objects). SQL lives in `merlin.db.repositories.topics`.

Phase 1 covers the taxonomy CRUD, manual assignment, the topic filter's
uncategorised count, and slug generation. The batch proposal pipeline
(`propose_topics` + accept/reject/merge of proposals) is added in Phase 4.
"""

import re

from merlin.db.engine import SessionFactory
from merlin.db.repositories.topics import TopicRepository


def slugify(label: str) -> str:
    """Lowercase, hyphen-separated, alphanumeric slug. 'Smart Home!' -> 'smart-home'."""
    s = re.sub(r"[^a-z0-9]+", "-", label.strip().lower()).strip("-")
    return s or "topic"


def _unique_slug(session, label: str) -> str:
    """A slug for `label` that doesn't collide with an existing topic."""
    base = slugify(label)
    slug = base
    n = 2
    while TopicRepository.get_by_slug(session, slug) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


def _serialize_topic(topic, count: int = 0) -> dict:
    return {
        "id": topic.id,
        "slug": topic.slug,
        "label": topic.label,
        "status": topic.status,
        "origin": topic.origin,
        "description": topic.description,
        "count": count,
    }


# ---------------------------------------------------------------------------
# Taxonomy CRUD
# ---------------------------------------------------------------------------


def list_topics(status: str | None = "active") -> list[dict]:
    """Topics (default active) with their assigned-item counts, label-sorted."""
    with SessionFactory() as session:
        topics = TopicRepository.list_active(session, status=status)
        counts = TopicRepository.counts_by_topic(session)
        return [_serialize_topic(t, counts.get(t.id, 0)) for t in topics]


def create_topic(
    label: str, description: str | None = None, origin: str = "user"
) -> dict:
    """Create a new active topic. Raises ValueError on empty label."""
    label = (label or "").strip()
    if not label:
        raise ValueError("Topic label is required")
    with SessionFactory() as session:
        slug = _unique_slug(session, label)
        topic = TopicRepository.create(
            session, label=label, slug=slug, origin=origin, description=description
        )
        result = _serialize_topic(topic, 0)
        session.commit()
        return result


def rename_topic(topic_id: str, label: str) -> dict | None:
    """Change a topic's display label. Slug is stable (kept for existing links)."""
    label = (label or "").strip()
    if not label:
        raise ValueError("Topic label is required")
    with SessionFactory() as session:
        topic = TopicRepository.update(session, topic_id, label=label)
        if not topic:
            return None
        counts = TopicRepository.counts_by_topic(session)
        result = _serialize_topic(topic, counts.get(topic.id, 0))
        session.commit()
        return result


def archive_topic(topic_id: str) -> dict | None:
    """Archive a topic (hidden from the picker; keeps its assignments)."""
    with SessionFactory() as session:
        topic = TopicRepository.update(session, topic_id, status="archived")
        if not topic:
            return None
        counts = TopicRepository.counts_by_topic(session)
        result = _serialize_topic(topic, counts.get(topic.id, 0))
        session.commit()
        return result


def delete_topic(topic_id: str) -> bool:
    """Hard-delete a topic and its assignments (cascade)."""
    with SessionFactory() as session:
        ok = TopicRepository.delete(session, topic_id)
        if ok:
            session.commit()
        return ok


def merge_topics(src_id: str, dest_id: str) -> bool:
    """Fold src topic into dest (repoint assignments, dedup), delete src."""
    with SessionFactory() as session:
        ok = TopicRepository.merge(session, src_id, dest_id)
        if ok:
            session.commit()
        return ok


# ---------------------------------------------------------------------------
# Manual assignment
# ---------------------------------------------------------------------------


def set_item_topics(
    item_id: str, topic_ids: list[str], primary_id: str | None
) -> dict | None:
    """Replace an item's topic assignments with a user-chosen set.

    Writes `assigned_by="user"` — these rows are never clobbered by the
    LLM classifier (§10.4). `primary_id`, when given, must be one of
    `topic_ids` and becomes the single primary. Returns the item's new topic
    list (as serialize_item emits it), or None if the item is missing.
    """
    from merlin.db.repositories.knowledge import KnowledgeItemRepository

    topic_ids = list(dict.fromkeys(topic_ids or []))  # de-dupe, keep order
    if primary_id is not None and primary_id not in topic_ids:
        raise ValueError("primary_id must be one of the assigned topic ids")
    # A single primary must exist when any topics are assigned.
    if topic_ids and primary_id is None:
        primary_id = topic_ids[0]

    with SessionFactory() as session:
        item = KnowledgeItemRepository.get_by_id(session, item_id)
        if not item:
            return None
        # Validate the topics exist before touching anything.
        for tid in topic_ids:
            if TopicRepository.get(session, tid) is None:
                raise ValueError(f"Unknown topic id: {tid}")
        TopicRepository.clear_assignments(session, item_id)
        for tid in topic_ids:
            TopicRepository.add_assignment(
                session,
                item_id,
                tid,
                is_primary=(tid == primary_id),
                assigned_by="user",
            )
        assignments = TopicRepository.assignments_for_items(session, [item_id])
        session.commit()
    return {"item_id": item_id, "topics": assignments.get(item_id, [])}


# ---------------------------------------------------------------------------
# Uncategorised (drives the Feed affordance)
# ---------------------------------------------------------------------------


def count_uncategorised() -> int:
    """Completed items with no topic assignment yet."""
    with SessionFactory() as session:
        return TopicRepository.uncategorised_count(session)


# ---------------------------------------------------------------------------
# Batch proposal pipeline (§7) — discover new topics from the uncategorised pile
# ---------------------------------------------------------------------------


def propose_topics() -> str:
    """Kick off the batch proposal pipeline as a background task.

    Gathers the uncategorised items' title+summary, asks the LLM to cluster and
    label them (chunked + consolidated — see classify.propose_clusters), and
    writes the result as pending `topic_proposals` rows sharing a batch_id. A new
    run supersedes any still-pending proposals from prior batches. Returns a
    task_id to poll (same task queue as ingest).
    """
    import uuid

    from merlin.core.task_queue import task_queue
    from merlin.db.repositories.tasks import BackgroundTaskRepository

    def work(task_id: str, report) -> None:
        report(5, "Gathering uncategorised items…")
        with SessionFactory() as session:
            items = TopicRepository.uncategorised_items(session)
            data = [(i.id, i.title or "", i.summary or "") for i in items]

        if not data:
            with SessionFactory() as session:
                BackgroundTaskRepository.set_completed(
                    session, task_id, {"batch_id": None, "count": 0}
                )
                session.commit()
            return

        from merlin.core.task_queue import TaskCancelled
        from merlin.services.classify import _merge_by_label, propose_clusters

        batch_id = str(uuid.uuid4())
        # `partial` collects completed chunks so a mid-run cancel keeps that work.
        partial: list[dict] = []
        cancelled = False
        try:
            clusters = propose_clusters(data, report=report, sink=partial)
        except TaskCancelled:
            # Stop, but don't discard the batches that already finished: merge
            # them by label (skip the extra consolidation LLM call — we're
            # cancelling) and persist them as proposals.
            cancelled = True
            clusters = _merge_by_label(partial)

        # No report() after a cancel — it would re-raise TaskCancelled and abort
        # the save (the cancel flag is still set until the task ends).
        if not cancelled:
            report(90, "Saving proposals…")
        with SessionFactory() as session:
            # Supersede only now (after clustering finished/stopped) so a failed
            # run never wipes the existing pending proposals.
            TopicRepository.supersede_pending(session)
            for c in clusters:
                TopicRepository.create_proposal(
                    session,
                    proposed_label=c["proposed_label"],
                    item_ids=c["item_ids"],
                    rationale=c.get("rationale"),
                    batch_id=batch_id,
                )
            BackgroundTaskRepository.set_completed(
                session,
                task_id,
                {"batch_id": batch_id, "count": len(clusters), "cancelled": cancelled},
            )
            session.commit()

    return task_queue.submit_callable(work, task_type="propose_topics", input_data={})


def backfill_topics() -> str:
    """Classify the uncategorised backlog against the EXISTING taxonomy.

    The counterpart to `propose_topics`: where *discovery* invents new topics from
    the pile, *backfill* fits each still-uncategorised item to a topic that
    already exists (via `classify.classify_and_persist`, reused unchanged). Runs
    the ~1,100 LLM calls bounded-parallel + rate-limited through
    `parallel_map`, with live progress. Returns a task_id to poll.
    """
    from merlin.config import settings
    from merlin.core.parallel_llm import parallel_map
    from merlin.core.rate_limit import MinIntervalRateLimiter
    from merlin.core.task_queue import TaskCancelled, task_queue
    from merlin.db.repositories.tasks import BackgroundTaskRepository
    from merlin.services.classify import classify_and_persist

    def work(task_id: str, report) -> None:
        report(2, "Gathering uncategorised items…")
        with SessionFactory() as session:
            ids = [i.id for i in TopicRepository.uncategorised_items(session)]

        if not ids:
            with SessionFactory() as session:
                BackgroundTaskRepository.set_completed(
                    session,
                    task_id,
                    {"classified": 0, "requested": 0, "still_uncategorised": 0},
                )
                session.commit()
            return

        limiter = MinIntervalRateLimiter(
            settings.classify_min_interval,
            name="classify",
            cooldown_seconds=settings.classify_cooldown_seconds,
            cooldown_max=settings.classify_cooldown_seconds * 8,
        )
        # classify_and_persist commits per item, so items done before a cancel are
        # already saved — nothing to preserve, just stop and record the count.
        cancelled = False
        try:
            parallel_map(
                ids,
                classify_and_persist,
                concurrency=settings.classify_concurrency,
                limiter=limiter,
                report=report,
                label="Classified",
                progress_range=(5, 95),
                max_retries=settings.classify_max_retries,
            )
        except TaskCancelled:
            cancelled = True

        with SessionFactory() as session:
            remaining = TopicRepository.uncategorised_count(session)
            BackgroundTaskRepository.set_completed(
                session,
                task_id,
                {
                    "classified": len(ids) - remaining,
                    "requested": len(ids),
                    "still_uncategorised": remaining,
                    "cancelled": cancelled,
                },
            )
            session.commit()

    return task_queue.submit_callable(
        work, task_type="backfill_topics", input_data={}
    )


def _serialize_proposal(session, proposal) -> dict:
    import json

    ids = json.loads(proposal.item_ids) if proposal.item_ids else []
    items = TopicRepository.member_items(session, ids)
    return {
        "id": proposal.id,
        "proposed_label": proposal.proposed_label,
        "rationale": proposal.rationale,
        "batch_id": proposal.batch_id,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        "item_count": len(items),
        "items": items,
    }


def list_proposals(batch_id: str | None = None) -> list[dict]:
    """Pending proposals (label, rationale, resolved member items)."""
    with SessionFactory() as session:
        proposals = TopicRepository.list_proposals(
            session, batch_id=batch_id, status="pending"
        )
        return [_serialize_proposal(session, p) for p in proposals]


def _assign_members(session, item_ids: list[str], topic_id: str) -> int:
    """Assign each still-eligible member to `topic_id` as its primary.

    Tolerates drift (§7): skips ids that were deleted, or already carry a topic
    (manually classified, or covered by an earlier accepted proposal in the same
    batch). Returns how many were actually assigned.
    """
    from merlin.db.repositories.knowledge import KnowledgeItemRepository

    assigned = 0
    for iid in item_ids:
        item = KnowledgeItemRepository.get_by_id(session, iid)
        if item is None:
            continue
        if TopicRepository.get_assignments(session, iid):
            continue  # already categorised — leave it be
        TopicRepository.add_assignment(
            session, iid, topic_id, is_primary=True, assigned_by="llm"
        )
        assigned += 1
    return assigned


def accept_proposal(
    proposal_id: str, label: str | None = None, topic_id: str | None = None
) -> dict | None:
    """Accept a pending proposal.

    With `topic_id` → assign the members to that existing topic (merge into
    existing, no new topic). Otherwise create a new active topic (origin
    "proposed") from `label` (or the proposed label) and assign the members.
    Returns {topic, assigned, requested}, or None if the proposal is missing or
    no longer pending.
    """
    import json

    with SessionFactory() as session:
        proposal = TopicRepository.get_proposal(session, proposal_id)
        if proposal is None or proposal.status != "pending":
            return None
        item_ids = json.loads(proposal.item_ids) if proposal.item_ids else []

        if topic_id:
            topic = TopicRepository.get(session, topic_id)
            if topic is None:
                raise ValueError("Unknown target topic")
        else:
            lbl = (label or proposal.proposed_label).strip()
            if not lbl:
                raise ValueError("A topic label is required")
            slug = _unique_slug(session, lbl)
            topic = TopicRepository.create(
                session, label=lbl, slug=slug, origin="proposed"
            )

        assigned = _assign_members(session, item_ids, topic.id)
        proposal.status = "accepted"
        counts = TopicRepository.counts_by_topic(session)
        result = {
            "topic": _serialize_topic(topic, counts.get(topic.id, assigned)),
            "assigned": assigned,
            "requested": len(item_ids),
        }
        session.commit()
        return result


def reject_proposal(proposal_id: str) -> bool:
    """Reject a pending proposal — members stay uncategorised."""
    with SessionFactory() as session:
        proposal = TopicRepository.get_proposal(session, proposal_id)
        if proposal is None or proposal.status != "pending":
            return False
        proposal.status = "rejected"
        session.commit()
        return True
