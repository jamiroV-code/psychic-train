import type { ComponentStatus } from "@/lib/types/regime";

/**
 * Display formatting for the /regime page, driven by each component's `unit`
 * string from the API (RFC-005 decision 6). Formatting only — every number
 * comes from the API; nothing is recomputed here. Mirrors the one-place
 * discipline of format-unavailable-reason.ts so panels, readout and
 * drill-down cannot drift apart.
 */

const NO_VALUE = "no value";

function signed(text: string, value: number): string {
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}

function usd(abs: number): string {
  if (abs >= 1e12) return `$${(abs / 1e12).toFixed(2)}tn`;
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}bn`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}m`;
  return `$${abs.toFixed(0)}`;
}

/** Plotted impulse (`value`) in the component's unit, signed. */
export function formatRegimeValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return NO_VALUE;
  const abs = Math.abs(value);
  switch (unit) {
    case "USD":
      return signed(usd(abs), value);
    case "fraction":
      return signed(`${(abs * 100).toFixed(2)}%`, value);
    case "percentage points":
      return signed(`${abs.toFixed(2)}pp`, value);
    case "index":
      return value.toFixed(1);
    default:
      return `${value.toFixed(2)} ${unit}`.trim();
  }
}

/**
 * Raw underlying level. The API gives one `unit` per component, which
 * describes the impulse; for "fraction" components the level is not itself
 * a fraction (supply in USD, a dollar index), so it is shown as a plain
 * compact number rather than guessing its unit.
 */
export function formatRegimeRaw(raw: number | null | undefined, unit: string): string {
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return NO_VALUE;
  switch (unit) {
    case "USD":
      return raw < 0 ? `−${usd(Math.abs(raw))}` : usd(raw);
    case "percentage points":
      return `${raw.toFixed(2)}%`;
    default:
      return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(raw);
  }
}

/** Normalised −1..+1 contribution. */
export function formatContribution(contribution: number | null | undefined): string {
  if (contribution === null || contribution === undefined || !Number.isFinite(contribution)) return NO_VALUE;
  return signed(Math.abs(contribution).toFixed(3), contribution);
}

/** Coverage share (0..1) as a percentage. */
export function formatCoverage(coverage: number | null | undefined): string {
  if (coverage === null || coverage === undefined || !Number.isFinite(coverage)) return NO_VALUE;
  return `${Math.round(coverage * 100)}%`;
}

/** Readable text for a non-ok component status; null when status is ok. */
export function formatRegimeStatus(status: ComponentStatus, reason: string | null): string | null {
  switch (status) {
    case "ok":
      return null;
    case "stale":
      return `Stale — ${reason ?? "showing the last cached data"}`;
    case "unavailable":
      return `Unavailable — ${reason ?? "source failed and nothing is cached"}`;
    case "not_applicable":
      return `Not applicable — ${reason ?? "this component cannot exist in the requested range"}`;
    case "no_data":
      return `No data — ${reason ?? "no points in the requested range"}`;
    default:
      return `Status: ${String(status)}`;
  }
}
