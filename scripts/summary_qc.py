"""Quality-check the YouTube summary prompts against already-ingested videos.

Re-summarises a sample of stored videos with the *current* prompt templates and
compares the result to the summary already saved in the DB ("before" vs
"after"). Reports the metrics we actually care about for the short summary:

  - bold-lead compliance: does every key point start with a **bold insight**
    (so skimming only the bold leads gives the gist)?
  - key-point count distribution: is the model padding to the 10-point cap, or
    using only as many points as the content warrants?

It is **read-only** on the database: it reads each item's stored transcript and
metadata and calls the plugin's synchronous `resummarize()` in-process, so it
never starts a server, never writes to the DB, and never touches the network
beyond the LLM calls the summariser itself makes.

Usage:
    uv run python scripts/summary_qc.py                      # 5 en + 5 fr, short
    uv run python scripts/summary_qc.py --n 8 --langs en,fr,de
    uv run python scripts/summary_qc.py --length long
    uv run python scripts/summary_qc.py --ids 9a99eef0,0c67b2a3
    uv run python scripts/summary_qc.py --db data/merlin.db --out summary_qc

Each run writes <out>/qc_<length>.json (full before/after) and prints the
metrics table. Add `--out` artifacts are gitignored under summary_qc/.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

# Allow `uv run python scripts/summary_qc.py` to import the `merlin` package:
# running a script puts scripts/ (not the repo root) on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merlin.bootstrap import register_plugins  # noqa: E402
from merlin.config import settings  # noqa: E402
from merlin.db.engine import SessionFactory  # noqa: E402
from merlin.knowledge_sources.registry import registry  # noqa: E402


def _pick_items(session, langs: list[str], n: int, ids: list[str] | None, length: str):
    """Read candidate items (read-only). Returns list of dicts with before-text."""
    from sqlalchemy import text

    if ids:
        rows = []
        for pref in ids:
            r = session.execute(
                text(
                    """
                    SELECT k.id, k.title, k.author, k.raw_content, k.summary,
                           lower(substr(m.detected_language,1,2)) AS lang,
                           m.detected_language AS detected
                    FROM knowledge_items k
                    JOIN youtube_metadata m ON m.knowledge_item_id = k.id
                    WHERE k.id LIKE :pat LIMIT 1
                    """
                ),
                {"pat": pref + "%"},
            ).fetchone()
            if r:
                rows.append(r)
    else:
        rows = []
        for lang in langs:
            got = session.execute(
                text(
                    """
                    SELECT k.id, k.title, k.author, k.raw_content, k.summary,
                           lower(substr(m.detected_language,1,2)) AS lang,
                           m.detected_language AS detected
                    FROM knowledge_items k
                    JOIN youtube_metadata m ON m.knowledge_item_id = k.id
                    WHERE k.status = 'completed' AND k.summary_length = :length
                      AND k.summary IS NOT NULL AND k.raw_content IS NOT NULL
                      AND lower(substr(m.detected_language,1,2)) = :lang
                    ORDER BY k.ingested_at DESC
                    LIMIT :n
                    """
                ),
                {"length": length, "lang": lang, "n": n},
            ).fetchall()
            rows.extend(got)

    return [
        {
            "id": r.id,
            "title": r.title,
            "author": r.author,
            "raw_content": r.raw_content,
            "detected": r.detected or "",
            "lang": r.lang,
            "before": r.summary or "",
        }
        for r in rows
    ]


def _key_points(text: str, length: str) -> list[str]:
    """Extract the numbered key points from a summary."""
    header = "## Main Key Points" if length == "short" else "## Key Points"
    parts = re.split(rf"^{re.escape(header)}\s*$", text, flags=re.M)
    if len(parts) < 2:
        return []
    section = re.split(r"^##\s+", parts[1], flags=re.M)[0]
    return re.findall(r"^\s*\d+\.\s+(.*)$", section, flags=re.M)


def _analyze(text: str, length: str) -> dict:
    pts = _key_points(text, length)
    leads = 0
    lead_words: list[int | str] = []
    for p in pts:
        m = re.match(r"\*\*(.+?)\*\*", p.strip())
        if m:
            leads += 1
            lead_words.append(len(m.group(1).split()))
        else:
            lead_words.append("X")
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    return {
        "n_points": len(pts),
        "bold_leads": leads,
        "lead_words": lead_words,
        "preamble": not first.strip().startswith("#"),
        "first_line": first.strip()[:80],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None, help="DB path (default: from settings)")
    ap.add_argument("--langs", default="en,fr", help="comma-separated 2-letter codes")
    ap.add_argument("--n", type=int, default=5, help="items per language")
    ap.add_argument(
        "--ids", default=None, help="comma-separated id prefixes (overrides langs/n)"
    )
    ap.add_argument("--length", default="short", choices=["short", "long"])
    ap.add_argument("--out", default="summary_qc", help="output dir for the JSON dump")
    args = ap.parse_args()

    if args.db:
        # point the engine at an explicit DB before it is first used
        settings.database_url = f"sqlite:///{Path(args.db).resolve()}"

    register_plugins()
    plugin = registry.get("youtube")
    if not plugin:
        raise SystemExit("youtube plugin not registered")

    langs = [s.strip().lower() for s in args.langs.split(",") if s.strip()]
    ids = [s.strip() for s in args.ids.split(",")] if args.ids else None

    with SessionFactory() as session:
        items = _pick_items(session, langs, args.n, ids, args.length)
    if not items:
        raise SystemExit("no matching items found")

    print(f"Re-summarising {len(items)} items ({args.length}) with current prompt…\n")
    results = []
    for it in items:
        # user_languages seeds with the video's own language then en/fr, mirroring
        # the service layer so a French video re-reads in French.
        base = it["detected"].split("-")[0].lower()
        user_langs = [lang for lang in (base, "en", "fr") if lang]
        summary, _topics, _ts = plugin.resummarize(
            raw_text=it["raw_content"],
            title=it["title"],
            channel=it["author"],
            detected_language=it["detected"],
            user_languages=user_langs,
            summary_length=args.length,
        )
        kept = {k: it[k] for k in ("id", "title", "lang", "before")}
        results.append({**kept, "after": summary})
        print(f"  {it['lang']} {it['id'][:8]}  {it['title'][:55]}")

    # ---- metrics ----
    hdr = f"\n{'id':<10} {'lang':<4} {'before':<12} {'after':<12} after bold-lead words"
    print(hdr)
    print("=" * 92)
    tot_pts = tot_lead = 0
    counts: list[int] = []
    for r in results:
        b = _analyze(r["before"], args.length)
        a = _analyze(r["after"], args.length)
        counts.append(a["n_points"])
        tot_pts += a["n_points"]
        tot_lead += a["bold_leads"]
        bdesc = f"{b['bold_leads']}/{b['n_points']}pts"
        adesc = f"{a['bold_leads']}/{a['n_points']}pts"
        row = f"{r['id'][:8]:<10} {r['lang']:<4} {bdesc:<12} {adesc:<12} "
        print(row + str(a["lead_words"]))

    mean = sum(counts) / len(counts)
    print("\n--- after: key-point count distribution ---")
    print(sorted(counts), f" mean={mean:.1f}", dict(Counter(counts)))
    pct = 100 * tot_lead / tot_pts if tot_pts else 0
    print(f"--- after: bold-lead compliance: {tot_lead}/{tot_pts} ({pct:.0f}%) ---")

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"qc_{args.length}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
