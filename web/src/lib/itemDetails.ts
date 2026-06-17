import type { ListItem } from "./api/endpoints";
import { compactNumber, formatDuration, relDate, thousands } from "./format";

/**
 * Key/value rows for an item's "Details" panel (empties dropped). Shared by the
 * Reader's context rail and the Feed card so the two never drift. Typed on
 * ListItem since every field used here is present on the list shape too.
 */
export function detailRows(item: ListItem): [string, string][] {
  const rows: [string, string][] = [["Source", item.source_type.toUpperCase()]];
  const channel = item.channel ?? item.author;
  if (channel) rows.push(["Channel", channel]);
  const dur = formatDuration(item.duration);
  if (dur) rows.push(["Length", dur]);
  if (item.detected_language)
    rows.push(["Language", item.detected_language.toUpperCase()]);
  if (item.word_count) rows.push(["Words", thousands(item.word_count)]);
  if (item.views != null) rows.push(["Views", compactNumber(item.views)]);
  if (item.summary_length) rows.push(["Summary", item.summary_length]);
  if (item.llm_model) rows.push(["Model", item.llm_model]);
  if (item.published_at) rows.push(["Published", relDate(item.published_at)]);
  if (item.ingested_at) rows.push(["Added", relDate(item.ingested_at)]);
  return rows;
}
