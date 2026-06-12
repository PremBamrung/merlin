"""Library endpoints — list/get/update/delete items, tags, source types.

Each handler calls exactly one `merlin.services.library` function and returns
the dict it produces. A service returning `None`/`False` for a missing row maps
to 404 via `not_found`.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Response

from merlin.services import library

from ..errors import not_found
from ..schemas import (
    Item,
    ItemListResponse,
    NameCount,
    UpdateItemRequest,
)

router = APIRouter(prefix="/api", tags=["items"])


@router.get("/items", response_model=ItemListResponse)
def list_items(
    search: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    tags: list[str] | None = Query(default=None),
    sort: str = "newest",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
):
    return library.list_items(
        search=search,
        source_type=source_type,
        status=status,
        tags=tags,
        sort=sort,
        page=page,
        per_page=per_page,
    )


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


@router.get("/tags", response_model=list[NameCount])
def list_tags():
    return library.list_tags()


@router.get("/source-types", response_model=list[NameCount])
def list_source_types():
    return library.list_source_types()
