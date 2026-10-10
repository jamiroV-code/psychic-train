import { describe, expect, it } from "vitest";
import { brusselsAxis, brusselsTicks, formatBrusselsTicks } from "@/lib/chart-time-format";

// Goldens come from the EU rule (summer time from the last Sunday of March
// 01:00Z to the last Sunday of October 01:00Z), never from the module.
const DAY = 86_400_000;
const at = (iso: string) => new Date(iso);
const isos = (ticks: Date[]) => ticks.map((t) => t.toISOString().replace(".000Z", "Z"));

describe("chart-time-format", () => {
  it("15m ticks put the Brussels midnight on the day label", () => {
    const axis = brusselsAxis(at("2026-10-03T21:00:00Z"), at("2026-10-03T23:30:00Z"), "15m");
    expect(isos(axis.ticks)).toEqual(["2026-10-03T21:00:00Z", "2026-10-03T22:00:00Z", "2026-10-03T23:00:00Z"]);
    expect(axis.labels).toEqual(["03 Oct", "04 Oct", "01:00"]);
  });

  it("4h frame steps 6 h on the Brussels clock", () => {
    const axis = brusselsAxis(at("2026-10-03T00:00:00Z"), at("2026-10-04T00:00:00Z"), "4h");
    expect(isos(axis.ticks)).toEqual(["2026-10-03T04:00:00Z", "2026-10-03T10:00:00Z", "2026-10-03T16:00:00Z", "2026-10-03T22:00:00Z"]);
    expect(axis.labels).toEqual(["03 Oct", "12:00", "18:00", "04 Oct"]);
  });

  it("1d ticks sit on Brussels midnights across 25 Oct", () => {
    const axis = brusselsAxis(at("2026-10-23T22:00:00Z"), at("2026-10-27T00:00:00Z"), "1d");
    expect(isos(axis.ticks)).toEqual(["2026-10-23T22:00:00Z", "2026-10-24T22:00:00Z", "2026-10-25T23:00:00Z", "2026-10-26T23:00:00Z"]);
    const gaps = axis.ticks.slice(1).map((t, i) => (t.getTime() - axis.ticks[i].getTime()) / 3_600_000);
    expect(gaps).toEqual([24, 25, 24]);
    expect(axis.labels).toEqual(["24 Oct", "25 Oct", "26 Oct", "27 Oct"]);
  });

  it("1w ticks sit on Brussels Mondays", () => {
    // 28 days / 4 = a 7-day step; Mondays 05, 12, 19 and 26 Oct 2026 (CET from 25 Oct).
    const axis = brusselsAxis(at("2026-10-01T00:00:00Z"), at("2026-10-29T00:00:00Z"), "1w");
    expect(isos(axis.ticks)).toEqual(["2026-10-04T22:00:00Z", "2026-10-11T22:00:00Z", "2026-10-18T22:00:00Z", "2026-10-25T23:00:00Z"]);
    expect(axis.labels).toEqual(["05 Oct", "12 Oct", "19 Oct", "26 Oct"]);
  });

  it("year rule beyond 365 days and the month step", () => {
    const years = brusselsAxis(at("2024-10-01T00:00:00Z"), at("2026-10-01T00:00:00Z"), "1d");
    expect(isos(years.ticks)).toEqual(["2024-12-31T23:00:00Z", "2025-12-31T23:00:00Z"]);
    expect(years.labels).toEqual(["Jan 25", "Jan 26"]);

    const months = brusselsAxis(at("2026-01-01T00:00:00Z"), at("2026-10-01T00:00:00Z"), "1w");
    expect(isos(months.ticks)).toEqual(["2026-03-31T22:00:00Z", "2026-06-30T22:00:00Z", "2026-09-30T22:00:00Z"]);
    expect(months.labels).toEqual(["01 Apr", "01 Jul", "01 Oct"]);
  });

  it("intraday never uses the year rule", () => {
    const ticks = [at("2026-10-03T21:00:00Z"), at("2026-10-03T22:00:00Z"), at("2026-10-03T23:00:00Z")];
    expect(formatBrusselsTicks(ticks, "1h", 400 * DAY)).toEqual(["03 Oct", "04 Oct", "01:00"]);
    expect(formatBrusselsTicks(ticks, "1d", 400 * DAY)).toEqual(["Oct 26", "Oct 26", "Oct 26"]);
  });

  it("spring change with a 3 h step", () => {
    const axis = brusselsAxis(at("2026-03-28T22:00:00Z"), at("2026-03-29T04:00:00Z"), "1h");
    expect(isos(axis.ticks)).toEqual(["2026-03-28T23:00:00Z", "2026-03-29T01:00:00Z", "2026-03-29T04:00:00Z"]);
    expect(axis.labels).toEqual(["29 Mar", "03:00", "06:00"]);
  });

  it("spring change with a 1 h step has no 02:00", () => {
    const axis = brusselsAxis(at("2026-03-29T00:00:00Z"), at("2026-03-29T03:00:00Z"), "15m");
    expect(axis.labels).toEqual(["29 Mar", "03:00", "04:00", "05:00"]);
    expect(axis.labels).not.toContain("02:00");
  });

  it("autumn change keeps 02:00 once", () => {
    const hourly = brusselsAxis(at("2026-10-24T23:00:00Z"), at("2026-10-25T03:00:00Z"), "1h");
    expect(isos(hourly.ticks)).toEqual(["2026-10-24T23:00:00Z", "2026-10-25T00:00:00Z", "2026-10-25T02:00:00Z", "2026-10-25T03:00:00Z"]);
    expect(hourly.labels).toEqual(["25 Oct", "02:00", "03:00", "04:00"]);

    const quarter = brusselsAxis(at("2026-10-25T00:30:00Z"), at("2026-10-25T01:30:00Z"), "15m");
    expect(isos(quarter.ticks)).toEqual(["2026-10-25T00:30:00Z", "2026-10-25T00:45:00Z"]);
    expect(quarter.labels).toEqual(["25 Oct", "02:45"]);
  });

  it("a 23:30 instant belongs to the next Brussels day", () => {
    expect(formatBrusselsTicks([at("2026-01-15T23:30:00Z")], "1d", DAY)).toEqual(["16 Jan"]);
    expect(formatBrusselsTicks([at("2026-07-15T23:30:00Z")], "1d", DAY)).toEqual(["16 Jul"]);
    expect(formatBrusselsTicks([at("2026-01-15T22:00:00Z"), at("2026-01-15T23:30:00Z")], "1h", DAY)).toEqual(["15 Jan", "16 Jan"]);
  });

  it("brusselsAxis.format returns tick labels and formats other values", () => {
    const axis = brusselsAxis(at("2026-10-03T21:00:00Z"), at("2026-10-03T23:30:00Z"), "15m");
    expect(axis.format(at("2026-10-03T23:00:00Z"))).toBe("01:00");
    expect(axis.format(at("2026-10-03T23:00:00Z").getTime())).toBe("01:00");
    // Off-tick: a single label, which is the Brussels day for an intraday frame.
    expect(axis.format(at("2026-10-03T22:40:00Z"))).toBe("04 Oct");
    const daily = brusselsAxis(at("2026-10-23T22:00:00Z"), at("2026-10-27T00:00:00Z"), "1d");
    expect(daily.format(at("2026-10-26T12:00:00Z"))).toBe("26 Oct");
  });

  it("degenerate or invalid domains give at most one tick", () => {
    expect(isos(brusselsTicks(at("2026-10-03T12:00:00Z"), at("2026-10-03T12:00:00Z")))).toEqual(["2026-10-03T12:00:00Z"]);
    expect(brusselsTicks(at("2026-10-04T00:00:00Z"), at("2026-10-03T00:00:00Z")).length).toBeLessThanOrEqual(1);
    expect(brusselsTicks(new Date("bad"), new Date("bad"))).toEqual([]);
    expect(brusselsAxis(new Date("bad"), at("2026-10-03T00:00:00Z"), "1d").ticks).toEqual([]);
  });
});
