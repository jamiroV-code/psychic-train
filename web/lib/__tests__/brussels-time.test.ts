import { describe, expect, it } from "vitest";
import {
  dayKey,
  formatDateTime,
  formatDateTimeZone,
  formatDay,
  formatTime,
  formatTimeZone,
  midnightOf,
  offsetLabel,
  offsetMinutes,
  zoneAbbr,
} from "@/lib/brussels-time";

// Goldens come from the EU rule (summer time from the last Sunday of March
// 01:00Z to the last Sunday of October 01:00Z), never from this module.
const DAY = 86_400_000;
const at = (iso: string) => new Date(iso);
const key = (y: number, m: number, d: number) => Date.UTC(y, m - 1, d) / DAY;

describe("brussels-time", () => {
  it("winter and summer offset, abbreviation and offset label", () => {
    const winter = at("2026-01-15T12:00:00Z");
    const summer = at("2026-07-15T12:00:00Z");
    expect([offsetMinutes(winter), zoneAbbr(winter), offsetLabel(winter)]).toEqual([60, "CET", "+01:00"]);
    expect([offsetMinutes(summer), zoneAbbr(summer), offsetLabel(summer)]).toEqual([120, "CEST", "+02:00"]);
  });

  it("spring change on 29 Mar skips 02:00", () => {
    expect(formatTimeZone(at("2026-03-29T00:59:59Z"))).toBe("01:59 CET");
    expect(formatTimeZone(at("2026-03-29T01:00:00Z"))).toBe("03:00 CEST");
  });

  it("autumn change on 25 Oct repeats 02:00", () => {
    expect(formatTimeZone(at("2026-10-25T00:59:59Z"))).toBe("02:59 CEST");
    expect(formatTimeZone(at("2026-10-25T01:00:00Z"))).toBe("02:00 CET");
  });

  it("day boundary follows the Brussels day, never 24:00", () => {
    const late = at("2026-10-03T22:30:00Z");
    expect(`${formatDay(late)} ${formatTime(late)}`).toBe("04 Oct 00:30");
    expect(dayKey(late)).toBe(key(2026, 10, 4));
    expect(dayKey(late)).not.toBe(Math.floor(late.getTime() / DAY));
    expect(formatTime(at("2026-10-03T22:00:00Z"))).toBe("00:00");
  });

  it("midnightOf around both changes, 23 h and 25 h days", () => {
    const iso = (y: number, m: number, d: number) => midnightOf(key(y, m, d)).toISOString();
    expect([iso(2026, 3, 28), iso(2026, 3, 29), iso(2026, 3, 30)]).toEqual([
      "2026-03-27T23:00:00.000Z",
      "2026-03-28T23:00:00.000Z",
      "2026-03-29T22:00:00.000Z",
    ]);
    expect([iso(2026, 10, 24), iso(2026, 10, 25), iso(2026, 10, 26)]).toEqual([
      "2026-10-23T22:00:00.000Z",
      "2026-10-24T22:00:00.000Z",
      "2026-10-25T23:00:00.000Z",
    ]);
    const hours = (y: number, m: number, d: number) =>
      (midnightOf(key(y, m, d) + 1).getTime() - midnightOf(key(y, m, d)).getTime()) / 3_600_000;
    expect(hours(2026, 3, 29)).toBe(23);
    expect(hours(2026, 10, 25)).toBe(25);
  });

  it("output does not depend on the process zone", () => {
    const original = process.env.TZ;
    const sample = () =>
      [at("2026-10-03T22:30:00Z"), at("2026-03-29T01:00:00Z"), at("2026-01-15T12:00:00Z")].map(formatDateTimeZone);
    try {
      const outputs = ["UTC", "America/Los_Angeles", "Asia/Tokyo"].map((tz) => {
        process.env.TZ = tz;
        return sample();
      });
      for (const out of outputs) {
        expect(out).toEqual(["2026-10-04 00:30 CEST", "2026-03-29 03:00 CEST", "2026-01-15 13:00 CET"]);
      }
    } finally {
      if (original === undefined) delete process.env.TZ;
      else process.env.TZ = original;
    }
  });

  it("an invalid date gives n/a, never a throw", () => {
    const bad = new Date("not a date");
    expect([formatDateTimeZone(bad), formatTimeZone(bad), formatDateTime(bad), formatDay(bad), zoneAbbr(bad)]).toEqual([
      "n/a",
      "n/a",
      "n/a",
      "n/a",
      "n/a",
    ]);
  });

  it("formatDateTimeZone and formatTimeZone goldens", () => {
    expect(formatDateTimeZone(at("2026-10-03T14:15:00Z"))).toBe("2026-10-03 16:15 CEST");
    expect(formatDateTimeZone(at("2026-01-15T12:00:00Z"))).toBe("2026-01-15 13:00 CET");
    expect(formatTimeZone(at("2026-10-03T14:15:00Z"))).toBe("16:15 CEST");
    expect(formatTimeZone(at("2026-12-31T23:45:00Z"))).toBe("00:45 CET");
  });
});
