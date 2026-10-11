/**
 * "Since last time" needs a last time. It's per browser (there are no
 * accounts), kept in localStorage: the moment you last *left* home. Reading
 * it doesn't move it, so a reload still shows what was new; leaving home (or
 * hiding the tab while on it) does. Storage can be unavailable (private
 * windows, blocked site data) — then it's always "the last 24 hours".
 */
const KEY = "merlin-last-visit";
const DAY = 86_400_000;

export function readLastVisit(): Date {
  try {
    const raw = localStorage.getItem(KEY);
    const d = raw ? new Date(raw) : null;
    if (d && !Number.isNaN(d.getTime())) return d;
  } catch {
    /* storage unavailable */
  }
  return new Date(Date.now() - DAY);
}

export function markVisited(at: Date = new Date()): void {
  try {
    localStorage.setItem(KEY, at.toISOString());
  } catch {
    /* storage unavailable */
  }
}

/** "Since yesterday", "Since earlier today", "Since Oct 3". */
export function sinceLabel(since: Date, now: Date = new Date()): string {
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(now) - day(since)) / DAY);
  if (days <= 0) return "Since earlier today";
  if (days === 1) return "Since yesterday";
  if (days < 7) return `In the last ${days} days`;
  return `Since ${since.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}
