import { describe, expect, it } from "vitest";
import {
  axisTicks,
  bandPoints,
  coverageBars,
  dayIndexAt,
  fitScale,
  isConstant,
  xTickIndices,
  linePath,
  shapeCategoryChart,
  shapeCoinChart,
  thinDayCount,
} from "@/lib/discovery-chart";
import type { DiscoveryCategoryHistory, DiscoveryCoinHistory, DiscoveryPrice } from "@/lib/types/discovery";

const day = (date: string, over = {}) => ({
  date,
  score: 10,
  covered_weight: 35,
  rising_weight: 25,
  trigger: false,
  thin: false,
  ...over,
});

const coin = (days: DiscoveryCoinHistory["days"], over: Partial<DiscoveryCoinHistory> = {}): DiscoveryCoinHistory => ({
  kind: "coin",
  id: "AAA",
  window: 7,
  as_of: days.at(-1)?.date ?? "2026-10-15",
  status: "ok",
  reason: "",
  min_history_days: 30,
  min_covered_weight: 30,
  history_days: {},
  days,
  ...over,
});

const price = (rows: [string, number][], over: Partial<DiscoveryPrice> = {}): DiscoveryPrice => ({
  symbol: "AAA",
  window: 7,
  status: rows.length ? "ok" : "no-data",
  last_date: rows.at(-1)?.[0] ?? null,
  days: rows.map(([date, close]) => ({ date, close })),
  ...over,
});

describe("shapeCoinChart", () => {
  it("marks trigger days from the stored flag, never recomputing", () => {
    // 90 rising of 100 would trigger by the 60% rule; the stored flag says no, so no marker.
    const h = coin([
      day("2026-10-13", { trigger: true }),
      day("2026-10-14", { rising_weight: 35, covered_weight: 35, trigger: false }),
      day("2026-10-15", { trigger: true }),
    ]);
    const s = shapeCoinChart(h, null);
    expect(s.rows.map((r) => r.trigger)).toEqual([true, false, true]);
    expect(s.rows.filter((r) => r.trigger).map((r) => r.date)).toEqual(["2026-10-13", "2026-10-15"]);
  });

  it("indexes price to 0% change at the first common day and leaves gaps as null", () => {
    const h = coin([day("2026-10-13"), day("2026-10-14"), day("2026-10-15"), day("2026-10-16")]);
    // no price on 10-13; 10-14 is the first common day; 10-15 missing; an extra price day without a score row is ignored
    const p = price([["2026-10-14", 200], ["2026-10-16", 250], ["2026-10-17", 999]]);
    const s = shapeCoinChart(h, p);
    expect(s.priceAvailable).toBe(true);
    expect(s.priceBase).toEqual({ date: "2026-10-14", close: 200 });
    expect(s.rows.map((r) => r.price)).toEqual([null, 200, null, 250]);
    expect(s.rows.map((r) => r.priceChange)).toEqual([null, 0, null, 25]);
  });

  it("reports price unavailable for null, no-data and fully non-overlapping price", () => {
    const h = coin([day("2026-10-14")]);
    expect(shapeCoinChart(h, null).priceAvailable).toBe(false);
    expect(shapeCoinChart(h, price([])).priceAvailable).toBe(false);
    const far = shapeCoinChart(h, price([["2026-01-01", 5]]));
    expect(far.priceAvailable).toBe(false);
    expect(far.rows[0].priceChange).toBeNull();
  });

  it("drops non-finite prices and a zero base instead of dividing", () => {
    const h = coin([day("2026-10-13"), day("2026-10-14")]);
    const s = shapeCoinChart(h, price([["2026-10-13", 0], ["2026-10-14", Number.NaN]]));
    expect(s.priceAvailable).toBe(false);
    expect(s.rows.every((r) => r.priceChange === null && r.price === null)).toBe(true);
  });

  it("drops days whose score is not finite", () => {
    const h = coin([day("2026-10-13", { score: Number.NaN }), day("2026-10-14")]);
    expect(shapeCoinChart(h, null).rows.map((r) => r.date)).toEqual(["2026-10-14"]);
  });

  it("is empty for a no-data history", () => {
    const s = shapeCoinChart(coin([], { status: "no-data", reason: "no-attention-data" }), null);
    expect(s.rows).toEqual([]);
  });
});

