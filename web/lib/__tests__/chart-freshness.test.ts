import { describe, expect, it } from "vitest";
import { formatAge, freshnessCaption } from "@/lib/chart-freshness";

describe("formatAge", () => {
  it("uses <1 min, N min under 120, N h under 48, else N d", () => {
    expect(formatAge(0)).toBe("<1 min");
    expect(formatAge(59)).toBe("<1 min");
    expect(formatAge(-30)).toBe("<1 min"); // a clock a little ahead never reads negative
    expect(formatAge(60)).toBe("1 min");
    expect(formatAge(119 * 60 + 59)).toBe("119 min");
    expect(formatAge(120 * 60)).toBe("2 h");
    expect(formatAge(47 * 3600 + 3599)).toBe("47 h");
    expect(formatAge(48 * 3600)).toBe("2 d");
    expect(formatAge(10 * 86400)).toBe("10 d");
    expect(formatAge(Number.NaN)).toBe("<1 min");
  });
});

describe("freshnessCaption", () => {
  it("captions a forming bar with its open age (golden)", () => {
    expect(
      freshnessCaption({ last_bar_ts: "2026-10-03T14:15:00Z", is_partial: true, server_time: "2026-10-03T14:22:00Z", stale: false }),
    ).toBe("Last bar 2026-10-03 14:15 UTC, opened 7 min ago (forming)");
  });

  it("captions a closed bar without the forming suffix (golden)", () => {
    expect(
      freshnessCaption({ last_bar_ts: "2026-10-03T14:00:00Z", is_partial: false, server_time: "2026-10-03T14:22:00Z", stale: false }),
    ).toBe("Last bar 2026-10-03 14:00 UTC, 22 min ago");
  });

  it("ages against server_time, never the browser clock", () => {
    const caption = freshnessCaption({
      last_bar_ts: "2020-01-01T00:00:00Z",
      is_partial: false,
      server_time: "2020-01-03T06:00:00Z",
      stale: true,
    });
    expect(caption).toBe("Last bar 2020-01-01 00:00 UTC, 2 d ago");
  });

  it("drops the age without server_time and returns null without a last bar", () => {
    expect(freshnessCaption({ last_bar_ts: "2026-10-03T00:00:00Z", is_partial: false, server_time: null, stale: false })).toBe(
      "Last bar 2026-10-03 00:00 UTC",
    );
    expect(freshnessCaption({ last_bar_ts: null, is_partial: null, server_time: "2026-10-03T00:00:00Z", stale: false })).toBeNull();
    expect(freshnessCaption({ last_bar_ts: "not a date", is_partial: null, server_time: null, stale: false })).toBeNull();
  });
});
