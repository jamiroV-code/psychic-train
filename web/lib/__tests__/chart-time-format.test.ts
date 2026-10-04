// Runs green in any zone; G-S2-4 runs it again under TZ=Pacific/Kiritimati
// (UTC+14), where every local date differs from the UTC one for ten hours a day.
import { describe, expect, it } from "vitest";
import { formatUtcDateTime, formatUtcTicks, utcAxis, utcTicks } from "@/lib/chart-time-format";

const d = (iso: string) => new Date(iso);
const iso = (dates: Date[]) => dates.map((x) => x.toISOString());

function axisLabels(start: string, end: string, tf: Parameters<typeof utcAxis>[2]) {
  return utcAxis(d(start), d(end), tf, 4).labels;
}

describe("chart-time-format: per-timeframe goldens", () => {
  it("15m: HH:mm with the day on the first tick", () => {
    expect(axisLabels("2026-10-03T13:00:00Z", "2026-10-03T14:00:00Z", "15m")).toEqual([
      "03 Oct",
      "13:15",
      "13:30",
      "13:45",
      "14:00",
    ]);
  });

  it("1h: the first tick of each UTC day reads DD MMM (day-boundary tick)", () => {
    const axis = utcAxis(d("2026-10-03T18:00:00Z"), d("2026-10-04T06:00:00Z"), "1h", 4);
    expect(iso(axis.ticks)).toEqual([
      "2026-10-03T18:00:00.000Z",
      "2026-10-03T21:00:00.000Z",
      "2026-10-04T00:00:00.000Z",
      "2026-10-04T03:00:00.000Z",
      "2026-10-04T06:00:00.000Z",
    ]);
    expect(axis.labels).toEqual(["03 Oct", "21:00", "04 Oct", "03:00", "06:00"]);
  });

  it("4h: HH:mm between UTC midnights", () => {
    expect(axisLabels("2026-10-01T00:00:00Z", "2026-10-03T00:00:00Z", "4h")).toEqual([
      "01 Oct",
      "12:00",
      "02 Oct",
      "12:00",
      "03 Oct",
    ]);
  });

  it("1d: DD MMM on Monday-aligned ticks", () => {
    const axis = utcAxis(d("2026-09-01T00:00:00Z"), d("2026-10-01T00:00:00Z"), "1d", 4);
    for (const tick of axis.ticks) {
      expect(tick.getUTCDay()).toBe(1);
      expect(tick.getUTCHours()).toBe(0);
    }
    expect(axis.labels.length).toBeGreaterThanOrEqual(2);
    for (const label of axis.labels) expect(label).toMatch(/^\d{2} [A-Z][a-z]{2}$/);
  });

  it("1w: DD MMM within a year", () => {
    const labels = axisLabels("2026-01-01T00:00:00Z", "2026-10-01T00:00:00Z", "1w");
    expect(labels).toEqual(["01 Jan", "01 Apr", "01 Jul", "01 Oct"]);
  });
});

describe("chart-time-format: year rule", () => {
  it("1d/1w switch to MMM YY only once the span exceeds 365 days", () => {
    const ticks = [d("2025-01-01T00:00:00Z"), d("2026-01-01T00:00:00Z")];
    const day = 86_400_000;
    expect(formatUtcTicks(ticks, "1w", 365 * day)).toEqual(["01 Jan", "01 Jan"]);
    expect(formatUtcTicks(ticks, "1w", 365 * day + 1)).toEqual(["Jan 25", "Jan 26"]);
    expect(axisLabels("2024-10-01T00:00:00Z", "2026-10-01T00:00:00Z", "1d")).toEqual(["Jan 25", "Jan 26"]);
  });

  it("intraday frames never use the year rule", () => {
    const ticks = [d("2025-01-01T00:00:00Z"), d("2025-01-01T12:00:00Z")];
    expect(formatUtcTicks(ticks, "4h", 400 * 86_400_000)).toEqual(["01 Jan", "12:00"]);
  });
});

describe("chart-time-format: zone independence", () => {
  it("labels a 23:30 UTC instant by its UTC day and time, whatever the local zone", () => {
    const late = d("2026-10-03T23:30:00Z");
    expect(formatUtcDateTime(late)).toBe("2026-10-03 23:30");
    expect(formatUtcTicks([d("2026-10-03T23:00:00Z"), late], "15m", 3_600_000)).toEqual(["03 Oct", "23:30"]);
  });

  it("utcAxis.format returns the tick's own label and formats off-tick values in UTC", () => {
    const axis = utcAxis(d("2026-10-03T18:00:00Z"), d("2026-10-04T06:00:00Z"), "1h", 4);
    expect(axis.format(d("2026-10-04T00:00:00Z"))).toBe("04 Oct");
    expect(axis.format(d("2026-10-04T03:00:00Z").getTime())).toBe("03:00");
    expect(axis.format(d("2026-10-04T05:30:00Z"))).toBe("04 Oct");
  });

  it("degenerate domains yield at most one tick", () => {
    expect(utcTicks(d("2026-10-03T00:00:00Z"), d("2026-10-03T00:00:00Z"))).toHaveLength(1);
    expect(utcTicks(d("invalid"), d("invalid"))).toHaveLength(0);
  });
});
