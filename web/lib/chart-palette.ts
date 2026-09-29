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
  /** --series-3 */
  green: "#1baf7a",
  /** --series-4 */
  indigo: "#4a3aa7",
  /** --series-5 */
  pink: "#e87ba4",
  /** --series-8 */
  red: "#e34948",
} as const;

/**
 * The /narrative panel's series colours.
 *
 * Replaces seven hand-picked hexes that the UI audit measured as failing
 * colour-blindness and legibility gates. Every colour here comes from the
 * validated `--series-N` set instead.
 *
 * The two pytrends variants deliberately SHARE a hue and are separated by the
 * dash pattern rather than by colour. They are the same source read over two
 * different windows, so one hue is the honest encoding — and the old palette's
 * teal/light-teal pair was exactly the kind of low-separation adjacency the
 * audit flagged.
 */
export const NARRATIVE_SERIES: Record<string, string> = {
  "pytrends-nightly-7d": SERIES.green,
  "pytrends-backfill-269d": SERIES.green,
  reddit: SERIES.red,
  "coingecko-narrative": SERIES.indigo,
  exchange_volume_share: SERIES.pink,
};

export const NARRATIVE_COMPOSITE_COLOR = SERIES.primary;
/** Backfilled points sit on a different Google Trends scale — a warning, hence the warning hue. */
export const NARRATIVE_MIXED_SCALE_COLOR = SERIES.secondary;
export const NARRATIVE_FALLBACK_COLOR = "#8a8f98";

/**
 * Floor/ramp markers on /onchain.
 *
 * Deliberately NEUTRAL: every one of the six chain slots is a series hue, so a
 * coloured marker would read as "some other chain". They sit on the light plot
 * and in the light legend strip, which is why they are the plot's ink tokens
 * rather than shell ink.
 */
export const MARKER = {
  /** --an-ink-1 */
  floor: "#0b0b0b",
  /** --an-ink-3 */
  ramp: "#898781",
} as const;
