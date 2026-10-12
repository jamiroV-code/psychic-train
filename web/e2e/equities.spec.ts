/**
 * T48 / S9D: /equities through the whole stack, on the synthetic tickers
 * `seed_e2e_equities.py` writes (SYNA, SYNB, SYNC and the 20-bar SYNTHIN).
 * Every read is the real API serving the disposable cache; LSE_API_KEY is
 * empty in the API process, so no request can reach the data vendor.
 *
 * Each test leaves the seeded state behind it (afterEach): the manifest's
 * tickers in their order and no saved equities layout.
 */
import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8")) as {
  watchlist: string[];
  equities: { tickers: string[]; thin_ticker: string };
};
const TICKERS = manifest.equities.tickers;

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";
const CAP_TEXT = "Equities list is full: 30 tickers maximum. Remove a ticker to add another.";
const NOTE_START = "Private use only.";

async function tickers(request: APIRequestContext): Promise<string[]> {
  const res = await request.get(`${API_BASE_URL}/api/equities`);
  expect(res.ok()).toBe(true);
  return ((await res.json()) as { tickers: string[] }).tickers;
}

async function restore(request: APIRequestContext) {
  for (const symbol of await tickers(request)) {
    await request.delete(`${API_BASE_URL}/api/equities/${encodeURIComponent(symbol)}`);
  }
  for (const symbol of TICKERS) {
    const res = await request.post(`${API_BASE_URL}/api/equities`, { data: { symbol } });
    expect(res.ok(), `re-adding ${symbol}`).toBe(true);
  }
  const reset = await request.delete(`${API_BASE_URL}/api/layout/equities`);
  expect(reset.ok()).toBe(true);
}

test.afterEach(async ({ request }) => {
  await restore(request);
});

function grid(page: Page): Locator {
  return page.getByTestId("screener-board-grid");
}

function group(page: Page, name: string): Locator {
  return page.getByRole("region", { name, exact: true });
}

async function order(page: Page): Promise<string[]> {
  return grid(page)
    .locator('[data-testid^="coin-panel-"]')
    .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")!.replace("coin-panel-", "")));
}

async function groupOrder(page: Page): Promise<string[]> {
  return grid(page)
    .locator('[data-testid^="coin-group-"]')
    .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")!.replace("coin-group-", "")));
}

function layoutSaved(page: Page) {
  return page.waitForResponse(
    (r) => r.url().endsWith("/api/layout/equities") && r.request().method() === "POST" && r.ok(),
  );
}

async function open(page: Page) {
  await page.goto("/equities");
  for (const symbol of TICKERS) {
    await expect(page.getByTestId(`coin-panel-${symbol}`)).toBeVisible();
  }
}

async function ctrlWheel(page: Page, plot: Locator) {
  await plot.scrollIntoViewIfNeeded();
  const box = (await plot.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2);
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -400);
  await page.keyboard.up("Control");
}

