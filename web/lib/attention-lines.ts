import { CATEGORICAL, SERIES } from "@/lib/chart-palette";
import type { SimpleLineSeries } from "@/lib/island-loader";
import type { BasketAttention } from "@/lib/types/attention";

export const NO_DATA = "no data";

/**
 * The attention chart sits on the page's dark surface, not on a light slab.
 * Indigo (--series-4) is 2.06:1 on --sh-1 and a line is a graphic (3:1), so it
 * is the one categorical slot left out; the other seven measure 3.56:1 or more.
 */
const BASKET_COLORS = CATEGORICAL.filter((color) => color !== SERIES.indigo);

/** Colour of a basket, by its position in the response (stable per payload). */
export function basketColor(index: number): string {
  return BASKET_COLORS[index % BASKET_COLORS.length];
}

/** The faint start = 100 reference line, a step above --sh-rule (a canvas line cannot read a CSS variable). */
const BASELINE_COLOR = "#4b5568";

/** A flat line at 100 across the drawn range, or null when nothing is drawn. */
export function baselineSeries(lines: readonly SimpleLineSeries[]): SimpleLineSeries | null {
  const times = lines.flatMap((l) => l.points.map((p) => p.timestamp)).sort();
  if (times.length === 0) return null;
  return {
    key: "baseline",
    color: BASELINE_COLOR,
    width: 1,
    points: [
      { timestamp: times[0], value: 100 },
      { timestamp: times[times.length - 1], value: 100 },
    ],
  };
}

const SOURCE_LABELS: Record<string, string> = {
  wikipedia: "Wikipedia",
  wiki: "Wikipedia",
  coingecko: "CoinGecko",
  exchange: "Exchange volume",
  exchange_volume: "Exchange volume",
  hyperliquid_volume: "Hyperliquid volume",
  trends: "Google Trends",
  reddit: "Reddit",
  xsearch: "X",
  x: "X",
};

/** Human label for a source id; an unknown id is capitalised, never printed raw. */
export function sourceLabel(id: string): string {
  const known = SOURCE_LABELS[id];
  if (known) return known;
  const words = id.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const COMPACT = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 });

/** A raw source value, compact with at most two decimals: 1234567890.12 -> "1.23B". */
export function formatCompact(value: number | null): string {
  return value === null ? NO_DATA : COMPACT.format(value);
}

function toTimestamp(date: string): string {
  return date.length === 10 ? `${date}T00:00:00Z` : date;
}

/**
 * One line per basket. A null value ends the current run and the next real
 * value starts a new series with the same colour, so the chart shows a gap
 * and never a bridge or a zero.
 */
export function buildAttentionLines(
  baskets: readonly BasketAttention[],
  hidden: ReadonlySet<string>,
): SimpleLineSeries[] {
  const lines: SimpleLineSeries[] = [];
  baskets.forEach((basket, index) => {
    if (hidden.has(basket.id)) return;
    const color = basketColor(index);
    let run: SimpleLineSeries["points"] = [];
    let n = 0;
    const flush = () => {
      if (run.length > 0) lines.push({ key: `${basket.id}:${n++}`, color, points: run });
      run = [];
    };
    for (const point of basket.series) {
      if (point.value === null) flush();
      else run.push({ timestamp: toTimestamp(point.date), value: point.value });
    }
    flush();
  });
  return lines;
}

export function formatScore(value: number | null): string {
  return value === null ? NO_DATA : value.toFixed(1);
}

export function formatSigned(value: number | null): string {
  if (value === null) return NO_DATA;
  const text = value.toFixed(1);
  return value > 0 ? `+${text}` : text;
}

export function formatBreadth(value: number | null): string {
  return value === null ? NO_DATA : `${Math.round(value * 100)}%`;
}
