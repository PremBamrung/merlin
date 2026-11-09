/**
 * THE MARK — D2, the hat with the gold star in the cone.
 *
 * Shape **D2**: steeper cone (half-width 5.8, not 7.2), wide brim, and the
 * brim separated from the cone by 0.9 units of *ground* rather than by a
 * lighter colour — same read, no new value in the palette, and it lifts the
 * mark's lower edge against the ground from 1.84:1 to 2.89:1.
 *
 *   cone  #2B3C9E   brim  #4B5CB8   star  #FFB94A
 *
 * **One form at every size** (2026-11-09). There used to be a second,
 * `monogram` form (M1: gold point capping the tip, a white M in the cone)
 * drawn at >=28px, with this star form below that because the M turns to mush
 * under ~4px tall. The switch meant the rail (26px) showed a different logo
 * from the home greeting and the chat empty state (40px), and the user chose
 * to drop the M rather than force it smaller. The favicon and the app icons
 * were already this form. The monogram's geometry is in git history.
 */

interface MarkProps {
  size?: number;
  className?: string;
  /** Set when the mark sits next to the wordmark, which already names the app. */
  decorative?: boolean;
}

const CONE = "#2B3C9E";
const BRIM = "#4B5CB8";
const GOLD = "#FFB94A";

export function Mark({ size = 24, className, decorative = false }: MarkProps) {
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
      <path d="M12 2.4L17.8 17.6H6.2Z" fill={CONE} />
      <circle cx="12" cy="13.2" r="2.5" fill={GOLD} />
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
