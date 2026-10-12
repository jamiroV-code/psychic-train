/**
 * T41 / S5b: the screener layout through the whole stack: RSI readouts,
 * groups, coin moves, add and remove, the 30-coin cap, saved line toggles
 * and an unreadable layout file. Every edit goes through the real API and
 * the real layout.json in the disposable e2e cache.
 *
 * Each test leaves the seeded state behind it (afterEach): the manifest's
 * watchlist in its order and no saved layout. A 60 s live tick may refetch
 * the board in the middle of a test; it must not change the order.
 */
import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8")) as {
  watchlist: string[];
  thin_symbol: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";
const E2E_CACHE_ROOT = path.join(os.tmpdir(), "screener-e2e-cache");
const CAP_TEXT = "Screener is full: 30 coins maximum. Remove a coin to add another.";

async function watchlist(request: APIRequestContext): Promise<string[]> {
  const res = await request.get(`${API_BASE_URL}/api/watchlist`);
  expect(res.ok()).toBe(true);
  return ((await res.json()) as { coins: string[] }).coins;
}

async function restore(request: APIRequestContext) {
  for (const symbol of await watchlist(request)) {
    await request.delete(`${API_BASE_URL}/api/watchlist/${encodeURIComponent(symbol)}`);
  }
  for (const symbol of manifest.watchlist) {
    const res = await request.post(`${API_BASE_URL}/api/watchlist`, { data: { symbol } });
    expect(res.ok(), `re-adding ${symbol}`).toBe(true);
  }
  const reset = await request.delete(`${API_BASE_URL}/api/layout/crypto`);
  expect(reset.ok()).toBe(true);
}

test.afterEach(async ({ request }) => {
  await restore(request);
});

function grid(page: Page): Locator {
  return page.getByTestId("screener-board-grid");
}

async function order(page: Page): Promise<string[]> {
  return grid(page)
    .locator('[data-testid^="coin-panel-"]')
    .evaluateAll((els) => els.map((el) => el.getAttribute("data-testid")!.replace("coin-panel-", "")));
}

function group(page: Page, name: string): Locator {
  return page.getByRole("region", { name, exact: true });
}

function layoutSaved(page: Page) {
  return page.waitForResponse((r) => r.url().endsWith("/api/layout/crypto") && r.request().method() === "POST" && r.ok());
}

