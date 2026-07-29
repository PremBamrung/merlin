import { HatGlyph, type HatShape } from "./Mark";

/**
 * THE WORDMARK — **L1**, locked in session 4.
 *
 * `Merlin.` where the hat replaces the dot of the **i**, that hat carries no
 * star, and the gold period is kept. The goal is that the icon and the
 * wordmark read as one thing rather than two objects sharing a palette.
 *
 * Two details that are easy to get wrong, both measured:
 *
 * 1. **The dotless ı.** Built from U+0131 plus an absolutely-positioned SVG.
 *    Verified present in Archivo's *latin* subset (`unicode-range:
 *    U+0000-00FF,U+0131,…`), so it does not silently fall back.
 * 2. **0.64em / bottom 0.62em.** The first pass at 0.52em read as a bare
 *    triangle — the brim vanished entirely. Also needs ~2.3rem of headroom
 *    in its container, since the hat overflows the line box.
 *
 * The period is a **drawn round dot**, overriding Archivo's glyph, which is
 * a hard square (verified by rendering it at 400px). The round dot is locked
 * for the wordmark *and* every mark's gold point.
 *
 * **Cost, recorded so it isn't rediscovered:** this stops being a string. It
 * cannot be selected as "Merlin", so it carries an `aria-label` and the
 * letters are `aria-hidden`. In running prose, use the plain text "Merlin".
 */

interface WordmarkProps {
  /** Any CSS length. The hat and period scale with it (both are em-based). */
  fontSize?: string;
  className?: string;
  /**
   * `squat` (the default) keeps the brim readable at interface sizes; `tall`
   * is v8's locked geometry, which only holds at hero scale. See `HatGlyph`.
   */
  hat?: HatShape;
}

export function Wordmark({
  fontSize = "1.15rem",
  className,
  hat = "squat",
}: WordmarkProps) {
  return (
    <span
      className={`wm ${className ?? ""}`}
      style={{ fontSize }}
      role="img"
      aria-label="Merlin"
    >
      <span aria-hidden="true">Merl</span>
      <span className={`ih${hat === "squat" ? " ih-squat" : ""}`} aria-hidden="true">
        {/* U+0131 LATIN SMALL LETTER DOTLESS I */}
        {"ı"}
        <HatGlyph className="hat" shape={hat} />
      </span>
      <span aria-hidden="true">n</span>
      <i className="dot" aria-hidden="true" />
    </span>
  );
}
