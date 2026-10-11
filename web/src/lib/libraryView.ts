/**
 * The Library's views as the context panel presents them. Each panel row is a
 * *place to go* — All / Unread / Saved, one topic, one channel, one source —
 * so a row replaces the others rather than stacking with them (the main view
 * still lets you narrow further: search, tags, the transcript toggle). Kept in
 * the URL like every other Library filter.
 */
export const UNCATEGORISED = "uncategorised";

export type LibraryView =
  | { kind: "all" }
  | { kind: "unread" }
  | { kind: "saved" }
  | { kind: "topic"; slug: string }
  | { kind: "channel"; name: string }
  | { kind: "source"; type: string };

/** The view a set of Library params is showing ("all" when nothing selects one). */
export function viewOf(p: URLSearchParams): LibraryView {
  const topics = p.getAll("topics");
  if (p.get("read") === "false") return { kind: "unread" };
  if (p.get("saved") === "true") return { kind: "saved" };
  if (p.get("channel")) return { kind: "channel", name: p.get("channel")! };
  if (topics.length === 1) return { kind: "topic", slug: topics[0] };
  if (p.get("source_type")) return { kind: "source", type: p.get("source_type")! };
  return { kind: "all" };
}

export function sameView(a: LibraryView, b: LibraryView): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** `/library?…` for a view. Keeps only the sort, so switching views doesn't
 *  drag the previous view's search or tags along. */
export function libraryHref(view: LibraryView, from?: URLSearchParams | null): string {
  const sp = new URLSearchParams();
  const sort = from?.get("sort");
  if (sort && sort !== "relevance") sp.set("sort", sort);
  if (view.kind === "unread") sp.set("read", "false");
  else if (view.kind === "saved") sp.set("saved", "true");
  else if (view.kind === "topic") sp.set("topics", view.slug);
  else if (view.kind === "channel") sp.set("channel", view.name);
  else if (view.kind === "source") sp.set("source_type", view.type);
  const qs = sp.toString();
  return qs ? `/library?${qs}` : "/library";
}
