"""Background-task progress — native, self-refreshing."""

from merlin.services import ingest
import streamlit as st
from ui.styles import STATUS_EMOJI
from ui.util import short


@st.fragment(run_every=2)
def task_panel(limit: int = 8) -> None:
    """Render recent ingest tasks; auto-refreshes every 2s while mounted."""
    tasks = ingest.recent_tasks(limit=limit)
    if not tasks:
        st.caption("No ingest tasks yet.")
        return

    active = sum(1 for t in tasks if t["status"] in ("queued", "processing"))
    st.caption(f"{active} active · {len(tasks)} recent")

    for t in tasks:
        emoji = STATUS_EMOJI.get(t["status"], "•")
        label = short(t.get("message") or t.get("error") or t["status"], 80)
        if t["status"] in ("queued", "processing"):
            pct = max(0, min(100, t.get("progress") or 0))
            st.progress(pct / 100, text=f"{emoji} {label}")
        elif t["status"] == "failed":
            st.error(f"{emoji} {t.get('error') or 'failed'}")
        else:
            st.caption(f"{emoji} {label}")
