// Mirrors api/models/regime.py (RFC-004, plan §11). Points never carry
// null/0 stand-ins — a date with no value is simply absent.

export type ComponentStatus = "ok" | "stale" | "unavailable" | "not_applicable" | "no_data";
export type PublishedStatus = "ok" | "unavailable";

export interface ComponentPoint {
  date: string;
  value: number; // impulse, in the component's unit
  raw: number; // underlying level
  contribution: number; // sign·tanh(impulse/scale), in [-1, 1]
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
  points: ComponentPoint[];
}

export interface ReproducedPoint {
  date: string;
  value: number;
  coverage: number;
}

export interface ReproducedComposite {
  label: string;
  normalisation: string;
  points: ReproducedPoint[];
}

export interface PublishedPoint {
  date: string;
  value: number;
  regime_label: string | null;
}

export interface PublishedComposite {
  label: string;
  attribution: string;
  status: PublishedStatus;
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
