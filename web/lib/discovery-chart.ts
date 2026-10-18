import type {
  DiscoveryCategoryHistory,
  DiscoveryCoinHistory,
  DiscoveryPrice,
} from "@/lib/types/discovery";

const finite = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

export interface CoinChartRow {
  date: string;
  score: number;
  covered: number;
  rising: number;
  /** The stored per-day flag, plotted as is (AC-W16). */
  trigger: boolean;
  thin: boolean;
  price: number | null;
  /** Price change in percent since the first day that has both a score and a price. */
  priceChange: number | null;
}

export interface CoinChartShape {
  rows: CoinChartRow[];
  floor: number;
  priceAvailable: boolean;
  priceBase: { date: string; close: number } | null;
}

/** Joins the stored score days with the daily closes by date; a missing price stays null, never 0. */
export function shapeCoinChart(history: DiscoveryCoinHistory, price: DiscoveryPrice | null): CoinChartShape {
  const closes = new Map<string, number>();
  for (const p of price?.days ?? []) {
    if (finite(p.close) && p.close > 0) closes.set(p.date, p.close);
  }
  const days = history.days.filter((d) => finite(d.score) && finite(d.covered_weight));
  const base = days.map((d) => ({ date: d.date, close: closes.get(d.date) })).find((p) => p.close !== undefined);
  const rows = days.map((d): CoinChartRow => {
    const close = closes.get(d.date) ?? null;
    return {
      date: d.date,
      score: d.score,
      covered: d.covered_weight,
      rising: d.rising_weight,
      trigger: d.trigger,
      thin: d.thin,
      price: base && close !== null ? close : null,
      priceChange: base && close !== null ? (close / (base.close as number) - 1) * 100 : null,
    };
  });
  return {
    rows,
    floor: history.min_covered_weight,
    priceAvailable: base !== undefined,
    priceBase: base ? { date: base.date, close: base.close as number } : null,
  };
}

export interface CategoryChartRow {
  date: string;
  score: number;
  /** Share of scorable coins whose trigger was set that day, 0..100. */
  sharePct: number;
  coinsUsed: number;
  triggered: number;
}

export function shapeCategoryChart(history: DiscoveryCategoryHistory): { rows: CategoryChartRow[] } {
  const rows = history.days
    .filter((d) => finite(d.score) && finite(d.triggered_share))
    .map((d) => ({
      date: d.date,
      score: d.score,
      sharePct: d.triggered_share * 100,
      coinsUsed: d.coins_used,
      triggered: d.triggered_count,
    }));
  return { rows };
}

/** Covered weight per day for the band, clamped to the 0-100 scale. */
export function bandPoints(rows: readonly CoinChartRow[]): number[] {
  return rows.map((r) => Math.min(100, Math.max(0, r.covered)));
}

export function thinDayCount(rows: readonly CoinChartRow[]): number {
  return rows.filter((r) => r.thin).length;
}

