import { describe, expect, it } from "vitest";
import {
  buildSpaghettiLines,
  COIN_PALETTE,
  COIN_WIDTH,
  formatPercentChange,
  REFERENCE_WIDTH,
  spaghettiLegend,
} from "@/lib/spaghetti-lines";
import { SERIES } from "@/lib/chart-palette";
import type { SpaghettiLine, SpaghettiResponse } from "@/lib/types/screener";

function line(symbol: string, available = true, closes: number[] = [0, 1.5]): SpaghettiLine {
  return {
    symbol,
    available,
    reason: available ? null : "insufficient-history",
    points: available
      ? closes.map((close, i) => ({ timestamp: `2026-10-0${i + 1}T00:00:00Z`, close }))
      : [],
    window_start: available ? "2026-10-01T00:00:00Z" : null,
    window_end: available ? `2026-10-0${closes.length}T00:00:00Z` : null,
    bars: available ? closes.length : 0,
    last_bar_ts: available ? `2026-10-0${closes.length}T00:00:00Z` : null,
    stale: false,
  };
}

function response(series: SpaghettiLine[], references = [line("BTC"), line("HYPE")]): SpaghettiResponse {
  return { timeframe: "1d", window_cap_bars: 200, server_time: null, series, references };
}

describe("spaghetti-lines", () => {
  it("one line per available coin, on one plot, values passed through untouched", () => {
    const lines = buildSpaghettiLines(response([line("SOL", true, [0, 2.5, -1]), line("ETH")]));
    expect(lines.map((l) => l.key)).toEqual(["SOL", "ETH", "BTC", "HYPE"]);
    expect(lines[0].points.map((p) => p.value)).toEqual([0, 2.5, -1]);
    // The axis says it is a percent, with a sign, and never "+0%".
    expect(formatPercentChange(2)).toBe("+2%");
    expect(formatPercentChange(-3.5)).toBe("-3.5%");
    expect(formatPercentChange(0)).toBe("0%");
    expect(formatPercentChange(0.04)).toBe("0%");
    expect(formatPercentChange(-0.04)).toBe("0%");
  });

  it("references thicker and distinct, in the fixed first two palette slots, drawn on top", () => {
    const lines = buildSpaghettiLines(response([line("SOL"), line("ETH")]));
    const byKey = Object.fromEntries(lines.map((l) => [l.key, l]));
    expect(byKey.BTC.color).toBe(SERIES.primary);
    expect(byKey.HYPE.color).toBe(SERIES.secondary);
    expect(byKey.BTC.width).toBe(REFERENCE_WIDTH);
    expect(byKey.SOL.width).toBe(COIN_WIDTH);
    expect(REFERENCE_WIDTH).toBeGreaterThan(COIN_WIDTH);
    expect(byKey.SOL.color).not.toBe(byKey.ETH.color);
    expect(lines.slice(-2).map((l) => l.key)).toEqual(["BTC", "HYPE"]);
  });

  it("hidden coins leave the lines but stay in the legend, keeping their colour", () => {
    const data = response([line("SOL"), line("ETH"), line("ARB")]);
    const shown = buildSpaghettiLines(data);
    const lines = buildSpaghettiLines(data, new Set(["ETH", "HYPE"]));
    expect(lines.map((l) => l.key)).toEqual(["SOL", "ARB", "BTC"]);
    expect(lines.find((l) => l.key === "ARB")?.color).toBe(shown.find((l) => l.key === "ARB")?.color);
    expect(spaghettiLegend(data).map((e) => e.symbol)).toEqual(["BTC", "HYPE", "SOL", "ETH", "ARB"]);
  });

  it("unavailable coin has a note and no line, never a flat zero", () => {
    const data = response([line("SOL"), line("NEWCOIN", false)], [line("BTC"), line("HYPE", false)]);
    const lines = buildSpaghettiLines(data);
    expect(lines.map((l) => l.key)).toEqual(["SOL", "BTC"]);
    const legend = spaghettiLegend(data);
    const newcoin = legend.find((e) => e.symbol === "NEWCOIN");
    expect(newcoin).toMatchObject({ available: false, reason: "insufficient-history" });
    expect(legend.find((e) => e.symbol === "HYPE")).toMatchObject({ available: false, reference: true });
  });

  it("palette cycles past 8 without the reserved slots", () => {
    const many = Array.from({ length: 10 }, (_, i) => line(`C${i}`));
    const colors = buildSpaghettiLines(response(many), new Set(["BTC", "HYPE"])).map((l) => l.color);
    expect(COIN_PALETTE).toHaveLength(6);
    expect(colors).toHaveLength(10);
    expect(colors[6]).toBe(colors[0]);
    expect(new Set(colors).size).toBe(6);
    expect(colors).not.toContain(SERIES.primary);
    expect(colors).not.toContain(SERIES.secondary);
  });
});
