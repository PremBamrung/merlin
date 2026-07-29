import { useIngestActivity } from "@/hooks/useTaskProgress";

/**
 * Progress drawn *around* the top-bar mark while an ingest runs — one of the two
 * state-tied motion moments the identity allows (the other is the gold-leaf ★).
 * Gold, because gold is "what wants you", and it exists only while something is
 * actually happening: no task, no ring.
 *
 * Several concurrent ingests are averaged into one arc; the count goes in the
 * brand link's tooltip rather than adding a second indicator. Frames come from
 * the task store, so this costs a subscription and no extra connection.
 */
export function IngestRing({ size }: { size: number }) {
  const { running, percent } = useIngestActivity();
  if (running === 0) return null;

  // The ring sits just outside the mark's box, so it never crowds the glyph.
  const box = size + 10;
  const r = (box - 2.5) / 2;
  const circumference = 2 * Math.PI * r;

  return (
    <svg
      width={box}
      height={box}
      viewBox={`0 0 ${box} ${box}`}
      className="pointer-events-none absolute -inset-[5px]"
      aria-hidden="true"
    >
      <circle
        cx={box / 2}
        cy={box / 2}
        r={r}
        fill="none"
        stroke="var(--color-border)"
        strokeWidth="1.5"
      />
      <circle
        cx={box / 2}
        cy={box / 2}
        r={r}
        fill="none"
        stroke="var(--color-signal)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - percent / 100)}
        transform={`rotate(-90 ${box / 2} ${box / 2})`}
        className="transition-[stroke-dashoffset] duration-500 ease-linear"
      />
    </svg>
  );
}
