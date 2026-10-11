/**
 * Stored summaries come in several historical shapes: "1. **Overview**",
 * "## Overview", "**1. Overview**", "1. **Aperçu (2 phrases max)**",
 * "### Résumé de la vidéo …", "2. **Main Key Points**". Render them all one
 * way: the overview prose without a heading, then plain "## Key points" (or
 * "## Points clés") over the list — so no summary numbers its own headings.
 * Render-side only; the real fix is the summariser prompt.
 */

/** A line that is only a heading: `#…`, or a bold run on its own, optionally
 *  numbered either side of the bold markers and with a trailing colon. */
const HEADINGISH = /^(?:#{1,6}\s+.+|(?:\d+\.\s*)?\*\*(?:\d+\.\s*)?[^*]+\*\*:?)$/;

const OVERVIEW = /^(overview|aperçu|aperçu général|vue d[’']ensemble|résumé|resume|summary|summary of the video)$/i;
const KEY_POINTS =
  /^(main key points|key points|key takeaways|points clés|points-clés|points principaux|points clés principaux)$/i;
// `\b` doesn't work after "é" in a JS regex, hence the lookahead.
const TITLE_WORD = /^(résumé|summary)(?=\s|$|[:"«])/i;
/** "**1. Overview:** This video…" — the label inline, prose after it. */
const INLINE_OVERVIEW =
  /^(?:\d+\.\s*)?\*\*(?:\d+\.\s*)?(?:overview|aperçu(?: général)?|vue d[’']ensemble|summary)(?:\s*\([^)]*\))?:?\*\*:?\s+/i;

/** "**2. Main Key Points (5 max):**" → "Main Key Points". */
function bareHeading(line: string): string {
  return line
    .replace(/\*\*/g, "")
    .replace(/^#+\s*/, "")
    .replace(/^\d+\.\s*/, "")
    .replace(/\s*\([^)]*\)\s*/g, " ")
    .replace(/:\s*$/, "")
    .trim();
}

/** A title over the whole summary ("## Lamy Safari: … - Summary"): the first
 *  line is a `#` heading that says it's a summary, or that sits directly on top
 *  of another heading. The page already shows the item's title. */
function dropLeadingTitle(lines: string[]): string[] {
  const first = lines.findIndex((l) => l.trim());
  if (first < 0 || !/^#{1,6}\s/.test(lines[first].trim())) return lines;
  const next = lines.slice(first + 1).find((l) => l.trim())?.trim() ?? "";
  const titled = /(summary|résumé)(?=\s|$|[:"«])/i.test(lines[first]);
  if (titled || HEADINGISH.test(next)) return lines.slice(first + 1);
  return lines;
}

export function normalizeSummary(markdown: string | null | undefined): string {
  if (!markdown) return "";
  const out: string[] = [];
  for (const raw of dropLeadingTitle(markdown.split("\n"))) {
    const line = raw.trim();
    if (INLINE_OVERVIEW.test(line)) {
      out.push(line.replace(INLINE_OVERVIEW, ""));
      continue;
    }
    if (!HEADINGISH.test(line)) {
      out.push(raw.replace(/\s+$/, ""));
      continue;
    }
    const bare = bareHeading(line);
    // "### Résumé de la vidéo …" — a title over the whole thing: drop it.
    if (/^#/.test(line) && TITLE_WORD.test(bare)) continue;
    if (OVERVIEW.test(bare)) continue;
    if (KEY_POINTS.test(bare)) {
      out.push(`## ${/clés|principaux/i.test(bare) ? "Points clés" : "Key points"}`);
      continue;
    }
    // A `#` heading stays a heading (unnumbered). A bold-only line that names
    // no known section is left alone: it may be a key point that's all bold.
    out.push(/^#/.test(line) ? `## ${bare}` : raw.replace(/\s+$/, ""));
  }
  return out.join("\n").replace(/^\s+/, "");
}
