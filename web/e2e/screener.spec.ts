/**
 * End-to-end specs for /screener.
 *
 * What these exist to cover, stated plainly: `ScreenerBoard` takes
 * `fetchBoard`/`fetchScalp` as injectable props and all seven vitest suites
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
  active_benchmark: { active: string; reason: string };
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
  await expect(page.getByTestId("active-benchmark")).not.toHaveText(/…/);
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
test("a thin-history symbol shows unavailable, never a zero", async ({ page }) => {
  const thin = manifest.thin_symbol;
  expect(manifest.bars_written[thin]["1d"]).toBeLessThan(manifest.min_bars_required);

  await page.goto("/screener");
  const panel = page.getByTestId(`coin-panel-${thin}`);
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId("chart-unavailable")).toBeVisible();

  const chips = await panel.getByTestId(/^gain-chip-/).allInnerTexts();
  expect(chips.length).toBeGreaterThan(0);
  for (const chip of chips) {
    expect(chip, `a thin-history chip read "${chip}" — 0% must never stand in for missing data`)
      .not.toMatch(/\b0\.0%/);
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
// 6. Drill-down is on demand (AC-7), against a real scalp request.
// ---------------------------------------------------------------------------
test("drill-down opens on demand and fetches the scalp view", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();

  // AC-7: not rendered as part of the grid until asked for.
  await expect(page.getByTestId("drilldown-view")).toHaveCount(0);

  const scalpRequest = page.waitForRequest((r) => r.url().includes("/scalp"));
  await page.getByTestId("open-drilldown-BTC").click();
  const req = await scalpRequest;

  expect(req.url()).toContain("/api/screener/BTC/scalp");
  const view = page.getByTestId("drilldown-view");
  await expect(view).toBeVisible();
  await expect(view).toHaveAttribute("aria-label", "BTC drill-down");
  // The scalp reading came from the real endpoint, not a placeholder.
  await expect(view.getByTestId("scalp-rsi-reading")).toBeVisible();

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

test("the relative-performance chart draws its lines, and the board's mini charts are not blank", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();

  const relative = page.getByTestId("rp-chart-container").locator("canvas").first();
  await expect(relative).toBeVisible();
  // The first watchlist coin is the first line, so its colour must be on the plot.
  expect(await seriesPixels(relative, FIRST_SERIES), "relative-performance has no line drawn").toBeGreaterThan(20);

  // Which line is which. A multi-coin chart with no names on it cannot be read.
  await expect(page.getByTestId("rp-legend-BTC")).toBeVisible();
  await expect(page.getByTestId("rp-legend-ETH")).toBeVisible();

  // The role/label is what makes the plot reachable by assistive tech.
  await expect(page.getByTestId("rp-chart-container").getByRole("img")).toHaveAttribute(
    "aria-label",
    /Relative performance over/
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
