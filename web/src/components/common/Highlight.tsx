import type { ReactNode } from "react";

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Renders `text` with every occurrence of the search `term`'s words wrapped in
 * a <mark>. Tokenised (whitespace-split, ≥2 chars) so it tracks FTS-style
 * multi-word queries. No term → plain text.
 */
export function Highlight({
  text,
  term,
}: {
  text: string;
  term?: string | null;
}): ReactNode {
  const tokens = (term ?? "")
    .trim()
    .split(/\s+/)
    .filter((t) => t.length >= 2)
    .map(escape);
  if (!tokens.length) return text;

  const re = new RegExp(`(${tokens.join("|")})`, "gi");
  const parts = text.split(re);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="rounded-sm bg-accent/35 text-fg">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}
