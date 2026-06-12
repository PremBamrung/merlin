"""Color constants + the Plotly template. No CSS, no Streamlit imports.

Mirrors apple_health/utils/styles.py: this is purely a palette for charts and
tag dots — all UI chrome is native Streamlit.
"""

import hashlib

PLOTLY_TEMPLATE = "plotly_dark"

# Streamlit's default-dark accent (red) — kept intentionally.
ACCENT = "#ff4b4b"

STATUS_COLORS = {
    "completed": "#21c45d",
    "processing": "#fbbf24",
    "queued": "#9aa0a6",
    "pending": "#9aa0a6",
    "failed": "#ff4b4b",
}

STATUS_EMOJI = {
    "completed": "🟢",
    "processing": "🟡",
    "queued": "⚪",
    "pending": "⚪",
    "failed": "🔴",
}

# Deterministic tag/category colors for charts + badges.
TAG_SWATCHES = [
    "#ff7043", "#42a5f5", "#66bb6a", "#ab47bc", "#ffca28",
    "#26c6da", "#ec407a", "#7e57c2", "#8d6e63", "#5c6bc0",
]


def tag_color(name: str) -> str:
    h = int(hashlib.md5(name.lower().encode()).hexdigest(), 16)
    return TAG_SWATCHES[h % len(TAG_SWATCHES)]
