/**
 * End-to-end proof for /narrative (narrative dashboard plan RFC-6; AC-1, AC-2,
 * AC-4..AC-11 automated part; AC-3 and AC-12 are user-run on a real machine).
 *
 * Real browser, real Next.js page, real API client, real FastAPI `/history`
 * route, real DuckDB reads. `seed_e2e_cache.py::seed_narrative` writes the
 * narrative archive through the production cache writers. Every expectation
 * (ranks, signs, dates, counts) comes from the seeder's manifest, where it is
 * hand-derived from the seeded shape. Nothing is retyped here, and no
 * assertion depends on a raw value for "today".
 *
 * Not covered here: the 10-panel soft cap and its "+N more" overflow. `/history`
 * can only return the 4 fixed seed categories (unknown ids are a 422), so the
 * cap cannot be reached end to end. It is unit-tested in vitest
 * (NarrativeDashboard.test.tsx, narrative-view-model.test.ts).
 *
 * Ordering: the `/screener` AC-1 check is LAST. `/screener`'s NarrativeStrip
 * calls `/categories`, which may write live pytrends/coingecko rows into the
 * same cache when the network is reachable.
 */
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

interface RankFact {
  category_id: string;
  rank: number | null;
  reason?: string;
  sign?: number;
}

interface NarrativeFacts {
  today: string;
  day_minus_1: string;
  category_ids: string[];
  gap: { category: string; series: string; gap_date: string };
  ai_chart_points: number;
  ai_mixed_scale_points: number;
  ai_new_listings: number;
  ai_legacy_count: number;
  narrative_only_symbol: string | null;
  comparison: RankFact[];
  change: RankFact[];
  no_market_category: string;
}

interface HistoryPoint {
  date: string;
  raw_value: number | null;
  point_status: string | null;
  reason: string | null;
  gap_before: boolean;
}

interface HistoryResponse {
  redistributable_all: boolean;
  categories: {
    category_id: string;
    series: { source: string; variant: string | null; status: string; reason: string | null; points: HistoryPoint[] }[];
    composite: { status: string; points: { date: string; mixed_scale: boolean; gap_before: boolean }[] };
  }[];
  comparison: { as_of: string | null; entries: { category_id: string; rank: number | null; reason: string | null }[] };
  change_in_attention: { entries: { category_id: string; rank: number | null; delta: number | null; reason: string | null }[] };
}

const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8")) as {
  narrative: NarrativeFacts;
};
const facts = manifest.narrative;

async function openNarrative(page: Page): Promise<HistoryResponse> {
  const responsePromise = page.waitForResponse((r) => r.url().includes("/api/narrative/history"));
  await page.goto("/narrative");
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  await expect(page.getByTestId("narrative-dashboard")).toBeVisible();
  await expect(page.getByTestId("narrative-history")).toBeVisible();
  return (await response.json()) as HistoryResponse;
}

function series(body: HistoryResponse, cid: string, source: string, variant: string | null = null) {
  const cat = body.categories.find((c) => c.category_id === cid);
  expect(cat, `category ${cid} in /history`).toBeDefined();
  const s = cat!.series.find((x) => x.source === source && (x.variant ?? null) === variant);
  expect(s, `${cid} ${source} ${variant ?? ""}`).toBeDefined();
  return s!;
}

test("page loads from a real request with the data-quality caveat shown exactly once", async ({ page }) => {
  await openNarrative(page);
  await expect(page.getByTestId("narrative-caveat")).toHaveCount(1);
  await expect(page.getByTestId("narrative-caveat")).toBeVisible();
  await expect(page.getByTestId("narrative-error")).toHaveCount(0);
  await expect(page.getByTestId("narrative-empty")).toHaveCount(0);
});

test("one panel per seed category; charted categories have points, rwa shows its unavailable composite", async ({ page }) => {
  await openNarrative(page);
  for (const cid of facts.category_ids) {
    await expect(page.getByTestId(`narrative-panel-${cid}`)).toBeVisible();
  }
  for (const cid of ["ai", "l2s", "memecoins"]) {
    const points = Number(await page.getByTestId(`narrative-chart-${cid}`).getAttribute("data-points"));
    expect(points, `${cid} data-points`).toBeGreaterThan(0);
    await expect(page.getByTestId(`narrative-chart-${cid}`).locator("canvas").first()).toBeVisible();
  }
  await expect(page.getByTestId("narrative-chart-ai")).toHaveAttribute("data-points", String(facts.ai_chart_points));
  await expect(page.getByTestId(`narrative-composite-notice-${facts.no_market_category}`)).toBeVisible();
  // 4 seed categories < 10-panel cap: no overflow (cap itself is unit-tested only).
  await expect(page.getByTestId("narrative-overflow-toggle")).toHaveCount(0);
});

test("the seeded hole is flagged gap_before by the API on exactly the manifest date", async ({ page }) => {
  const body = await openNarrative(page);
  const nightly = series(body, facts.gap.category, "pytrends", "nightly-7d");
  const flagged = nightly.points.filter((p) => p.gap_before).map((p) => p.date);
  expect(flagged).toEqual([facts.gap.gap_date]);
  await expect(page.getByTestId(`narrative-legend-${facts.gap.category}-pytrends-nightly-7d`)).toBeVisible();
});

test("nightly and backfilled pytrends are separate lines", async ({ page }) => {
  const body = await openNarrative(page);
  await expect(page.getByTestId("narrative-legend-ai-pytrends-nightly-7d")).toBeVisible();
  await expect(page.getByTestId("narrative-legend-ai-pytrends-backfill-269d")).toContainText("backfill");
  const backfill = series(body, "ai", "pytrends", "backfill-269d");
  expect(backfill.points.every((p) => p.point_status === "backfilled")).toBe(true);
});

