import { formatDateTimeZone } from "@/lib/brussels-time";
import type { RsiReading, RsiReason } from "@/lib/types/screener";

/**
 * T41 / S5b: display copy for RSI 14 (Wilder) readings. A missing value is
 * "N/A" with a reason, never 0; times are Brussels time (S11a).
 */

export function formatRsi(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  return value.toFixed(1);
}

export function rsiReasonText(reason: RsiReason | null): string {
  switch (reason) {
    case "insufficient-history":
      return "Not enough history for RSI 14";
    case "bad-symbol":
      return "Symbol configuration issue";
    case "source-unavailable":
      return "Data source unavailable";
    case "flat-price":
      return "Price did not change in this window";
    default:
      return "No RSI value";
  }
}

export function rsiTitle(reading: RsiReading): string | undefined {
  if (reading.value === null) return rsiReasonText(reading.reason);
  if (!reading.as_of) return undefined;
  return `RSI ${reading.length} at ${formatDateTimeZone(new Date(reading.as_of))}`;
}
