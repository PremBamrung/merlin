"""
Export YouTube knowledge items for EDA and LoRA fine-tuning.

Outputs (in export/):
  - youtube_items.json      — full joined dataset (EDA)
  - youtube_items.csv       — same data, flat CSV (EDA)
  - finetune_pairs.jsonl    — (transcript, summary) pairs in ChatML format (LoRA)
  - DATASET.md              — schema + stats doc
"""

import csv
from datetime import datetime
import json
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).parent.parent / "data" / "merlin.db"
OUT_DIR = Path(__file__).parent.parent / "export"
OUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = (
    "You are a knowledge assistant. Given a YouTube video transcript, "
    "write a concise structured summary covering the main ideas, key points, and takeaways."
)


def fetch_rows(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT
            ki.id,
            ki.source_id          AS video_id,
            ki.title,
            ki.author             AS channel_name,
            ki.published_at,
            ki.ingested_at,
            ki.raw_content        AS transcript,
            ki.summary,
            ki.summary_length,
            ki.tags,
            ki.sections AS topics,
            ki.llm_model,
            ki.word_count,
            ki.status,
            ym.channel,
            ym.views,
            ym.duration,
            ym.subscribers,
            ym.detected_language,
            ym.thumbnail_url,
            ym.timestamps
        FROM knowledge_items ki
        LEFT JOIN youtube_metadata ym ON ym.knowledge_item_id = ki.id
        WHERE ki.source_type = 'youtube'
          AND ki.status = 'completed'
        ORDER BY ki.ingested_at
    """)
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        # parse JSON string fields into native types
        for field in ("tags", "topics", "timestamps"):
            if d[field]:
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        rows.append(d)
    return rows


def write_json(rows: list[dict]) -> Path:
    path = OUT_DIR / "youtube_items.json"
    with open(path, "w") as f:
        json.dump(rows, f, indent=2, default=str)
    return path


def write_csv(rows: list[dict]) -> Path:
    path = OUT_DIR / "youtube_items.csv"
    if not rows:
        return path
    # flatten list/dict fields to JSON strings for CSV compatibility
    flat_rows = []
    for r in rows:
        flat = dict(r)
        for field in ("tags", "topics", "timestamps"):
            if isinstance(flat[field], (list, dict)):
                flat[field] = json.dumps(flat[field])
        flat_rows.append(flat)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=flat_rows[0].keys())
        writer.writeheader()
        writer.writerows(flat_rows)
    return path


def write_finetune_jsonl(rows: list[dict]) -> tuple[Path, int, int]:
    """ChatML format: system + user (transcript) → assistant (summary)."""
    path = OUT_DIR / "finetune_pairs.jsonl"
    skipped = 0
    written = 0
    with open(path, "w") as f:
        for r in rows:
            if not r["transcript"] or not r["summary"]:
                skipped += 1
                continue
            record = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": r["transcript"]},
                    {"role": "assistant", "content": r["summary"]},
                ],
                # metadata passengers — ignored by trainers but useful for filtering
                "_meta": {
                    "id": r["id"],
                    "video_id": r["video_id"],
                    "title": r["title"],
                    "llm_model": r["llm_model"],
                    "summary_length": r["summary_length"],
                    "detected_language": r["detected_language"],
                    "word_count": r["word_count"],
                },
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    return path, written, skipped


def compute_stats(rows: list[dict]) -> dict:
    models = {}
    lengths = {}
    langs = {}
    transcript_words = []
    summary_words = []
    for r in rows:
        models[r["llm_model"] or "unknown"] = models.get(r["llm_model"] or "unknown", 0) + 1
        lengths[r["summary_length"] or "unknown"] = lengths.get(r["summary_length"] or "unknown", 0) + 1
        lang = r["detected_language"] or "unknown"
        langs[lang] = langs.get(lang, 0) + 1
        if r["transcript"]:
            transcript_words.append(len(r["transcript"].split()))
        if r["summary"]:
            summary_words.append(len(r["summary"].split()))

    def avg(lst):
        return round(sum(lst) / len(lst)) if lst else 0

    return {
        "total": len(rows),
        "models": models,
        "summary_lengths": lengths,
        "languages": langs,
        "avg_transcript_words": avg(transcript_words),
        "avg_summary_words": avg(summary_words),
        "max_transcript_words": max(transcript_words) if transcript_words else 0,
    }


def write_dataset_md(rows: list[dict], stats: dict, ft_written: int, ft_skipped: int) -> Path:
    path = OUT_DIR / "DATASET.md"
    now = datetime.utcnow().strftime("%Y-%m-%d")

    models_table = "\n".join(f"| {m} | {c} |" for m, c in sorted(stats["models"].items(), key=lambda x: -x[1]))
    langs_table = "\n".join(f"| {l} | {c} |" for l, c in sorted(stats["languages"].items(), key=lambda x: -x[1]))

    content = rf"""# Merlin YouTube Export — Dataset Documentation

Generated: {now}

## Overview

| Field | Value |
|-------|-------|
| Total items | {stats["total"]} |
| Fine-tune pairs | {ft_written} |
| Skipped (missing transcript or summary) | {ft_skipped} |
| Avg transcript length | {stats["avg_transcript_words"]:,} words |
| Avg summary length | {stats["avg_summary_words"]:,} words |
| Max transcript length | {stats["max_transcript_words"]:,} words |

---

## Files

| File | Format | Purpose |
|------|--------|---------|
| `youtube_items.json` | JSON array | Full dataset for EDA — all fields, parsed JSON sub-fields |
| `youtube_items.csv` | CSV | Same data, JSON-string-encoded nested fields — spreadsheet/pandas friendly |
| `finetune_pairs.jsonl` | JSONL (ChatML) | One line per training example, ready for Unsloth / axolotl / LLaMA-Factory |
| `DATASET.md` | Markdown | This file |

---

## Schema

### `youtube_items.json` / `youtube_items.csv`

One record per ingested YouTube video. Fields are a flat join of `knowledge_items` and `youtube_metadata`.

| Field | Type | Source table | Description |
|-------|------|-------------|-------------|
| `id` | string (UUID) | knowledge_items | Primary key |
| `video_id` | string | knowledge_items.source_id | YouTube video ID (e.g. `dQw4w9WgXcQ`) |
| `title` | string | knowledge_items | Video title |
| `channel_name` | string | knowledge_items.author | Uploader channel name |
| `published_at` | datetime | knowledge_items | Video publish date |
| `ingested_at` | datetime | knowledge_items | When Merlin ingested it |
| `transcript` | string | knowledge_items.raw_content | Full transcript / subtitle text |
| `summary` | string | knowledge_items | LLM-generated summary |
| `summary_length` | string | knowledge_items | `short` \| `medium` \| `long` |
| `tags` | array | knowledge_items | JSON array of tag strings |
| `topics` | object | knowledge_items | JSON map of topic → timestamp |

| `llm_model` | string | knowledge_items | Model that generated the summary |
| `word_count` | int | knowledge_items | Word count of the transcript |
| `status` | string | knowledge_items | Always `completed` in this export |
| `channel` | string | youtube_metadata | Channel name (YouTube-side) |
| `views` | int | youtube_metadata | View count at ingest time |
| `duration` | string | youtube_metadata | Video duration (`HH:MM:SS`) |
| `subscribers` | string | youtube_metadata | Subscriber count string |
| `detected_language` | string | youtube_metadata | ISO language code of transcript |
| `thumbnail_url` | string | youtube_metadata | YouTube thumbnail URL |
| `timestamps` | object | youtube_metadata | Topic-to-timestamp map (may overlap `topics`) |

### `finetune_pairs.jsonl`

ChatML format — one JSON object per line:

```json
{{
  "messages": [
    {{"role": "system", "content": "<system prompt>"}},
    {{"role": "user",   "content": "<full transcript>"}},
    {{"role": "assistant", "content": "<summary>"}}
  ],
  "_meta": {{
    "id": "<uuid>",
    "video_id": "<yt_id>",
    "title": "<title>",
    "llm_model": "<model that wrote the summary>",
    "summary_length": "short|medium|long",
    "detected_language": "<iso code>",
    "word_count": 1234
  }}
}}
```

`_meta` is a non-standard passenger field — strip it before passing to a trainer if needed.

---

## Data Provenance

### Summaries by LLM model

| Model | Count |
|-------|-------|
{models_table}

> **Note:** Summaries were generated at different times with different models and prompts.
> For consistent LoRA fine-tuning signal, consider re-summarizing all items with a single
> model and a fixed prompt template before training.

### Languages

| Language | Count |
|----------|-------|
{langs_table}

---

## Relationships

```
knowledge_items (1) ──── (1) youtube_metadata
     id ──────────────────── knowledge_item_id
     source_id               video_id
     raw_content             channel / views / duration
     summary                 detected_language / thumbnail_url
     tags / topics           timestamps
```

The join key is `knowledge_items.id = youtube_metadata.knowledge_item_id`.
In the flat export files this join is already resolved — no joining needed.
"""
    path.write_text(content)
    return path


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = fetch_rows(conn)
    finally:
        conn.close()

    stats = compute_stats(rows)

    json_path = write_json(rows)
    csv_path = write_csv(rows)
    jsonl_path, ft_written, ft_skipped = write_finetune_jsonl(rows)
    md_path = write_dataset_md(rows, stats, ft_written, ft_skipped)

    print(f"Exported {stats['total']} items to {OUT_DIR}/")
    print(f"  {json_path.name}")
    print(f"  {csv_path.name}")
    print(f"  {jsonl_path.name}  ({ft_written} pairs, {ft_skipped} skipped)")
    print(f"  {md_path.name}")
    print()
    print(f"Avg transcript: {stats['avg_transcript_words']:,} words")
    print(f"Avg summary:    {stats['avg_summary_words']:,} words")
    print(f"Models: {stats['models']}")


if __name__ == "__main__":
    main()
