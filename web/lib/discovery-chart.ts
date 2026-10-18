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
