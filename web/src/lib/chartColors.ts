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
