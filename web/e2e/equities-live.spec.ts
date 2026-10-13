/**
 * T50 / S9E: the equities freshness strip on the seeded stack. The e2e API
 * runs with its workers off (SCREENER_REFRESH_WORKER=0, an empty
 * LSE_API_KEY), so the strip names the off reason and shows the latest daily
 * bar date the API reads from the seeded cache. Nothing reaches the data
 * vendor. The stale marker is not asserted (A6).
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

const OFF_WORDS: Record<string, string> = {
  "SCREENER_REFRESH_WORKER=0": "switched off by SCREENER_REFRESH_WORKER=0",
  "missing-key": "no market data key is set on the server",
};

async function equitiesStatus(request: APIRequestContext) {
  const res = await request.get(`${API_BASE_URL}/api/equities/status`);
  expect(res.ok()).toBe(true);
  return (await res.json()) as { running: boolean; disabled_reason: string | null; last_bar_date: string | null };
}

test("the strip shows the latest daily bar date and why the refresh is off", async ({ page, request }) => {
  const status = await equitiesStatus(request);
  expect(status.running).toBe(false);
  expect(status.last_bar_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  const words = OFF_WORDS[status.disabled_reason ?? ""];
  expect(words, `known off reason ${status.disabled_reason}`).toBeTruthy();

  await page.goto("/equities");
  const strip = page.getByTestId("freshness-strip");
  await expect(strip.getByTestId("strip-last-bar")).toHaveText(`Latest daily bar ${status.last_bar_date}`);
  await expect(strip).toContainText(
    `Automatic market-close refresh is off (${words}). This page still re-checks every minute.`,
  );
  await expect(strip.getByTestId("strip-help")).toContainText("about 30 min after the 16:00 New York close");
});

test("with the worker off nothing reads overdue", async ({ page }) => {
  await page.goto("/equities");
  const strip = page.getByTestId("freshness-strip");
  await expect(strip.getByTestId("strip-checked")).toBeVisible();
  await expect(strip.getByTestId("strip-overdue")).toHaveCount(0);
  await expect(strip).not.toContainText("overdue: expected");
});
