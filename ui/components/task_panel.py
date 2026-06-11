"""Background-task progress panel — a self-refreshing fragment."""

import streamlit as st

from merlin.services import ingest

_STATUS_ICON = {
    "queued": "⏳",
    "processing": "⚙️",
    "completed": "✅",
    "failed": "❌",
}


@st.fragment(run_every=2)
def task_panel(limit: int = 8) -> None:
    """Render recent ingest tasks; auto-refreshes every 2s while mounted."""
    tasks = ingest.recent_tasks(limit=limit)
    if not tasks:
        st.caption("No ingest tasks yet.")
        return

    active = [t for t in tasks if t["status"] in ("queued", "processing")]
    st.caption(f"{len(active)} active · {len(tasks)} recent")

    for t in tasks:
        icon = _STATUS_ICON.get(t["status"], "•")
        label = t["message"] or t["status"]
        if t["status"] in ("queued", "processing"):
            st.progress((t["progress"] or 0) / 100, text=f"{icon} {label}")
        elif t["status"] == "failed":
            st.error(f"{icon} {t['error'] or 'failed'}", icon="🚫")
        else:
            st.caption(f"{icon} {label}")
