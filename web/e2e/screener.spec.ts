/**
 * End-to-end specs for /screener.
 *
 * What these exist to cover, stated plainly: `ScreenerBoard` takes
 * `fetchBoard`/`fetchChart` as injectable props and all seven vitest suites
 * pass fakes, so `lib/api/screener.ts` — the real client, the real URL
 * construction, the real JSON decode — has never been executed by a test.
 * Neither has CORS, the Next.js runtime, nor the FastAPI-to-TypeScript
 * response-shape contract.
 *
 * Two defects on 19-09-26 (ADR-5, ADR-6) both lived at boundaries the unit
 * suites sat above. These specs cross boundaries; that is the whole point.
 * Every layer here is real except the exchange, which is absent because the
 * seeded cache is fresh.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

// Fixture facts come from the seeder's own manifest, never retyped here —
// two copies of a golden value drift, and the drifted one is always the
// assertion rather than the data.
const manifest = JSON.parse(
  fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8")
) as {
  watchlist: string[];
  thin_symbol: string;
  min_bars_required: number;
  bars_written: Record<string, Record<string, number>>;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

interface ChartBar {
  timestamp: string;
  close: number;
}
interface BoardResponse {
  timeframe: string;
  coins: {
    symbol: string;
    chart: { price: ChartBar[]; sma: ChartBar[]; available: boolean };
    percent_change_by_timeframe: Record<string, number | null>;
  }[];
}

async function board(request: APIRequestContext, timeframe: string): Promise<BoardResponse> {
  const res = await request.get(`${API_BASE_URL}/api/screener/board?timeframe=${timeframe}`);
  expect(res.ok(), `board?timeframe=${timeframe} returned ${res.status()}`).toBe(true);
  return (await res.json()) as BoardResponse;
}

// ---------------------------------------------------------------------------
// 1. The board renders from the real API.
//    Catches: any break in the real client, URL construction, CORS, or the
//    FastAPI-to-TypeScript response shape. None of those is touched today.
// ---------------------------------------------------------------------------
test("the board renders one panel per watchlist symbol, from a real request", async ({ page }) => {
  await page.goto("/screener");

  await expect(page.getByTestId("screener-board")).toBeVisible();
  for (const symbol of manifest.watchlist) {
    await expect(page.getByTestId(`coin-panel-${symbol}`)).toBeVisible();
  }
  await expect(page.getByTestId("screener-board-grid").locator("> div")).toHaveCount(
    manifest.watchlist.length
  );
  // No error path was taken — if the client, CORS or the shape were broken,
  // this is where it would surface instead of an empty grid.
  await expect(page.getByTestId("board-error")).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// 2. The timeframe toggle issues a real refetch.
//    Catches: a toggle that mutates local state without a request — invisible
//    to a vitest suite that injects a fake fetcher.
// ---------------------------------------------------------------------------
test("switching timeframe issues a new board request", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();

  const requested = page.waitForRequest((r) => r.url().includes("timeframe=1w"));
  await page.getByTestId("timeframe-button-1w").click();
  await requested;

  await expect(page.getByTestId("timeframe-button-1w")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();
});

// ---------------------------------------------------------------------------
// 3. Weekly bars are Monday-anchored, end to end, on this machine's timezone.
//    Catches ADR-5 (label was the week's close, +6 days) and ADR-6 (the cache
//    round trip returned local time, so the anchor sat on local midnight —
//    Monday locally, Sunday 22:00/23:00 UTC).
//
//    This is the assertion neither suite could make: the 13 ADR-5 tests ran
//    above the cache, the 13 ADR-6 tests ran below the browser. Only the `1w`
//    series is derived on request rather than seeded, so this reads the real
//    derivation, not the fixture.
// ---------------------------------------------------------------------------
test("weekly bars are Monday 00:00 UTC through the whole stack", async ({ request }) => {
  const weekly = await board(request, "1w");
  const btc = weekly.coins.find((c) => c.symbol === "BTC");
  expect(btc, "BTC missing from the 1w board").toBeTruthy();
  expect(btc!.chart.price.length).toBeGreaterThan(0);

  for (const bar of btc!.chart.price) {
    const t = new Date(bar.timestamp);
    expect(
      t.getUTCDay(),
      `weekly bar ${bar.timestamp} is not a Monday in UTC — Monday in a local ` +
        `timezone is Sunday 22:00/23:00 UTC (ADR-6)`
    ).toBe(1); // JS: 0=Sun, 1=Mon
    expect(
      [t.getUTCHours(), t.getUTCMinutes(), t.getUTCSeconds()],
      `weekly bar ${bar.timestamp} is a Monday but not at midnight UTC — the anchor is still local`
    ).toEqual([0, 0, 0]);
  }

  // Spacing is a constant 7 days. A locally-anchored series is 167 or 169
  // hours across a DST change; this catches that without waiting for October.
  const times = btc!.chart.price.map((b) => new Date(b.timestamp).getTime());
  for (let i = 1; i < times.length; i++) {
    expect(times[i] - times[i - 1], "weekly spacing is not a constant 7 days").toBe(
      7 * 24 * 60 * 60 * 1000
    );
  }
});

// ---------------------------------------------------------------------------
// 4. Thin history degrades honestly.
//    Catches a regression of AC-20, currently proven only against an injected
//    fixture: a missing gain must read N/A, never 0%.
// ---------------------------------------------------------------------------
test("a thin-history symbol shows unavailable, never a zero", async ({ page, request }) => {
  const thin = manifest.thin_symbol;
  expect(manifest.bars_written[thin]["1d"]).toBeLessThan(manifest.min_bars_required);

  await page.goto("/screener");
  const panel = page.getByTestId(`coin-panel-${thin}`);
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId("chart-unavailable")).toBeVisible();

  // T34 / S2 (D8): a chip is the current candle, open to latest. A real flat
  // candle may read 0.0%, so the old "never 0.0%" rule no longer holds; what
  // must hold is that every chip is N/A or a well-formed percentage, and that
  // the API backs each N/A with a reason.
  const chips = await panel.locator(".coin-panel__gain-chip-value").allInnerTexts();
  expect(chips.length).toBe(5);
  for (const chip of chips) {
    expect(chip.trim(), `chip read "${chip}"`).toMatch(/^(N\/A|[+-]?\d+\.\d%)$/);
  }

  type Chip = { pct: number | null; reason: string | null };
  const data = (await board(request, "1d")) as unknown as {
    coins: { symbol: string; gain_by_timeframe: Record<string, Chip> }[];
  };
  const thinCoin = data.coins.find((c) => c.symbol === thin);
  expect(thinCoin, `${thin} missing from the board response`).toBeDefined();
  for (const tf of ["15m", "1h", "4h", "1d", "1w"]) {
    const chip = thinCoin!.gain_by_timeframe[tf];
    expect(chip, `gain_by_timeframe.${tf} missing`).toBeDefined();
    expect(chip.pct !== null || chip.reason !== null, `${tf}: neither pct nor reason`).toBe(true);
  }
});

// ---------------------------------------------------------------------------
// 5. A dead API degrades honestly rather than white-screening.
//    Asserts TODAY's behaviour deliberately. `getJson` has no timeout and no
//    catch, and three of its four call sites do not catch either — RFC-006
//    will change that, and this spec should change with it. A test that
//    changes when behaviour changes is doing its job.
// ---------------------------------------------------------------------------
test("a failing API surfaces an error, not a blank page", async ({ page }) => {
  await page.route("**/api/screener/board**", (route) => route.abort("failed"));
  await page.goto("/screener");

  await expect(page.getByTestId("board-error")).toBeVisible();
  // The page itself must survive — the heading is still there.
  await expect(page.getByRole("heading", { name: "Screener" })).toBeVisible();
});

