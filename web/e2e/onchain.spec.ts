/**
 * End-to-end proof for /onchain (chain participant growth plan RFC-6; the
 * automated part of AC-1..AC-13. AC-14 is the user's real-archive walkthrough).
 *
 * Real browser, real Next.js page, real API client, real FastAPI
 * `/api/onchain/growth`, real DuckDB reads. `seed_e2e_cache.py::seed_onchain`
 * writes the archive through `cache.merge_onchain_series` only. Every
 * expectation (dates, states, ids, divergence) comes from the seeder's
 * manifest; nothing is retyped here. Series dates are fixed (seed "today"
 * 2026-09-26); only the fetch stamps use the real clock, so the stale badge's
 * "10 days" is deterministic within a run.
 *
 * `/onchain` never contacts a provider and never writes to the cache, so the
 * order of these tests relative to the other specs does not matter.
 */
import { expect, test, type Page, type Response } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

interface ChainFact {
  label: string;
  launch_date: string;
  pre_launch_points: number;
  state: string;
  has_transactions: boolean;
}

interface OnchainFacts {
  seed_today: string;
  default_start: string;
  start_2y: string;
  live_ids: string[];
  unavailable_ids: string[];
  chains: Record<string, ChainFact>;
  designed: { chain: string; events: { floor_date: string; ramp_date: string }[] };
  gap: { chain: string; gap_before_date: string };
  stale: { chain: string; days: number };
  limited: { chain: string; gate_met_on: string; history_days: number; rebase_date: string };
  cross_check: { chains: string[]; divergence_pct: number };
  no_tx_archive: { chain: string; reason: string };
  attribution: string;
  attribution_url: string;
}

interface GrowthResponse {
  metric: string;
  grid_dates: string[];
  chains: {
    id: string;
    status: string;
    unavailable_reason: string | null;
    floor_ramp: { state: string; events: { floor_date: string; ramp_date: string }[] } | null;
  }[];
  comparison: { start_date: string };
}

const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8")) as {
  onchain: OnchainFacts;
};
const facts = manifest.onchain;

const isGrowth = (r: Response) => r.url().includes("/api/onchain/growth");

async function openOnchain(page: Page): Promise<GrowthResponse> {
  const responsePromise = page.waitForResponse(isGrowth);
  await page.goto("/onchain");
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  await expect(page.getByTestId("onchain-dashboard")).toBeVisible();
  return (await response.json()) as GrowthResponse;
}

/** Click a control and return the growth response it triggered, after the re-render. */
async function refetchVia(page: Page, testId: string): Promise<{ url: URL; body: GrowthResponse }> {
  const responsePromise = page.waitForResponse(isGrowth);
  await page.getByTestId(testId).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  await expect(page.getByTestId("onchain-refetching")).toHaveCount(0);
  return { url: new URL(response.url()), body: (await response.json()) as GrowthResponse };
}

test("1. page loads from a real request with the method note", async ({ page }) => {
  const body = await openOnchain(page);
  await expect(page.getByTestId("onchain-dashboard")).toHaveAttribute("data-metric", "active_addresses");
  expect(body.grid_dates.at(-1)).toBe(facts.seed_today);
  const note = page.getByTestId("onchain-method-note");
  await expect(note).toContainText("28-day EMA");
  await expect(note).toContainText("180-day low");
  await expect(note).toContainText("25% above that floor held for 14 days");
  await expect(note).toContainText("194 days of history");
  await expect(page.getByTestId("onchain-error")).toHaveCount(0);
  await expect(page.getByTestId("onchain-empty")).toHaveCount(0);
});

test("2. six live panels, each with visible source and method text", async ({ page }) => {
  await openOnchain(page);
  await expect(page.getByTestId("onchain-panels").locator("> section")).toHaveCount(facts.live_ids.length);
  for (const id of facts.live_ids) {
    await expect(page.getByTestId(`onchain-panel-${id}`)).toContainText(facts.chains[id].label);
    const source = page.getByTestId(`onchain-panel-${id}-source`);
    await expect(source).toContainText("Source: growthepie");
    await expect(source).toContainText("Method: unique addresses active per UTC day");
  }
});

test("3. pre-launch shading is labelled on every seeded chain", async ({ page }) => {
  await openOnchain(page);
  for (const id of facts.live_ids) {
    expect(facts.chains[id].pre_launch_points).toBeGreaterThan(0);
    await expect(page.getByTestId(`onchain-panel-${id}-prelaunch`)).toContainText(
      `before launch (${facts.chains[id].launch_date}), not used in analytics`,
    );
  }
});

