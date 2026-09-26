import type {
  ChainGrowth,
  ComparisonSeries,
  FloorRampState,
  GrowthParams,
  OnchainMetric,
  OnchainGrowthResponse,
} from "@/lib/types/onchain";

/**
 * View model for /onchain (chain-growth RFC-5). Pure mapping from the API
 * response to render props: grid alignment, label copy, colour lookup. Every
 * number shown (values, EMAs, index, % above low, floor/ramp events, state,
 * divergence) comes from Python. Nothing here re-implements an analytic.
 */

/**
 * Categorical slots (dataviz palette.md), assigned in FIXED order per chain
 * entity. Colour follows the chain, never its rank or the current filter.
 * Validated with validate_palette.js in both modes (see the RFC-5 report).
 */
export const CHAIN_SLOT_ORDER = ["ethereum", "base", "arbitrum", "optimism", "polygon", "robinhood"] as const;
const LIGHT_SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];
const DARK_SLOTS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"];
/** A chain outside the six slots gets muted ink, never a generated 7th hue. */
export const UNSLOTTED_COLOR = "#898781";

export function chainColor(id: string, mode: "light" | "dark" = "light"): string {
  const slot = (CHAIN_SLOT_ORDER as readonly string[]).indexOf(id);
  if (slot < 0) return UNSLOTTED_COLOR;
  return (mode === "dark" ? DARK_SLOTS : LIGHT_SLOTS)[slot];
}

/** Text and chrome tokens (palette.md §Chart chrome & ink, light). Text never uses a series colour. */
export const INK = {
  primary: "#0b0b0b",
  secondary: "#52514e",
  muted: "#898781",
  gridline: "#e1e0d9",
  baseline: "#c3c2b7",
  /** Pre-launch points: muted, so they read as context, not signal (D2). */
  preLaunch: "#c3c2b7",
  preLaunchFill: "rgba(195, 194, 183, 0.25)",
} as const;

export const METRIC_LABELS: Record<OnchainMetric, string> = {
  active_addresses: "Active addresses",
  transactions: "Transactions",
};

export type RangeKey = "1y" | "2y" | "5y" | "all";
export const RANGE_OPTIONS: { key: RangeKey; label: string; days: number | null }[] = [
  { key: "1y", label: "1Y", days: 365 },
  { key: "2y", label: "2Y", days: 730 },
  { key: "5y", label: "5Y", days: 1825 },
  { key: "all", label: "All", days: null },
];
export const DEFAULT_RANGE: RangeKey = "1y";

function isoMinusDays(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d) - days * 86_400_000).toISOString().slice(0, 10);
}

/**
 * The `start` query value for a range (calendar arithmetic on the last grid
 * date). "all" = the first grid date. Undefined for an empty grid, which lets
 * the API apply its own default.
 */
export function rangeStart(range: RangeKey, gridDates: string[]): string | undefined {
  if (gridDates.length === 0) return undefined;
  const opt = RANGE_OPTIONS.find((o) => o.key === range);
  if (!opt || opt.days === null) return gridDates[0];
  return isoMinusDays(gridDates[gridDates.length - 1], opt.days);
}

/** Logical grid range from `start` to the last grid date; null for an empty grid. */
export function visibleRangeFrom(gridDates: string[], start: string): { from: number; to: number } | null {
  if (gridDates.length === 0) return null;
  let from = gridDates.findIndex((g) => g >= start);
  if (from < 0) from = 0;
  return { from, to: gridDates.length - 1 };
}

export const STATE_LABELS: Record<FloorRampState, string> = {
  floor: "Near floor",
  ramping: "Ramping",
  declining: "Declining",
  neutral: "Neutral",
  "not-enough-history": "Not enough history",
};

export interface PanelMarker {
  date: string;
  kind: "floor" | "ramp";
}

export interface PanelModel {
  id: string;
  label: string;
  color: string;
  /** All aligned to grid_dates; null = no value on that date. */
  value: (number | null)[];
  preLaunchValue: (number | null)[];
  ema7: (number | null)[];
  ema28: (number | null)[];
  gapBefore: boolean[];
  hasPreLaunch: boolean;
  markers: PanelMarker[];
}

