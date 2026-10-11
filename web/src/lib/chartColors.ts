/**
 * Chart colours, as hexes. Recharts writes SVG presentation attributes, which
 * don't resolve `var()`, so these MIRROR the `--color-ui-chart-*` and base
 * tokens in styles/index.css — change both together. Validated with the
 * dataviz skill's `validate_palette.js`; re-run it before touching a value.
 */

/** Chrome + the ONE data series. `series` is sky (#3f97c9: L 0.645, C 0.112,
 * 3:1+ on the #232529 card — passes the dark band), `emphasis` its hover step.
 * grid = rule, axis = fg-subtle, cursor = surface-2. */
export const CHART = {
  series: "#3f97c9", // --color-ui-chart-1
  emphasis: "#6fb6de", // --color-ui-chart-2
  grid: "#393b41", // --color-border
  axis: "#8e8e98", // --color-fg-subtle
  surface: "#2c2e33", // --color-surface-2
  border: "#4a4c54", // --color-border-strong
};

/**
 * Magnitude ramp for the calendar heatmap: one hue (sky, 237°), monotone
 * lightness, brightening with the count; slot 0 is the empty day. Validated as
 * an ordinal ramp on the card (#232529): monotone L, every adjacent gap ≥ 0.06,
 * single hue (1° spread), dim end 2.48:1 — the level-1 square has to be visible
 * against the empty one.
 */
export const SEQ_RAMP = [
  "var(--color-surface-2)", // CSS background, so var() is fine here
  "#23678d",
  "#2f81af",
  "#449cce",
  "#74bae6",
];

/**
 * Status is a **reserved** scale: green = done, gold = running, sky = waiting
 * on us, grey = waiting in line, rust = broken. Never reused as "series N".
 * Rust and green are ΔE 4.7 apart under deuteranopia, which is why the charts
 * render a named legend — colour alone never distinguishes failed from
 * completed. (`pending` was indigo; mono keeps indigo for the mark only.)
 */
export const STATUS_COLORS: Record<string, string> = {
  completed: "#4fa97a", // --color-success
  processing: "#ffb94a", // --color-signal
  pending: "#6fb6de", // --color-ui-chart-2
  queued: "#8e8e98", // --color-fg-subtle
  failed: "#d4705a", // --color-fail
};

/**
 * Categorical slots for the stacked spend bar, in **stacking order** — the order
 * is the colourblind-safety mechanism, so don't re-shuffle it. Stepped into the
 * dark-mode lightness band (OKLCH L 0.48–0.67) on Merlin's ground and validated:
 * all five clear the chroma floor and 3:1 vs #1a1b1f, worst adjacent pair is
 * ΔE 9.2 under deuteranopia / 21.4 normal
 * (`validate_palette.js --mode dark --surface "#1a1b1f"`).
 */
export const SURFACE_COLORS: Record<string, string> = {
  chat: "#5c82da",
  summarize: "#b98a00",
  transcribe: "#13a5b2",
  classify: "#b93c8c",
  discover: "#429c5a",
};
export const SURFACE_ORDER = ["chat", "summarize", "transcribe", "classify", "discover"];