// ---------------------------------------------------------------------------
// 6. Drill-down is on demand (AC-7), against a real chart request.
// ---------------------------------------------------------------------------
test("drill-down opens on demand and fetches the chart view", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();

  // AC-7: not rendered as part of the grid until asked for.
  await expect(page.getByTestId("drilldown-view")).toHaveCount(0);

  const chartRequest = page.waitForRequest((r) => r.url().includes("/api/screener/BTC/chart"));
  await page.getByTestId("open-drilldown-BTC").click();
  await chartRequest;

  const view = page.getByTestId("drilldown-view");
  await expect(view).toBeVisible();
  await expect(view).toHaveAttribute("aria-label", "BTC drill-down");

  await view.getByTestId("drilldown-close").click();
  await expect(page.getByTestId("drilldown-view")).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// 7. The screener's charts actually draw.
//    Catches: a plot that mounts and stays blank. That is the failure a canvas
//    hides — the element exists, the console is clean, the header says "ok",
//    and nothing is on it. Every earlier island conversion (/regime, /narrative,
//    /onchain) shipped or nearly shipped a defect of exactly this shape, found
//    only by looking at pixels. Both screener charts are islands too, and until
//    this spec neither had any browser-level assertion at all.
// ---------------------------------------------------------------------------
// Counts pixels close to ONE series colour. Axes, gridlines and the zero rule
// are neutral greys, so a frame with no data on it scores 0 here — which is the
// point: "any pixel painted" would pass on an empty plot.
const FIRST_SERIES = "#2a78d6"; // --series-1: BTC's line, and the mini chart's price

async function seriesPixels(canvas: import("@playwright/test").Locator, hex: string): Promise<number> {
  return canvas.evaluate((el, target) => {
    const c = el as HTMLCanvasElement;
    const want = [1, 3, 5].map((i) => parseInt(target.slice(i, i + 2), 16));
    const data = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
    let hits = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] < 200) continue;
      if (
        Math.abs(data[i] - want[0]) <= 14 &&
        Math.abs(data[i + 1] - want[1]) <= 14 &&
        Math.abs(data[i + 2] - want[2]) <= 14
      ) {
        hits++;
      }
    }
    return hits;
  }, hex);
}