test("the page loads with its heading, the private-use note and the seeded tickers in a group", async ({ page }) => {
  await open(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Equities");
  await expect(page.getByTestId("equities-note")).toContainText(NOTE_START);
  const main = group(page, "Main");
  for (const symbol of TICKERS) await expect(main.getByTestId(`coin-panel-${symbol}`)).toBeVisible();
  expect(await order(page)).toEqual(TICKERS);
  await expect(page.getByTestId("coin-count")).toHaveText(`${TICKERS.length} / 30 tickers`);
});

test("an added ticker shows and survives a reload", async ({ page, request }) => {
  await open(page);
  await page.getByLabel("Ticker symbol").fill("synd");
  await page.getByRole("button", { name: "Add ticker" }).click();
  await expect(page.getByTestId("coin-panel-SYND")).toBeVisible();
  await expect(page.getByTestId("coin-count")).toHaveText(`${TICKERS.length + 1} / 30 tickers`);
  expect(await tickers(request)).toContain("SYND");

  await page.reload();
  await expect(page.getByTestId("coin-panel-SYND")).toBeVisible();
});

test("a removed ticker leaves the board and the list", async ({ page, request }) => {
  await open(page);
  await page.getByTestId("remove-SYNC").click();
  await page.getByTestId("confirm-remove-SYNC").click();
  await expect(page.getByTestId("coin-panel-SYNC")).toHaveCount(0);
  await expect(page.getByTestId("coin-count")).toHaveText(`${TICKERS.length - 1} / 30 tickers`);
  expect(await tickers(request)).not.toContain("SYNC");

  await page.reload();
  await expect(page.getByTestId("coin-panel-SYNA")).toBeVisible();
  await expect(page.getByTestId("coin-panel-SYNC")).toHaveCount(0);
});

test("no equity appears in any crypto group, in the API or on the crypto page", async ({ page, request }) => {
  const res = await request.get(`${API_BASE_URL}/api/layout/crypto`);
  expect(res.ok()).toBe(true);
  const layout = (await res.json()) as { groups: { coins: string[] }[] };
  const cryptoCoins = layout.groups.flatMap((g) => g.coins);
  for (const symbol of TICKERS) expect(cryptoCoins).not.toContain(symbol);

  await page.goto("/screener");
  await expect(page.getByTestId(`coin-panel-${manifest.watchlist[0]}`)).toBeVisible();
  for (const symbol of TICKERS) await expect(page.getByTestId(`coin-panel-${symbol}`)).toHaveCount(0);
});

test("a 31st ticker is refused with the cap text and a 409, the count stays 30", async ({ page, request }) => {
  await open(page);
  const fillers = Array.from({ length: 30 - TICKERS.length }, (_, i) => `FILL${i + 1}`);
  for (const symbol of fillers) {
    const res = await request.post(`${API_BASE_URL}/api/equities`, { data: { symbol } });
    expect(res.ok(), `filler ${symbol}`).toBe(true);
  }
  expect(await tickers(request)).toHaveLength(30);

  const refused = await request.post(`${API_BASE_URL}/api/equities`, { data: { symbol: "SYNX" } });
  expect(refused.status()).toBe(409);
  expect(((await refused.json()) as { detail: string }).detail).toBe(CAP_TEXT);

  await page.getByLabel("Ticker symbol").fill("SYNY");
  await page.getByRole("button", { name: "Add ticker" }).click();
  await expect(page.getByTestId("add-coin-error")).toHaveText(CAP_TEXT);
  await expect(page.getByTestId("coin-panel-SYNY")).toHaveCount(0);
  const after = await tickers(request);
  expect(after).toHaveLength(30);
  expect(after).not.toContain("SYNX");
  expect(after).not.toContain("SYNY");
});

test("new group, rename, move a ticker, reorder groups: all kept after a reload", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "New group" }).click();
  await page.getByLabel("New group name").fill("Watch");
  let saved = layoutSaved(page);
  await page.getByLabel("New group name").press("Enter");
  await saved;
  await expect(group(page, "Watch")).toBeVisible();

  await page.getByRole("button", { name: "Rename group Watch" }).click();
  await page.getByLabel("New name for group Watch").fill("Later");
  saved = layoutSaved(page);
  await page.getByLabel("New name for group Watch").press("Enter");
  await saved;
  await expect(group(page, "Later")).toBeVisible();

  saved = layoutSaved(page);
  await page.getByTestId("move-to-group-SYNB").selectOption({ label: "Later" });
  await saved;
  await expect(group(page, "Later").getByTestId("coin-panel-SYNB")).toBeVisible();

  const before = await groupOrder(page);
  expect(before).toHaveLength(2);
  saved = layoutSaved(page);
  await page.getByRole("button", { name: "Move group Later up" }).click();
  await saved;
  await expect.poll(() => groupOrder(page)).toEqual([before[1], before[0]]);

  await page.reload();
  await expect(group(page, "Later").getByTestId("coin-panel-SYNB")).toBeVisible();
  await expect(group(page, "Main").getByTestId("coin-panel-SYNA")).toBeVisible();
  expect(await groupOrder(page)).toEqual([before[1], before[0]]);
});

