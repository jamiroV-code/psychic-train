import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Axis labels on the light plot surface are 10px TEXT, so they need 4.5:1.
 *
 * --an-ink-3 measured 3.5:1 there; --an-ink-2 is 7.7:1. This is pinned in a
 * unit test because the browser contrast audit (e2e/contrast.spec.ts) cannot
 * see it for the canvas charts: a canvas has no text nodes, so their axis
 * labels — coloured by `currentColor` on `.analytic-plot` — are invisible to a
 * DOM walk. The rule that colours them is asserted here instead.
 */
const css = readFileSync(join(__dirname, "..", "..", "app", "globals.css"), "utf-8");

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`globals.css has no --${name}`);
  return match[1].trim();
}

function block(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = css.match(new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`));
  if (!match) throw new Error(`globals.css has no rule for ${selector}`);
  return match[1];
}

function lin(c: number): number {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}
function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("plot axis ink", () => {
  it("--an-ink-2 clears 4.5:1 on both plot surfaces", () => {
    expect(contrast(token("an-ink-2"), token("an-bg"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("an-ink-2"), token("an-panel"))).toBeGreaterThanOrEqual(4.5);
  });

  it("--an-ink-3 does NOT, which is why axis labels must not use it", () => {
    // If this ever starts passing, the token was retuned and the rules below
    // could go back to it — but that should be a decision, not a drift.
    expect(contrast(token("an-ink-3"), token("an-panel"))).toBeLessThan(4.5);
  });

  it("colours canvas axis labels (via currentColor) and SVG tick text with --an-ink-2", () => {
    expect(block(".analytic-plot")).toMatch(/color:\s*var\(--an-ink-2\)/);
    expect(block(".spread-chart .tick text,\n.spread-chart text")).toMatch(/fill:\s*var\(--an-ink-2\)/);
  });
});