test("the spaghetti chart draws its lines, and the board's mini charts are not blank", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();

  const spaghetti = page.getByTestId("spaghetti-chart-container").locator("canvas").first();
  await expect(spaghetti).toBeVisible();
  // BTC is a reference line in the first palette slot, so its colour must be on the plot.
  expect(await seriesPixels(spaghetti, FIRST_SERIES), "spaghetti chart has no BTC line drawn").toBeGreaterThan(20);

  // Which line is which: one legend toggle per line, both references among them.
  await expect(page.getByTestId("spaghetti-legend")).toBeVisible();
  await expect(page.getByTestId("spaghetti-toggle-BTC")).toHaveAttribute("data-reference", "true");
  await expect(page.getByTestId("spaghetti-toggle-HYPE")).toHaveAttribute("data-reference", "true");
  await expect(page.getByTestId("spaghetti-span")).toContainText("Brussels time");

  // The role/label is what makes the plot reachable by assistive tech.
  // (The plot itself, not LayerChart's per-label text nodes, which also carry role="img".)
  await expect(page.getByTestId("spaghetti-chart-container").locator(".simple-lines")).toHaveAttribute(
    "aria-label",
    /Percent change from the window start/
  );

  // A mini chart per coin, each drawing something.
  const minis = page.getByTestId("mini-chart");
  await expect(minis.first().locator("canvas").first()).toBeVisible();
  const count = await minis.count();
  expect(count).toBeGreaterThanOrEqual(manifest.watchlist.length - 1); // the thin symbol has no chart
  for (let i = 0; i < count; i++) {
    const canvas = minis.nth(i).locator("canvas").first();
    if ((await canvas.count()) === 0) continue; // an honest unavailable state has no plot
    expect(await seriesPixels(canvas, FIRST_SERIES), `mini chart ${i} has no price line`).toBeGreaterThan(10);
  }
});

