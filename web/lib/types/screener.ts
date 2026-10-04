// Mirrors api/models/screener.py exactly (Public Contracts sync point —
// PLAN.md: "mirrored (manually, documented as a sync point in Rules) by
// web/lib/types/screener.ts"). Keep this file's shapes in lockstep with the
// pydantic models by hand; api/tests/routers/test_screener_integration.py
// (RFC-004, item 65) cross-checks a real response's `confidence` field
// against this file's union type.

export type Timeframe = "15m" | "1h" | "4h" | "1d" | "1w";
export const TIMEFRAMES: Timeframe[] = ["15m", "1h", "4h", "1d", "1w"];

export type RelativePerformanceTimeframe = "7d" | "30d" | "90d" | "ytd";

export type MomentumStateLiteral = "PASS" | "FAIL" | "insufficient";
export type TrendDirectionLiteral = "up" | "down" | "insufficient";

// RFC-005 (mirrors api/models/screener.py): why a ChartSeries/RelativePerformanceSeries
// entry has no data. Before this existed, `available: false` collapsed three unrelated
// causes — a misconfigured symbol, a dead data source, and genuinely short history —
// into one signal.
export type UnavailableReason = "insufficient-history" | "bad-symbol" | "source-unavailable";

// ADR-4's closed confidence enum (exactly these 4 values) — a closed union,
// not an open string, per Public Contracts.
export type ConfidenceState = "aligned" | "mixed" | "conflicting" | "insufficient-data";

// ADR-4's two derived-input closed enums (RFC-004, item 64a) — exposed on
// CoinPanel alongside `confidence` so SignalDetailPanel renders each signal
// from its own typed state, never re-derived from the aggregate badge
// (Risk Prediction #4).
export type LegContextLiteral = "confirmed" | "candidate-pending" | "unavailable";
export type NarrativeStateLiteral =
  | "in-focus"
  | "confirmed-emerging"
  | "unconfirmed-emerging"
  | "rotated-out"
  | "unmapped"
  | "unavailable";

export interface MomentumState {
  state: MomentumStateLiteral;
  daily_value: number | null;
  weekly_value: number | null;
}

export interface TrendState {
  direction: TrendDirectionLiteral;
  sma_value: number | null;
}

export interface BenchmarkSelection {
  active: "BTC" | "HYPE";
  reason: string;
}

export interface ChartBar {
  timestamp: string;
  close: number;
}

export interface ChartSeries {
  price: ChartBar[];
  sma: ChartBar[];
  available: boolean;
  reason: UnavailableReason | null;
  // T32 / S1: freshness. ISO-8601 UTC with a trailing "Z"; nulls and
  // stale=false when the chart is unavailable.
  last_bar_ts: string | null;
  fetched_at: string | null;
  is_partial: boolean | null;
  server_time: string | null;
  stale: boolean;
}

// T34 / S2 (mirrors api/models/screener.py::GainChip): the current candle of
// one timeframe, open to latest price (1w: the newest Monday-anchored week).
// `pct` is null with a `reason` when there is nothing honest to show, never
// 0; a flat candle is a real 0. `open_ts` is ISO-8601 UTC with a trailing "Z".
export interface GainChip {
  pct: number | null;
  open_ts: string | null;
  is_partial: boolean;
  stale: boolean;
  reason: UnavailableReason | null;
}

export interface CoinPanel {
  symbol: string;
  momentum: MomentumState;
  trend: TrendState;
  confidence: ConfidenceState;
  leg_context: LegContextLiteral;
  narrative_state: NarrativeStateLiteral;
  chart: ChartSeries;
  // Kept for existing consumers; equals gain_by_timeframe[tf].pct.
  percent_change_by_timeframe: Record<Timeframe, number | null>;
  gain_by_timeframe: Record<Timeframe, GainChip>;
}

export interface ScreenerBoardResponse {
  timeframe: Timeframe;
  active_benchmark: BenchmarkSelection;
  coins: CoinPanel[];
  // T32 / S1: server clock and measured skew vs the exchange (seconds,
  // null = unknown); warning above 120 s.
  server_time: string | null;
  clock_skew_seconds: number | null;
  clock_skew_warning: boolean;
}

export interface ScalpMomentumState {
  state: MomentumStateLiteral;
  value: number | null;
  timeframe: Timeframe;
}

export interface ScalpView {
  symbol: string;
  timeframe: Timeframe;
  chart: ChartSeries;
  scalp_momentum: ScalpMomentumState;
}

export interface RelativePerformanceSeries {
  symbol: string;
  available: boolean;
  points: ChartBar[]; // `close` holds % change from the window's start here
  reason: UnavailableReason | null;
}

export interface RelativePerformanceResponse {
  timeframe: RelativePerformanceTimeframe;
  series: RelativePerformanceSeries[];
}

// RFC-002 (item 46) — mirrors api/models/regime.py.
export type LiquidityCompositeVariant = "reduced" | "full";

export interface LegBoundary {
  date: string; // ISO date (YYYY-MM-DD)
  z_score: number;
  confirmed: boolean;
  confirmed_date: string | null;
}

export interface LegBoundaryResponse {
  composite_variant: LiquidityCompositeVariant;
  candidate_boundaries: LegBoundary[];
  confirmed_boundaries: LegBoundary[];
  active_benchmark_reason: string;
}

// RFC-003 (item 60) — mirrors api/models/narrative.py.
export type SourceAvailability = "ok" | "unavailable" | "stale" | "presumed-dead";

export interface NarrativeCategory {
  id: string;
  label: string;
  keywords: string[];
  seed: boolean;
  triggered: boolean;
  confirmed: boolean;
  trust_weight: number;
  source_availability: Record<string, SourceAvailability>;
}
