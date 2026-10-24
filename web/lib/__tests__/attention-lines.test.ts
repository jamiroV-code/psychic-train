import { describe, expect, it } from "vitest";
import { buildAttentionLines, formatScore, formatSigned } from "@/lib/attention-lines";
import type { BasketAttention } from "@/lib/types/attention";

const basket = (id: string, values: (number | null)[]): BasketAttention => ({
  id,
  name: id,
  score: 1,
  change: 0.5,
  breadth: 0.5,
  coverage: "covers 2 of 3",
  series: values.map((value, i) => ({ date: `2026-10-0${i + 1}`, value })),
  coins: [],
  status: "ok",
  reason: "",
  universe_size: 3,
});

describe("buildAttentionLines", () => {
  it("splits a line at a null so the gap is not bridged", () => {
    const lines = buildAttentionLines([basket("a", [1, 2, null, 4, 5])], new Set());
    expect(lines).toHaveLength(2);
    expect(lines[0].points).toHaveLength(2);
    expect(lines[1].points).toHaveLength(2);
    expect(lines[0].color).toBe(lines[1].color);
  });
  it("never turns null into 0", () => {
    const lines = buildAttentionLines([basket("a", [null, 3, null])], new Set());
    expect(lines.flatMap((l) => l.points.map((p) => p.value))).toEqual([3]);
  });
  it("drops hidden baskets", () => {
    expect(buildAttentionLines([basket("a", [1, 2])], new Set(["a"]))).toEqual([]);
  });
});

describe("formatting", () => {
  it("shows no data for null, never 0", () => {
    expect(formatScore(null)).toBe("no data");
    expect(formatSigned(null)).toBe("no data");
  });
  it("signs change", () => {
    expect(formatSigned(1.5)).toBe("+1.5");
    expect(formatSigned(-1.5)).toBe("-1.5");
    expect(formatSigned(0)).toBe("0.0");
  });
});