// ---------------------------------------------------------------------------
// 8. Every simple-lines chart zooms, pans and resets (T37 / S6, C6).
//    Catches: a wheel that hijacks page scrolling, a zoom with no way back,
//    and a drag that does nothing. Read through the plot's own test hooks.
// ---------------------------------------------------------------------------
// T44: the small charts have no reset button; `linked` is a second small
// chart that must follow every zoom, pan and reset of `plot` (linked zoom).
// Charts that are not linked keep their reset button.
async function exerciseZoom(
  page: import("@playwright/test").Page,
  plot: import("@playwright/test").Locator,
  linked?: import("@playwright/test").Locator,
) {
  const follows = async () => {
    if (!linked) return;
    await expect(linked).toHaveAttribute("data-zoomed", (await plot.getAttribute("data-zoomed"))!);
    await expect(linked).toHaveAttribute("data-visible-from", (await plot.getAttribute("data-visible-from"))!);
    await expect(linked).toHaveAttribute("data-visible-to", (await plot.getAttribute("data-visible-to"))!);
  };
  await plot.scrollIntoViewIfNeeded();
  await expect(plot).toHaveAttribute("data-zoomed", "false");
  const fullFrom = (await plot.getAttribute("data-visible-from"))!;
  const fullTo = (await plot.getAttribute("data-visible-to"))!;
  expect(fullFrom).toMatch(/Z$/);

  const box = (await plot.boundingBox())!;
  const cx = box.x + box.width * 0.6;
  const cy = box.y + box.height / 2;
  await page.mouse.move(cx, cy);

  // A plain wheel is the page's, not the chart's.
  await page.mouse.wheel(0, -400);
  await expect(plot).toHaveAttribute("data-zoomed", "false");

  // Ctrl + wheel zooms about the pointer. The plain wheel may have scrolled
  // the page, so bring the plot back into view and re-read its position first.
  await plot.scrollIntoViewIfNeeded();
  const zb = (await plot.boundingBox())!;
  await page.mouse.move(zb.x + zb.width * 0.6, zb.y + zb.height / 2);
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -400);
  await page.keyboard.up("Control");
  await expect(plot).toHaveAttribute("data-zoomed", "true");
  const zFrom = (await plot.getAttribute("data-visible-from"))!;
  const zTo = (await plot.getAttribute("data-visible-to"))!;
  expect(Date.parse(zFrom)).toBeGreaterThan(Date.parse(fullFrom));
  expect(Date.parse(zTo)).toBeLessThanOrEqual(Date.parse(fullTo));
  await expect(plot.getByTestId("chart-reset")).toHaveCount(linked ? 0 : 1);
  await follows();

  // A drag to the right brings earlier time into view.
  const pb = (await plot.boundingBox())!;
  const py = pb.y + pb.height / 2;
  await page.mouse.move(pb.x + pb.width * 0.6, py);
  await page.mouse.down();
  await page.mouse.move(pb.x + pb.width * 0.75, py, { steps: 5 });
  await page.mouse.up();
  await expect.poll(async () => Date.parse((await plot.getAttribute("data-visible-from"))!)).toBeLessThan(Date.parse(zFrom));
  await follows();

  // A double-click resets to the full range.
  await page.mouse.dblclick(pb.x + pb.width * 0.5, py);
  await expect(plot).toHaveAttribute("data-zoomed", "false");
  await expect(plot).toHaveAttribute("data-visible-from", fullFrom);
  await expect(plot.getByTestId("chart-reset")).toHaveCount(0);
  await follows();
}

test("ctrl-wheel zooms, drag pans, double-click resets, plain wheel does not zoom, small charts zoom together", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();

  const coinPlot = page.getByTestId("coin-panel-BTC").getByTestId("mini-chart").locator(".simple-lines");
  await expect(coinPlot.locator("canvas").first()).toBeVisible();
  const ethPlot = page.getByTestId("coin-panel-ETH").getByTestId("mini-chart").locator(".simple-lines");
  await exerciseZoom(page, coinPlot, ethPlot);

  const spaghettiPlot = page.getByTestId("spaghetti-chart-container").locator(".simple-lines");
  await expect(spaghettiPlot.locator("canvas").first()).toBeVisible();
  await exerciseZoom(page, spaghettiPlot);

  // The reset button resets too (the spaghetti chart keeps it).
  const box = (await spaghettiPlot.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -400);
  await page.keyboard.up("Control");
  await expect(spaghettiPlot).toHaveAttribute("data-zoomed", "true");
  await spaghettiPlot.getByTestId("chart-reset").click();
  await expect(spaghettiPlot).toHaveAttribute("data-zoomed", "false");
});

