"""Library endpoints — list/get/update/delete items, tags, source types.

Each handler calls exactly one `merlin.services.library` function and returns
the dict it produces. A service returning `None`/`False` for a missing row maps
to 404 via `not_found`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from merlin.services import library, topics as topics_service

from ..errors import not_found
from ..schemas import (
    CountResponse,
    Item,
    ItemListResponse,
    ItemTopicsResponse,
    ListItem,
    NameCount,
    SetItemTopicsRequest,
    UpdateItemRequest,
)

router = APIRouter(prefix="/api", tags=["items"])


@router.get("/items", response_model=ItemListResponse)
def list_items(
    search: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    tags: list[str] | None = Query(default=None),
    topics: list[str] | None = Query(default=None),
    read: bool | None = Query(default=None),
    saved: bool | None = Query(default=None),
    sort: str = "newest",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search_transcripts: bool = Query(default=False),
):
    return library.list_items(
        search=search,
        source_type=source_type,
        status=status,
        tags=tags,
        topics=topics,
        read=read,
        saved=saved,
        sort=sort,
        page=page,
        per_page=per_page,
        search_transcripts=search_transcripts,
    )


@router.get("/items/unread-count", response_model=CountResponse)
def unread_count():
    return {"count": library.count_unread()}


@router.post("/items/read-all", response_model=CountResponse)
def mark_all_read():
    return {"count": library.mark_all_read()}


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str):
    item = library.get_item(item_id)
    if item is None:
        raise not_found("Item not found.")
    return item


@router.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: str, body: UpdateItemRequest):
    updated = library.update_item(item_id, tags=body.tags, title=body.title)
    if updated is None:
        raise not_found("Item not found.")
    # Return the full detail shape (with raw_content) so the client cache is
    # consistent with GET /api/items/{id}.
    return library.get_item(item_id)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str):
    if not library.delete_item(item_id):
        raise not_found("Item not found.")
    return Response(status_code=204)


@router.post("/items/{item_id}/clear-summary", status_code=204)
def clear_summary(item_id: str):
    if not library.clear_summary(item_id):
        raise not_found("Item not found.")
    return Response(status_code=204)


@router.post("/items/{item_id}/read", response_model=ListItem)
def mark_read(item_id: str):
    item = library.set_read(item_id, True)
    if item is None:
        raise not_found("Item not found.")
    return item


@router.post("/items/{item_id}/unread", response_model=ListItem)
def mark_unread(item_id: str):
    item = library.set_read(item_id, False)
    if item is None:
        raise not_found("Item not found.")
    return item


@router.post("/items/{item_id}/save", response_model=ListItem)
def save_item(item_id: str):
    item = library.set_saved(item_id, True)
    if item is None:
        raise not_found("Item not found.")
    return item


@router.post("/items/{item_id}/unsave", response_model=ListItem)
def unsave_item(item_id: str):
    item = library.set_saved(item_id, False)
    if item is None:
        raise not_found("Item not found.")
    return item


@router.post("/items/{item_id}/topics", response_model=ItemTopicsResponse)
def set_item_topics(item_id: str, body: SetItemTopicsRequest):
    """Manually assign an item's topics (writes assigned_by="user")."""
    result = topics_service.set_item_topics(item_id, body.topic_ids, body.primary_id)
    if result is None:
        raise not_found("Item not found.")
    return result


@router.get("/tags", response_model=list[NameCount])
def list_tags(
    unread: bool = Query(
        default=False, description="Scope tag counts to unread items (the Feed)."
    ),
):
    return library.list_tags(unread_only=unread)


@router.get("/source-types", response_model=list[NameCount])
def list_source_types():
    return library.list_source_types()
