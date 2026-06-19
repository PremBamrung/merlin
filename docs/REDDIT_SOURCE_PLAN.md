# Reddit Knowledge Source — Design Plan

> Status: **planning only**. Mirrors the existing YouTube source. No code written yet.

## Goal

Add Reddit threads as a knowledge source alongside YouTube: ingest a thread URL,
summarise it into the same "overview + main key points" shape, and store it in the
source-agnostic knowledge base. The twist unique to Reddit: **insights must be
weighted by upvotes**, because on Reddit the value lives in the crowd-ranked
comments, not (only) in the original post.

## Why this fits the plugin architecture

The dependency arrow (`api/` → `merlin.services` → `merlin.{core,db,rag,knowledge_sources}`)
and the plugin model mean most of the pipeline is reused unchanged: the task queue,
FTS5 index + triggers, `(source_type, source_id)` dedup, and the `IngestResult`
envelope. The real work is in two source-specific places, plus one small core fix.

### How Reddit differs from YouTube (this drives every design choice)

| | YouTube | Reddit |
|---|---|---|
| Content shape | One linear transcript, one author | A post + a **tree of comments**, many authors |
| Where value lives | The video itself | Often in **highly-upvoted comments**, not the post |
| Quality signal | None | **Upvote scores** = crowd-ranked relevance |
| "Insight" | What the speaker said | What the community *concluded* — consensus + dissent |

