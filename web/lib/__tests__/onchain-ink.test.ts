import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { INK } from "@/lib/onchain-view-model";

const css = readFileSync(join(__dirname, "..", "..", "app", "globals.css"), "utf-8");

function token(name: string): string {
  const match = css.match(new RegExp(`--${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`globals.css has no --${name}`);
  return match[1].trim();
}

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const ch = [0, 2, 4].map((i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("onchain INK", () => {
  it("draws page text from the shell tokens and chart ink from the plot tokens", () => {
    expect(INK.primary).toBe(token("ink-1"));
    expect(INK.secondary).toBe(token("ink-2"));
    expect(INK.muted).toBe(token("ink-3"));
    expect(INK.gridline).toBe(token("an-grid"));
    expect(INK.baseline).toBe(token("an-axis"));
  });

  it("keeps ALL page text legible on EVERY shell surface it can sit on", () => {
    // The regression this pins: these were light-surface values on a dark
    // shell, so every chain label rendered at about 1:1 — invisible.
    //
    // Muted is held to 4.5:1 like the rest. It used to be held to 3:1 on the
    // grounds that it was "supporting text", but 12px supporting text is small
    // text: a browser-side contrast audit measured the old value at 3.1-4.1:1
    // across the shell's surfaces. And the check is against every surface, not
    // just the page background — cards and badges sit on the lighter ones, and
    // that is where it failed.
    for (const surface of ["sh-0", "sh-1", "sh-2", "sh-3"]) {
      const bg = token(surface);
      expect(contrast(INK.primary, bg), `primary on ${surface}`).toBeGreaterThanOrEqual(4.5);
      expect(contrast(INK.secondary, bg), `secondary on ${surface}`).toBeGreaterThanOrEqual(4.5);
      expect(contrast(INK.muted, bg), `muted on ${surface}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("uses the same grey for the insufficient-severity text as for muted ink", () => {
    // --sev-insuf is used as a text colour, so it is held to the same bar.
    expect(token("sev-insuf")).toBe(token("ink-3"));
  });
});
