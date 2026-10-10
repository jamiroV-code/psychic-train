/**
 * T42 / S11a: every time /screener shows is Brussels wall time with CET or
 * CEST, whatever the browser's own zone and locale. The browser here runs in
 * Tokyo with a Japanese locale, so any label that leaked the browser zone
 * would read nine or seven hours off.
 *
 * Expected values come from an arithmetic oracle (the EU rule: summer time
 * from the last Sunday of March 01:00Z to the last Sunday of October 01:00Z),
 * never from Intl, so the oracle cannot share a bug with the page.
 */
import { expect, test } from "@playwright/test";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

const OLD_STATUS_KEYS = [
  "running",
  "disabled_reason",
  "interval_seconds",
  "last_tick_started",
  "last_tick_finished",
  "last_tick_ok",
  "last_tick_failed",
  "next_tick_at",
  "queue_depth",
  "backoff_seconds",
];

test.use({ timezoneId: "Asia/Tokyo", locale: "ja-JP" });

/** 01:00Z on the last Sunday of `month` (0-based) in `year`. */
function lastSundayOneZ(year: number, month: number): number {
  const lastDay = new Date(Date.UTC(year, month + 1, 0));
  return Date.UTC(year, month, lastDay.getUTCDate() - lastDay.getUTCDay(), 1);
}

/** `2026-10-03 16:15 CEST` for an ISO instant, by the EU rule alone. */
function brusselsOracle(iso: string): string {
  const t = Date.parse(iso);
  const year = new Date(t).getUTCFullYear();
  const summer = t >= lastSundayOneZ(year, 2) && t < lastSundayOneZ(year, 9);
  const wall = new Date(t + (summer ? 2 : 1) * 3_600_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${wall.getUTCFullYear()}-${pad(wall.getUTCMonth() + 1)}-${pad(wall.getUTCDate())} ` +
    `${pad(wall.getUTCHours())}:${pad(wall.getUTCMinutes())} ${summer ? "CEST" : "CET"}`
  );
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test("BTC caption equals the oracle's Brussels time under a Tokyo browser", async ({ page, request }) => {
  const res = await request.get(`${API_BASE_URL}/api/screener/board?timeframe=1d`);
  expect(res.ok()).toBe(true);
  const body = (await res.json()) as { coins: { symbol: string; chart: { last_bar_ts: string | null } }[] };
  const lastBar = body.coins.find((c) => c.symbol === "BTC")?.chart.last_bar_ts;
  expect(lastBar, "BTC 1d last_bar_ts missing from the seeded board").toBeTruthy();

  await page.goto("/screener");
  const caption = page.getByTestId("coin-panel-BTC").getByTestId("chart-freshness-caption");
  await expect(caption).toHaveText(new RegExp(`^Last bar ${escapeRegExp(brusselsOracle(lastBar!))}(,| \\(|$)`));
});

test("/screener shows no UTC word, Brussels span lines and a zoned 1d chip title", async ({ page }) => {
  await page.goto("/screener");
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();
  await expect(page.getByTestId("spaghetti-span")).toContainText("(Brussels time)");
  await expect(page.getByTestId("btc-leg-span")).toContainText("(Brussels time)");

  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(/\bUTC\b/);

  const title = await page.getByTestId("coin-panel-BTC").getByTestId("gain-chip-1d").getAttribute("title");
  expect(title ?? "").toMatch(/candle from \d{4}-\d\d-\d\d \d\d:\d\d (CET|CEST)/);
});

test("refresh status carries a Z server_time near the host clock", async ({ request }) => {
  const res = await request.get(`${API_BASE_URL}/api/refresh/status`);
  expect(res.ok()).toBe(true);
  const body = (await res.json()) as Record<string, unknown>;

  for (const key of OLD_STATUS_KEYS) expect(body, `status lost ${key}`).toHaveProperty(key);
  const serverTime = body["server_time"];
  expect(typeof serverTime).toBe("string");
  expect(serverTime as string).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
  expect(Math.abs(Date.parse(serverTime as string) - Date.now())).toBeLessThan(120_000);
});