async function open(page: Page) {
  await page.goto("/screener");
  for (const symbol of manifest.watchlist) {
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

test("RSI on every box equals the API value; the thin coin is N/A with a reason; rows match in height; the drill-down shows RSI", async ({
  page,
  request,
}) => {
  const res = await request.get(`${API_BASE_URL}/api/screener/board?timeframe=1d`);
  expect(res.ok()).toBe(true);
  const board = (await res.json()) as { coins: { symbol: string; rsi: { value: number | null; reason: string | null } }[] };
  await open(page);

  for (const coin of board.coins) {
    const value = page.getByTestId(`rsi-value-${coin.symbol}`);
    await expect(value).toHaveText(coin.rsi.value === null ? "N/A" : coin.rsi.value.toFixed(1));
    await expect(page.getByTestId(`rsi-readout-${coin.symbol}`)).toContainText("RSI 14 (1d)");
  }
  const thin = page.getByTestId(`rsi-value-${manifest.thin_symbol}`);
  await expect(thin).toHaveText("N/A");
  expect((await thin.getAttribute("title"))?.length ?? 0).toBeGreaterThan(0);

  const btcRow = (await page.getByTestId("rsi-readout-BTC").boundingBox())!;
  const thinRow = (await page.getByTestId(`rsi-readout-${manifest.thin_symbol}`).boundingBox())!;
  expect(Math.abs(btcRow.height - thinRow.height)).toBeLessThan(0.5);

  const chartRes = await request.get(`${API_BASE_URL}/api/screener/BTC/chart?timeframe=4h`);
  const chart = (await chartRes.json()) as { chart: { rsi: { value: number }[] } };
  expect(chart.chart.rsi.length).toBeGreaterThan(0);
  await page.getByTestId("open-drilldown-BTC").click();
  const view = page.getByTestId("drilldown-view");
  await expect(view.getByTestId("drilldown-rsi-chart").locator("canvas").first()).toBeVisible();
  await expect(view.getByTestId("drilldown-rsi-value")).toHaveText(
    `RSI 14 (4h): ${chart.chart.rsi[chart.chart.rsi.length - 1].value.toFixed(1)}`,
  );
});

test("reorder by buttons keeps every zoom, survives a reload, and Enter keeps focus on the button", async ({ page }) => {
  await open(page);
  const spaghetti = page.getByTestId("spaghetti-chart-container").locator(".simple-lines");
  await expect(spaghetti.locator("canvas").first()).toBeVisible();
  await ctrlWheel(page, spaghetti);
  await expect(spaghetti).toHaveAttribute("data-zoomed", "true");

  const btcPlot = page.getByTestId("coin-panel-BTC").getByTestId("mini-chart").locator(".simple-lines");
  const ethPlot = page.getByTestId("coin-panel-ETH").getByTestId("mini-chart").locator(".simple-lines");
  await expect(btcPlot.locator("canvas").first()).toBeVisible();
  await ctrlWheel(page, btcPlot);
  await expect(btcPlot).toHaveAttribute("data-zoomed", "true");
  await expect(ethPlot).toHaveAttribute("data-zoomed", "true");

  expect(await order(page)).toEqual(manifest.watchlist);
  const later = page.getByTestId("move-later-BTC");
  await later.focus();
  const saved = layoutSaved(page);
  await page.keyboard.press("Enter");
  await saved;
  const expected = ["ETH", "BTC", ...manifest.watchlist.filter((s) => s !== "BTC" && s !== "ETH")];
  await expect.poll(() => order(page)).toEqual(expected);
  await expect(page.getByTestId("move-later-BTC")).toBeFocused();
  await expect(page.getByTestId("board-announcer")).toHaveText(/BTC moved later in Main/);
  await expect(btcPlot).toHaveAttribute("data-zoomed", "true");
  await expect(ethPlot).toHaveAttribute("data-zoomed", "true");
  await expect(spaghetti).toHaveAttribute("data-zoomed", "true");

  await page.reload();
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();
  expect(await order(page)).toEqual(expected);
});

test("create, rename, move a coin by the menu, reload, delete the group: the coin goes back", async ({ page }) => {
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
  await page.getByTestId("move-to-group-ETH").selectOption({ label: "Later" });
  await saved;
  await expect(group(page, "Later").getByTestId("coin-panel-ETH")).toBeVisible();

  await page.reload();
  await expect(group(page, "Later").getByTestId("coin-panel-ETH")).toBeVisible();

  saved = layoutSaved(page);
  await page.getByRole("button", { name: "Delete group Later" }).click();
  await saved;
  await expect(group(page, "Later")).toHaveCount(0);
  await expect(group(page, "Main").getByTestId("coin-panel-ETH")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Main", exact: true })).toBeFocused();
});

test("remove ETH with Confirm and add it back: the count, its panel and its spaghetti line go and return without a reload", async ({
  page,
}) => {
  await open(page);
  const n = manifest.watchlist.length;
  await expect(page.getByTestId("coin-count")).toHaveText(`${n} / 30 coins`);
  await expect(page.getByTestId("spaghetti-toggle-ETH")).toBeVisible();

  await page.getByTestId("remove-ETH").click();
  await page.getByTestId("confirm-remove-ETH").click();
  await expect(page.getByTestId("coin-panel-ETH")).toHaveCount(0);
  await expect(page.getByTestId("spaghetti-toggle-ETH")).toHaveCount(0);
  await expect(page.getByTestId("coin-count")).toHaveText(`${n - 1} / 30 coins`);

  await page.getByLabel("Coin symbol").fill("eth");
  await page.getByRole("button", { name: "Add coin" }).click();
  await expect(page.getByTestId("coin-panel-ETH")).toBeVisible();
  await expect(page.getByTestId("spaghetti-toggle-ETH")).toBeVisible();
  await expect(page.getByTestId("coin-count")).toHaveText(`${n} / 30 coins`);
  await expect(page.getByLabel("Coin symbol")).toHaveValue("");
});

test("a 31st coin is refused with the cap message and nothing changes on the board", async ({ page, request }) => {
  await open(page);
  const fillers = Array.from({ length: 30 - manifest.watchlist.length }, (_, i) => `FILL${i + 1}`);
  try {
    for (const symbol of fillers) {
      const res = await request.post(`${API_BASE_URL}/api/watchlist`, { data: { symbol } });
      expect(res.ok(), `filler ${symbol}`).toBe(true);
    }
    expect(await watchlist(request)).toHaveLength(30);
    await page.getByLabel("Coin symbol").fill("SOL");
    await page.getByRole("button", { name: "Add coin" }).click();
    await expect(page.getByTestId("add-coin-error")).toHaveText(CAP_TEXT);
    await expect(grid(page).locator('[data-testid^="coin-panel-"]')).toHaveCount(manifest.watchlist.length);
    const coins = await watchlist(request);
    expect(coins).toHaveLength(30);
    expect(coins).not.toContain("SOL");
  } finally {
    for (const symbol of fillers) {
      await request.delete(`${API_BASE_URL}/api/watchlist/${symbol}`);
    }
  }
});

test("a hidden spaghetti line stays hidden after a reload", async ({ page }) => {
  await open(page);
  const toggle = page.getByTestId("spaghetti-toggle-ETH");
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  const saved = layoutSaved(page);
  await toggle.click();
  await saved;
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await page.reload();
  await expect(page.getByTestId("spaghetti-toggle-ETH")).toHaveAttribute("aria-pressed", "false");
});

test("an unreadable layout file shows the recovered notice and every panel", async ({ page }) => {
  expect(fs.existsSync(path.join(E2E_CACHE_ROOT, "watchlist.json"))).toBe(true);
  fs.writeFileSync(path.join(E2E_CACHE_ROOT, "layout.json"), "{ this is not json", "utf-8");
  await page.goto("/screener");
  await expect(page.getByTestId("layout-notice")).toContainText("The saved layout file was unreadable");
  await expect(grid(page).locator('[data-testid^="coin-panel-"]')).toHaveCount(manifest.watchlist.length);
});
