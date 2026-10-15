import type { Item, ListItem } from "./api/endpoints";
import { compactNumber, formatDuration, relDate, thousands } from "./format";

const TRANSCRIPT_SOURCE: Record<string, string> = {
  auto: "auto-generated",
  manual: "manual subtitles",
};

/** "$0.0035" for fractions of a cent, "$0.12" otherwise. */
function usd(n: number): string {
  return `$${n < 0.01 ? n.toPrecision(2) : n.toFixed(2)}`;
}

/** Channel stats arrive as scraped strings ("1.2M", "803") or "N/A". */
function stat(v: number | string | null | undefined): string {
  if (v === null || v === undefined || v === "" || v === "N/A") return "";
  return typeof v === "number" ? compactNumber(v) : v;
}

/**
 * Key/value rows for an item's "Details" panel (empties dropped). Shared by the
 * Reader's context rail, the item drawer and the Feed card so they never drift.
 * Typed on ListItem — the detail-only `ingest_usage` (tokens, cost) shows when
 * the caller has the full Item.
 */
export function detailRows(
  item: ListItem & { ingest_usage?: Item["ingest_usage"] },
): [string, string][] {
  const rows: [string, string][] = [["Source", item.source_type.toUpperCase()]];
  const channel = item.channel ?? item.author;
  if (channel) rows.push(["Channel", channel]);
  const subs = stat(item.subscribers);
  if (subs) rows.push(["Subscribers", subs]);
  const videos = stat(item.videos_count);
  if (videos) rows.push(["Channel videos", videos]);
  const dur = formatDuration(item.duration);
  if (dur) rows.push(["Length", dur]);
  if (item.views != null) rows.push(["Views", compactNumber(item.views)]);
  if (item.detected_language)
    rows.push(["Language", item.detected_language.toUpperCase()]);
  if (item.transcript_source === "audio") {
    rows.push(["Transcript", "audio transcription"]);
  } else if (item.transcript_source) {
    const kind = TRANSCRIPT_SOURCE[item.transcript_source] ?? item.transcript_source;
    const lang = item.transcript_language?.toUpperCase();
    rows.push(["Transcript", lang ? `${lang} · ${kind}` : kind]);
  }
  if (item.word_count) rows.push(["Words", thousands(item.word_count)]);
  const summary = [item.summary_length, item.summary_language]
    .filter(Boolean)
    .map((s) => s!.charAt(0).toUpperCase() + s!.slice(1))
    .join(" · ");
  if (summary) rows.push(["Summary", summary]);
  if (item.llm_model) rows.push(["Model", item.llm_model]);
  const usage = item.ingest_usage;
  if (usage?.input_tokens != null || usage?.output_tokens != null)
    rows.push([
      "Tokens",
      `${compactNumber(usage?.input_tokens ?? 0)} in · ${compactNumber(usage?.output_tokens ?? 0)} out`,
    ]);
  if (usage?.cost_usd != null)
    rows.push([
      "Cost",
      usage.runs > 1 ? `${usd(usage.cost_usd)} · ${usage.runs} runs` : usd(usage.cost_usd),
    ]);
  if (item.published_at) rows.push(["Published", relDate(item.published_at)]);
  if (item.ingested_at) rows.push(["Added", relDate(item.ingested_at)]);
  return rows;
}
