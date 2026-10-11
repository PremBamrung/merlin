import { Link } from "react-router-dom";
import { FileText } from "lucide-react";
import { citeAnchorId, type Citation } from "@/hooks/useAgentChat";
import { formatDuration, thumbnailUrl } from "@/lib/format";
import { setCiteHot } from "@/lib/citeHot";

/** One source: thumbnail with its number and duration, title, channel. The
 *  layout (row card / side card / 2-up) comes from `.src-*` CSS in index.css. */
export function SourceCard({
  citation,
  index,
  messageId,
}: {
  citation: Citation;
  index: number;
  /** When set, the card is the scroll/hover target for its inline chips. */
  messageId?: string;
}) {
  const anchor = messageId ? citeAnchorId(messageId, citation.item_id) : undefined;
  const thumb =
    citation.thumbnail_url ??
    (citation.source_id
      ? thumbnailUrl({ source_type: citation.source_type, source_id: citation.source_id })
      : null);
  const duration = citation.duration ? formatDuration(citation.duration) : "";
  const meta = citation.channel ?? citation.source_type;

  return (
    <Link
      id={anchor}
      to={`/library/${citation.item_id}`}
      className="src-card scroll-mt-6 text-left"
      onMouseEnter={anchor ? () => setCiteHot(anchor, true) : undefined}
      onMouseLeave={anchor ? () => setCiteHot(anchor, false) : undefined}
      title={citation.snippet || citation.title}
    >
      <span className="src-thumb relative block aspect-video overflow-hidden rounded-lg bg-surface-2">
        {thumb ? (
          <img src={thumb} alt="" loading="lazy" className="size-full object-cover" />
        ) : (
          <span className="grid size-full place-items-center text-fg-subtle">
            <FileText className="size-6" strokeWidth={1.3} />
          </span>
        )}
        <span className="absolute left-1.5 top-1.5 grid h-5 min-w-5 place-items-center rounded-[5px] bg-ui-cite-num-bg px-[5px] font-mono text-[11px] font-medium leading-none text-ui-cite-num-fg">
          {index + 1}
        </span>
        {duration && (
          <span className="absolute bottom-1.5 right-1.5 rounded bg-black/75 px-1.5 py-1 font-mono text-[11px] font-medium leading-none text-white">
            {duration}
          </span>
        )}
      </span>
      <span className="src-title line-clamp-2 block text-[13px] font-medium leading-[18px] text-fg">
        {citation.title}
      </span>
      <span className="src-meta block truncate font-mono text-[11px] uppercase leading-4 text-fg-subtle">
        {meta}
      </span>
    </Link>
  );
}
