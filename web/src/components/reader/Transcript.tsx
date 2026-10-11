import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * Group transcript text into short paragraphs. Subtitle transcripts arrive as
 * one unbroken blob (no newlines), so we sentence-split and bundle ~3 sentences
 * per block. Splitting into many blocks lets `content-visibility:auto` skip the
 * off-screen ones, which is what keeps a 70k-char transcript from janking the
 * tab on mount.
 */
function splitParagraphs(text: string): string[] {
  const clean = text.replace(/\r\n/g, "\n").trim();
  if (!clean) return [];
  const out: string[] = [];
  for (const segment of clean.split(/\n+/)) {
    const sentences = segment.split(/(?<=[.!?…])\s+/);
    for (let i = 0; i < sentences.length; i += 3) {
      const para = sentences.slice(i, i + 3).join(" ").trim();
      if (para) out.push(para);
    }
  }
  return out.length ? out : [clean];
}

/** Transcript tab — searchable raw content, chunked for cheap rendering. */
export function Transcript({ text }: { text: string }) {
  const [filter, setFilter] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const q = filter.trim().toLowerCase();

  const paragraphs = useMemo(() => splitParagraphs(text), [text]);

  useEffect(() => {
    if (!q || !ref.current) return;
    const mark = ref.current.querySelector("mark");
    mark?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [q]);

  if (!text)
    return <p className="text-[14px] text-fg-muted">No transcript available.</p>;

  return (
    <div className="space-y-3">
      <div className="relative max-w-[75ch]">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Find in transcript…"
          className="pl-9"
        />
      </div>
      <div
        ref={ref}
        className="max-h-[70vh] max-w-[75ch] overflow-y-auto rounded-[10px] border border-border bg-surface p-4 text-[13.5px] leading-relaxed text-fg/85"
      >
        {paragraphs.map((para, i) => {
          const hit = q && para.toLowerCase().includes(q);
          return (
            <p
              key={i}
              className={cn(
                "mb-3 [contain-intrinsic-size:auto_4rem] [content-visibility:auto] last:mb-0",
                hit && "rounded bg-ui-flash px-1",
              )}
            >
              {hit ? <Highlight text={para} term={q} /> : para}
            </p>
          );
        })}
      </div>
    </div>
  );
}

function Highlight({ text, term }: { text: string; term: string }) {
  const idx = text.toLowerCase().indexOf(term);
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-ui-hl text-fg">{text.slice(idx, idx + term.length)}</mark>
      {text.slice(idx + term.length)}
    </>
  );
}
