import type { GainChip, Timeframe } from "@/lib/types/screener";

/**
 * T47 / S9C: captions for date-only bars (equities). A daily bar is a
 * trading date and a weekly bar is labelled with its Monday, so the caption
 * names the date only, never a clock time or an age:
 *   1d: `Latest daily bar 2026-10-09`
 *   1w: `Latest weekly bar, week of 2026-10-05`
 * plus ` (forming)` while the bar is still open. The date is read from the
 * payload's ISO string as is; no clock is consulted here.
 */

const DATE = /^(\d{4}-\d{2}-\d{2})/;

/** The `YYYY-MM-DD` of an ISO timestamp, or null. */
export function barDate(ts: string | null | undefined): string | null {
  if (!ts) return null;
  const match = DATE.exec(ts);
  return match ? match[1] : null;
}

export function dateOnlyCaption(
  fields: { last_bar_ts: string | null; is_partial: boolean | null },
  timeframe: Timeframe | undefined,
): string | null {
  const date = barDate(fields.last_bar_ts);
  if (!date) return null;
  const head = timeframe === "1w" ? `Latest weekly bar, week of ${date}` : `Latest daily bar ${date}`;
  return fields.is_partial ? `${head} (forming)` : head;
}

/** The gain-chip tooltip for a chip with a value: `1d candle from 2026-10-09`. */
export function dateOnlyChipTitle(tf: Timeframe, chip: GainChip): string {
  const date = barDate(chip.open_ts) ?? "?";
  return `${tf} candle from ${date}${chip.is_partial ? " (forming)" : ""}`;
}
