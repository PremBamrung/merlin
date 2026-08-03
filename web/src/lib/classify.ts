/**
 * Does this text look like a link the user means to ingest?
 *
 * Used by the Library search field, which is one box doing two jobs: filter the
 * grid, or swallow a pasted link. That makes false positives expensive — every
 * one of them is a search that silently stopped searching — so this is
 * deliberately stricter than the old Today omnibox's `omniboxRoute`, whose
 * `\b\w[\w-]*\.\w{2,}` rule would have claimed "web.dev", "node.js" and any
 * other perfectly good query with a dot in it.
 *
 * The bar: an explicit scheme, or an unmistakable YouTube host.
 */
const URL_RE = /^(https?:\/\/\S+|(?:www\.)?(?:youtube\.com|youtu\.be)\/\S+)$/i;

export function looksLikeUrl(text: string): boolean {
  return URL_RE.test(text.trim());
}