test("linked zoom: ctrl-wheel on one small chart zooms the others", async ({ page }) => {
  await open(page);
  const synaPlot = page.getByTestId("coin-panel-SYNA").getByTestId("mini-chart").locator(".simple-lines");
  const synbPlot = page.getByTestId("coin-panel-SYNB").getByTestId("mini-chart").locator(".simple-lines");
  await expect(synaPlot.locator("canvas").first()).toBeVisible();
  await expect(synbPlot.locator("canvas").first()).toBeVisible();
  await expect(synbPlot).toHaveAttribute("data-zoomed", "false");
  await ctrlWheel(page, synaPlot);
  await expect(synaPlot).toHaveAttribute("data-zoomed", "true");
  await expect(synbPlot).toHaveAttribute("data-zoomed", "true");
});

test("spaghetti has no BTC or HYPE entry and a hidden line stays hidden after a reload", async ({ page }) => {
  await open(page);
  const legend = page.getByTestId("spaghetti-legend");
  await expect(legend.getByTestId("spaghetti-toggle-SYNA")).toBeVisible();
  await expect(legend.getByTestId("spaghetti-toggle-BTC")).toHaveCount(0);
  await expect(legend.getByTestId("spaghetti-toggle-HYPE")).toHaveCount(0);
  await expect(legend.locator('[data-reference="true"]')).toHaveCount(0);
  await expect(page.getByTestId(`spaghetti-note-${manifest.equities.thin_ticker}`)).toBeVisible();

  const toggle = legend.getByTestId("spaghetti-toggle-SYNB");
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  const saved = layoutSaved(page);
  await toggle.click();
  await saved;
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await page.reload();
  await expect(page.getByTestId("spaghetti-toggle-SYNB")).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("spaghetti-toggle-SYNA")).toHaveAttribute("aria-pressed", "true");
});

test("the drill-down opens on 1d with RSI and switches to 1w", async ({ page, request }) => {
  const res = await request.get(`${API_BASE_URL}/api/equities/SYNA/chart?timeframe=1d`);
  expect(res.ok()).toBe(true);
  const chart = (await res.json()) as { chart: { rsi: { value: number }[] } };
  expect(chart.chart.rsi.length).toBeGreaterThan(0);

  await open(page);
  await page.getByTestId("open-drilldown-SYNA").click();
  const view = page.getByTestId("drilldown-view");
  await expect(view.getByTestId("drilldown-timeframe-button-1d")).toHaveAttribute("aria-pressed", "true");
  await expect(view.getByTestId("drilldown-timeframe-button-15m")).toHaveCount(0);
  await expect(view.getByTestId("drilldown-rsi-chart").locator("canvas").first()).toBeVisible();
  await expect(view.getByTestId("drilldown-rsi-value")).toHaveText(
    `RSI 14 (1d): ${chart.chart.rsi[chart.chart.rsi.length - 1].value.toFixed(1)}`,
  );

  await view.getByTestId("drilldown-timeframe-button-1w").click();
  await expect(view.getByTestId("drilldown-timeframe-button-1w")).toHaveAttribute("aria-pressed", "true");
  await expect(view.getByTestId("drilldown-rsi-value")).toContainText("RSI 14 (1w)");
  await expect(view.getByTestId("chart-freshness-caption")).toContainText("Latest weekly bar, week of");
});

test("Brussels time: captions are dates only, axis labels are dates, no UTC word on the page", async ({ page }) => {
  await open(page);
  const caption = page.getByTestId("coin-panel-SYNA").getByTestId("chart-freshness-caption");
  await expect(caption).toHaveText(/^Latest daily bar \d{4}-\d\d-\d\d( \(forming\))?$/);
  await expect(page.getByTestId("spaghetti-span")).toContainText("(Brussels time)");

  const plot = page.getByTestId("coin-panel-SYNA").getByTestId("mini-chart").locator(".simple-lines");
  await expect(plot.locator("svg text").first()).toBeVisible();
  const labels = await plot.locator("svg text").allTextContents();
  expect(labels.length).toBeGreaterThan(0);
  for (const label of labels) expect(label).not.toMatch(/\d\d:\d\d|CES?T/);

  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(/\bUTC\b/);
});
