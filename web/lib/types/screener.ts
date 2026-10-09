// Mirrors api/models/screener.py exactly (Public Contracts sync point —
// PLAN.md: "mirrored (manually, documented as a sync point in Rules) by
// web/lib/types/screener.ts"). Keep this file's shapes in lockstep with the
// pydantic models by hand; api/tests/routers/test_screener_freshness_payload.py
// and test_screener_gain_contract.py cross-check the field names.

export type Timeframe = "15m" | "1h" | "4h" | "1d" | "1w";
export const TIMEFRAMES: Timeframe[] = ["15m", "1h", "4h", "1d", "1w"];

// RFC-005 (mirrors api/models/screener.py): why a ChartSeries/SpaghettiLine
// entry has no data. Before this existed, `available: false` collapsed three unrelated
// causes — a misconfigured symbol, a dead data source, and genuinely short history —
// into one signal.
export type UnavailableReason = "insufficient-history" | "bad-symbol" | "source-unavailable";

// T40 / S5a (mirrors api/models/screener.py::RsiReason/RsiReading/RsiPoint):
// RSI(14, Wilder) of the displayed timeframe. `value` is null with a `reason`
// when there is nothing honest to show, never 0; `as_of` ends in "Z".
export type RsiReason = "insufficient-history" | "bad-symbol" | "source-unavailable" | "flat-price";

export interface RsiReading {
  value: number | null;
  length: number;
  as_of: string | null;
  reason: RsiReason | null;
}

export interface RsiPoint {
  timestamp: string;
  value: number;
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
  // T40 / S5a: filled only by the drill-down chart view; board charts carry [].
  rsi: RsiPoint[];
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
  chart: ChartSeries;
  // Kept for existing consumers; equals gain_by_timeframe[tf].pct.
  percent_change_by_timeframe: Record<Timeframe, number | null>;
  gain_by_timeframe: Record<Timeframe, GainChip>;
  rsi: RsiReading;
}

export interface ScreenerBoardResponse {
  timeframe: Timeframe;
  coins: CoinPanel[];
  // T32 / S1: server clock and measured skew vs the exchange (seconds,
  // null = unknown); warning above 120 s.
  server_time: string | null;
  clock_skew_seconds: number | null;
  clock_skew_warning: boolean;
}

// T36 / S4 (mirrors api/models/screener.py::ChartView): the drill-down chart
// at its own interval (default 4h).
export interface ChartView {
  symbol: string;
  timeframe: Timeframe;
  chart: ChartSeries;
}

// T37 / S6 (mirrors api/models/screener.py::SpaghettiLine/SpaghettiResponse;
// api/tests/routers/test_spaghetti.py cross-checks the fields). `close` on a
// point is the percent change from the window's first close; timestamps are
// ISO-8601 UTC with a trailing "Z".
export interface SpaghettiLine {
  symbol: string;
  available: boolean;
  reason: UnavailableReason | null;
  points: ChartBar[];
  window_start: string | null;
  window_end: string | null;
  bars: number;
  last_bar_ts: string | null;
  stale: boolean;
}

export interface SpaghettiResponse {
  timeframe: Timeframe;
  window_cap_bars: number;
  server_time: string | null;
  series: SpaghettiLine[];
  references: SpaghettiLine[];
}