test("4. floor/ramp markers only on the designed chain, at the seeded dates", async ({ page }) => {
  const body = await openOnchain(page);
  for (const c of body.chains.filter((x) => x.floor_ramp)) {
    const expected = c.id === facts.designed.chain ? facts.designed.events : [];
    expect(c.floor_ramp!.events, c.id).toEqual(expected);
    await expect(page.getByTestId(`onchain-chart-${c.id}`)).toHaveAttribute("data-marker-count", String(expected.length * 2));
  }
  expect(facts.designed.events).toEqual([{ floor_date: "2026-03-01", ramp_date: "2026-04-14" }]);
});

test("5. current-state label per chain matches the manifest", async ({ page }) => {
  await openOnchain(page);
  for (const id of facts.live_ids) {
    await expect(page.getByTestId(`onchain-panel-${id}-state`)).toHaveAttribute("data-state", facts.chains[id].state);
  }
  await expect(page.getByTestId("onchain-panel-polygon-state")).toContainText("Near floor");
  await expect(page.getByTestId(`onchain-panel-${facts.limited.chain}-state`)).toContainText("Not enough history");
});

test("6. Robinhood shows its limited-history note with the gate date", async ({ page }) => {
  await openOnchain(page);
  await expect(page.getByTestId(`onchain-panel-${facts.limited.chain}-limited-history`)).toContainText(
    `floor/ramp markers from ${facts.limited.gate_met_on}`,
  );
  for (const id of facts.live_ids.filter((x) => x !== facts.limited.chain)) {
    await expect(page.getByTestId(`onchain-panel-${id}-limited-history`)).toHaveCount(0);
  }
});

test("7. comparison view: log index by default, % above low forces linear", async ({ page }) => {
  const body = await openOnchain(page);
  expect(body.comparison.start_date).toBe(facts.default_start);
  const comparison = page.getByTestId("onchain-comparison");
  await expect(comparison).toHaveAttribute("data-mode", "index");
  await expect(comparison).toHaveAttribute("data-log-scale", "true");
  await expect(page.getByTestId("onchain-comparison-log-toggle")).toBeEnabled();
  await expect(page.getByTestId("onchain-comparison-method")).toContainText(`Range start: ${facts.default_start}`);
  for (const id of facts.live_ids) {
    await expect(page.getByTestId(`onchain-legend-${id}`)).toBeVisible();
  }

  await page.getByTestId("onchain-comparison-mode-pct").click();
  await expect(comparison).toHaveAttribute("data-mode", "pct");
  await expect(comparison).toHaveAttribute("data-log-scale", "false");
  await expect(page.getByTestId("onchain-comparison-log-toggle")).toBeDisabled();
  await expect(page.getByTestId(`onchain-legend-${facts.designed.chain}`)).toContainText("%");

  await page.getByTestId("onchain-comparison-mode-index").click();
  await expect(comparison).toHaveAttribute("data-log-scale", "true");
});

test("8. late-start tag only on the chain rebased after the range start", async ({ page }) => {
  await openOnchain(page);
  await expect(page.getByTestId(`onchain-rebased-late-${facts.limited.chain}`)).toHaveText(
    `late start (${facts.limited.rebase_date})`,
  );
  for (const id of facts.live_ids.filter((x) => x !== facts.limited.chain)) {
    await expect(page.getByTestId(`onchain-rebased-late-${id}`)).toHaveCount(0);
  }
});

test("9. range picker re-fetches with ?start= and moves the visible range", async ({ page }) => {
  await openOnchain(page);
  await expect(page.getByTestId("onchain-range-1y")).toHaveAttribute("aria-checked", "true");
  const { url, body } = await refetchVia(page, "onchain-range-2y");
  expect(url.searchParams.get("start")).toBe(facts.start_2y);
  expect(body.comparison.start_date).toBe(facts.start_2y);
  await expect(page.getByTestId("onchain-range-2y")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("onchain-comparison-method")).toContainText(`Range start: ${facts.start_2y}`);
  const visible = JSON.parse((await page.getByTestId("onchain-comparison-chart").getAttribute("data-visible-range")) ?? "{}");
  expect(visible.fromDate).toBe(facts.start_2y);
  expect(visible.toDate).toBe(facts.seed_today);
});

