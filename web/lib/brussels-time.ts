/**
 * Display clock for the screener (T42 / S11a): every time the page shows is
 * Europe/Brussels wall time, labelled CET or CEST.
 *
 * This is the only module that names the zone. It reads the wall clock from
 * one module-level `Intl.DateTimeFormat` via `formatToParts`, never from the
 * browser's zone or locale (`getHours`, `toLocale*`), so the output is the
 * same on any machine. The offset is the wall clock minus the instant (60 or
 * 120 minutes); the abbreviation is derived from it, because en-US prints the
 * summer zone as `GMT+2` rather than `CEST`.
 */

export const DISPLAY_ZONE = "Europe/Brussels";

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const INVALID = "n/a";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const WALL_FORMAT = new Intl.DateTimeFormat("en-US", {
  timeZone: DISPLAY_ZONE,
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

interface Wall {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
  second: number;
}

function valid(date: Date): boolean {
  return date instanceof Date && Number.isFinite(date.getTime());
}

function wall(date: Date): Wall {
  const p: Record<string, number> = {};
  for (const part of WALL_FORMAT.formatToParts(date)) {
    if (part.type !== "literal") p[part.type] = Number(part.value);
  }
  return { year: p.year, month: p.month, day: p.day, hour: p.hour % 24, minute: p.minute, second: p.second };
}

function pad(n: number, width = 2): string {
  return String(n).padStart(width, "0");
}

/** Brussels wall clock minus the instant, in minutes (60 in winter, 120 in summer). NaN for an invalid date. */
export function offsetMinutes(date: Date): number {
  if (!valid(date)) return Number.NaN;
  const w = wall(date);
  const wallMs = Date.UTC(w.year, w.month - 1, w.day, w.hour, w.minute, w.second);
  const instantMs = Math.floor(date.getTime() / 1000) * 1000;
  return Math.round((wallMs - instantMs) / MINUTE);
}

/** `+02:00` */
export function offsetLabel(date: Date): string {
  const offset = offsetMinutes(date);
  if (!Number.isFinite(offset)) return INVALID;
  const abs = Math.abs(offset);
  return `${offset < 0 ? "-" : "+"}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

/** `CET` (offset 60), `CEST` (offset 120), anything else as `+HH:MM`. */
export function zoneAbbr(date: Date): string {
  const offset = offsetMinutes(date);
  if (offset === 60) return "CET";
  if (offset === 120) return "CEST";
  return offsetLabel(date);
}

/** `16:15` */
export function formatTime(date: Date): string {
  if (!valid(date)) return INVALID;
  const w = wall(date);
  return `${pad(w.hour)}:${pad(w.minute)}`;
}

/** `03 Oct` */
export function formatDay(date: Date): string {
  if (!valid(date)) return INVALID;
  const w = wall(date);
  return `${pad(w.day)} ${MONTHS[w.month - 1]}`;
}

/** `Oct 26` */
export function formatMonthYear(date: Date): string {
  if (!valid(date)) return INVALID;
  const w = wall(date);
  return `${MONTHS[w.month - 1]} ${pad(w.year % 100)}`;
}

/** `2026-10-03` */
export function formatDate(date: Date): string {
  if (!valid(date)) return INVALID;
  const w = wall(date);
  return `${pad(w.year, 4)}-${pad(w.month)}-${pad(w.day)}`;
}

/** `2026-10-03 16:15` */
export function formatDateTime(date: Date): string {
  if (!valid(date)) return INVALID;
  return `${formatDate(date)} ${formatTime(date)}`;
}

/** `2026-10-03 16:15 CEST` */
export function formatDateTimeZone(date: Date): string {
  if (!valid(date)) return INVALID;
  return `${formatDateTime(date)} ${zoneAbbr(date)}`;
}

/** `16:15 CEST` */
export function formatTimeZone(date: Date): string {
  if (!valid(date)) return INVALID;
  return `${formatTime(date)} ${zoneAbbr(date)}`;
}

/** The Brussels calendar date of an instant, as whole days since 1970-01-01. NaN for an invalid date. */
export function dayKey(date: Date): number {
  if (!valid(date)) return Number.NaN;
  const w = wall(date);
  return Math.round(Date.UTC(w.year, w.month - 1, w.day) / DAY);
}

/**
 * The instant of Brussels midnight starting `day` (a `dayKey`): that date's
 * midnight on the data's own clock minus the offset in force 3 h before it.
 * Both clock changes happen later in the night, so the offset 3 h earlier
 * is the one at midnight (29 Mar is 23 h long, 25 Oct 25 h).
 */
export function midnightOf(day: number): Date {
  const base = day * DAY;
  return new Date(base - offsetMinutes(new Date(base - 3 * HOUR)) * MINUTE);
}
