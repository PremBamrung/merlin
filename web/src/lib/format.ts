// Pure presentation helpers — ported from streamlit/ui/util.py, plus a few extras.

/** YouTube watch URL, optionally deep-linked to a timestamp (seconds). */
export function youtubeUrl(sourceId: string, seconds?: number | null): string {
  const base = `https://www.youtube.com/watch?v=${sourceId}`;
  return seconds ? `${base}&t=${Math.floor(seconds)}s` : base;
}

/** "HH:MM:SS" / "MM:SS" / "90" → total seconds, or null. */
export function tsToSeconds(stamp: string | number | null | undefined): number | null {
  if (stamp === null || stamp === undefined || stamp === "") return null;
  if (typeof stamp === "number") return Math.floor(stamp);
  const parts = String(stamp).trim().split(":");
  let secs = 0;
  for (const p of parts) {
    const n = Number(p);
    if (!Number.isFinite(n)) return null;
    secs = secs * 60 + n;
  }
  return secs;
}

/** Thumbnail URL for an item — prefer the stored one, fall back to YouTube's. */
export function thumbnailUrl(item: {
  thumbnail_url?: string | null;
  source_type: string;
  source_id: string;
}): string | null {
  if (item.thumbnail_url) return item.thumbnail_url;
  if (item.source_type === "youtube")
    // mqdefault is a true 16:9 frame (320×180). hqdefault is 4:3 with baked-in
    // letterbox bars, which `object-cover` can't fully crop away — see cards.
    return `https://i.ytimg.com/vi/${item.source_id}/mqdefault.jpg`;
  return null;
}

/** Seconds → "H:MM:SS" or "M:SS". Accepts the API's int seconds or a string. */
export function formatDuration(value: number | string | null | undefined): string {
  const secs = tsToSeconds(value);
  if (secs === null) return typeof value === "string" ? value : "";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

export function shortText(text: string | null | undefined, limit: number): string {
  const t = (text ?? "").trim();
  return t.length > limit ? t.slice(0, limit) + "…" : t;
}

/** Compact relative date: "today", "3d ago", "Jun 11". */
export function relDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso.slice(0, 10);
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const now = new Date();
  const delta = Math.round(
    (startOfDay(now).getTime() - startOfDay(dt).getTime()) / 86_400_000,
  );
  if (delta <= 0) return "today";
  if (delta === 1) return "yesterday";
  if (delta < 7) return `${delta}d ago`;
  const opts: Intl.DateTimeFormatOptions =
    dt.getFullYear() === now.getFullYear()
      ? { month: "short", day: "numeric" }
      : { month: "short", day: "numeric", year: "numeric" };
  return dt.toLocaleDateString("en-US", opts);
}

/** Clock time for a chat message: "2:34 PM" today, "Jun 11, 2:34 PM" otherwise.
 * Accepts an epoch-ms number (how chat timestamps are stored). */
export function msgTime(ms: number | null | undefined): string {
  if (ms == null) return "";
  const dt = new Date(ms);
  if (Number.isNaN(dt.getTime())) return "";
  const now = new Date();
  const time = dt.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  if (dt.toDateString() === now.toDateString()) return time;
  const opts: Intl.DateTimeFormatOptions =
    dt.getFullYear() === now.getFullYear()
      ? { month: "short", day: "numeric" }
      : { month: "short", day: "numeric", year: "numeric" };
  return `${dt.toLocaleDateString("en-US", opts)}, ${time}`;
}

/** 1234567 → "1.2M", 12300 → "12.3K". */
export function compactNumber(n: number | string | null | undefined): string {
  const num = typeof n === "string" ? Number(n) : n;
  if (num === null || num === undefined || !Number.isFinite(num)) return "";
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(
    num,
  );
}

/** Estimated reading time from a word count (~220 wpm), e.g. "6 min read". */
export function readingTime(words: number | null | undefined): string {
  if (!words || words <= 0) return "";
  return `${Math.max(1, Math.round(words / 220))} min read`;
}

/** 1234567 → "1,234,567". */
export function thousands(n: number | null | undefined): string {
  if (n === null || n === undefined) return "0";
  return Intl.NumberFormat("en-US").format(n);
}
