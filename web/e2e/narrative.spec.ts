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
  v2: NarrativeV2Facts;
}

/** narrative-v2 RFC-7: the seeder's disposable NARRATIVES_PATH config + variants. */
interface NarrativeV2Facts {
  narratives_path: string;
  base_path: string;
  base_ids: string[];
  variants: Record<string, { path: string; ids: string[] }>;
  mature: string[];
  thin: string[];
  no_data: string[];
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

// --- narrative-v2 RFC-7 (ADR-7 item 5) ------------------------------------
// The API reads NARRATIVES_PATH, a disposable copy of api/data/narratives.json
// under the E2E cache root (the seeder refuses the real file). Specs that swap
// the config always restore the base copy in `finally`.

const v2 = facts.v2;

function writeConfig(json: string): void {
  // Guard: never write outside the seeder's disposable directory.
  expect(path.resolve(v2.narratives_path)).not.toContain(path.join("api", "data", "narratives.json"));
  fs.writeFileSync(v2.narratives_path, json, "utf-8");
}

function restoreBase(): void {
  writeConfig(fs.readFileSync(v2.base_path, "utf-8"));
}

async function waitForV2Views(page: Page): Promise<void> {
  await expect(page.getByTestId("narrative-momentum")).toBeVisible();
  await expect(page.getByTestId("narrative-mindshare")).toBeVisible();
}

test("momentum view is populated: every narrative is ranked or shows why not", async ({ page }) => {
  await openNarrative(page);
  await waitForV2Views(page);
  for (const cid of v2.base_ids) {
    const row = page.getByTestId(`momentum-row-${cid}`);
    const insufficient = page.getByTestId(`momentum-insufficient-${cid}`);
    await expect(row.or(insufficient)).toHaveCount(1);
  }
  await expect(page.getByTestId("narrative-momentum-error")).toHaveCount(0);
});

test("mindshare view is populated for the latest seeded day, with an excluded narrative accounted for", async ({ page }) => {
  await openNarrative(page);
  await waitForV2Views(page);
  await expect(page.getByTestId("mindshare-bar")).toBeVisible();
  for (const cid of ["ai", "l2s", "memecoins"]) {
    await expect(page.getByTestId(`mindshare-row-${cid}`)).toBeVisible();
  }
  await expect(page.getByTestId(`mindshare-excluded-${facts.no_market_category}`)).toBeVisible();
  await expect(page.getByTestId("mindshare-date-picker")).toHaveValue(facts.today);
  await expect(page.getByTestId("narrative-mindshare-error")).toHaveCount(0);
});

test("AC-4: a config file edit (add, rename, remove) shows up without restarting the API", async ({ page }) => {
  const base = JSON.parse(fs.readFileSync(v2.base_path, "utf-8")) as {
    narratives: { id: string; label: string }[];
  };
  const added = v2.variants[String(Math.min(...Object.keys(v2.variants).map(Number)))]!.ids.find(
    (id) => !v2.base_ids.includes(id),
  )!;
  const edited = JSON.parse(fs.readFileSync(v2.variants["15"]!.path, "utf-8")) as typeof base;
  edited.narratives = [
    ...base.narratives
      .filter((n) => n.id !== "memecoins")
      .map((n) => (n.id === "ai" ? { ...n, label: "AI (edited)" } : n)),
    edited.narratives.find((n) => n.id === added)!,
  ];
  try {
    writeConfig(JSON.stringify(edited));
    const body = await openNarrative(page);
    expect(body.categories.map((c) => c.category_id)).toEqual(edited.narratives.map((n) => n.id));
    await expect(page.getByTestId(`narrative-panel-${added}`)).toBeVisible();
    await expect(page.getByTestId("narrative-panel-memecoins")).toHaveCount(0);
    await expect(page.getByTestId("narrative-panel-ai")).toContainText("AI (edited)");
  } finally {
    restoreBase();
  }
  // And back again, still without a restart.
  const body = await openNarrative(page);
  expect(body.categories.map((c) => c.category_id)).toEqual(v2.base_ids);
});

test("AC-8: 15 narratives — every cross-narrative view lists all 15, none silently truncated", async ({ page }) => {
  const fifteen = v2.variants["15"]!;
  expect(fifteen.ids).toHaveLength(15);
  try {
    writeConfig(fs.readFileSync(fifteen.path, "utf-8"));
    const body = await openNarrative(page);
    await waitForV2Views(page);
    expect(body.categories.map((c) => c.category_id)).toEqual(fifteen.ids);
    // History panels: 10-panel soft cap + an overflow listing the other 5.
    await expect(page.getByTestId("narrative-overflow-toggle")).toContainText("+5 more");
    // Comparison and change-in-attention: one row per narrative.
    await expect(page.getByTestId("narrative-comparison").locator("tbody tr")).toHaveCount(15);
    expect(body.change_in_attention.entries).toHaveLength(15);
    // Momentum: every narrative ranked or explicitly insufficient.
    for (const cid of fifteen.ids) {
      await expect(page.getByTestId(`momentum-row-${cid}`).or(page.getByTestId(`momentum-insufficient-${cid}`))).toHaveCount(1);
    }
    for (const cid of v2.mature) {
      await expect(page.getByTestId(`momentum-row-${cid}`)).not.toHaveAttribute("data-rank", "");
      await expect(page.getByTestId(`momentum-arrow-${cid}`)).not.toBeEmpty();
    }
    for (const cid of [...v2.thin, ...v2.no_data]) {
      await expect(page.getByTestId(`momentum-insufficient-${cid}`)).toBeVisible();
    }
    // Mindshare: every narrative has a row or an explicit exclusion.
    for (const cid of fifteen.ids) {
      await expect(page.getByTestId(`mindshare-row-${cid}`).or(page.getByTestId(`mindshare-excluded-${cid}`))).toHaveCount(1);
    }
    for (const cid of v2.no_data) {
      await expect(page.getByTestId(`mindshare-excluded-${cid}`)).toBeVisible();
    }
    // Still exactly one caveat with 15 narratives (AC-12).
    await expect(page.getByTestId("narrative-caveat")).toHaveCount(1);
  } finally {
    restoreBase();
  }
});

test("home page links to the narrative dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("home-link-narrative").click();
  await expect(page).toHaveURL(/\/narrative$/);
  await expect(page.getByTestId("narrative-dashboard")).toBeVisible();
});