/** SVG path through the finite values; a null or NaN starts a new sub-path, so gaps stay gaps. */
export function linePath(
  values: readonly (number | null)[],
  x: (index: number) => number,
  y: (value: number) => number,
): string {
  let d = "";
  let pen = false;
  values.forEach((v, i) => {
    if (!finite(v)) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${round(x(i))} ${round(y(v))}`;
    pen = true;
  });
  return d;
}

const round = (n: number) => Math.round(n * 10) / 10;

/** [min, max] over the finite values, always containing 0 and never zero-width. */
export function valueDomain(values: readonly (number | null)[]): [number, number] {
  const vs = values.filter(finite);
  const lo = Math.min(0, ...vs);
  const hi = Math.max(0, ...vs);
  return hi - lo < 1e-9 ? [lo - 1, hi + 1] : [lo, hi];
}

export interface PanelScale {
  /** Padded domain the panel draws. */
  lo: number;
  hi: number;
  /** Data extremes (zero-inclusive when asked): where the axis labels sit. */
  min: number;
  max: number;
}

/**
 * Domain for one panel, fitted to that panel's own data (T107): finite values only, zero included when it
 * means something, a little padding, clamped when the quantity has hard bounds. Never zero-width.
 */
export function fitScale(
  values: readonly (number | null | undefined)[],
  opts: { includeZero?: boolean; padFrac?: number; clamp?: [number, number] } = {},
): PanelScale {
  const { includeZero = false, padFrac = 0.1, clamp } = opts;
  const vs = values.filter(finite);
  let min = vs.length ? Math.min(...vs) : 0;
  let max = vs.length ? Math.max(...vs) : 0;
  if (includeZero) {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }
  let lo = min;
  let hi = max;
  if (hi - lo < 1e-9) {
    const half = Math.max(1, Math.abs(lo) * 0.1);
    lo -= half;
    hi += half;
  }
  const pad = (hi - lo) * padFrac;
  lo -= pad;
  hi += pad;
  if (clamp) {
    lo = Math.max(clamp[0], lo);
    hi = Math.min(clamp[1], hi);
    if (hi - lo < 1e-9) {
      lo = clamp[0];
      hi = clamp[1];
    }
  }
  return { lo, hi, min, max };
}

export interface AxisTick {
  value: number;
  label: string;
  /** Pixel offset from the top of a panel `height` tall. */
  y: number;
}

/** "+30%", "-3%", "0%"; finer decimals on tiny spans so ticks stay distinct, and never "-0". */
export function tickLabel(v: number, span: number): string {
  const decimals = span >= 10 ? 0 : span >= 1 ? 1 : 2;
  const s = v.toFixed(decimals);
  const n = Number(s);
  if (n === 0) return "0%";
  return `${n > 0 ? "+" : ""}${s}%`;
}

/**
 * At most 3 y labels (max, min, then zero or the midpoint), ascending by value. A candidate that sits within
 * `minGap` pixels of one already kept, or repeats its label, is dropped, so labels never overlap.
 */
export function axisTicks(
  scale: PanelScale,
  opts: { height: number; includeZero?: boolean; minGap?: number; fmt?: (v: number, span: number) => string },
): AxisTick[] {
  const { height, includeZero = false, minGap = 14, fmt = tickLabel } = opts;
  const span = scale.hi - scale.lo;
  const y = (v: number) => ((scale.hi - v) / (scale.hi - scale.lo)) * height;
  const middle = includeZero && scale.min < 0 && scale.max > 0 ? 0 : (scale.min + scale.max) / 2;
  const kept: AxisTick[] = [];
  for (const value of [scale.max, scale.min, middle]) {
    const t: AxisTick = { value, label: fmt(value, scale.max - scale.min || span), y: y(value) };
    if (kept.some((k) => k.label === t.label || Math.abs(k.y - t.y) < minGap)) continue;
    kept.push(t);
  }
  return kept.sort((a, b) => a.value - b.value);
}

/** First, middle and last day index for the shared date axis; no duplicates on short series. */
export function xTickIndices(n: number): number[] {
  if (n <= 0) return [];
  return Array.from(new Set([0, Math.floor((n - 1) / 2), n - 1]));
}

export interface CoverageBar {
  value: number;
  /** Under the floor: drawn muted, because such a day cannot trigger. */
  muted: boolean;
}

export function coverageBars(rows: readonly CoinChartRow[], floor: number): CoverageBar[] {
  return bandPoints(rows).map((value) => ({ value, muted: value < floor }));
}

export function isConstant(values: readonly number[]): boolean {
  return values.every((v) => v === values[0]);
}

/** Pointer x (px from the plot's left edge) to the nearest day index. */
export function dayIndexAt(px: number, left: number, plotW: number, n: number): number {
  if (n <= 1 || plotW <= 0) return 0;
  return Math.min(n - 1, Math.max(0, Math.round(((px - left) / plotW) * (n - 1))));
}
