"""Small pure presentation helpers (no Streamlit, no merlin imports)."""

from datetime import date, datetime
from html import escape as _escape


def esc(value) -> str:
    """HTML-escape a value for safe inline rendering."""
    return _escape(str(value)) if value is not None else ""


def youtube_url(source_id: str, seconds: int | None = None) -> str:
    url = f"https://www.youtube.com/watch?v={source_id}"
    if seconds:
        url += f"&t={seconds}s"
    return url


def ts_to_seconds(stamp: str) -> int | None:
    """Convert 'HH:MM:SS' / 'MM:SS' / '90' into total seconds, or None."""
    if not stamp:
        return None
    parts = str(stamp).strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    secs = 0
    for n in nums:
        secs = secs * 60 + n
    return secs


def short(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def rel_date(iso: str | None) -> str:
    """A compact relative date like 'today', '3d ago', or 'Jun 11'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    today = date.today()
    delta = (today - dt.date()).days
    if delta <= 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if delta < 7:
        return f"{delta}d ago"
    if dt.year == today.year:
        return dt.strftime("%b %-d")
    return dt.strftime("%b %-d, %Y")
