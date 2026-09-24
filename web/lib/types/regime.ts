// Mirrors api/models/regime.py (RFC-004, plan §11). Points never carry
// null/0 stand-ins — a date with no value is simply absent.
//
// `gap_before` (RFC-005 decision 9): true when the previous point of the same
// series is more than that series' `max_gap_days` calendar days earlier — a
// real data hole, not the series' normal cadence. The API computes it on the
// full series; charts must not draw a line into such a point.

export type ComponentStatus = "ok" | "stale" | "unavailable" | "not_applicable" | "no_data";
export type PublishedStatus = "ok" | "unavailable";

export interface ComponentPoint {
  date: string;
  value: number; // impulse, in the component's unit
  raw: number; // underlying level
  contribution: number; // sign·tanh(impulse/scale), in [-1, 1]
  gap_before: boolean;
}

export interface RegimeComponent {
  id: string;
  label: string;
  weight: number;
  source: string;
  transform: string;
  frequency: string;
  unit: string;
  status: ComponentStatus;
  reason: string | null;
  notes: string[];
  first_date: string | null;
  last_date: string | null;
  last_fetched_utc: string | null;
  max_gap_days: number;
  points: ComponentPoint[];
}

export interface ReproducedPoint {
  date: string;
  value: number;
  coverage: number;
  gap_before: boolean;
}

export interface ReproducedComposite {
  label: string;
  normalisation: string;
  max_gap_days: number;
  points: ReproducedPoint[];
}

export interface PublishedPoint {
  date: string;
  value: number;
  regime_label: string | null;
  gap_before: boolean;
}

export interface PublishedComposite {
  label: string;
  attribution: string;
  status: PublishedStatus;
  max_gap_days: number;
  points: PublishedPoint[];
}

export interface CompositeAgreement {
  overlap_days: number;
  pearson_r: number | null;
  mean_abs_diff: number | null;
  full_coverage_days: number;
  full_coverage_mean_abs_diff: number | null;
}

export interface RegimeComposite {
  reproduced: ReproducedComposite;
  published: PublishedComposite;
  agreement: CompositeAgreement;
}

export interface RegimeComponentsResponse {
  generated_utc: string;
  grid_dates: string[];
  components: RegimeComponent[];
  composite: RegimeComposite;
}
