import { describe, expect, it } from "vitest";
import {
  NOT_MEAN_REVERTING_TEXT,
  formatDirection,
  formatHalfLife,
  formatJohansen,
  formatNumber,
  formatPValue,
  formatSampleWindow,
  formatZScore,
  isRawOnlySignificant,
  significanceSummary,
  sortPairs,
} from "@/lib/format-pairs-value";
import { okPair, tablePairs } from "@/components/pairs/__tests__/fixtures";

describe("formatPValue", () => {
  it("uses 3 decimals at and above 0.01", () => {
    expect(formatPValue(0.087)).toBe("0.087");
    expect(formatPValue(0.723)).toBe("0.723");
    expect(formatPValue(0.01)).toBe("0.010");
    expect(formatPValue(1)).toBe("1.000");
  });
  it("uses 2 significant figures between 0.0001 and 0.01", () => {
    expect(formatPValue(0.00057)).toBe("0.00057");
    expect(formatPValue(0.0017)).toBe("0.0017");
    expect(formatPValue(0.0099)).toBe("0.0099");
    expect(formatPValue(0.0001)).toBe("0.00010");
  });
  it("floors below 0.0001", () => {
    expect(formatPValue(0.00009)).toBe("< 0.0001");
    expect(formatPValue(0)).toBe("< 0.0001");
  });
  it("never shows NaN, Infinity or a zero stand-in", () => {
    for (const v of [null, undefined, NaN, Infinity, -Infinity]) expect(formatPValue(v)).toBe("—");
  });
});

describe("formatHalfLife", () => {
  it("whole days at 10 and above, one decimal below", () => {
    expect(formatHalfLife({ state: "computed", days: 114 })).toBe("114 d");
    expect(formatHalfLife({ state: "computed", days: 10 })).toBe("10 d");
    expect(formatHalfLife({ state: "computed", days: 7.44 })).toBe("7.4 d");
  });
  it("states not-mean-reverting explicitly", () => {
    expect(formatHalfLife({ state: "not_mean_reverting", days: null })).toBe(NOT_MEAN_REVERTING_TEXT);
  });
  it("missing or non-finite → dash", () => {
    expect(formatHalfLife(null)).toBe("—");
    expect(formatHalfLife({ state: "computed", days: NaN })).toBe("—");
  });
});

describe("formatZScore / formatNumber", () => {
  it("signs with U+2212 minus and a plus", () => {
    expect(formatZScore(-0.12)).toBe("−0.12");
    expect(formatZScore(0.44)).toBe("+0.44");
    expect(formatZScore(0)).toBe("0.00");
    expect(formatZScore(NaN)).toBe("—");
  });
  it("formatNumber uses U+2212 for negatives", () => {
    expect(formatNumber(-4.614, 2)).toBe("−4.61");
    expect(formatNumber(0.8123, 3)).toBe("0.812");
    expect(formatNumber(null, 2)).toBe("—");
  });
});

describe("other formatters", () => {
  it("Johansen shows trace vs critical value and the API's yes/no", () => {
    expect(formatJohansen({ trace_stat: 18.31, crit_value_95: 15.49, rank_at_least_1: true })).toBe("18.31 vs 15.49 — Yes");
    expect(formatJohansen({ trace_stat: 12.5, crit_value_95: 15.49, rank_at_least_1: false })).toBe("12.50 vs 15.49 — No");
    expect(formatJohansen(null)).toBe("—");
  });
  it("direction and sample window", () => {
    expect(formatDirection("ETH~BTC")).toBe("ETH on BTC");
    expect(formatDirection(null)).toBe("—");
    expect(formatSampleWindow("2021-01-01", "2026-09-24", 1820)).toBe("2021-01-01 → 2026-09-24 (1,820 days)");
    expect(formatSampleWindow(null, null, null)).toBe("—");
  });
});

describe("sortPairs (AC-4)", () => {
  it("orders ok rows by corrected p ascending, then non-ok rows as a separate group", () => {
    const order = sortPairs(tablePairs()).map((p) => `${p.coin_a}/${p.coin_b}`);
    expect(order).toEqual(["DOGE/BCH", "ETH/BCH", "BCH/DOGE", "ETH/DOGE", "BCH/NEW", "DOGE/DEAD"]);
  });
  it("is independent of input order", () => {
    const pairs = tablePairs();
    const expected = sortPairs(pairs);
    expect(sortPairs([...pairs].reverse())).toEqual(expected);
  });
  it("breaks corrected-p ties on raw p, then on coin names", () => {
    const pairs = [
      okPair({ coin_a: "C", coin_b: "D", eg_p_bh: 0.5, eg_p_raw: 0.2 }),
      okPair({ coin_a: "A", coin_b: "B", eg_p_bh: 0.5, eg_p_raw: 0.2 }),
      okPair({ coin_a: "Z", coin_b: "Y", eg_p_bh: 0.5, eg_p_raw: 0.1 }),
    ];
    expect(sortPairs(pairs).map((p) => p.coin_a)).toEqual(["Z", "A", "C"]);
  });
  it("does not mutate its input", () => {
    const pairs = tablePairs();
    const before = pairs.map((p) => p.coin_a + p.coin_b);
    sortPairs(pairs);
    expect(pairs.map((p) => p.coin_a + p.coin_b)).toEqual(before);
  });
});

describe("isRawOnlySignificant", () => {
  it("tags raw < 5% with corrected ≥ 5% only", () => {
    expect(isRawOnlySignificant(okPair({ coin_a: "A", coin_b: "B", eg_p_raw: 0.00057, eg_p_bh: 0.087 }))).toBe(true);
    expect(isRawOnlySignificant(okPair({ coin_a: "A", coin_b: "B", eg_p_raw: 0.001, eg_p_bh: 0.04 }))).toBe(false);
    expect(isRawOnlySignificant(okPair({ coin_a: "A", coin_b: "B", eg_p_raw: 0.2, eg_p_bh: 0.5 }))).toBe(false);
    expect(isRawOnlySignificant(okPair({ coin_a: "A", coin_b: "B", eg_p_raw: 0.05, eg_p_bh: 0.5 }))).toBe(false);
  });
  it("never tags non-ok rows", () => {
    expect(isRawOnlySignificant(tablePairs()[0])).toBe(false);
  });
});

describe("significanceSummary", () => {
  it("none significant: count = corrected-p rows, names the closest", () => {
    expect(significanceSummary(tablePairs())).toBe(
      "No pair is significant after correcting for 4 tests (5% level). Closest: DOGE/BCH, corrected p 0.087."
    );
  });
  it("some significant: states how many", () => {
    const pairs = [
      ...tablePairs(),
      okPair({ coin_a: "X", coin_b: "Y", eg_p_raw: 0.0001, eg_p_bh: 0.01 }),
    ];
    expect(significanceSummary(pairs)).toBe("1 of 5 pairs are significant after correcting for 5 tests (5% level).");
  });
  it("no testable pair", () => {
    expect(significanceSummary(tablePairs().filter((p) => p.status !== "ok"))).toBe("No pair has enough data to test.");
  });
});
