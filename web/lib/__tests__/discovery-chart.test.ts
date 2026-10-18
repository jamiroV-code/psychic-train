import { describe, expect, it } from "vitest";
import {
  bandPoints,
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
