/**
 * Contrast audit, every route, measured in a real browser.
 *
 * Why this exists: /onchain shipped with every chain label, heading, filter
 * button and readout at about 1:1 contrast (#0b0b0b on the #0c0f14 shell) while
 * every unit test passed and the console was clean. Unit tests assert on
 * strings and structure; nothing asserted on what a person can actually read.
 * A later audit found more of the same — a muted-grey token below 4.5:1 on
 * every shell surface, series-blue label text on a dark card, a stray white bar
 * from a CSS system colour.
 *
 * This walks every visible text node on each route and measures its colour
 * against the background it is really painted on (the nearest ancestor with a
 * non-transparent background), not against what the source says.
 *
 * Scope, stated plainly:
 *  - TEXT must clear WCAG 4.5:1 (3:1 for large text). Asserted.
 *  - Legend GLYPHS (―, ▬, ▇, ●) are graphics, not text, and are NOT asserted.
 *    They wear the chart's series colours, and three of the validated palette's
 *    light slots (green, pink, amber) sit at 2.1-2.8:1 on the plot surface. The
 *    palette validator reports that as a WARN whose required relief is visible
 *    labels or a table view — which every chart using them has. That is a
 *    managed condition of the palette, not something this spec should re-litigate.
 *  - Canvas contents are out of scope; a canvas has no text nodes. Whether a
 *    plot paints at all is asserted by the per-route specs.
 */
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8")) as {
  pairs: { significant_pair: [string, string] };
};
const [pairA, pairB] = manifest.pairs.significant_pair;

interface Offender {
  ratio: number;
  need: number;
  color: string;
  background: string;
  count: number;
  sample: string;
  testid: string | null;
}

async function textContrastOffenders(page: Page): Promise<Offender[]> {
  return page.evaluate(() => {
    const parse = (s: string) => {
      const m = s.match(/rgba?\(([^)]+)\)/);
      if (!m) return null;
      const [r, g, b, a = 1] = m[1].split(",").map((x) => parseFloat(x));
      return { r, g, b, a };
    };
    type RGB = { r: number; g: number; b: number };
    const lin = (c: number) => {
      const v = c / 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    const lum = ({ r, g, b }: RGB) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    const ratio = (a: RGB, b: RGB) => {
      const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
      return (hi + 0.05) / (lo + 0.05);
    };
    const backgroundOf = (el: Element): RGB => {
      for (let n: Element | null = el; n; n = n.parentElement) {
        const c = parse(getComputedStyle(n).backgroundColor);
        if (c && c.a > 0.5) return c;
      }
      return { r: 255, g: 255, b: 255 };
    };

    const found = new Map<string, Offender>();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let t = walker.nextNode(); t; t = walker.nextNode()) {
      const text = (t.textContent ?? "").trim();
      if (!text) continue;
      // Legend glyphs are graphics, not text — see the header for why.
      if (/^[―▬▇●┄▲\s]+$/.test(text)) continue;
      const el = t.parentElement;
      if (!el || ["SCRIPT", "STYLE", "NOSCRIPT"].includes(el.tagName)) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none" || parseFloat(cs.opacity) === 0) continue;
      const box = el.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      // SVG text is painted by `fill`; CSS `color` on it is just an inherited
      // value that nothing draws with. Measuring `color` there reads the shell's
      // near-white against the light plot and reports a phantom 1.15:1.
      const isSvg = el instanceof SVGElement;
      const fg = parse(isSvg ? cs.fill : cs.color);
      if (!fg) continue;

      const bg = backgroundOf(el);
      const size = parseFloat(cs.fontSize);
      const bold = parseInt(cs.fontWeight, 10) >= 700;
      const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
      const cr = ratio(fg, bg);
      if (cr >= need) continue;

      const key = `${isSvg ? cs.fill : cs.color}|${bg.r},${bg.g},${bg.b}`;
      const existing = found.get(key);
      if (existing) {
        existing.count++;
      } else {
        found.set(key, {
          ratio: Math.round(cr * 100) / 100,
          need,
          color: isSvg ? cs.fill : cs.color,
          background: `rgb(${bg.r},${bg.g},${bg.b})`,
          count: 1,
          sample: text.slice(0, 40),
          testid: el.closest("[data-testid]")?.getAttribute("data-testid") ?? null,
        });
      }
    }
    return [...found.values()].sort((a, b) => a.ratio - b.ratio);
  });
}

const ROUTES: { name: string; path: string; ready: string | null }[] = [
  { name: "home", path: "/", ready: null },
  { name: "screener", path: "/screener", ready: '[data-testid="spaghetti-legend"]' },
  { name: "regime", path: "/regime", ready: '[data-testid="regime-chart-net_liquidity"] canvas' },
  { name: "narrative", path: "/narrative", ready: '[data-testid="narrative-chart-ai"] canvas' },
  { name: "pairs table", path: "/pairs", ready: '[data-testid="pairs-table"]' },
  { name: "pair detail", path: `/pairs/${pairA}/${pairB}`, ready: null },
  { name: "onchain", path: "/onchain", ready: '[data-testid="onchain-chart-ethereum"] canvas' },
];

for (const route of ROUTES) {
  test(`${route.name}: all text is legible against what it is painted on`, async ({ page }) => {
    await page.goto(route.path);
    if (route.ready) await page.waitForSelector(route.ready, { timeout: 30_000 });
    // Charts and late-arriving panels settle after the first paint.
    await page.waitForTimeout(1_500);

    const offenders = await textContrastOffenders(page);
    expect(
      offenders,
      `${route.path} has text below its contrast requirement:\n${JSON.stringify(offenders, null, 2)}`
    ).toEqual([]);
  });
}
