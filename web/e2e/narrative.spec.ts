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

function seededBasket(name: string, over: object) {
  const day = (n: number) => `2026-10-${String(n).padStart(2, "0")}`;
  const mk = (base: number) => Array.from({ length: 10 }, (_, k) => ({ date: day(k + 1), value: base + k * 2 + (k % 3) }));
  const src = (source: string, raw: number | null) => ({
    source, raw, ratio: raw === null ? null : raw / 50, rank: raw === null ? null : 1,
    state: raw === null ? ("unavailable" as const) : ("ok" as const),
  });
  return {
    id: name.toLowerCase(), name, score: name === "Majors" ? 72.4 : 48.1, change: name === "Majors" ? 12.5 : -3.2,
    breadth: name === "Majors" ? 0.8 : 0.5, coverage: "covers 2 of 2", series: mk(name === "Majors" ? 40 : 20),
    coins: name === "Majors"
      ? [
          { symbol: "BTC", score: 80.2, sources_used: 1, sources_total: 2, sources: [src("trends", 61), src("wiki", null)] },
          { symbol: "ETH", score: 64.6, sources_used: 2, sources_total: 2, sources: [src("trends", 44), src("wiki", 38)] },
        ]
      : [{ symbol: "THIN", score: 48.1, sources_used: 2, sources_total: 2, sources: [src("trends", 30), src("wiki", 22)] }],
    status: "ok", reason: "", universe_size: 2, ...over,
  };
}

function seededBody(baskets: object[] = [seededBasket("Majors", {}), seededBasket("Layer2", {})]) {
  return { window: 30, as_of: "2026-10-16", membership_as_of: "2026-10-10", baskets };
}

async function noHorizontalScroll(page: Page): Promise<void> {
  const fits = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  expect(fits).toBe(true);
}

async function shot(page: Page, name: string, width: number, fullPage = true): Promise<void> {
  if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/${name}-${width}.png`, fullPage });
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

  for (const width of WIDTHS) {
    test(`seeded states at ${width}px: no horizontal scroll, screenshots`, async ({ page, request }) => {
      await page.setViewportSize({ width, height: 900 });

      // ok with numbers: routed fixture, baskets still created through the real API.
      await page.route("**/baskets/attention*", (route) => route.fulfill({ json: seededBody() }));
      await page.goto("/narrative");
      await expect(page.getByTestId("attention-row-majors")).toBeVisible();
      await expect(page.getByTestId("attention-row-majors")).toContainText("+12.5");
      await expect(page.getByTestId("attention-row-majors")).toContainText("covers 2 of 2");
      await expect(page.getByTestId("attention-row-majors")).toContainText("80%");
      await expect(page.locator("[data-testid='attention-chart-container'] canvas").first()).toBeVisible();
      await expect(page.getByTestId("attention-membership")).toContainText("membership as of 2026-10-10");
      await noHorizontalScroll(page);
      await shot(page, "ok", width);
      await page.getByRole("button", { name: "Majors" }).last().click();
      await expect(page.getByTestId("attention-coins-majors")).toContainText("BTC");
      await expect(page.getByTestId("coin-source-BTC-trends")).toContainText("61");
      await expect(page.getByTestId("coin-source-BTC-wiki")).toContainText("no data");
      await noHorizontalScroll(page);
      await shot(page, "coin-expand", width);

      // partial: one basket without data.
      await page.unroute("**/baskets/attention*");
      await page.route("**/baskets/attention*", (route) =>
        route.fulfill({ json: seededBody([seededBasket("Majors", {}), seededBasket("Layer2", { status: "no-data", score: null, change: null, breadth: null })]) }),
      );
      await page.goto("/narrative");
      await expect(page.getByTestId("attention-partial")).toBeVisible();
      await expect(page.locator("[data-testid='attention-chart-container'] canvas").first()).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, "partial", width);

      // ranking off: the reference is missing.
      await page.unroute("**/baskets/attention*");
      await page.route("**/baskets/attention*", (route) =>
        route.fulfill({
          json: seededBody([
            seededBasket("Majors", { status: "no-data", score: null, reason: "reference-missing" }),
            seededBasket("Layer2", { status: "no-data", score: null, reason: "reference-missing" }),
          ]),
        }),
      );
      await page.goto("/narrative");
      await expect(page.getByTestId("attention-ranking-off")).toBeVisible();
      await expect(page.locator("[data-testid='attention-chart-container'] canvas").first()).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, "ranking-off", width);

      // loading, then error (routed 500 after a delay).
      await page.unroute("**/baskets/attention*");
      await page.route("**/baskets/attention*", async (route) => {
        await new Promise((r) => setTimeout(r, 1500));
        await route.fulfill({ status: 500, body: "{}" });
      });
      await page.goto("/narrative");
      await expect(page.getByTestId("attention-loading")).toBeVisible();
      await shot(page, "loading", width);
      await expect(page.getByTestId("attention-error")).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, "error", width);

      // empty: no baskets, one line and a screener link.
      await page.unroute("**/baskets/attention*");
      await request.delete(`${API_BASE_URL}/api/layout/crypto`);
      await page.goto("/narrative");
      await expect(page.getByTestId("attention-empty")).toBeVisible();
      await expect(page.getByTestId("attention-empty").getByRole("link")).toHaveAttribute("href", "/screener");
      await noHorizontalScroll(page);
      await shot(page, "empty", width);
    });
  }

  for (const width of WIDTHS) {
    test(`removing a coin in the screener names the basket at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/screener");
      await page.getByRole("button", { name: /remove ETH/i }).first().click();
      await page.getByRole("button", { name: /confirm/i }).first().click();
      const notice = page.getByTestId("board-announcement-visible");
      await expect(notice).toBeVisible();
      await expect(notice).toContainText(/Basket Majors no longer counts it/);
      await notice.scrollIntoViewIfNeeded();
      await noHorizontalScroll(page);
      await shot(page, "removal-notice", width, false);
    });
  }
});

