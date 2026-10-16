import { CATEGORICAL } from "@/lib/chart-palette";
import type { SimpleLineSeries } from "@/lib/island-loader";
import type { BasketAttention } from "@/lib/types/attention";

export const NO_DATA = "no data";

/** Colour of a basket, by its position in the response (stable per payload). */
export function basketColor(index: number): string {
  return CATEGORICAL[index % CATEGORICAL.length];
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
