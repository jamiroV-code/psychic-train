import { describe, expect, it } from "vitest";
import { barDate, dateOnlyCaption, dateOnlyChipTitle } from "@/lib/equities-freshness";
import type { GainChip } from "@/lib/types/screener";

function chip(over: Partial<GainChip>): GainChip {
  return { pct: 1.2, open_ts: "2026-10-09T00:00:00Z", is_partial: false, stale: false, reason: null, ...over };
}

describe("date-only bar captions (T47 / S9C)", () => {
  it("a daily bar is named by its date, with no clock time", () => {
    const caption = dateOnlyCaption({ last_bar_ts: "2026-10-09T00:00:00Z", is_partial: false }, "1d");
    expect(caption).toBe("Latest daily bar 2026-10-09");
    expect(caption).not.toMatch(/\d{2}:\d{2}/);
  });

  it("a weekly bar is named by the week it starts", () => {
    expect(dateOnlyCaption({ last_bar_ts: "2026-10-05T00:00:00Z", is_partial: false }, "1w")).toBe(
      "Latest weekly bar, week of 2026-10-05",
    );
  });

  it("an open bar says (forming)", () => {
    expect(dateOnlyCaption({ last_bar_ts: "2026-10-09T00:00:00Z", is_partial: true }, "1d")).toBe(
      "Latest daily bar 2026-10-09 (forming)",
    );
  });

  it("no last bar means no caption", () => {
    expect(dateOnlyCaption({ last_bar_ts: null, is_partial: null }, "1d")).toBeNull();
    expect(barDate("not a date")).toBeNull();
    expect(barDate(undefined)).toBeNull();
  });

  it("the 1d chip title is the candle's date", () => {
    expect(dateOnlyChipTitle("1d", chip({}))).toBe("1d candle from 2026-10-09");
  });

  it("the 1w chip title is its Monday, plus (forming) while open", () => {
    expect(dateOnlyChipTitle("1w", chip({ open_ts: "2026-10-05T00:00:00Z", is_partial: true }))).toBe(
      "1w candle from 2026-10-05 (forming)",
    );
  });
});
