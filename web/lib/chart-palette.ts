/**
 * Series colours for charts drawn to a canvas.
 *
 * SVG charts are themed from globals.css (see `.spread-chart`), which is where
 * the palette belongs. A canvas mark cannot read a CSS custom property, so a
 * canvas chart has to be handed a literal colour — these constants.
 *
 * They mirror the `--series-N` slots in app/globals.css, and
 * __tests__/chart-palette.test.ts parses that file to prove they still match,
 * so the two cannot drift apart silently.
 */
export const SERIES = {
  /** --series-1 */
  primary: "#2a78d6",
  /** --series-2 */
  secondary: "#eb6834",
} as const;
