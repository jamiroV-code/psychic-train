import { dayKey, formatDay, formatMonthYear, formatTime, midnightOf, offsetMinutes } from "./brussels-time";
import type { Timeframe } from "./types/screener";

/**
 * Brussels time-axis ticks and labels for the screener charts (T34 / S2,
 * T42 / S11a).
 *
 * Pure: ticks sit on the Europe/Brussels wall clock and every label comes
 * from `brussels-time`, so the axis reads the same whatever zone the browser
 * is in. The simple-lines island takes the ticks and their labels from here
 * rather than letting the scale pick ticks in local time.
 *
 * - 15m / 1h / 4h: `HH:mm`, except the first tick of each Brussels day,
 *   which reads `DD MMM` so the day is never lost.
 * - 1d / 1w: `DD MMM`, or `MMM YY` once the span exceeds 365 days.
 *
 * Sub-day steps keep instants on the 15-minute grid whose Brussels minutes
 * since midnight are a multiple of the step. On 25 Oct the repeated hour gets
 * ticks only on its first pass (a candidate whose wall time is not later than
 * the previous tick's is skipped); the hour skipped on 29 Mar has none.
 * Day, week and month steps sit on Brussels midnights: weeks (7 and 14 days)
 * on Mondays counted from Monday 1970-01-05, and the 2-day step on Brussels
 * days with an even number since 1970-01-01.
 */

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const YEAR_SPAN_MS = 365 * DAY;
const GRID = 15 * MINUTE;
// 1970-01-05, the first Monday, is day 4.
const MONDAY_ANCHOR = 4;

const INTRADAY: ReadonlySet<Timeframe> = new Set<Timeframe>(["15m", "1h", "4h"]);

/** Labels for an ordered list of ticks spanning `spanMs`. */
export function formatBrusselsTicks(ticks: Date[], timeframe: Timeframe, spanMs: number): string[] {
  if (!INTRADAY.has(timeframe)) {
    const fmt = spanMs > YEAR_SPAN_MS ? formatMonthYear : formatDay;
    return ticks.map(fmt);
  }
  return ticks.map((tick, i) =>
    i === 0 || dayKey(ticks[i - 1]) !== dayKey(tick) ? formatDay(tick) : formatTime(tick),
  );
}

// Candidate fixed tick steps, smallest first. Calendar months and years are
// handled separately because their length varies.
const FIXED_STEPS = [15 * MINUTE, 30 * MINUTE, HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 2 * DAY, 7 * DAY, 14 * DAY];
const MONTH_STEPS = [1, 3, 6, 12, 24, 60];

/** Brussels wall clock of an instant, as milliseconds on a zone-free scale. */
function wallMs(t: number): number {
  return t + offsetMinutes(new Date(t)) * MINUTE;
}

function subDayTicks(lo: number, hi: number, step: number): Date[] {
  const out: Date[] = [];
  let previousWall = -Infinity;
  for (let t = Math.ceil(lo / GRID) * GRID; t <= hi; t += GRID) {
    const wall = wallMs(t);
    const sinceMidnight = ((wall % DAY) + DAY) % DAY;
    if (sinceMidnight % step !== 0 || wall <= previousWall) continue;
    out.push(new Date(t));
    previousWall = wall;
  }
  return out;
}

function dayTicks(lo: number, hi: number, days: number): Date[] {
  const anchor = days >= 7 ? MONDAY_ANCHOR : 0;
  let day = dayKey(new Date(lo));
  if (midnightOf(day).getTime() < lo) day += 1;
  day += (((anchor - day) % days) + days) % days;
  const out: Date[] = [];
  for (let t = midnightOf(day).getTime(); t <= hi; day += days, t = midnightOf(day).getTime()) out.push(new Date(t));
  return out;
}

function monthTicks(lo: number, hi: number, months: number): Date[] {
  const first = new Date(dayKey(new Date(lo)) * DAY);
  let index = first.getUTCFullYear() * 12 + first.getUTCMonth();
  if (midnightOf(Date.UTC(Math.floor(index / 12), index % 12, 1) / DAY).getTime() < lo) index += 1;
  index = Math.ceil(index / months) * months;
  const out: Date[] = [];
  for (;;) {
    const t = midnightOf(Date.UTC(Math.floor(index / 12), index % 12, 1) / DAY).getTime();
    if (t > hi) break;
    out.push(new Date(t));
    index += months;
  }
  return out;
}

/** About `count` ticks inside `[start, end]`, aligned to whole steps of the Brussels wall clock. */
export function brusselsTicks(start: Date, end: Date, count = 4): Date[] {
  const lo = start.getTime();
  const hi = end.getTime();
  if (!(hi > lo)) return Number.isFinite(lo) ? [new Date(lo)] : [];
  const target = (hi - lo) / Math.max(1, count);

  const fixed = FIXED_STEPS.find((step) => step >= target);
  if (fixed !== undefined) return fixed < DAY ? subDayTicks(lo, hi, fixed) : dayTicks(lo, hi, fixed / DAY);

  const months = MONTH_STEPS.find((m) => m * 30 * DAY >= target) ?? MONTH_STEPS[MONTH_STEPS.length - 1];
  return monthTicks(lo, hi, months);
}

/** Ticks plus a formatter keyed on them, ready for an axis. */
export function brusselsAxis(start: Date, end: Date, timeframe: Timeframe, count = 4) {
  const ticks = brusselsTicks(start, end, count);
  const labels = formatBrusselsTicks(ticks, timeframe, end.getTime() - start.getTime());
  const byTime = new Map(ticks.map((t, i) => [t.getTime(), labels[i]]));
  const format = (value: Date | number): string => {
    const date = value instanceof Date ? value : new Date(value);
    return byTime.get(date.getTime()) ?? formatBrusselsTicks([date], timeframe, end.getTime() - start.getTime())[0];
  };
  return { ticks, labels, format };
}
