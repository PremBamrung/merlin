"""
GET /api/graph/nodes  — knowledge items + tag nodes
GET /api/graph/edges  — item→tag edges + tag co-occurrence edges
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.engine import get_db_session
from backend.db.models import KnowledgeItem

router = APIRouter(prefix="/graph", tags=["graph"])


def _parse_tags(raw) -> list[str]:
    if not raw:
        return []
    try:
        result = json.loads(raw) if isinstance(raw, str) else raw
        return (
            [t for t in result if isinstance(t, str)]
            if isinstance(result, list)
            else []
        )
    except Exception:
        return []


@router.get("/nodes")
def get_graph_nodes(db: Session = Depends(get_db_session)):
    items = db.query(KnowledgeItem).filter(KnowledgeItem.status == "completed").all()

    tag_counts: dict[str, int] = {}
    for item in items:
        for tag in _parse_tags(item.tags):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    source_nodes = [
        {
            "id": item.id,
            "type": item.source_type,
            "label": (item.title or "Untitled")[:60],
            "tags": _parse_tags(item.tags),
            "ingested_at": item.ingested_at.isoformat() if item.ingested_at else None,
        }
        for item in items
    ]

    tag_nodes = [
        {"id": f"tag:{name}", "type": "tag", "label": name, "count": count}
        for name, count in sorted(tag_counts.items(), key=lambda x: -x[1])
    ]

    return {"nodes": source_nodes + tag_nodes}


@router.get("/edges")
def get_graph_edges(db: Session = Depends(get_db_session)):
    items = db.query(KnowledgeItem).filter(KnowledgeItem.status == "completed").all()

    edges = []
    tag_co: dict[str, set[str]] = {}

    for item in items:
        tags = _parse_tags(item.tags)
        for tag in tags:
            edges.append(
                {"source": item.id, "target": f"tag:{tag}", "type": "item_tag"}
            )
        # track tag co-occurrence
        for tag in tags:
            tag_co.setdefault(tag, set()).update(t for t in tags if t != tag)

    seen: set[tuple[str, str]] = set()
    for tag, related in tag_co.items():
        for other in related:
            key = tuple(sorted([tag, other]))
            if key not in seen:
                seen.add(key)
                edges.append(
                    {
                        "source": f"tag:{tag}",
                        "target": f"tag:{other}",
                        "type": "tag_cooccurrence",
                    }
                )

    return {"edges": edges}
