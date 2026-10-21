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
      await expect(page.getByTestId("attention-error")).not.toContainText("/api");
      await expect(page.getByTestId("attention-retry")).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, "error", width);

      // as shipped: the real API, no probe records, so no scores and no series (F-5).
      await page.unroute("**/baskets/attention*");
      await page.goto("/narrative");
      await expect(page.getByTestId("attention-nodata")).toBeVisible();
      await expect(page.getByRole("group", { name: "Baskets shown" })).toHaveCount(0);
      await noHorizontalScroll(page);
      await shot(page, "as-shipped", width);

      // empty: no baskets, one line and a screener link.
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
  const coin = (symbol: string, change: number, trigger: boolean, thin = false) => ({
    symbol, change, raw_change: change + 3, covered_weight: 35, rising_weight: trigger ? 25 : 0, trigger,
    primary: true, volume_24h: thin ? 4_000_000 : 900_000_000, thin_volume: thin, tradeability: "unverified",
    sources: [
      { source: "wikipedia", change: change + 20, as_of: "2026-10-15" },
      { source: "exchange_activity", change: -12, as_of: "2026-10-15" },
      { source: "trends", change: 4, as_of: "2026-10-14" },
    ],
  });
  const cat = (id: string, name: string, score: number) => ({
    id, name, score, median: score - 1.5, coins_used: 2, gaining_count: 1, ranked: true,
    coins: [coin("AAA", score + 4, true), coin("BBB", score - 4, false, true)],
  });
  const idle = (id: string, name: string) => ({ id, name, score: null, median: null, coins_used: 0, gaining_count: 0, ranked: false, coins: [] });
  const tiny = { ...cat("oracle", "Oracles", 50), coins_used: 1, ranked: false, coins: [coin("LINK", 54, true)] };
  return {
    window: 30, as_of: "2026-10-16", categories_as_of: "2026-10-10", status: "ok", reason: "",
    universe_size: 100, eligible_size: 81, shown_size: 54,
    excluded: { exclusion_list: 23, below_volume_floor: 0, no_category: 4, no_source_data: 19 },
    excluded_counts: { "no-source-data": 19, stablecoin: 16, "no-market": 7, unassigned: 4 },
    excluded_coins: [
      ...["USDT", "USDC", "USDE", "DAI", "USD1", "PYUSD", "FDUSD", "USDG", "RLUSD", "U", "USDS", "TUSD", "USDF", "BUSD", "GHO", "FRAX"]
        .map((symbol) => ({ symbol, reason: "stablecoin", detail: "stablecoin" })),
      ...["BUIDL", "USYC", "OUSG", "USTB", "BENJI", "JTRSY", "WTGXX"].map((symbol) => ({ symbol, reason: "no-market", detail: "tokenized fund" })),
      ...["M", "GRAM", "AKE", "PRL"].map((symbol) => ({ symbol, reason: "unassigned", detail: "" })),
      ...Array.from({ length: 19 }, (_, i) => ({ symbol: `NOSRC${i + 1}`, reason: "no-source-data", detail: "" })),
    ],
    narratives_status: "reviewed", unassigned: ["M", "GRAM", "AKE", "PRL"],
    hidden_narratives: [{ id: "privacy", name: "Privacy", coins: ["XMR", "ZEC"] }],
    min_category_coins: 3, rising_threshold_pct: 10, min_covered_weight: 30,
    categories: [
      cat("ai", "Artificial Intelligence", 31.2), cat("defi", "Decentralized Finance", 14.8), tiny,
      idle("gaming", "Gaming"), idle("rwa", "Real World Assets"),
    ],
    ...over,
  };
}