/** Grid-aligned arrays for one live chain. Pre-launch points are split out (D2). */
export function buildPanelModel(chain: ChainGrowth, gridDates: string[]): PanelModel {
  const n = gridDates.length;
  const indexOf = new Map(gridDates.map((d, i) => [d, i]));
  const value: (number | null)[] = new Array(n).fill(null);
  const preLaunchValue: (number | null)[] = new Array(n).fill(null);
  const ema7: (number | null)[] = new Array(n).fill(null);
  const ema28: (number | null)[] = new Array(n).fill(null);
  const gapBefore: boolean[] = new Array(n).fill(false);
  let hasPreLaunch = false;
  for (const p of chain.series?.points ?? []) {
    const i = indexOf.get(p.date);
    if (i === undefined) continue;
    if (p.pre_launch) {
      preLaunchValue[i] = p.value;
      hasPreLaunch = true;
    } else {
      value[i] = p.value;
    }
    ema7[i] = p.ema7;
    ema28[i] = p.ema28;
    gapBefore[i] = p.gap_before;
  }
  const markers: PanelMarker[] = [];
  for (const e of chain.floor_ramp?.events ?? []) {
    markers.push({ date: e.floor_date, kind: "floor" }, { date: e.ramp_date, kind: "ramp" });
  }
  markers.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  return {
    id: chain.id,
    label: chain.label,
    color: chainColor(chain.id),
    value,
    preLaunchValue,
    ema7,
    ema28,
    gapBefore,
    hasPreLaunch,
    markers,
  };
}

export function isLive(chain: ChainGrowth): boolean {
  return chain.status !== "unavailable" && chain.series !== null;
}

/** Whole days between the last fetch and the response time (display arithmetic only). */
export function staleDays(lastAsOfUtc: string | null, generatedUtc: string): number | null {
  if (lastAsOfUtc === null) return null;
  const last = Date.parse(lastAsOfUtc.endsWith("Z") || lastAsOfUtc.includes("+") ? lastAsOfUtc : `${lastAsOfUtc}Z`);
  const gen = Date.parse(generatedUtc);
  if (Number.isNaN(last) || Number.isNaN(gen)) return null;
  return Math.max(0, Math.floor((gen - last) / 86_400_000));
}

export function limitedHistoryText(chain: ChainGrowth): string | null {
  if (!chain.limited_history) return null;
  const gate = chain.floor_ramp?.gate_met_on;
  return gate
    ? `Limited history — floor/ramp markers from ${gate}`
    : "Limited history — floor/ramp markers once enough history exists";
}

/** Visible method note, built from the API's own params (AC-2). */
export function methodNote(params: GrowthParams): string {
  const pct = (x: number) => `${Math.round(x * 100)}%`;
  return (
    `Daily values per chain from growthepie, smoothed with a ${params.ema_span}-day EMA (the ${params.ema_fast_span}-day EMA is shown on hover). ` +
    `A floor is a ${params.window_days}-day low of the smoothed line; a ramp is a recovery of ${pct(params.recovery_pct)} above that floor held for ${params.sustain_days} days. ` +
    `"Near floor" means within ${pct(params.floor_state_pct)} of the ${params.window_days}-day low. ` +
    `Markers need ${params.min_history_days} days of history. Raw counts are not comparable across chains — use the normalised comparison.`
  );
}

export type ComparisonMode = "index" | "pct";

export function comparisonValues(s: ComparisonSeries, mode: ComparisonMode): (number | null)[] {
  return mode === "index" ? s.index_values : s.pct_above_low_values;
}

/** Last non-null value in a grid-aligned array (the direct endpoint label). */
export function latestValue(values: (number | null)[]): { index: number; value: number } | null {
  for (let i = values.length - 1; i >= 0; i--) {
    const v = values[i];
    if (v !== null && v !== undefined) return { index: i, value: v };
  }
  return null;
}

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });
const whole = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function formatCount(v: number | null): string {
  return v === null ? "—" : v >= 10_000 ? compact.format(v) : whole.format(v);
}

export function formatComparison(v: number | null, mode: ComparisonMode): string {
  if (v === null) return "—";
  return mode === "index" ? v.toFixed(1) : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export function formatSignedPct(v: number | null, digits = 2): string {
  if (v === null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

/** True when any displayed chain is served from growthepie (drives the CC BY footer). */
export function usesGrowthepie(resp: OnchainGrowthResponse): boolean {
  return resp.chains.some((c) => c.series?.source === "growthepie");
}
