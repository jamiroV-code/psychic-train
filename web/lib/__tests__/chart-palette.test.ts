import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { MARKER, NARRATIVE_SERIES, SERIES } from "@/lib/chart-palette";

/**
 * The canvas charts need literal colours, so the validated palette exists in
 * two places. This is the seam that keeps them honest: if someone retunes a
 * --series-N slot in globals.css, this fails rather than letting the charts
 * quietly drift off the palette.
 */
const css = readFileSync(join(__dirname, "..", "..", "app", "globals.css"), "utf-8");

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`globals.css has no --${name}`);
  return match[1].trim();
}

describe("chart palette", () => {
  it("matches the --series-N slots in globals.css", () => {
    expect(SERIES.primary).toBe(token("series-1"));
    expect(SERIES.secondary).toBe(token("series-2"));
    expect(SERIES.green).toBe(token("series-3"));
    expect(SERIES.indigo).toBe(token("series-4"));
    expect(SERIES.pink).toBe(token("series-5"));
    expect(SERIES.red).toBe(token("series-8"));
  });

  it("draws every narrative series from the validated set", () => {
    // The audit measured the old hand-picked narrative palette as failing
    // colour-blindness gates. Nothing here may reintroduce an unvalidated hex.
    const validated = new Set(Object.values(SERIES));
    for (const [key, color] of Object.entries(NARRATIVE_SERIES)) {
      expect(validated, `${key} is off-palette`).toContain(color);
    }
  });

  it("separates the two pytrends windows by dash, not by a near-identical hue", () => {
    expect(NARRATIVE_SERIES["pytrends-backfill-269d"]).toBe(NARRATIVE_SERIES["pytrends-nightly-7d"]);
  });

  it("keeps floor/ramp markers neutral so they never read as a chain", () => {
    expect(MARKER.floor).toBe(token("an-ink-1"));
    expect(MARKER.ramp).toBe(token("an-ink-3"));
    const chainHues = new Set<string>(Object.values(SERIES));
    expect(chainHues.has(MARKER.floor)).toBe(false);
    expect(chainHues.has(MARKER.ramp)).toBe(false);
  });
});