// ---------------------------------------------------------------------------
// 9. Axis text is crisp: SVG text, never clipped, over a DPR-sized canvas.
//    Its own describe at DPR 2, so tests 1-8 keep DPR 1 (test 7's pixel
//    thresholds are tuned there).
// ---------------------------------------------------------------------------
test.describe("at device pixel ratio 2", () => {
  test.use({ deviceScaleFactor: 2 });

  test("axis text is SVG, every tick label stays inside the plot box, canvas backing store matches DPR 2", async ({ page }) => {
    await page.goto("/screener");
    await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();
    expect(await page.evaluate(() => window.devicePixelRatio)).toBe(2);

    const plots = [
      page.getByTestId("coin-panel-BTC").getByTestId("mini-chart").locator(".simple-lines"),
      page.getByTestId("spaghetti-chart-container").locator(".simple-lines"),
    ];
    for (const plot of plots) {
      await expect(plot.locator("canvas").first()).toBeVisible();
      await expect(plot.locator("svg text").first()).toBeVisible();
      const result = await plot.evaluate((el) => {
        const box = el.getBoundingClientRect();
        const texts = [...el.querySelectorAll("svg text")].filter((t) => (t.textContent ?? "").trim() !== "");
        const outside = texts
          .map((t) => ({ text: t.textContent, r: t.getBoundingClientRect() }))
          .filter(({ r }) => r.left < box.left - 0.5 || r.right > box.right + 0.5 || r.top < box.top - 0.5 || r.bottom > box.bottom + 0.5)
          .map(({ text }) => text);
        const canvas = el.querySelector("canvas") as HTMLCanvasElement;
        return {
          labels: texts.length,
          outside,
          width: canvas.width,
          expected: Math.round(canvas.clientWidth * 2),
        };
      });
      expect(result.labels, "no SVG axis labels").toBeGreaterThan(3);
      expect(result.outside, "tick labels outside the plot box").toEqual([]);
      expect(result.width, "canvas backing store is not DPR 2").toBe(result.expected);
    }
  });
});

// ---------------------------------------------------------------------------
// T38 / S7: the BTC leg chart over all cached BTC daily history.
//    Catches: a payload that trims daily bars, legs out of order, or an
//    estimate panel whose heading drifted from the D-14 wording.
// ---------------------------------------------------------------------------
test("the BTC leg chart covers every seeded daily bar, with ordered legs and the estimate heading", async ({
  page,
  request,
}) => {
  const res = await request.get(`${API_BASE_URL}/api/regime/btc-legs`);
  expect(res.ok(), `btc-legs returned ${res.status()}`).toBe(true);
  const body = (await res.json()) as {
    available: boolean;
    bar_count: number;
    legs: { start: string; end: string | null }[];
    estimate: { heading: string } | null;
  };
  expect(body.available).toBe(true);
  expect(body.bar_count).toBe(manifest.bars_written.BTC["1d"]);
  for (let i = 1; i < body.legs.length; i++) {
    expect(body.legs[i].start > body.legs[i - 1].start, "legs strictly increasing").toBe(true);
  }

  await page.goto("/screener");
  await expect(page.getByTestId("btc-leg-chart-container")).toBeVisible();
  await expect(page.getByTestId("btc-leg-span")).toContainText(`${body.bar_count} bars`);
  if (body.estimate) {
    await expect(page.getByTestId("leg-estimate-heading")).toHaveText("Estimate (rule over the numbers shown)");
  } else {
    await expect(page.getByTestId("leg-estimate-na")).toContainText("N/A:");
  }
});