test("10. metric switch re-fetches transactions and shows the L2BEAT cross-check", async ({ page }) => {
  await openOnchain(page);
  for (const id of facts.cross_check.chains) {
    await expect(page.getByTestId(`onchain-panel-${id}-crosscheck`)).toHaveCount(0); // tx-only
  }
  const { url, body } = await refetchVia(page, "onchain-metric-transactions");
  expect(url.searchParams.get("metric")).toBe("transactions");
  expect(body.metric).toBe("transactions");
  await expect(page.getByTestId("onchain-dashboard")).toHaveAttribute("data-metric", "transactions");
  await expect(page.getByTestId(`onchain-panel-${facts.designed.chain}-source`)).toContainText("Method: transactions per UTC day");
  for (const id of facts.cross_check.chains) {
    const note = page.getByTestId(`onchain-panel-${id}-crosscheck`);
    await expect(note).toContainText("Cross-check vs L2BEAT (display only)");
    await expect(note).toContainText(`${facts.cross_check.divergence_pct.toFixed(1)}`);
    await expect(note).toContainText(`on ${facts.seed_today}`);
  }
  // D3: the chain with no transactions archive becomes an unavailable card
  // through the real reader, while every other live chain keeps rendering.
  const missing = facts.no_tx_archive.chain;
  await expect(page.getByTestId(`onchain-panel-${missing}`)).toHaveCount(0);
  await expect(page.getByTestId(`onchain-unavailable-${missing}`)).toHaveAttribute("data-reason", facts.no_tx_archive.reason);
  for (const id of facts.live_ids.filter((x) => x !== missing)) {
    await expect(page.getByTestId(`onchain-panel-${id}`)).toBeVisible();
  }
});

test("11. stale series: panel badge and page banner", async ({ page }) => {
  await openOnchain(page);
  const id = facts.stale.chain;
  await expect(page.getByTestId(`onchain-panel-${id}-stale`)).toContainText(`last updated ${facts.stale.days} days ago`);
  await expect(page.getByTestId("onchain-stale-banner")).toContainText(
    `${facts.chains[id].label} last updated ${facts.stale.days} days ago`,
  );
  for (const other of facts.live_ids.filter((x) => x !== id)) {
    await expect(page.getByTestId(`onchain-panel-${other}-stale`)).toHaveCount(0);
  }
});

test("12. unavailable chains render as labelled cards, never a zero", async ({ page }) => {
  const body = await openOnchain(page);
  for (const id of facts.unavailable_ids) {
    expect(body.chains.find((c) => c.id === id)?.status).toBe("unavailable");
    const card = page.getByTestId(`onchain-unavailable-${id}`);
    await expect(card).toHaveAttribute("data-reason", "source-unavailable");
    await expect(page.getByTestId(`onchain-panel-${id}`)).toHaveCount(0);
    expect((await card.textContent()) ?? "").not.toMatch(/(^|[^\d])0([^\d]|$)/);
  }
});

test("13. attribution footer carries the growthepie string verbatim", async ({ page }) => {
  await openOnchain(page);
  await expect(page.getByTestId("onchain-attribution-text")).toHaveText(facts.attribution);
  await expect(page.getByTestId("onchain-attribution-text").locator("a")).toHaveAttribute("href", facts.attribution_url);
  await expect(page.getByTestId("onchain-attribution")).toHaveCount(1);
});

test("14. home page links to /onchain", async ({ page }) => {
  await page.goto("/");
  const responsePromise = page.waitForResponse(isGrowth);
  await page.getByTestId("home-link-onchain").click();
  await expect(page).toHaveURL(/\/onchain$/);
  expect((await responsePromise).status()).toBe(200);
  await expect(page.getByTestId("onchain-dashboard")).toBeVisible();
});

test("15. the seeded hole breaks the line on its panel", async ({ page }) => {
  await openOnchain(page);
  const chart = page.getByTestId(`onchain-chart-${facts.gap.chain}`);
  await expect(chart).toHaveAttribute("data-gap-dates", new RegExp(facts.gap.gap_before_date));
  for (const id of facts.live_ids.filter((x) => x !== facts.gap.chain)) {
    await expect(page.getByTestId(`onchain-chart-${id}`)).toHaveAttribute("data-gap-count", "0");
  }
});

test("16. hovering a panel moves the raw-value readout to the hovered date", async ({ page }) => {
  const body = await openOnchain(page);
  const id = facts.designed.chain;
  const readout = page.getByTestId(`onchain-panel-${id}-readout`);
  await expect(readout).toContainText(`on ${facts.seed_today}`);

  const canvas = page.getByTestId(`onchain-chart-${id}`).locator("canvas").first();
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width * 0.6, box!.y + box!.height / 2);
  await page.mouse.move(box!.x + box!.width * 0.3, box!.y + box!.height / 2, { steps: 8 });

  await expect(readout).not.toContainText(`on ${facts.seed_today}`);
  const hovered = /on (\d{4}-\d{2}-\d{2})/.exec((await readout.textContent()) ?? "")?.[1];
  expect(body.grid_dates).toContain(hovered);
  await expect(readout).toContainText("EMA28");
});
