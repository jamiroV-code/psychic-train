import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { API_BASE_URL, E2E_CACHE_ROOT } from "../playwright.config";
import type { ScreenerBoardResponse, ChartView, DailyDataGap } from "../lib/types/screener";

const repo = path.resolve(__dirname, "../..");
function fixture(action: "repair" | "restore") {
  execFileSync("uv", ["run", "--project", "api", "python", "-m", "api.tests.daily_gap_e2e", action], {
    cwd: repo, env: {
      ...process.env, UV_FROZEN: "1", SCREENER_CACHE_ROOT: E2E_CACHE_ROOT,
      OPENBLAS_NUM_THREADS: "1", OMP_NUM_THREADS: "1", MKL_NUM_THREADS: "1", NUMEXPR_NUM_THREADS: "1",
    }, stdio: "pipe",
  });
}

test("stored daily gaps persist across cache/reload, all widths, and disappear on repair offline", async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  const gap: DailyDataGap = JSON.parse(fs.readFileSync(path.join(E2E_CACHE_ROOT, "manifest.json"), "utf8"));
  const attempts = path.join(E2E_CACHE_ROOT, "attempts.jsonl");
  const localOnly: string[] = [];
  await page.route("**/*", route => {
    const hostname = new URL(route.request().url()).hostname;
    if (!["localhost", "127.0.0.1", ""].includes(hostname)) {
      localOnly.push(route.request().url());
      return route.abort();
    }
    return route.continue();
  });
  const getBoard = async () => {
    const response = await request.get(`${API_BASE_URL}/api/screener/board?timeframe=4h`);
    expect(response.ok()).toBeTruthy();
    return await response.json() as ScreenerBoardResponse;
  };
  const getChart = async () => {
    const response = await request.get(`${API_BASE_URL}/api/screener/BTC/chart?timeframe=4h`);
    expect(response.ok()).toBeTruthy();
    return await response.json() as ChartView;
  };
  const original = await getBoard();
  const beforeChart = await getChart();
  expect(original.coins.find(c => c.symbol === "BTC")?.daily_data_gap).toEqual(gap);
  expect(beforeChart.daily_data_gap).toEqual(gap);
  expect((await getBoard()).coins.find(c => c.symbol === "BTC")?.daily_data_gap).toEqual(gap);
  await page.goto("/screener");
  const btc = page.getByTestId("coin-panel-BTC");
  await expect(btc.getByText("Daily data gap: 3 missing days")).toBeVisible();
  await expect(page.getByTestId("coin-panel-ETH").getByRole("region", { name: "Daily data gap" })).toHaveCount(0);
  await page.reload();
  await expect(btc.getByText("Daily data gap: 3 missing days")).toBeVisible();
  await page.getByTestId("timeframe-button-15m").click();
  await expect(btc.getByText("Daily data gap: 3 missing days")).toBeVisible();
  await page.getByTestId("open-drilldown-BTC").click();
  const drill = page.getByRole("dialog", { name: "BTC drill-down" });
  await expect(drill.getByText("Daily data gap: 3 missing days")).toBeVisible();
  for (const width of [375, 768, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const range of gap.ranges) {
      await expect(drill.getByText(range.start, { exact: true }).first()).toBeVisible();
      if (range.start !== range.end) await expect(drill.getByText(range.end, { exact: true })).toBeVisible();
    }
    await expect(drill.getByText("Missing date ranges (UTC, inclusive):")).toBeVisible();
    const notice = drill.getByRole("region", { name: "Daily data gap" });
    expect(await notice.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`daily-gap-${width}.png`), fullPage: true });
  }
  try {
    fixture("repair");
    const repaired = await getChart();
    expect(repaired.daily_data_gap).toEqual({ missing_days: 0, ranges: [] });
    expect((await getBoard()).coins.find(c => c.symbol === "BTC")?.daily_data_gap?.missing_days).toBe(0);
    await page.reload();
    await expect(btc).toBeVisible();
    await expect(btc.getByText(/Daily data gap:/)).toHaveCount(0);
    expect(repaired.chart.price).toEqual(beforeChart.chart.price);
    expect(repaired.chart.sma).toEqual(beforeChart.chart.sma);
    expect(repaired.chart.rsi).toEqual(beforeChart.chart.rsi);
    await page.getByTestId("open-drilldown-BTC").click();
    await expect(drill).toBeVisible();
    await expect(drill.getByText(/Daily data gap:/)).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath("daily-gap-repaired.png"), fullPage: true });
  } finally {
    fixture("restore");
  }
  expect(fs.readFileSync(attempts, "utf8")).toBe("");
  expect(localOnly).toEqual([]);
  await testInfo.attach("offline-provider-attempts", { body: fs.readFileSync(attempts), contentType: "text/plain" });
});
