import { CATEGORICAL, SERIES } from "@/lib/chart-palette";
import type { SpaghettiLine, SpaghettiResponse, Timeframe, UnavailableReason } from "@/lib/types/screener";

/**
 * T37 / S6: the pure builders behind the spaghetti chart, kept out of the
 * component so they are tested directly (jsdom never mounts the island).
 *
 * BTC and HYPE are references: drawn thicker, in the fixed first two palette
 * slots, and on top. Every other coin cycles the remaining six categorical
 * colours by its position in the API's list, so a coin keeps its colour when
 * another is hidden or unavailable. Nothing is ranked: the order is the
 * watchlist's.
 */

export interface SpaghettiPlotLine {
  key: string;
  color: string;
  width: number;
  points: { timestamp: string; value: number }[];
}

export interface SpaghettiLegendEntry {
  symbol: string;
  color: string;
  reference: boolean;
  available: boolean;
  reason: UnavailableReason | null;
}

export const REFERENCE_COLORS: Record<string, string> = {
  BTC: SERIES.primary,
  HYPE: SERIES.secondary,
};
export const REFERENCE_WIDTH = 3;
export const COIN_WIDTH = 1.5;

/** The categorical set without the two slots the references own. */
export const COIN_PALETTE: readonly string[] = CATEGORICAL.filter(
  (c) => c !== SERIES.primary && c !== SERIES.secondary,
);

/**
 * Axis label for a percent change from the window start. Formatting only: a
 * tick that lands on zero reads "0%", never "+0%".
 */
export function formatPercentChange(v: number): string {
  const rounded = Number(v.toFixed(1));
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

function referenceColor(symbol: string, idx: number): string {
  return REFERENCE_COLORS[symbol] ?? COIN_PALETTE[idx % COIN_PALETTE.length];
}

/** Every coin and reference, available or not, in the order they are drawn in the legend. */
export function spaghettiLegend(data: Pick<SpaghettiResponse, "series" | "references">): SpaghettiLegendEntry[] {
  const refs = data.references.map((r, idx) => ({
    symbol: r.symbol,
    color: referenceColor(r.symbol, idx),
    reference: true,
    available: r.available,
    reason: r.reason,
  }));
  const coins = data.series.map((s, idx) => ({
    symbol: s.symbol,
    color: COIN_PALETTE[idx % COIN_PALETTE.length],
    reference: false,
    available: s.available,
    reason: s.reason,
  }));
  return [...refs, ...coins];
}

function toPoints(line: SpaghettiLine) {
  return line.points.map((p) => ({ timestamp: p.timestamp, value: p.close }));
}

/**
 * The lines handed to the island: one per available, visible coin, then the
 * references on top. An unavailable coin gets no line at all, never a flat
 * zero; a hidden coin leaves the plot but keeps its legend entry.
 */
export function buildSpaghettiLines(
  data: Pick<SpaghettiResponse, "series" | "references">,
  hidden: ReadonlySet<string> = new Set(),
): SpaghettiPlotLine[] {
  const coins = data.series
    .map((s, idx) => ({ s, color: COIN_PALETTE[idx % COIN_PALETTE.length] }))
    .filter(({ s }) => s.available && !hidden.has(s.symbol))
    .map(({ s, color }) => ({ key: s.symbol, color, width: COIN_WIDTH, points: toPoints(s) }));
  const refs = data.references
    .map((r, idx) => ({ r, color: referenceColor(r.symbol, idx) }))
    .filter(({ r }) => r.available && !hidden.has(r.symbol))
    .map(({ r, color }) => ({ key: r.symbol, color, width: REFERENCE_WIDTH, points: toPoints(r) }));
  return [...coins, ...refs];
}

const SPAN_UNITS: Record<Timeframe, string> = {
  "15m": "15-minute bars",
  "1h": "hourly bars",
  "4h": "4-hour bars",
  "1d": "days",
  "1w": "weeks",
};

function spanDate(iso: string, timeframe: Timeframe, end: boolean): string {
  const ms = Date.parse(iso);
  if (timeframe === "1w") {
    // A weekly bar opens Monday 00:00 UTC; the last one ends on its Sunday.
    const d = new Date(end ? ms + 6 * 86_400_000 : ms);
    return d.toISOString().slice(0, 10);
  }
  const d = new Date(ms).toISOString();
  return timeframe === "1d" ? d.slice(0, 10) : `${d.slice(0, 10)} ${d.slice(11, 16)}`;
}

/**
 * What the chart covers, for example `Last 28 weeks, 2026-03-23 to 2026-10-04 UTC`.
 * Null when no line is available.
 */
export function spaghettiSpanText(data: SpaghettiResponse): string | null {
  const lines = [...data.series, ...data.references].filter((l) => l.available && l.window_start && l.window_end);
  if (lines.length === 0) return null;
  const bars = Math.max(...lines.map((l) => l.bars));
  const start = lines.map((l) => l.window_start as string).sort()[0];
  const end = lines.map((l) => l.window_end as string).sort()[lines.length - 1];
  const tf = data.timeframe;
  return `Last ${bars} ${SPAN_UNITS[tf]}, ${spanDate(start, tf, false)} to ${spanDate(end, tf, true)} UTC`;
}
