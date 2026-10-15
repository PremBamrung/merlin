"""
AppStateRepository — get/set JSON values in the app_state key-value table.
"""

from datetime import UTC, datetime
import json
from typing import Any

from sqlalchemy.orm import Session

from merlin.db.models import AppState


class AppStateRepository:
    @staticmethod
    def get(session: Session, key: str) -> Any | None:
        row = session.get(AppState, key)
        return json.loads(row.value) if row else None

    @staticmethod
    def set(session: Session, key: str, value: Any) -> None:
        row = session.get(AppState, key)
        if row is None:
            row = AppState(key=key)
            session.add(row)
        row.value = json.dumps(value)
        row.updated_at = datetime.now(UTC)
        session.flush()