describe("band and thin days", () => {
  it("band values are covered_weight on a 0-100 scale, clamped, with the floor", () => {
    const h = coin([day("2026-10-13", { covered_weight: 10, thin: true }), day("2026-10-14", { covered_weight: 35 })]);
    const s = shapeCoinChart(h, null);
    expect(bandPoints(s.rows)).toEqual([10, 35]);
    expect(s.floor).toBe(30);
    expect(thinDayCount(s.rows)).toBe(1);
  });

  it("clamps out-of-range weights into 0..100", () => {
    const h = coin([day("2026-10-13", { covered_weight: 140 }), day("2026-10-14", { covered_weight: -3 })]);
    expect(bandPoints(shapeCoinChart(h, null).rows)).toEqual([100, 0]);
  });
});

describe("shapeCategoryChart", () => {
  const cat = (days: DiscoveryCategoryHistory["days"]): DiscoveryCategoryHistory => ({
    kind: "category",
    id: "ai",
    window: 7,
    as_of: "2026-10-15",
    status: "ok",
    reason: "",
    min_history_days: 30,
    min_covered_weight: 30,
    history_days: {},
    days,
  });

  it("keeps score, share as a 0-100 percent and coins_used", () => {
    const s = shapeCategoryChart(
      cat([
        { date: "2026-10-14", score: 4, coins_used: 4, triggered_count: 1, triggered_share: 0.25 },
        { date: "2026-10-15", score: 6, coins_used: 5, triggered_count: 5, triggered_share: 1 },
      ]),
    );
    expect(s.rows.map((r) => r.sharePct)).toEqual([25, 100]);
    expect(s.rows.map((r) => r.coinsUsed)).toEqual([4, 5]);
  });
});

describe("linePath", () => {
  it("breaks the path at nulls so missing is never drawn as zero", () => {
    expect(linePath([1, null, 3, 4], (i) => i * 10, (v) => 100 - v)).toBe("M0 99M20 97L30 96");
  });
  it("is empty when nothing is finite", () => {
    expect(linePath([null, Number.NaN], (i) => i, (v) => v)).toBe("");
  });
});

describe("fitScale (T107 per-panel scale)", () => {
  it("fits each series to its own range with padding, so a -3%..0% price is not flattened by a +49% score", () => {
    const price = fitScale([-3, -1, 0], { includeZero: true });
    const score = fitScale([5, 49], { includeZero: true });
    expect([price.min, price.max]).toEqual([-3, 0]);
    expect(price.lo).toBeLessThan(-3);
    expect(price.hi).toBeGreaterThan(0);
    expect(price.hi - price.lo).toBeLessThan(4);
    expect(score.hi).toBeGreaterThan(49);
    expect(score.lo).toBeLessThan(0);
  });

  it("includes zero only when asked", () => {
    const a = fitScale([40, 50], { includeZero: false });
    expect(a.lo).toBeGreaterThan(30);
    const b = fitScale([40, 50], { includeZero: true });
    expect(b.lo).toBeLessThan(0);
  });

  it("handles negative-only series (zero line stays on the panel)", () => {
    const s = fitScale([-8, -2], { includeZero: true });
    expect(s.max).toBe(0);
    expect(s.min).toBe(-8);
    expect(s.hi).toBeGreaterThan(0);
  });

  it("never returns a zero-width domain for constant, one-point or empty input", () => {
    for (const vs of [[5, 5, 5], [7], [], [0], [null, Number.NaN]]) {
      const s = fitScale(vs, { includeZero: false });
      expect(s.hi - s.lo).toBeGreaterThan(0);
      const z = fitScale(vs, { includeZero: true });
      expect(z.hi - z.lo).toBeGreaterThan(0);
    }
  });

  it("skips null and NaN days", () => {
    const s = fitScale([null, 2, Number.NaN, 4, undefined], { includeZero: false });
    expect([s.min, s.max]).toEqual([2, 4]);
  });

  it("clamps to the given bounds (share panel stays inside 0..100)", () => {
    const s = fitScale([1, 99], { includeZero: false, clamp: [0, 100] });
    expect(s.lo).toBe(0);
    expect(s.hi).toBe(100);
  });
});

