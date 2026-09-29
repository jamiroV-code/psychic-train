import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { SERIES } from "@/lib/chart-palette";

/**
 * The canvas charts need literal colours, so the validated palette exists in
 * two places. This is the seam that keeps them honest: if someone retunes a
 * --series-N slot in globals.css, this fails rather than letting the regime
 * panels quietly drift off the palette.
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
  });
});