test("mixed-scale composite points are marked, and today's rankings are not mixed", async ({ page }) => {
  await openNarrative(page);
  await expect(page.getByTestId("narrative-mixed-scale-ai")).toHaveAttribute("data-count", String(facts.ai_mixed_scale_points));
  await expect(page.getByTestId(/^narrative-comparison-mixed-/)).toHaveCount(0);
});

test("legacy-map count is labelled as excluded from the composite", async ({ page }) => {
  await openNarrative(page);
  const legacy = page.getByTestId("narrative-legacy-count-ai");
  await expect(legacy).toContainText("legacy-map count");
  await expect(legacy).toContainText("excluded from the composite");
});

test("a narrative-only coin is labelled", async ({ page }) => {
  test.skip(!facts.narrative_only_symbol, "curated map has no narrative-only ai coin");
  await openNarrative(page);
  const coin = page.getByTestId(`narrative-coin-ai-${facts.narrative_only_symbol}`);
  await expect(coin).toHaveAttribute("data-narrative-only", "true");
  await expect(coin).toContainText("narrative-only");
});

test("personal-use badge shows on the page and on every panel", async ({ page }) => {
  const body = await openNarrative(page);
  expect(body.redistributable_all).toBe(false);
  await expect(page.getByTestId("narrative-redistribution-badge")).toContainText("Personal use only");
  for (const cid of facts.category_ids) {
    await expect(page.getByTestId(`narrative-redistribution-${cid}`)).toBeVisible();
  }
});

test("comparison ranks match the hand-derived order; a null rank shows — with a reason", async ({ page }) => {
  const body = await openNarrative(page);
  expect(body.comparison.as_of).toBe(facts.today);
  expect(body.comparison.entries.map((e) => [e.category_id, e.rank])).toEqual(
    facts.comparison.map((e) => [e.category_id, e.rank]),
  );
  const rows = page.getByTestId("narrative-comparison").locator("tbody tr");
  await expect(rows).toHaveCount(facts.comparison.length);
  for (const [i, expected] of facts.comparison.entries()) {
    const row = rows.nth(i);
    await expect(row).toHaveAttribute("data-testid", `narrative-comparison-row-${expected.category_id}`);
    await expect(row).toHaveAttribute("data-rank", expected.rank === null ? "" : String(expected.rank));
    if (expected.rank === null) {
      await expect(row.locator("td").first()).toHaveText("—");
      await expect(row.locator("td").nth(2)).toHaveText("—");
      await expect(row).toContainText("Unranked");
    }
  }
});

test("change-in-attention signs match; a null delta shows — with its reason", async ({ page }) => {
  const body = await openNarrative(page);
  const byId = new Map(body.change_in_attention.entries.map((e) => [e.category_id, e]));
  for (const expected of facts.change) {
    const got = byId.get(expected.category_id)!;
    expect(got.rank, `${expected.category_id} change rank`).toBe(expected.rank);
    const cell = page.getByTestId(`change-delta-${expected.category_id}`);
    if (expected.rank === null) {
      expect(got.delta).toBeNull();
      expect(got.reason).toBe(expected.reason);
      await expect(cell).toHaveText("—");
    } else {
      expect(Math.sign(got.delta!)).toBe(expected.sign);
      await expect(cell).toHaveText(expected.sign! > 0 ? /^\+/ : /^[-−]/);
    }
  }
  await expect(page.getByTestId("narrative-change-row-l2s")).toContainText("No change");
});

test("Hyperliquid: volume share line, new listings, no-baseline-yet on day 1, no-market reason", async ({ page }) => {
  const body = await openNarrative(page);
  await expect(page.getByTestId("narrative-legend-ai-exchange_volume_share")).toBeVisible();
  await expect(page.getByTestId("narrative-new-listings-ai")).toContainText(`${facts.ai_new_listings} (as of ${facts.today})`);
  const listings = series(body, "ai", "exchange_new_listings");
  const first = listings.points.find((p) => p.date === facts.day_minus_1)!;
  expect(first.raw_value).toBeNull();
  expect(first.reason).toBe("no-baseline-yet");
  const noMarket = series(body, facts.no_market_category, "exchange_volume_share");
  expect(noMarket.points.every((p) => p.raw_value === null && p.reason === "no-hyperliquid-market")).toBe(true);
});

test("reddit is unavailable (no archived data) and the other sources still render", async ({ page }) => {
  const body = await openNarrative(page);
  const reddit = series(body, "ai", "reddit");
  expect([reddit.status, reddit.reason]).toEqual(["unavailable", "no-archived-data"]);
  await expect(page.getByTestId("narrative-notice-ai-reddit")).toContainText("no archived data");
  await expect(page.getByTestId("narrative-legend-ai-coingecko-narrative")).toBeVisible();
});

test("home page links to the narrative dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("home-link-narrative").click();
  await expect(page).toHaveURL(/\/narrative$/);
  await expect(page.getByTestId("narrative-dashboard")).toBeVisible();
});

// LAST on purpose — see the file header.
test("AC-1: /screener's NarrativeStrip still renders", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/screener");
  const strip = page.getByTestId("narrative-strip");
  await expect(strip).toBeVisible();
  await expect(strip.getByTestId("narrative-loading")).toHaveCount(0, { timeout: 90_000 });
});
