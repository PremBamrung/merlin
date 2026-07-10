"""Topic endpoints — the cross-corpus taxonomy (Feed navigation axis).

Thin skin over `merlin.services.topics`: each handler calls one service function
and returns the dict it produces. A service returning `None`/`False` for a
missing row maps to 404 via `not_found`; a `ValueError` maps to 400 by the
global handler.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from merlin.services import topics as topics_service

from ..errors import invalid_input, not_found
from ..schemas import (
    AcceptProposalRequest,
    AcceptProposalResponse,
    CountResponse,
    CreateTopicRequest,
    PatchTopicRequest,
    TaskIdResponse,
    TopicItem,
    TopicProposalResponse,
)

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=list[TopicItem])
def list_topics(status: str | None = Query(default="active")):
    return topics_service.list_topics(status=status)


@router.get("/uncategorised-count", response_model=CountResponse)
def uncategorised_count():
    return {"count": topics_service.count_uncategorised()}


# -- Batch proposal pipeline (§7) ------------------------------------------
# Declared before the /{topic_id} param routes so the literal /proposals path
# always wins.


@router.post("/proposals", response_model=TaskIdResponse, status_code=202)
def propose_topics():
    """Trigger the batch proposal pipeline (background task; poll the task_id)."""
    return {"task_id": topics_service.propose_topics()}


@router.get("/proposals", response_model=list[TopicProposalResponse])
def list_proposals(batch_id: str | None = Query(default=None)):
    return topics_service.list_proposals(batch_id=batch_id)


@router.post("/backfill", response_model=TaskIdResponse, status_code=202)
def backfill_topics():
    """Classify the uncategorised backlog against existing topics (background
    task; poll the task_id)."""
    return {"task_id": topics_service.backfill_topics()}


@router.post("/proposals/{proposal_id}/accept", response_model=AcceptProposalResponse)
def accept_proposal(proposal_id: str, body: AcceptProposalRequest):
    result = topics_service.accept_proposal(
        proposal_id, label=body.label, topic_id=body.topic_id
    )
    if result is None:
        raise not_found("Proposal not found or no longer pending.")
    return result


@router.post("/proposals/{proposal_id}/reject", status_code=204)
def reject_proposal(proposal_id: str):
    if not topics_service.reject_proposal(proposal_id):
        raise not_found("Proposal not found or no longer pending.")
    return Response(status_code=204)


@router.post("", response_model=TopicItem, status_code=201)
def create_topic(body: CreateTopicRequest):
    return topics_service.create_topic(body.label, description=body.description)


@router.patch("/{topic_id}", response_model=TopicItem)
def patch_topic(topic_id: str, body: PatchTopicRequest):
    """Rename, archive, or merge a topic (one action per request).

    `merge_into` folds this topic into the target and returns the *target*.
    """
    if body.merge_into:
        if not topics_service.merge_topics(topic_id, body.merge_into):
            raise invalid_input("Could not merge these topics.")
        merged = next(
            (
                t
                for t in topics_service.list_topics(status=None)
                if t["id"] == body.merge_into
            ),
            None,
        )
        if merged is None:
            raise not_found("Target topic not found.")
        return merged
    if body.archive:
        topic = topics_service.archive_topic(topic_id)
    elif body.label is not None:
        topic = topics_service.rename_topic(topic_id, body.label)
    else:
        raise invalid_input("Nothing to update.")
    if topic is None:
        raise not_found("Topic not found.")
    return topic


@router.delete("/{topic_id}", status_code=204)
def delete_topic(topic_id: str):
    if not topics_service.delete_topic(topic_id):
        raise not_found("Topic not found.")
    return Response(status_code=204)
