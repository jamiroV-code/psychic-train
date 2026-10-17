/**
 * End-to-end proof for /narrative, the My baskets tab (narrative-baskets S-E2;
 * AC-35/32 UI, AC-42). Baskets are created through the real API (Playwright
 * `request`: the watchlist and layout routes), then the real page reads the
 * real /api/narrative/baskets/attention. Provider data is unreachable in the
 * sandbox, so the attention numbers themselves are asserted only as "a row per
 * basket"; the loading, error, partial and ranking-off states are driven by
 * routed responses and say so.
 *
 * Screenshots go to E2E_SHOT_DIR when set (never into the repo).
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API_BASE_URL = process.env["NEXT_PUBLIC_API_BASE_URL"] ?? "http://127.0.0.1:8001";
const WIDTHS = [375, 768, 1280] as const;
const SHOT_DIR = process.env["E2E_SHOT_DIR"];

interface Group {
  id: string;
  name: string;
  coins: string[];
}

async function resetBaskets(request: APIRequestContext, baskets: Record<string, string[]>): Promise<void> {
  const reset = await request.delete(`${API_BASE_URL}/api/layout/crypto`);
  expect(reset.ok()).toBeTruthy();
  for (const coin of Object.values(baskets).flat()) {
    const added = await request.post(`${API_BASE_URL}/api/watchlist`, { data: { symbol: coin } });
    expect([200, 201, 409]).toContain(added.status());
  }
  const current = await (await request.get(`${API_BASE_URL}/api/layout/crypto`)).json();
  const main: Group = current.groups[0];
  const moved = new Set(Object.values(baskets).flat());
  const groups: Group[] = [
    { ...main, coins: main.coins.filter((c) => !moved.has(c)) },
    ...Object.entries(baskets).map(([name, coins]) => ({ id: name.toLowerCase(), name, coins })),
  ];
  const saved = await request.post(`${API_BASE_URL}/api/layout/crypto`, {
    data: { revision: current.revision, groups, hidden_lines: current.hidden_lines },
  });
  expect(saved.ok(), await saved.text()).toBeTruthy();
}

async function noHorizontalScroll(page: Page): Promise<void> {
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  expect(fits).toBe(true);
}

async function shot(page: Page, name: string, width: number): Promise<void> {
  if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/${name}-${width}.png`, fullPage: true });
}

test.describe("narrative: My baskets", () => {
  test.beforeEach(async ({ request }) => {
    await resetBaskets(request, { Majors: ["BTC", "ETH"], Layer2: ["THIN"] });
  });

  test.afterAll(async ({ request }) => {
    // The removal test deletes ETH from the shared watchlist: put the seed back.
    await request.delete(`${API_BASE_URL}/api/layout/crypto`);
    for (const coin of ["BTC", "ETH", "THIN"]) {
      await request.post(`${API_BASE_URL}/api/watchlist`, { data: { symbol: coin } });
    }
  });

  test("two tabs, 30d default, a row per basket, window switch, coin expand", async ({ page }) => {
    await page.goto("/narrative");
    await expect(page.getByRole("tab")).toHaveText(["My baskets", "Discovery"]);
    await expect(page.getByTestId("attention-window-30")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("attention-row-majors")).toBeVisible();
    await expect(page.getByTestId("attention-row-layer2")).toBeVisible();
    await expect(page.locator("[data-testid='attention-table'] thead th")).toHaveCount(5);

    const refetch = page.waitForResponse((r) => r.url().includes("/baskets/attention?window=90"));
    await page.getByTestId("attention-window-90").click();
    await refetch;
    await expect(page.getByTestId("attention-window-90")).toHaveAttribute("aria-pressed", "true");

    await page.getByRole("button", { name: "Majors" }).last().click();
    await expect(page.getByTestId("attention-coins-majors")).toContainText("BTC");
    await expect(page.getByTestId("attention-coins-majors")).toContainText(/\d of \d sources/);
    await shot(page, "coin-expand", 1280);
  });

  test("Discovery is a one-line placeholder", async ({ page }) => {
    await page.goto("/narrative");
    await page.getByRole("tab", { name: "Discovery" }).click();
    await expect(page.getByTestId("discovery-placeholder")).toBeVisible();
  });

  test("empty: no baskets gives one line and a screener link", async ({ page, request }) => {
    await request.delete(`${API_BASE_URL}/api/layout/crypto`);
    await page.goto("/narrative");
    await expect(page.getByTestId("attention-empty")).toBeVisible();
    await expect(page.getByTestId("attention-empty").getByRole("link")).toHaveAttribute("href", "/screener");
    await shot(page, "empty", 1280);
  });

  test("loading and error states (routed responses)", async ({ page }) => {
    await page.route("**/baskets/attention*", async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.fulfill({ status: 500, body: "{}" });
    });
    await page.goto("/narrative");
    await expect(page.getByTestId("attention-loading")).toBeVisible();
    await shot(page, "loading", 1280);
    await expect(page.getByTestId("attention-error")).toBeVisible();
    await shot(page, "error", 1280);
  });

  test("partial and ranking-off notes (routed responses)", async ({ page }) => {
    const basket = (id: string, over: object) => ({
      id, name: id, score: 40, change: 1, breadth: 0.5, coverage: "covers 2 of 3",
      series: [{ date: "2026-10-01", value: 1 }, { date: "2026-10-02", value: 2 }], coins: [],
      status: "ok", reason: "", universe_size: 3, ...over,
    });
    const body = (baskets: object[]) => ({ window: 30, as_of: "2026-10-16", membership_as_of: "2026-10-10", baskets });
    await page.route("**/baskets/attention*", (route) =>
      route.fulfill({ json: body([basket("A", {}), basket("B", { status: "no-data", score: null })]) }),
    );
    await page.goto("/narrative");
    await expect(page.getByTestId("attention-partial")).toBeVisible();
    await shot(page, "partial", 1280);
    await page.unroute("**/baskets/attention*");
    await page.route("**/baskets/attention*", (route) =>
      route.fulfill({ json: body([basket("A", { status: "no-data", score: null, reason: "reference-missing" })]) }),
    );
    await page.goto("/narrative");
    await expect(page.getByTestId("attention-ranking-off")).toBeVisible();
    await shot(page, "ranking-off", 1280);
  });

  for (const width of WIDTHS) {
    test(`no horizontal scroll at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/narrative");
      await expect(page.getByTestId("attention-row-majors")).toBeVisible();
      await page.getByRole("button", { name: "Majors" }).last().click();
      await noHorizontalScroll(page);
      await shot(page, "ok", width);
    });
  }

  test("removing a coin in the screener names the basket", async ({ page }) => {
    await page.goto("/screener");
    await page.getByRole("button", { name: /remove ETH/i }).first().click();
    await page.getByRole("button", { name: /confirm/i }).first().click();
    await expect(page.getByText(/Basket Majors no longer counts it/)).toBeVisible();
  });
});
