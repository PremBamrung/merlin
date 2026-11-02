/**
 * Inline citation markers the agent writes after sentences: `[#<id>]`, or
 * `[<id>]` (models often drop the `#`), and — when one sentence draws on
 * several items — a **group** in one bracket: `[#a, #b]`, `[#a; #b]`, `[#a #b]`.
 * The backend parses the same shapes (`api/routers/chat.py` `_MARKER_GROUP_RE`)
 * to split used vs viewed sources; here we strip them from copied text and turn
 * them into numbered chips in rendered answers.
 *
 * Dependency-free on purpose: the Home route strips markers too, and must not
 * pull the AI SDK (which `useAgentChat` imports) out of its lazy chunk.
 *
 * An id is 8+ hex/dash chars, so prose brackets like `[1]` never match. The
 * separators are unambiguous (an id never contains space, comma, `;` or `#`),
 * which keeps the patterns linear — no catastrophic backtracking on a long
 * unclosed `[…`.
 */

import type { Citation } from "@/hooks/useAgentChat";

const ID = "[0-9a-fA-F-]{8,}";
const GROUP = `\\[\\s*#?${ID}(?:(?:\\s*[,;]\\s*|\\s+)#?${ID}|#${ID})*\\s*\\]`;

/** One marker bracket, single or grouped. */
const MARKER_RE = new RegExp(GROUP, "g");
/** Marker brackets the model wrapped in its own parentheses, e.g.
 * "DamsShiro ([id])" or "nerfés ([id] [id2])" — strip the whole group so no
 * empty "()" is left behind. Plain "(text)" is untouched. */
const WRAPPED_MARKER_RE = new RegExp(`\\(\\s*(?:${GROUP}\\s*)+\\)`, "g");
/** A marker still mid-stream (no closing `]` yet) at the very end of the text,
 * so a half-typed `[0dd1864…` or `[#a, #b…` never flashes while streaming. */
// One flat character class (no nested quantifiers), so it stays linear.
const PARTIAL_MARKER_RE = /\[[\s#,;0-9a-fA-F-]*$/;
const ID_RE = new RegExp(ID, "g");

function tidy(text: string): string {
  return text
    .replace(PARTIAL_MARKER_RE, "")
    .replace(/ +([.,;:!?])/g, "$1") // drop space stranded before punctuation
    .replace(/[ \t]{2,}/g, " "); // collapse double spaces left behind
}

/** Remove citation markers from answer text, tidying leftover whitespace. Used
 * for the copy action and anywhere markers mean nothing (Home previews). */
export function stripCitationMarkers(text: string): string {
  // Marker-only parens first, before the bare markers inside them.
  return tidy(text.replace(WRAPPED_MARKER_RE, "").replace(MARKER_RE, ""));
}

/** Resolve a marker id (often a UUID prefix) to its index in `citations`. */
function citationIndex(markerId: string, citations: Citation[]): number {
  const id = markerId.toLowerCase();
  let idx = citations.findIndex((c) => c.item_id.toLowerCase() === id);
  if (idx < 0) idx = citations.findIndex((c) => c.item_id.toLowerCase().startsWith(id));
  return idx;
}

/** DOM anchor id for a Source card, unique per message so the same item cited
 * across turns doesn't collide. Shared by `linkifyCitationMarkers` (the chip
 * href) and `CitationCard` (the scroll target). */
export function citeAnchorId(messageId: string, itemId: string): string {
  return `cite-${messageId}-${itemId}`;
}

/**
 * Rewrite markers into markdown links (`[n](#cite-<messageId>-<item_id>)`)
 * numbered to match the Sources list, so each claim carries a clickable chip
 * that scrolls to its Source card. A grouped marker becomes adjacent chips, one
 * per distinct item. Ids that don't resolve to a known citation — e.g. while
 * the citations list is still streaming in, or a hallucinated id — are
 * dropped. The `#cite-` href is rendered as a chip by `Markdown`.
 */
export function linkifyCitationMarkers(
  text: string,
  citations: Citation[],
  messageId: string,
): string {
  if (!citations.length) return stripCitationMarkers(text);
  return tidy(
    text.replace(MARKER_RE, (group) => {
      const ids = group.match(ID_RE) ?? [];
      return [...new Set(ids.map((id) => citationIndex(id, citations)))]
        .filter((idx) => idx >= 0)
        .map((idx) => `[${idx + 1}](#${citeAnchorId(messageId, citations[idx].item_id)})`)
        .join("");
    }),
  );
}
