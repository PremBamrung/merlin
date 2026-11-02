"""Summarise where library-chat turns spend their time.

Reads the `data-turn-timeline` part each answer carries (see
`merlin.services.chat_timeline`) and prints one line per answer plus medians.
Answers saved before the timeline existed are skipped.

From the saved threads (the DB `settings.database_url` points at — e.g. inside
the container, `docker compose exec api uv run python scripts/turn_timelines.py`):

    uv run python scripts/turn_timelines.py              # every thread
    uv run python scripts/turn_timelines.py --limit 5    # 5 most recent threads

From one thread fetched over the API (no DB needed):

    curl -s http://<host>:8000/api/chat/threads/<id> \\
        | uv run python scripts/turn_timelines.py --json -
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merlin.services.chat_timeline import TIMELINE_PART, describe  # noqa: E402


def _question(message: dict) -> str:
    text = " ".join(
        p.get("text", "") for p in message.get("parts", []) if p.get("type") == "text"
    )
    text = " ".join(text.split())
    return text[:70] + ("…" if len(text) > 70 else "")


def _timelines(thread: dict) -> list[tuple[str, dict]]:
    """`(question, timeline)` for each answer in the thread that has one."""
    out = []
    question = ""
    for m in thread.get("messages", []):
        if m.get("role") == "user":
            question = _question(m)
            continue
        for p in m.get("parts", []):
            if p.get("type") == TIMELINE_PART and isinstance(p.get("data"), dict):
                out.append((question, p["data"]))
    return out


def _load_threads(args) -> list[dict]:
    if args.json:
        raw = sys.stdin.read() if args.json == "-" else Path(args.json).read_text()
        data = json.loads(raw)
        return data if isinstance(data, list) else [data]
    from merlin.services import chat_history

    rows = chat_history.list_threads()
    if args.limit:
        rows = rows[: args.limit]
    return [t for r in rows if (t := chat_history.get_thread(r["id"]))]


def _sec(ms: float | None) -> str:
    return "?" if ms is None else f"{ms / 1000:.1f}s"


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--json", help="thread JSON file from the API ('-' = stdin)")
    ap.add_argument("--limit", type=int, help="only the N most recent threads")
    args = ap.parse_args()

    found: list[dict] = []
    for thread in _load_threads(args):
        rows = _timelines(thread)
        if not rows:
            continue
        print(f"\n## {thread.get('title') or thread.get('id')}")
        for question, tl in rows:
            print(f"- {question}\n  {describe(tl)}")
            found.append(tl)

    if not found:
        print("No answers with a turn timeline yet.")
        return

    def med(key: str) -> str:
        vals = [t[key] for t in found if t.get(key) is not None]
        return _sec(median(vals)) if vals else "?"

    steps = [len(t.get("steps") or []) for t in found]
    waits = [s["wait_ms"] for t in found for s in t.get("steps") or []]
    print(
        f"\n{len(found)} answer(s) — median: total {med('total_ms')}, "
        f"first text {med('first_text_ms')}, model {med('model_ms')}, "
        f"tools {med('tools_ms')}, {median(steps):g} step(s), "
        f"per-step wait {_sec(median(waits)) if waits else '?'}"
    )


if __name__ == "__main__":
    main()