Because of this, Reddit needs its own summariser prompt (the linear-transcript prompt
doesn't model "OP asked X; top answer ▲2.1k says Y; a ▲400 reply corrects it").

## File-by-file plan

### 1. New plugin package — `merlin/knowledge_sources/plugins/reddit/`
- `plugin.py` — `RedditPlugin(KnowledgeSourcePlugin)`, `source_type="reddit"`,
  `display_name="Reddit Thread"`. `can_handle()` = regex for
  `reddit.com/r/*/comments/*` (plus `redd.it`, `old.reddit.com`, `/s/` share links).
  `ingest()` orchestrates extract → serialize → summarise → `IngestResult`.
  `source_id` = the base-36 post id (the dedup key).
- `extractors.py` — fetch the thread + comment tree with scores (see Fetching below).
- `summarizer.py` — the Reddit-specific upvote-aware prompt (see Summarisation below).

### 2. DB — a `reddit_metadata` table (mirrors `youtube_metadata`)
Hand-written Alembic migration (autogenerate is unreliable here):
- PK `knowledge_item_id` FK→`knowledge_items` (cascade delete), `post_id` (unique),
  `subreddit`, `op_author`, `score`, `upvote_ratio`, `num_comments`,
  `post_type` (self/link), `permalink`, `flair`, `top_comment_score`.
- Add `RedditMetadataRepository.upsert()` in `merlin/db/repositories/`.
- Add the `reddit_metadata` relationship on `KnowledgeItem`.
- **No FTS changes** — triggers fire on `knowledge_items` only, so search just works.

### 3. Core fix — `persist_result` is not actually source-agnostic
`merlin/services/ingest.py::persist_result` hardcodes, for *every* source:
```python
YouTubeMetadataRepository.upsert(session, item.id, result.source_metadata)
```
To add Reddit, branch on `result.source_type` (a small dispatch map
`source_type → repository.upsert`). This is the one required core change — worth
doing cleanly now so source #3 is free.

### 4. Service layer
`submit_reddit(url, ...)` in `services/ingest.py`, mirroring `submit_youtube`
(validate → dedup by post_id → enqueue with `on_complete=persist_result`).
Resummarise works for free since `raw_content` is stored.

### 5. API + UI
- `POST /ingest/reddit` + `IngestRedditRequest` schema (keeps the thin-adapter rule).
- Add a source toggle (or rely on `can_handle` auto-detection from one omnibox) in
  the Streamlit ingest form.

## Fetching / downloading the thread

Reddit returns the entire thread as JSON for free — no API key, no HTML scraping.

### The core trick: append `.json` to any thread URL
```
https://www.reddit.com/r/AskHistorians/comments/abc123/some_title/.json
```
Returns a JSON array of **two `Listing` objects**:
- `data[0]` → the **post** (the submission)
- `data[1]` → the **comment tree**

**Post object** — `data[0].data.children[0].data`:
```
title, selftext         # selftext = body (empty for link posts)
author, id              # id = base-36 post id → source_id / dedup key
score, upvote_ratio     # upvote signal + controversy signal
num_comments
created_utc             # → published_at
subreddit, permalink
url, is_self            # is_self=false → link post, content is elsewhere
link_flair_text
```

**Comment tree** — `data[1].data.children`: a list of nodes, each with a `kind`:
- `"t1"` → a real comment
- `"more"` → a "load N more replies" placeholder (NOT loaded — see gotchas)

A `t1` comment's `data`:
```
body, author, score, created_utc
depth                   # nesting level (0 = top-level)
is_submitter            # true if OP is replying
stickied, distinguished # filter out mod/AutoMod stickies
replies                 # "" if none, else ANOTHER Listing (recursive)
```
`comment.data.replies.data.children` is the recursive list of child nodes.

### The param that does the upvote-weighting for you
```
{permalink}.json?sort=top&limit=200&depth=2
```
- **`sort=top`** → comments come back **already ranked by upvotes, server-side**.
  This collapses the summariser's "selection algorithm" to *"take the first N"*.
- **`limit`** → caps comment count.
- **`depth=2`** → top-level + one reply level (captures corrections/dissent).

### Code sketch (`extractors.py`)
```python
import requests

UA = "merlin/0.1 (personal knowledge manager)"   # REQUIRED — see gotchas

def fetch_thread(permalink: str, limit: int = 200) -> tuple[dict, list]:
    url = f"https://www.reddit.com{permalink}.json?sort=top&depth=2&limit={limit}"
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    resp.raise_for_status()
    post_listing, comment_listing = resp.json()
    return (
        post_listing["data"]["children"][0]["data"],
        comment_listing["data"]["children"],
    )

def flatten(children, out, max_depth=2):
    """Depth-first walk → flat list, skipping junk."""
    for node in children:
        if node["kind"] == "more":          # "load more" placeholder — skip in v1
            continue
        c = node["data"]
        if c.get("body") in ("[deleted]", "[removed]") or c.get("stickied"):
            continue
        out.append({
            "score": c["score"],
            "author": c.get("author"),
            "body": c["body"],
            "depth": c.get("depth", 0),
            "is_op": c.get("is_submitter", False),
        })
        replies = c.get("replies")
        if replies and c.get("depth", 0) < max_depth:   # replies is "" when empty
            flatten(replies["data"]["children"], out, max_depth)
```
Synchronous blocking I/O — exactly what the thread-pool plugin model wants. Wrap the
`requests.get` in the existing `MinIntervalRateLimiter` (`core/rate_limit.py`), same
as the YouTube subtitle fetcher.

### Gotchas to design around
1. **User-Agent is mandatory.** Reddit hard-blocks empty/generic agents with
   `429`/`403`. Set a descriptive one. (#1 reason naive fetchers fail.)
2. **`more` objects truncate deep threads.** The `.json` endpoint won't auto-expand
   "load 200 more comments." For popular threads you get the top slice — which is the
   high-upvote content you actually want. **Log how many comments were dropped** so
   truncation isn't silent. If exhaustive trees are ever needed, that's the moment to
   switch to PRAW (`replace_more()`).
3. **URL normalization before fetching.** Resolve `redd.it/...` and `/s/` share links
   by following redirects (`allow_redirects=True`, read `resp.url`); normalize
   `old.`/`www.`; strip trailing query junk before appending `.json`.
4. **Post type changes what "content" means.** A self-post has `selftext` = body;
   a link post has empty `selftext` and `url` off-site (content = title + comments,
   don't fetch the linked page — that's a future article plugin's job). Branch on
   `is_self`.

### PRAW alternative (for later)
`pip install praw`, register a script app for client id/secret, then
`reddit.submission(url=...)`, `submission.comments.replace_more(limit=0)`,
iterate `submission.comments.list()`. 100 req/min under OAuth + clean `more`
expansion, at the cost of a credential dependency in `.env`/`Settings`. Keep fetching
behind a single `fetch_thread()` function so JSON→PRAW is a one-file swap.

## Summarisation — "main insights" weighted by upvotes

Principle: **don't compute weights yourself — feed scores to the LLM inline and let it
reason**, but *do* deterministically pre-select/sort comments (trivial when
`sort=top` already ranked them) so you fit the context window reproducibly.

### Selection (in `extractors.py`)
1. Drop `[deleted]`/`[removed]`, AutoModerator, bot stickies.
2. Take the top ~15–25 top-level comments (already score-sorted by `sort=top`).
3. Include each one's single highest-scored reply above a threshold (captures
   corrections/debates — where the real insight often is).
4. Cap total chars to a token budget; keep `score` + `depth` so the LLM sees structure.

### Serialization fed to the LLM (scores inline)
```
[POST] ▲1,240 · 92% upvoted · r/AskHistorians · u/op
Title: <title>
<self-text body>

[TOP COMMENTS — ▲ = upvotes, higher = stronger community agreement]
▲892  u/a: <comment>
  ▲210 u/b (reply): <correction/dissent>
▲451  u/c: <comment>
▲ 88  u/d: <comment>
```

### Reddit short-summary prompt (draft)
```
You are summarizing a Reddit thread. A Reddit thread is a question or
post from the original poster (OP) followed by community responses, each
annotated with an upvote score (▲). Treat upvotes as the crowd's signal
of agreement and value: the highest-upvoted comments are the de-facto
accepted answers and should dominate the key points. A low upvote_ratio
on the post (or a heavily-upvoted reply that contradicts a comment)
signals controversy worth flagging.

Produce:

1. Overview (2 sentences max)
   - First: what OP asked or posted.
   - Second: the community's dominant conclusion — i.e. what the
     highest-upvoted responses actually answered. Use **bold** for key
     entities/claims.

2. Top Insights (up to 8, ordered by community weight, not by thread order)
   - Lead with the insights backed by the highest-upvoted comments.
   - Where a highly-upvoted reply corrects or disputes a comment, say so
     explicitly (e.g. "**Top answer claims X, but a ▲400 reply corrects
     this to Y**").
   - Each point 1–2 lines, **bold** the key term. Skip low-signal chatter.

3. Consensus vs. Controversy (1–2 lines)
   - Note whether the thread broadly agrees or is contested.

Write in {lang}.

{serialized_thread}
```
This produces the YouTube-style "overview + main key points" feel, but the points are
crowd-ranked and it surfaces the consensus/dissent dimension unique to Reddit. Reuse
the numbered-section parser pattern from the YouTube summariser (minus timestamps —
Reddit's analog is score / permalink anchor).

## Open decisions before building
1. **Fetch method** — public JSON (zero-setup, rate-limited, truncates deep trees) vs
   PRAW (credentials, robust). Recommendation: start with JSON behind a single
   `fetch_thread()` function.
2. **Comment-tree depth** — top-level only (simple) vs top-level + best reply
   (captures corrections). Recommendation: top-level + best reply (`depth=2`).
