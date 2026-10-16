import { useEffect, useRef, useState } from "react";
import { Pin, RefreshCw, Sparkles, ThumbsUp } from "lucide-react";
import { useComments, useRefreshComments } from "@/hooks/useComments";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { Comment } from "@/lib/api/endpoints";
import { compactNumber, relDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Comments tab — the video's top-level comments (pinned, then most-liked),
 *  fetched at ingest; Refresh re-fetches them from YouTube. Videos ingested
 *  before comments existed fetch once, automatically, the first time the tab
 *  opens (rate-limited server-side), so nothing hits YouTube for videos you
 *  never look at. */
export function Comments({
  itemId,
  hasViewerSection,
  onResummarize,
  resummarizing = false,
}: {
  itemId: string;
  /** Whether the summary already has its "What Viewers Say" section. */
  hasViewerSection: boolean;
  onResummarize?: () => void;
  resummarizing?: boolean;
}) {
  const q = useComments(itemId);
  const refresh = useRefreshComments(itemId);

  // One automatic fetch per item per visit; a failure is shown inline (with
  // the manual button), never retried in a loop.
  const autoFetched = useRef<string | null>(null);
  useEffect(() => {
    const d = q.data;
    if (!d || !d.enabled || d.fetched_at || autoFetched.current === itemId) return;
    autoFetched.current = itemId;
    refresh.mutate({ silent: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data, itemId]);

  const fetchingFirst = refresh.isPending && !q.data?.fetched_at;
  if (q.isLoading || fetchingFirst)
    return (
      <div className="max-w-[75ch] space-y-3">
        {fetchingFirst && (
          <p className="text-[13px] text-fg-muted">Fetching top comments from YouTube…</p>
        )}
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-20 w-full rounded-[10px]" />
        ))}
      </div>
    );
  if (q.isError || !q.data)
    return <p className="text-[14px] text-fg-muted">Couldn't load comments.</p>;

  const { comments, fetched_at, enabled } = q.data;
  const refreshButton = enabled && (
    <Button
      variant="outline"
      size="sm"
      onClick={() => refresh.mutate({})}
      disabled={refresh.isPending}
    >
      <RefreshCw className={cn(refresh.isPending && "animate-spin")} />
      {refresh.isPending ? "Fetching…" : fetched_at ? "Refresh" : "Fetch comments"}
    </Button>
  );

  return (
    <div className="max-w-[75ch] space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-fg-muted">
          {!enabled && !fetched_at
            ? "Comment fetching is off (YOUTUBE_COMMENTS_LIMIT=0)."
            : !fetched_at
              ? refresh.error
                ? `Couldn't fetch comments: ${refresh.error.message}`
                : "Comments haven't been fetched for this video yet."
              : comments.length
                ? `Top ${comments.length} comments · fetched ${relDate(fetched_at)}`
                : `No comments · checked ${relDate(fetched_at)}`}
        </p>
        {refreshButton}
      </div>

      {comments.length > 0 && !hasViewerSection && onResummarize && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-dashed border-border px-4 py-3">
          <p className="flex items-center gap-2 text-[13px] text-fg-muted">
            <Sparkles className="size-3.5 shrink-0 text-fg-subtle" />
            Re-summarize to add a “What Viewers Say” section to the summary.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={onResummarize}
            disabled={resummarizing}
          >
            <RefreshCw className={cn(resummarizing && "animate-spin")} />
            {resummarizing ? "Re-summarizing…" : "Re-summarize"}
          </Button>
        </div>
      )}

      {comments.length > 0 && (
        <ol className="space-y-3">
          {comments.map((c, i) => (
            <CommentRow key={c.comment_id ?? i} comment={c} />
          ))}
        </ol>
      )}
    </div>
  );
}

const CLAMP_CHARS = 420;

/** "3y ago" — YouTube only says "3 years ago", so a calendar date would
 *  claim a precision the timestamp doesn't have. */
function approxAge(iso: string): string {
  const days = (Date.now() - new Date(iso).getTime()) / 86_400_000;
  if (!Number.isFinite(days)) return "";
  if (days < 1) return "today";
  if (days < 30) return `${Math.floor(days)}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

function CommentRow({ comment: c }: { comment: Comment }) {
  const [open, setOpen] = useState(false);
  const long = c.text.length > CLAMP_CHARS;
  return (
    <li className="rounded-[10px] border border-border bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px]">
        <span className="min-w-0 truncate font-medium text-fg">
          {c.author || "Anonymous"}
        </span>
        {c.is_uploader && <Badge variant="new">Creator</Badge>}
        {c.is_pinned && (
          <Badge variant="outline">
            <Pin className="size-3" />
            Pinned
          </Badge>
        )}
        {c.posted_at && (
          <span className="text-fg-subtle">{approxAge(c.posted_at)}</span>
        )}
        <span className="ml-auto inline-flex items-center gap-1 tabular-nums text-fg-muted">
          <ThumbsUp className="size-3.5" />
          {compactNumber(c.like_count) || "0"}
        </span>
      </div>
      <p
        className={cn(
          "whitespace-pre-line break-words text-[13.5px] leading-relaxed text-fg/85",
          long && !open && "line-clamp-6",
        )}
      >
        {c.text}
      </p>
      {long && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="mt-1 text-[12.5px] text-ui-link hover:underline"
        >
          {open ? "Show less" : "Show more"}
        </button>
      )}
    </li>
  );
}
