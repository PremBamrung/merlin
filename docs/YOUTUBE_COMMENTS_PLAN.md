# YouTube Top Comments — Ingestion Investigation

> **Status:** investigation only, no code yet. Captures the options, the
> recommendation, the traps to avoid, and where this would land in the
> `merlin/` architecture. Date: 2026-06-19.

## Goal

When ingesting a YouTube video, additionally fetch the **most popular
("top") comments** alongside the existing metadata + transcript + description,
so they can be displayed, fed to the summariser, and/or indexed for chat RAG.

## TL;DR recommendation

Use **`yt-dlp`** — it is **already a dependency** (`pyproject.toml`, used by the
audio fallback). It can fetch comments **sorted "top" server-side** with no API
key and no quota ceiling. Treat comments as a **best-effort, capped,
non-blocking enrichment**: never let a missing/slow comment fetch fail an
ingest.

## The three real options

### 1. `yt-dlp` — recommended (already in `pyproject.toml`)

- No API key, no quota, actively maintained against YouTube changes.
- Supports **server-side "top" sorting**, so you get YouTube's own ranking
  instead of fetching everything and re-ranking. Relevant `extractor_args` on
  the `youtube` extractor:
  - `comment_sort=top` (default is `new`) — YouTube does the ranking.
  - `max_comments=N,M,R,T` — comma-separated cap:
    `max-comments, max-parents, max-replies, max-replies-per-thread`.
    e.g. `max_comments=50,all,0,0` ≈ top 50 top-level comments, no replies.
  - `getcomments=True` (Python-API equivalent of CLI `--write-comments`)
    triggers extraction.
- Each comment dict includes `text`, `like_count`, `author`, `timestamp`,
  `is_favorited` (creator heart), `author_is_uploader`, `parent` — enough to
  show "most-liked / pinned / creator-hearted."

### 2. YouTube Data API v3 (`commentThreads.list`)

- Official, SLA-backed. `order=relevance` (≈ top), up to 100/call at **1 quota
  unit/call**, 10,000 units/day free.
- **Downsides for Merlin:** requires provisioning + storing a Google API key
  (we currently use *zero* Google credentials — all metadata is scraped via
  pytube/InnerTube). Overkill unless batch-ingesting at volume.

### 3. `youtube-comment-downloader` / `yt-comment-dl`

- Dedicated lib with `SORT_BY_POPULAR (0)` vs `SORT_BY_RECENT (1)`. Original is
  **inactive**; `yt-comment-dl` is the maintained fork.
- A new dependency that does *less* than the yt-dlp we already ship. Skip unless
  yt-dlp's comment path proves flaky.

## Traps to avoid (the important part)

1. **It can be slow / it streams.** yt-dlp yields comments page-by-page
   (~20 at a time); "several minutes" for popular videos. **Always set
   `max_comments`** — without a cap it walks the entire comment tree. Cap
   top-level comments AND set replies to `0` to avoid recursing into threads.
2. **`comment_sort=top` is necessary but the cap is approximate.** The first
   `max_comments` number bounds the total; combine with `comment_sort=top` so
   the *capped* set is the *popular* set. Don't fetch `new` and re-sort by
   `like_count` yourself — you'd download far more for the same answer.
3. **Shares YouTube's rate-limit / bot-detection surface** — the same one the
   transcript path already fights. YouTube returns HTTP 429 on bursts; yt-dlp
   does **not** wait for the limit to reset (treats 429 as failure and gives
   up). Bot detection (403, fingerprinting) is increasingly aggressive.
   **Implication:** route comment fetches through the existing
   `MinIntervalRateLimiter` (or a sibling), since comments hit the same host as
   transcripts.
4. **Comments are frequently disabled / empty** (off, age-restricted,
   members-only). Treat missing/empty as normal — comments must **never** fail
   an ingest (mirrors transcript → audio fallback degradation).
5. **Don't double-fetch.** The audio transcriber already calls
   `yt_dlp.YoutubeDL(...).download(...)`. Comment extraction is a *separate*
   `extract_info(..., download=False)` call — only run it when needed.
6. **Quota math for Option 2** if reconsidered: 10k units/day "runs out fast" at
   real volume. Fine for a personal single-user app; not for library backfill.
7. **Storage / privacy.** Comments are user-generated PII (usernames, opinions).
   Store only what's used — text + like_count + author + pinned/hearted flags —
   not the full raw JSON blob.

## How this lands in the architecture

- **Extractor:** new method in
  `merlin/knowledge_sources/plugins/youtube/extractors.py` (alongside
  `extract_video_info`), guarded by the rate limiter, returning a small list of
  dicts.
- **Rate limiting:** reuse `MinIntervalRateLimiter`
  (`merlin/core/rate_limit.py`); add a `youtube_comment_min_interval` knob and a
  `youtube_max_comments` cap in `merlin/config.py`.
- **Model:** add a nullable `top_comments` (JSON-as-`Text`) column to
  `YouTubeMetadata` via a **hand-written** Alembic migration (autogenerate is
  unreliable here per CLAUDE.md).
- **Summarisation angle:** the genuinely *new* value is feeding top comments to
  the LLM as a "what viewers reacted to / corrections / audience-flagged
  timestamps" signal — same pattern as the recent description grounding.

## Open design decision (decide before coding)

**Are top comments a display feature, a summarisation input, or a chat-RAG
input?** Each has different storage/indexing implications — e.g. only the RAG
path needs them in `knowledge_fts`.

## Sources

- yt-dlp comment extraction overview — <https://write.corbpie.com/download-a-youtube-video-comments-with-yt-dlp/>
- yt-dlp 429 handling (#9427) — <https://github.com/yt-dlp/yt-dlp/issues/9427>
- yt-dlp bot detection (#13067) — <https://github.com/yt-dlp/yt-dlp/issues/13067>
- YouTube 429 guide — <https://decodo.com/blog/youtube-error-429>
- YouTube Data API quota — <https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota>
- No-key alternatives — <https://tubealfred.com/blog/youtube-api-alternatives/>
- Scraping YouTube in 2026 — <https://scrapfly.io/blog/posts/how-to-scrape-youtube>
- youtube-comment-downloader — <https://github.com/egbertbouman/youtube-comment-downloader>
- yt-comment-dl (maintained fork) — <https://pypi.org/project/yt-comment-dl/>