function sourcesBody() {
  const row = (id: string, label: string, weight: number | null, state: string, over: object = {}) => ({
    id, label, kind: "weighted", weight, state, newest: state === "ok" ? "2026-10-17" : null,
    history_days: state === "ok" ? 99 : 0, coins_with_data: state === "ok" ? 38 : 0, eligible_size: 50, note: "", ...over,
  });
  return {
    as_of: "2026-10-17", universe_size: 90, eligible_size: 50, live_sources: 2, total_sources: 7, live_weight: 35,
    newest: "2026-10-17",
    sources: [
      row("wikipedia", "Wikipedia pageviews", 25, "ok"),
      row("trends", "Google Trends", 25, "not-probed", { note: "not probed yet" }),
      row("xsearch", "X search", 10, "off", { note: "X search is off (X_LIVE not set): dry run only" }),
      row("exchange_activity", "Exchange activity", 10, "ok", { note: "12 of 38 coins use the CoinGecko volume fallback" }),
      row("hyperliquid", "Hyperliquid volume", 20, "insufficient-history", { kind: "exchange-member", history_days: 1, note: "insufficient history 1/90" }),
    ],
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
      await page.route("**/api/narrative/sources", (route) => route.fulfill({ json: sourcesBody() }));
      await open();
      await expect(page.getByTestId("discovery-row-ai")).toBeVisible();
      await expect(page.getByTestId("sources-summary")).toContainText("Sources: 2 of 7 live, 35 of 100 weight, newest data 2026-10-17");
      await expect(page.getByTestId("discovery-coverage")).toContainText(
        "54 of 100 top coins shown, 46 excluded: 19 no source data, 16 stablecoins, 7 tokenized funds / no market, 4 unassigned",
      );
      await expect(page.getByTestId("discovery-proposed-banner")).toHaveCount(0);
      await page.getByTestId("discovery-exclusions-toggle").click();
      await expect(page.getByTestId("discovery-excluded-stablecoin")).toContainText("USDT");
      await expect(page.getByTestId("discovery-unassigned")).toContainText("4 unassigned coins");
      await expect(page.getByTestId("discovery-hidden")).toContainText("1 hidden narrative");
      await expect(page.getByTestId("discovery-tab")).not.toContainText(/floor|exchange tokens/i);
      await expect(page.getByTestId("discovery-unranked")).toContainText("Too few coins to rank (need 3)");
      await expect(page.getByTestId("discovery-row-oracle")).toHaveCount(0);
      await page.getByTestId("sources-summary").click();
      await expect(page.getByTestId("sources-row-trends")).toContainText("not probed");
      await noHorizontalScroll(page);
      await shot(page, "discovery-sources-open", width);
      await page.getByTestId("sources-summary").click();
      await page.getByTestId("discovery-row-ai").getByRole("button").click();
      await expect(page.getByTestId("discovery-coins-ai")).toContainText("AAA");
      await expect(page.getByTestId("discovery-coins-ai")).toContainText("Wiki +");
      await expect(page.getByTestId("discovery-coins-ai")).toContainText("35 / 100");
      await expect(page.getByTestId("discovery-thin-ai-BBB")).toContainText("thin volume");
      await expect(page.getByTestId("discovery-thin-ai-AAA")).toHaveCount(0);
      await expect(page.getByTestId("discovery-empty-categories")).toContainText("2 categories without data");
      await expect(page.getByTestId("discovery-as-of")).toContainText("as of 2026-10-16");
      await noHorizontalScroll(page);
      await shot(page, "discovery-ok", width);

      await page.getByTestId("discovery-window-7").click();
      await expect(page.getByTestId("discovery-window-7")).toHaveAttribute("aria-pressed", "true");

      for (const reason of ["reference-missing", "no-attention-data"]) {
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

/** No two SVG labels in the history chart may overlap, and none may leave the plot's box. */
async function expectNoTextOverlap(page: Page) {
  const result = await page.getByTestId("history-plot").evaluate((plot) => {
    const box = plot.getBoundingClientRect();
    const rects = Array.from(plot.querySelectorAll("svg text")).map((t) => {
      const r = t.getBoundingClientRect();
      return { text: t.textContent ?? "", l: r.left, r: r.right, t: r.top, b: r.bottom };
    });
    const overlaps: string[] = [];
    for (let i = 0; i < rects.length; i += 1) {
      const a = rects[i];
      if (a.l < box.left - 1 || a.r > box.right + 1) overlaps.push(`clipped: ${a.text}`);
      for (let j = i + 1; j < rects.length; j += 1) {
        const c = rects[j];
        if (a.l < c.r && c.l < a.r && a.t < c.b && c.t < a.b) overlaps.push(`${a.text} x ${c.text}`);
      }
    }
    return overlaps;
  });
  expect(result).toEqual([]);
}

function historyBody(kind: "coin" | "category") {
  const dates = Array.from({ length: 30 }, (_, i) => new Date(Date.UTC(2026, 8, 16 + i)).toISOString().slice(0, 10));
  const base = { id: kind === "coin" ? "AAA" : "ai", window: 30, as_of: dates[29], status: "ok", reason: "", min_history_days: 30, min_covered_weight: 30, history_days: { wikipedia: 99 } };
  if (kind === "category") {
    return { ...base, kind, days: dates.map((date, i) => ({ date, score: 4 + i * 0.8, coins_used: 5, triggered_count: i % 4, triggered_share: (i % 4) / 5 })) };
  }
  return {
    ...base, kind,
    days: dates.map((date, i) => ({
      date, score: Math.sin(i / 4) * 12 + i * 0.9, covered_weight: i < 8 ? 10 : 35, rising_weight: i < 8 ? 0 : 25,
      trigger: i > 20 && i % 3 === 0, thin: i < 8,
    })),
  };
}

test.describe("narrative: Discovery history chart", () => {
  for (const width of [1280, 375] as const) {
    test(`coin and category charts at ${width}px (routed data)`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      await page.route("**/baskets/attention*", (route) => route.fulfill({ json: seededBody() }));
      await page.route("**/api/narrative/discovery?*", (route) => route.fulfill({ json: discoveryBody() }));
      await page.route("**/api/narrative/sources", (route) => route.fulfill({ json: sourcesBody() }));
      const history: string[] = [];
      await page.route("**/api/narrative/discovery/history*", (route) => {
        const url = new URL(route.request().url());
        history.push(`${url.searchParams.get("symbol") ?? url.searchParams.get("category")}:${url.searchParams.get("window")}`);
        return route.fulfill({ json: historyBody(url.searchParams.has("symbol") ? "coin" : "category") });
      });
      await page.route("**/api/narrative/discovery/price*", (route) => {
        const dates = historyBody("coin").days.map((d) => d.date);
        return route.fulfill({ json: { symbol: "AAA", window: 30, status: "ok", last_date: dates[29], days: dates.map((date, i) => ({ date, close: 100 + i * 2 })) } });
      });

      await page.goto("/narrative");
      await page.getByRole("tab", { name: "Discovery" }).click();
      await page.getByTestId("discovery-row-ai").getByRole("button").click();
      await expect(page.getByTestId("history-share-line")).toBeVisible();
      await expect(page.getByTestId("history-readout")).toContainText("coins used 5");
      await expect(page.getByTestId("history-panel-share")).toBeVisible();
      await expectNoTextOverlap(page);
      await page.getByTestId("history-plot").scrollIntoViewIfNeeded();
      await noHorizontalScroll(page);
      await shot(page, "discovery-history-category", width);

      await page.getByTestId("discovery-coin-ai-AAA").click();
      await expect(page.getByTestId("history-band")).toBeVisible();
      await expect(page.getByTestId("history-panel-title-coverage")).toHaveText("Data coverage (weight of sources with data, out of 100)");
      await expect(page.getByText("needs 30 to fire")).toBeVisible();
      await expect(page.getByTestId("history-price-line")).toBeVisible();
      expect(await page.getByTestId("history-trigger-marker").count()).toBeGreaterThan(0);
      await expectNoTextOverlap(page);
      await expect(page.getByTestId("history-weight-note")).toContainText("Early days have little history");
      await page.getByTestId("history-plot").focus();
      await page.keyboard.press("Home");
      await expect(page.getByTestId("history-readout")).toContainText("thin");

      await page.getByTestId("discovery-window-90").click();
      await page.getByTestId("discovery-row-ai").getByRole("button").click();
      await page.getByTestId("discovery-coin-ai-AAA").click();
      await expect(page.getByTestId("history-band")).toBeVisible();
      await expectNoTextOverlap(page);
      expect(history).toContain("AAA:90");
      await page.getByTestId("history-plot").scrollIntoViewIfNeeded();
      await noHorizontalScroll(page);
      await shot(page, "discovery-history-coin", width);
    });
  }
});
