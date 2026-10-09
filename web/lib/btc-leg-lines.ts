import { SERIES } from "@/lib/chart-palette";
import type { SimpleLineSeries } from "@/lib/island-loader";
import type {
  AgeEstimate,
  AgeLabel,
  BtcLegChartResponse,
  CompositeChangeLabel,
  CompositeEstimate,
} from "@/lib/types/btc-legs";

/**
 * T38 / S7: the pure builders behind the BTC leg chart, kept out of the
 * component so they are tested directly (jsdom never mounts the island).
 *
 * A band is one confirmed leg, from its boundary date to the next boundary;
 * the current leg runs to the last BTC bar. Bands alternate two tints so two
 * adjacent legs stay apart. A marker is one confirmed boundary date.
 *
 * The estimate text is built from the payload only: every number the rule
 * used is printed beside the label, and an N/A carries its reason. The only
 * label words are the six in ESTIMATE_LABELS.
 */

export const ESTIMATE_HEADING = "Estimate (rule over the numbers shown)";
export const AGE_LABELS: readonly AgeLabel[] = ["early", "mid", "late"];
export const COMPOSITE_LABELS: readonly CompositeChangeLabel[] = ["rising", "falling", "flat"];
export const ESTIMATE_LABELS: readonly string[] = [...AGE_LABELS, ...COMPOSITE_LABELS];

export interface LegBand {
  from: string;
  to: string;
  tint: 0 | 1;
  current: boolean;
}

export interface LegMarker {
  timestamp: string;
  label: string;
}

export interface Readout {
  key: string;
  label: string;
  value: string;
}

export interface EstimateLine {
  key: string;
  label: string;
  value: string;
}

export interface EstimatePart {
  title: string;
  label: string | null;
  reason: string | null;
  inputs: EstimateLine[];
  rule: string;
}

function dayStart(date: string): string {
  return `${date}T00:00:00Z`;
}

/** The BTC daily close as the chart's one line. */
export function btcSeries(data: Pick<BtcLegChartResponse, "btc">): SimpleLineSeries[] {
  return [
    {
      key: "BTC",
      color: SERIES.primary,
      width: 2,
      points: data.btc.map((b) => ({ timestamp: b.timestamp, value: b.close })),
    },
  ];
}

/** One band per confirmed leg; the current leg is open to the last bar. */
export function legBands(data: Pick<BtcLegChartResponse, "legs" | "last_bar_ts">): LegBand[] {
  const out: LegBand[] = [];
  data.legs.forEach((leg, idx) => {
    const to = leg.end !== null ? dayStart(leg.end) : data.last_bar_ts;
    if (to === null) return;
    out.push({ from: dayStart(leg.start), to, tint: (idx % 2) as 0 | 1, current: leg.is_current });
  });
  return out;
}

/** One marker per confirmed boundary date. */
export function boundaryMarkers(data: Pick<BtcLegChartResponse, "boundaries">): LegMarker[] {
  return data.boundaries.map((b) => ({ timestamp: dayStart(b.date), label: b.date }));
}

function num(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "n/a";
  return String(Number(v.toFixed(digits)));
}

function signed(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "n/a";
  const s = num(v, digits);
  return v > 0 ? `+${s}` : s;
}

function day(ts: string | null): string {
  return ts ? ts.slice(0, 10) : "n/a";
}

/** "Daily BTC, 2023-01-01 to 2026-10-08 UTC, 1377 bars (all cached history)". */
export function btcLegSpanText(data: Pick<BtcLegChartResponse, "first_bar_ts" | "last_bar_ts" | "bar_count">): string | null {
  if (!data.first_bar_ts || !data.last_bar_ts) return null;
  return `Daily BTC, ${day(data.first_bar_ts)} to ${day(data.last_bar_ts)} UTC, ${data.bar_count} bars (all cached history)`;
}

/** The current-leg numbers, each with its own testid key. */
export function currentLegReadouts(data: Pick<BtcLegChartResponse, "current_leg">): Readout[] {
  const c = data.current_leg;
  if (!c) return [];
  const rows: Readout[] = [
    { key: "start", label: "Leg start", value: c.start_date },
    { key: "days", label: "Days in leg", value: String(c.days_in_leg) },
    { key: "boundary-z", label: "Boundary z", value: signed(c.last_boundary_z, 2) },
    {
      key: "composite",
      label: `Composite (${c.composite_variant})`,
      value: `${num(c.composite_value)} as of ${c.composite_as_of ?? "n/a"}`,
    },
    { key: "change-14d", label: "14-point change", value: signed(c.change_14d) },
  ];
  if (c.latest_candidate) {
    const lc = c.latest_candidate;
    rows.push({
      key: "latest-candidate",
      label: "Latest candidate",
      value: `${lc.date}, z ${signed(lc.z_score, 2)}, ${lc.confirmed ? "confirmed" : "unconfirmed"}`,
    });
  }
  return rows;
}

/** The AGE part: label or N/A, and every input the rule used. */
export function ageEstimatePart(age: AgeEstimate): EstimatePart {
  return {
    title: "Leg age",
    label: age.label,
    reason: age.label === null ? (age.reason ?? "N/A") : null,
    inputs: [
      { key: "age-days", label: "age_days", value: String(age.age_days) },
      { key: "median-days", label: "median_days", value: num(age.median_days, 1) },
      { key: "ratio", label: "ratio", value: num(age.ratio) },
      { key: "earlier-legs", label: "earlier legs", value: String(age.earlier_legs) },
      {
        key: "earlier-lengths",
        label: "earlier lengths (days)",
        value: age.earlier_lengths_days.length ? age.earlier_lengths_days.join(", ") : "none",
      },
    ],
    rule: age.rule,
  };
}

/** The COMPOSITE part: label or N/A, and every input the rule used. */
export function compositeEstimatePart(comp: CompositeEstimate): EstimatePart {
  return {
    title: "Composite change",
    label: comp.label,
    reason: comp.label === null ? (comp.reason ?? "N/A") : null,
    inputs: [
      { key: "change-14d", label: "change_14d", value: signed(comp.change_14d, 4) },
      { key: "threshold", label: "T", value: num(comp.threshold, 4) },
      { key: "std", label: "std (ddof 1)", value: num(comp.history_std, 4) },
      { key: "n", label: "n", value: String(comp.n_changes) },
      { key: "as-of", label: "composite as of", value: comp.composite_as_of ?? "n/a" },
    ],
    rule: comp.rule,
  };
}

/** A part as one line of plain text: "Leg age: mid (age_days 10, ...)". */
export function estimatePartText(part: EstimatePart): string {
  const head = part.label ?? `N/A (${part.reason})`;
  const inputs = part.inputs.map((i) => `${i.label} ${i.value}`).join(", ");
  return `${part.title}: ${head}; ${inputs}`;
}