function discoveryBody(over: object = {}) {
  const coin = (symbol: string, change: number, gaining: boolean) => ({
    symbol, change, raw_change: change + 3, gaining, sources_used: 3, sources_gaining: gaining ? 2 : 1,
  });
  const cat = (id: string, name: string, score: number) => ({
    id, name, score, median: score - 1.5, coins_used: 2, gaining_count: 1,
    coins: [coin("AAA", score + 4, true), coin("BBB", score - 4, false)],
  });
  return {
    window: 30, as_of: "2026-10-16", categories_as_of: "2026-10-10", status: "ok", reason: "",
    universe_size: 90, eligible_size: 60,
    categories: [cat("ai", "Artificial Intelligence", 31.2), cat("defi", "Decentralized Finance", 14.8)],
    ...over,
  };
}

test.describe("narrative: Discovery", () => {
  const noData = (reason: string) => discoveryBody({ status: "no-data", reason, categories: [] });
  for (const width of WIDTHS) {
    test(`every state at ${width}px: no horizontal scroll, screenshots`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.route("**/baskets/attention*", (route) => route.fulfill({ json: seededBody() }));
      const open = async () => {
        await page.goto("/narrative");
        await page.getByRole("tab", { name: "Discovery" }).click();
      };

      await page.route("**/api/narrative/discovery*", (route) => route.fulfill({ json: discoveryBody() }));
      await open();
      await expect(page.getByTestId("discovery-row-ai")).toBeVisible();
      await page.getByTestId("discovery-row-ai").getByRole("button").click();
      await expect(page.getByTestId("discovery-coins-ai")).toContainText("AAA");
      await noHorizontalScroll(page);
      await shot(page, "discovery-ok", width);

      await page.getByTestId("discovery-window-7").click();
      await expect(page.getByTestId("discovery-window-7")).toHaveAttribute("aria-pressed", "true");

      for (const reason of ["categories-missing", "reference-missing", "no-attention-data"]) {
        await page.unroute("**/api/narrative/discovery*");
        await page.route("**/api/narrative/discovery*", (route) => route.fulfill({ json: noData(reason) }));
        await open();
        await expect(page.getByTestId(`discovery-nodata-${reason}`)).toBeVisible();
        await noHorizontalScroll(page);
        await shot(page, `discovery-nodata-${reason}`, width);
      }

      await page.unroute("**/api/narrative/discovery*");
      await page.route("**/api/narrative/discovery*", () => new Promise(() => undefined));
      await open();
      await expect(page.getByTestId("discovery-loading")).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, "discovery-loading", width);

      await page.unroute("**/api/narrative/discovery*");
      await page.route("**/api/narrative/discovery*", (route) => route.fulfill({ status: 500, body: "x" }));
      await open();
      await expect(page.getByTestId("discovery-error")).toBeVisible();
      await expect(page.getByTestId("discovery-retry")).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, "discovery-error", width);
    });
  }
});
