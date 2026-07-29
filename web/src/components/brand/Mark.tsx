/**
 * THE MARK — locked in session 4.
 *
 * Shape **D2**: steeper cone (half-width 5.8, not 7.2), wide brim, and the
 * brim separated from the cone by 0.9 units of *ground* rather than by a
 * lighter colour — same read, no new value in the palette, and it lifts the
 * mark's lower edge against the ground from 1.84:1 to 2.89:1.
 *
 *   cone  #2B3C9E   brim  #4B5CB8   point  #FFB94A
 *
 * Two locked forms, and a documented reason to switch between them:
 *
 * - `star`     — D2 with the gold star low in the cone body. Survives 16px.
 * - `monogram` — **M1**, the chosen app icon: the gold point caps the tip
 *                (moving it off the indigo and onto the ground, 5.48:1 →
 *                ~10:1, the strongest that point has ever been) and a white
 *                Archivo **M** fills the cone body. The cone had to shorten
 *                to make room (apex 2.4 → 5.6), which makes it squatter.
 *
 * The handoff records M1's one blocker verbatim: *"at 16px the M is under
 * 4px tall and turns to mush. If the favicon matters, this is the
 * blocker."* So `auto` (the default) renders M1 at ≥28px — app tiles, the
 * about screen, anywhere it stands alone — and falls back to the star form
 * at the sizes where the M cannot hold. The favicon uses `star`.
 *
 * The M is drawn as a path, not `<text>`: an icon must not depend on a
 * webfont having loaded. (v1's mockups silently fell back to Georgia and
 * the user rejected "the font" on that basis.)
 */

export type MarkVariant = "auto" | "star" | "monogram";

interface MarkProps {
  size?: number;
  variant?: MarkVariant;
  className?: string;
  /** Set when the mark sits next to the wordmark, which already names the app. */
  decorative?: boolean;
}

const CONE = "#2B3C9E";
const BRIM = "#4B5CB8";
const GOLD = "#FFB94A";

/** Below this the monogram's M is under ~4px tall and turns to mush. */
const MONOGRAM_FLOOR = 28;

export function Mark({
  size = 24,
  variant = "auto",
  className,
  decorative = false,
}: MarkProps) {
  const form =
    variant === "auto" ? (size >= MONOGRAM_FLOOR ? "monogram" : "star") : variant;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      role={decorative ? "presentation" : "img"}
      aria-label={decorative ? undefined : "Merlin"}
      aria-hidden={decorative || undefined}
    >
      {form === "monogram" ? (
        <>
          {/* Gold point CAPPING the tip — cy 3.6 / r 2.5, so the circle's
              lower edge (6.1) sits *below* the apex (5.6) and overlaps it.
              These are v8's numbers and the overlap is the whole point: an
              earlier pass at cy 2.9 / r 2.35 left a 0.35 gap, and the mark
              read as a ball hovering over a triangle rather than as a
              capped cone. Verified by looking at the specimen. */}
          <circle cx="12" cy="3.6" r="2.5" fill={GOLD} />
          {/* Shortened cone: apex 5.6 instead of 2.4, to make room. */}
          <path d="M12 5.6L17.8 17.6H6.2Z" fill={CONE} />
          {/* The M, drawn. Sits low and wide, where the cone has room. */}
          <path
            d="M9.15 16.5L9.9 11.5L12 14.6L14.1 11.5L14.85 16.5"
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="1.45"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      ) : (
        <>
          <path d="M12 2.4L17.8 17.6H6.2Z" fill={CONE} />
          <circle cx="12" cy="13.2" r="2.5" fill={GOLD} />
        </>
      )}
      {/* Brim, separated from the cone by 0.9 units of ground. */}
      <rect x="4" y="18.5" width="16" height="2.6" rx="1.3" fill={BRIM} />
    </svg>
  );
}

export type HatShape = "tall" | "squat";

/**
 * The hat alone, no gold point — this is what replaces the dot of the **i**
 * in the wordmark. It carries no star because the gold period two letters
 * later already *is* the gold point; exactly one gold element per lockup is
 * the rule that keeps the icon and the wordmark one idea instead of two.
 *
 * **Two shapes, because the locked one has a size problem.**
 *
 * `tall` is D2 verbatim, at v8's `0.64em / bottom 0.62em`. It was judged at
 * hero scale. At the size the top bar actually uses it (1.16rem) the brim is
 * about **1.3px** — so it vanishes, the glyph towers above Archivo's cap
 * height, and it reads as a brimless spike. That is the same failure the
 * handoff already recorded at 0.52em ("the brim vanished entirely"), just
 * arriving at a smaller size than expected.
 *
 * `squat` is the same hat drawn wider and shorter, so at 1.16rem the brim is
 * ~2.4px and survives. Nothing about the palette or the idea changes.
 *
 * Both are rendered side by side on `/brand` — a mark is judged by eye, not
 * by argument.
 */
export function HatGlyph({
  className,
  shape = "tall",
}: {
  className?: string;
  shape?: HatShape;
}) {
  if (shape === "squat") {
    return (
      <svg viewBox="0 0 24 19" className={className} aria-hidden="true">
        <path d="M12 1.4L20 12.2H4Z" fill={CONE} />
        <rect x="1.8" y="13.6" width="20.4" height="3.6" rx="1.8" fill={BRIM} />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M12 2.4L17.8 17.6H6.2Z" fill={CONE} />
      <rect x="4" y="18.5" width="16" height="2.6" rx="1.3" fill={BRIM} />
    </svg>
  );
}
