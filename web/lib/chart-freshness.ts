import { formatUtcDateTime } from "@/lib/chart-time-format";
import type { ChartSeries } from "@/lib/types/screener";

/**
 * The "last bar" caption under a screener chart (T34 / S2).
 *
 * Aged against the payload's own `server_time`, never the browser clock, so a
 * machine with a wrong clock still reads the same caption:
 *   forming: `Last bar 2026-10-03 14:15 UTC, opened 7 min ago (forming)`
 *   closed:  `Last bar 2026-10-03 14:00 UTC, 22 min ago`
 * Age is measured from the bar's open in both cases.
 */

export type ChartFreshnessFields = Pick<ChartSeries, "last_bar_ts" | "is_partial" | "server_time" | "stale">;

/** `<1 min`, `N min` (under 120 min), `N h` (under 48 h), else `N d`. */
export function formatAge(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 60) return "<1 min";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 120) return `${minutes} min`;
  const hours = Math.floor(seconds / 3600);
  if (hours < 48) return `${hours} h`;
  return `${Math.floor(seconds / 86400)} d`;
}

function parse(ts: string | null): Date | null {
  if (!ts) return null;
  const date = new Date(ts);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** The caption, or null when the series has no last bar to describe. */
export function freshnessCaption(fields: ChartFreshnessFields): string | null {
  const lastBar = parse(fields.last_bar_ts);
  if (!lastBar) return null;
  const head = `Last bar ${formatUtcDateTime(lastBar)} UTC`;
  const serverTime = parse(fields.server_time);
  if (!serverTime) return fields.is_partial ? `${head} (forming)` : head;
  const age = formatAge((serverTime.getTime() - lastBar.getTime()) / 1000);
  return fields.is_partial ? `${head}, opened ${age} ago (forming)` : `${head}, ${age} ago`;
}
