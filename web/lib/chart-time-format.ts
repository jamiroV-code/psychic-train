import type { Timeframe } from "@/lib/types/screener";

/**
 * UTC time-axis ticks and labels for the screener charts (T34 / S2).
 *
 * Pure: every label is formatted with `timeZone: "UTC"`, so the axis reads the
 * same whatever zone the browser is in. The simple-lines island takes the
 * ticks and their labels from here rather than letting the scale pick ticks
 * in local time.
 *
 * - 15m / 1h / 4h: `HH:mm`, except the first tick of each UTC day, which
 *   reads `DD MMM` so the day is never lost.
 * - 1d / 1w: `DD MMM`, or `MMM YY` once the span exceeds 365 days.
 */

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const YEAR_SPAN_MS = 365 * DAY;

const INTRADAY: ReadonlySet<Timeframe> = new Set<Timeframe>(["15m", "1h", "4h"]);

function parts(date: Date, options: Intl.DateTimeFormatOptions): Record<string, string> {
  const out: Record<string, string> = {};
  for (const p of new Intl.DateTimeFormat("en-US", { timeZone: "UTC", ...options }).formatToParts(date)) {
    out[p.type] = p.value;
  }
  return out;
}

/** `14:15` */
export function formatUtcTime(date: Date): string {
  const p = parts(date, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  return `${p.hour}:${p.minute}`;
}

/** `03 Oct` */
export function formatUtcDay(date: Date): string {
  const p = parts(date, { day: "2-digit", month: "short" });
  return `${p.day} ${p.month}`;
}

/** `Oct 26` */
export function formatUtcMonthYear(date: Date): string {
  const p = parts(date, { month: "short", year: "2-digit" });
  return `${p.month} ${p.year}`;
}

/** `2026-10-03 14:15` (UTC; the caller appends the zone). */
export function formatUtcDateTime(date: Date): string {
  const p = parts(date, { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;
}

function utcDayKey(date: Date): number {
  return Math.floor(date.getTime() / DAY);
}

/** Labels for an ordered list of ticks spanning `spanMs`. */
export function formatUtcTicks(ticks: Date[], timeframe: Timeframe, spanMs: number): string[] {
  if (!INTRADAY.has(timeframe)) {
    const fmt = spanMs > YEAR_SPAN_MS ? formatUtcMonthYear : formatUtcDay;
    return ticks.map(fmt);
  }
  return ticks.map((tick, i) =>
    i === 0 || utcDayKey(ticks[i - 1]) !== utcDayKey(tick) ? formatUtcDay(tick) : formatUtcTime(tick),
  );
}

// Candidate fixed tick steps, smallest first. Calendar months and years are
// handled separately because their length varies.
const FIXED_STEPS = [15 * MINUTE, 30 * MINUTE, HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 2 * DAY, 7 * DAY, 14 * DAY];
const MONTH_STEPS = [1, 3, 6, 12, 24, 60];

/**
 * About `count` UTC-aligned ticks inside `[start, end]`: multiples of a whole
 * UTC step (days start at 00:00 UTC, weeks on Mondays, months on the 1st).
 */
export function utcTicks(start: Date, end: Date, count = 4): Date[] {
  const lo = start.getTime();
  const hi = end.getTime();
  if (!(hi > lo)) return Number.isFinite(lo) ? [new Date(lo)] : [];
  const target = (hi - lo) / Math.max(1, count);

  const fixed = FIXED_STEPS.find((step) => step >= target);
  if (fixed !== undefined) {
    // 1970-01-05 was a Monday: weekly steps line up with Monday 00:00 UTC.
    const anchor = fixed >= 7 * DAY ? 4 * DAY : 0;
    const first = Math.ceil((lo - anchor) / fixed) * fixed + anchor;
    const out: Date[] = [];
    for (let t = first; t <= hi; t += fixed) out.push(new Date(t));
    return out;
  }

  const months = MONTH_STEPS.find((m) => m * 30 * DAY >= target) ?? MONTH_STEPS[MONTH_STEPS.length - 1];
  const s = new Date(lo);
  let index = s.getUTCFullYear() * 12 + s.getUTCMonth();
  if (Date.UTC(s.getUTCFullYear(), s.getUTCMonth(), 1) < lo) index += 1;
  index = Math.ceil(index / months) * months;
  const out: Date[] = [];
  for (;;) {
    const t = Date.UTC(Math.floor(index / 12), index % 12, 1);
    if (t > hi) break;
    out.push(new Date(t));
    index += months;
  }
  return out;
}

/** Ticks plus a formatter keyed on them, ready for an axis. */
export function utcAxis(start: Date, end: Date, timeframe: Timeframe, count = 4) {
  const ticks = utcTicks(start, end, count);
  const labels = formatUtcTicks(ticks, timeframe, end.getTime() - start.getTime());
  const byTime = new Map(ticks.map((t, i) => [t.getTime(), labels[i]]));
  const format = (value: Date | number): string => {
    const date = value instanceof Date ? value : new Date(value);
    return byTime.get(date.getTime()) ?? formatUtcTicks([date], timeframe, end.getTime() - start.getTime())[0];
  };
  return { ticks, labels, format };
}
