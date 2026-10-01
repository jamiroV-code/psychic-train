import { describe, expect, it } from "vitest";
import { toSpreadSeries } from "@/lib/pairs-spread-series";
import type { SpreadPoint } from "@/lib/types/pairs";

const points: SpreadPoint[] = [
  { date: "2020-09-24", spread: -1.5, z_score: -0.8 },
  { date: "2020-09-25", spread: 0, z_score: 0 },
  { date: "2020-09-26", spread: 2.25, z_score: 1.1 },
  { date: "2020-09-27", spread: -0.125, z_score: -0.05 },
];

describe("toSpreadSeries", () => {
  it("plots every spread value unchanged, in order (AC-7)", () => {
    expect(toSpreadSeries(points).map((p) => p.value)).toEqual([-1.5, 0, 2.25, -0.125]);
  });

  it("keeps the first and last points at the sample window edges", () => {
    const series = toSpreadSeries(points);
    expect(series[0].date.toISOString().slice(0, 10)).toBe("2020-09-24");
    expect(series[series.length - 1].date.toISOString().slice(0, 10)).toBe("2020-09-27");
    expect(series).toHaveLength(points.length);
  });

  it("reads dates as UTC, so a point never shifts a day by timezone", () => {
    expect(toSpreadSeries([points[0]])[0].date.toISOString()).toBe("2020-09-24T00:00:00.000Z");
  });

  it("does not drop, fill or reorder a zero or a negative spread", () => {
    // A spread oscillates around zero; treating 0 as missing, or sorting by
    // value, would silently rewrite the series. Guarding both.
    const series = toSpreadSeries(points);
    expect(series.map((p) => p.value)).toEqual(points.map((p) => p.spread));
    expect(series.some((p) => p.value === 0)).toBe(true);
  });

  it("returns an empty series for an empty spread, never a placeholder point", () => {
    expect(toSpreadSeries([])).toEqual([]);
  });
});
