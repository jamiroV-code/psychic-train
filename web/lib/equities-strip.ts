import { dayKey, formatDay, formatTimeZone } from "@/lib/brussels-time";
import type { LiveStatus } from "@/lib/live-poll";
import { offReason, stripModel, stripTime, type StripModel } from "@/lib/refresh-strip";
import type { EquitiesStatus } from "@/lib/types/equities";

/**
 * T50 / S9E: the equities freshness strip. It reuses the crypto strip model
 * (`stripModel`, its overdue rule and times) and swaps the words: the latest
 * daily bar date, the next expected market-close refresh in Brussels time
 * and plain wording for a worker that is off. The server only ever schedules
 * a refresh on a US market day, so a weekend or a holiday is never overdue.
 * Times come from the server's clock; nothing here reads the browser clock.
 */

export const EQUITIES_STRIP_HELP =
  "The server refreshes equities once per US market day, about 30 min after the 16:00 New York close; " +
  "weekends and US market holidays have no refresh. Page checked is the last time this page got an answer " +
  "from the server, by the server's clock; it re-checks every minute while this tab is visible. " +
  "Overdue means more than 5 min past the expected refresh time.";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const EQUITIES_REASONS: Record<string, string> = {
  "missing-key": "no market data key is set on the server",
};

export interface EquitiesStripModel extends StripModel {
  lastBar: string | null;
}

function instant(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

/** `Mon 12 Oct 22:30 CEST`, always with its Brussels weekday and date. */
export function refreshTime(ms: number | null): string {
  if (ms === null) return "n/a";
  const date = new Date(ms);
  const weekday = WEEKDAYS[(((dayKey(date) + 4) % 7) + 7) % 7];
  return `${weekday} ${formatDay(date)} ${formatTimeZone(date)}`;
}

export function equitiesOffReason(reason: string | null): string {
  const mapped = reason ? EQUITIES_REASONS[reason] : undefined;
  return mapped ?? offReason(reason);
}

export function equitiesStripModel(status: LiveStatus, nowMs: number | null): EquitiesStripModel {
  const base = stripModel(status, nowMs);
  const model: EquitiesStripModel = { ...base, help: EQUITIES_STRIP_HELP, lastBar: null, notes: [] };
  const last = status.lastGood;
  if (!last) return model;

  const s = last.status as EquitiesStatus;
  const next = instant(s.next_tick_at);
  const ref = nowMs ?? last.serverMs;
  model.lastBar = s.last_bar_date ? `Latest daily bar ${s.last_bar_date}` : "No daily bars cached yet";
  if (base.off) {
    model.off =
      `Automatic market-close refresh is off (${equitiesOffReason(s.disabled_reason)}). ` +
      "This page still re-checks every minute.";
  }
  if (base.first) model.first = `Server has not finished its first refresh. Next expected refresh ${refreshTime(next)}`;
  if (base.next) model.next = `Next expected refresh ${refreshTime(next)}`;
  if ((s.last_tick_failed ?? 0) > 0) {
    model.notes.push(`${s.last_tick_failed} tickers did not refresh in that run`);
  }
  if (s.backoff_seconds > 0) {
    model.notes.push(`Refreshes are failing; retrying about ${stripTime(next, ref)}`);
  }
  return model;
}