describe("axisTicks (at most 3 labels, never overlapping)", () => {
  it("gives min, zero and max for a signed series", () => {
    const s = fitScale([-10, 30], { includeZero: true });
    const t = axisTicks(s, { height: 120, includeZero: true });
    expect(t.map((x) => x.value)).toEqual([-10, 0, 30]);
    expect(t.map((x) => x.label)).toEqual(["-10%", "0%", "+30%"]);
  });

  it("merges zero with the max when they coincide, and never repeats a label", () => {
    const s = fitScale([-3, 0], { includeZero: true });
    const t = axisTicks(s, { height: 90, includeZero: true });
    expect(t.map((x) => x.label)).toEqual(["-3.0%", "-1.5%", "0%"]);
    expect(new Set(t.map((x) => x.label)).size).toBe(t.length);
  });

  it("is never more than 3 and keeps a minimum pixel gap", () => {
    const s = fitScale([-0.4, 0.5], { includeZero: true });
    const t = axisTicks(s, { height: 40, includeZero: true, minGap: 14 });
    expect(t.length).toBeLessThanOrEqual(3);
    const ys = t.map((x) => x.y).sort((a, b) => a - b);
    for (let i = 1; i < ys.length; i += 1) expect(ys[i] - ys[i - 1]).toBeGreaterThanOrEqual(14);
  });

  it("uses finer decimals on tiny ranges and never prints -0", () => {
    const s = fitScale([-0.12, 0.3], { includeZero: true });
    const t = axisTicks(s, { height: 120, includeZero: true });
    expect(t.map((x) => x.label)).toEqual(["-0.12%", "0%", "+0.30%"]);
  });

  it("a constant series gets a single tick", () => {
    const t = axisTicks(fitScale([5, 5], { includeZero: false }), { height: 90, includeZero: false });
    expect(t).toHaveLength(1);
    expect(t[0].label).toBe("+5.0%");
  });

  it("uses a mid tick when zero is not on the panel", () => {
    const t = axisTicks(fitScale([20, 40], { includeZero: false }), { height: 120, includeZero: false });
    expect(t.map((x) => x.value)).toEqual([20, 30, 40]);
  });
});

describe("xTickIndices", () => {
  it.each([
    [0, []],
    [1, [0]],
    [2, [0, 1]],
    [3, [0, 1, 2]],
    [30, [0, 14, 29]],
  ])("n=%i", (n, want) => {
    expect(xTickIndices(n)).toEqual(want);
  });
});

describe("coverageBars", () => {
  it("clamps to 0..100 and mutes days under the floor", () => {
    const rows = shapeCoinChart(
      coin([day("2026-10-11", { covered_weight: 10 }), day("2026-10-12", { covered_weight: 30 }), day("2026-10-13", { covered_weight: 140 })]),
      null,
    ).rows;
    expect(coverageBars(rows, 30)).toEqual([
      { value: 10, muted: true },
      { value: 30, muted: false },
      { value: 100, muted: false },
    ]);
  });

  it("flags a constant series", () => {
    expect(isConstant([35, 35, 35])).toBe(true);
    expect(isConstant([35, 36])).toBe(false);
    expect(isConstant([])).toBe(true);
  });
});

describe("dayIndexAt", () => {
  it("maps a pointer x to the nearest day and clamps", () => {
    expect(dayIndexAt(44, 44, 200, 5)).toBe(0);
    expect(dayIndexAt(244, 44, 200, 5)).toBe(4);
    expect(dayIndexAt(144, 44, 200, 5)).toBe(2);
    expect(dayIndexAt(-50, 44, 200, 5)).toBe(0);
    expect(dayIndexAt(900, 44, 200, 5)).toBe(4);
    expect(dayIndexAt(100, 44, 200, 1)).toBe(0);
  });
});
