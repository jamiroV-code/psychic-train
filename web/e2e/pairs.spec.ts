/**
 * End-to-end proof for /pairs and /pairs/[a]/[b] (pair screener plan RFC-005;
 * AC-1, AC-2, AC-6, AC-7, AC-12 at the browser boundary).
 *
 * Real browser, real Next.js pages, real API client, real FastAPI `/api/pairs`
 * routes, real parquet reads. `seed_e2e_cache.py::seed_pairs` writes six fake
 * coins' daily bars through `cache.write_ohlcv`, points PAIRS_UNIVERSE_PATH at
 * a fixture universe (never the real api/data/pairs_universe.json), then runs
 * the PRODUCTION `compute_and_persist()` and refuses to start the server if
 * any designed row state did not come out. Every expectation here (order,
 * counts, which pair is raw-only / not mean-reverting, sample dates) is read
 * from the seeder's manifest; no statistic is retyped.
 *
 * One test is UI-ONLY (marked below): the stale banner. A seeded run has one
 * results file, computed from the same cache it is compared against, so it is
 * always `fresh`. That test intercepts the real response in the browser and
 * flips `computation_status` to prove the banner is wired; the actual
 * staleness detection (universe/bar/statsmodels/autolag changes) is proven in
 * pytest (api/tests/routers/test_pairs.py, RFC-003).
 *
 * Deliberately NOT covered end to end (unit-tested instead):
 *  - a Johansen-refused row: needs complex eigenvalues with |imag| > 1e-9,
 *    which no real two-series input produced (0/153 in RFC-002). Covered by
 *    api/tests/scripts/test_compute_pairs.py and the PairsTable/PairDetailView
 *    vitest suites.
 *  - the "No pair is significant ... Closest: ..." banner wording: the seeded
 *    universe contains significant pairs by design. Covered by
 *    web/lib/__tests__/format-pairs-value.test.ts.
 */
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

interface PairsFacts {
  universe: string[];
  pair_count: number;
  status_counts: Record<string, number>;
  status_by_pair: Record<string, string>;
  ok_order: string[];
  non_ok_order: string[];
  tested_count: number;
  significant_count: number;
  raw_only_pairs: string[];
  significant_pair: [string, string];
  raw_only_pair: [string, string];
  not_mean_reverting_pair: [string, string];
  missing_coin: string;
  short_coin: string;
  significant_sample: { start: string; end: string; overlap_days: number };
}

// Read lazily: the seeder rewrites the manifest when the API server starts.
function facts(): PairsFacts {
  const raw = fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8");
  return (JSON.parse(raw) as { pairs: PairsFacts }).pairs;
}

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

async function openTable(page: Page) {
  const response = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/pairs");
  await page.goto("/pairs");
  expect((await response).status()).toBe(200);
  await expect(page.getByTestId("pairs-table")).toBeVisible();
}

test("table loads from a real request: fresh, significance banner, disclosure, no errors", async ({ page }) => {
  const f = facts();
  const errors = trackConsoleErrors(page);
  await openTable(page);

  await expect(page.getByTestId("pairs-status-banner")).toHaveCount(0); // fresh renders nothing
  await expect(page.getByTestId("pairs-api-error")).toHaveCount(0);
  await expect(page.getByTestId("pairs-significance-banner")).toHaveText(
    `${f.significant_count} of ${f.tested_count} pairs are significant after correcting for ${f.tested_count} tests (5% level).`,
  );
  await expect(page.getByTestId("pairs-disclosure")).not.toBeEmpty();
  expect(errors, `browser console/page errors:\n${errors.join("\n")}`).toEqual([]);
});

test("every pair is listed; ok rows by corrected p ascending, non-ok rows grouped at the bottom", async ({ page }) => {
  const f = facts();
  await openTable(page);
  const rows = page.locator('[data-testid^="pairs-row-"]');
  await expect(rows).toHaveCount(f.pair_count);
  const ids = await rows.evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")!.replace("pairs-row-", "")));
  expect(ids).toEqual([...f.ok_order, ...f.non_ok_order]);
  for (const id of ids) {
    await expect(page.getByTestId(`pairs-row-${id}`)).toHaveAttribute("data-status", f.status_by_pair[id]);
  }
});

test("raw-only tag appears on exactly the pair that passes raw but not after correction", async ({ page }) => {
  const f = facts();
  await openTable(page);
  const tags = page.locator('[data-testid^="pairs-raw-only-"]');
  await expect(tags).toHaveCount(f.raw_only_pairs.length);
  const [a, b] = f.raw_only_pair;
  await expect(page.getByTestId(`pairs-raw-only-${a}-${b}`)).toHaveText("passes raw, not after correction");
});

test("insufficient-overlap and unavailable-coin rows show their reason and no statistics", async ({ page }) => {
  const f = facts();
  await openTable(page);
  const nonOk = Object.entries(f.status_by_pair).filter(([, s]) => s !== "ok");
  expect(nonOk.length).toBe(f.status_counts["insufficient_overlap"] + f.status_counts["coin_unavailable"]);
  for (const [id, status] of nonOk) {
    const reason = page.getByTestId(`pairs-reason-${id}`);
    if (status === "coin_unavailable") {
      await expect(reason).toContainText(`${f.missing_coin}: no usable cached daily closes`);
    } else {
      await expect(reason).toContainText(/only \d+ days of overlapping history available, need 365/);
    }
    // No stat cells: the reason spans them, so the row has exactly 4 cells.
    await expect(page.getByTestId(`pairs-row-${id}`).locator("td")).toHaveCount(4);
  }
});

test("cointegrated pair detail: chart range matches the sample window, both EG directions, Johansen, half-life, disclosure", async ({ page }) => {
  const f = facts();
  const [a, b] = f.significant_pair;
  const errors = trackConsoleErrors(page);
  await openTable(page);
  await page.getByTestId(`pairs-row-${a}-${b}`).getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/pairs/${a}/${b}$`));

  await expect(page.getByTestId("pairs-detail-heading")).toContainText(`${a} / ${b}`);
  const { start, end, overlap_days } = f.significant_sample;
  await expect(page.getByTestId("pairs-sample-window")).toHaveText(
    `Sample: ${start} → ${end} (${overlap_days.toLocaleString("en-US")} days)`,
  );
  // AC-7: what is plotted is exactly the displayed sample window.
  await expect(page.getByTestId("pairs-chart-range")).toHaveText(
    `Plotted: ${start} → ${end} (${overlap_days.toLocaleString("en-US")} points)`,
  );
  // The spread chart is a Svelte/LayerChart island rendering SVG; it replaced a
  // canvas-based library, so a `canvas` locator no longer describes it. Asserting
  // the drawn series path is stricter than the old check anyway — a canvas
  // element can be present and still be blank, a path cannot.
  const series = page.locator('[data-testid="pairs-spread-chart"] .spread-chart__line');
  await expect(series).toBeVisible();
  await expect(series).toHaveAttribute("d", /^M/);

  await expect(page.getByTestId("pairs-eg-a-on-b")).toContainText(`${a} on ${b}`);
  await expect(page.getByTestId("pairs-eg-b-on-a")).toContainText(`${b} on ${a}`);
  await expect(page.locator('[data-used="true"]')).toHaveCount(1);
  await expect(page.getByTestId("pairs-johansen-verdict")).toBeVisible();
  await expect(page.getByTestId("pairs-half-life")).toContainText(/\d/);
  await expect(page.getByTestId("pairs-not-mean-reverting")).toHaveCount(0);
  await expect(page.getByTestId("pairs-detail-z")).toContainText(/\d/);
  await expect(page.getByTestId("pairs-disclosure")).not.toBeEmpty();
  expect(errors, `browser console/page errors:\n${errors.join("\n")}`).toEqual([]);
});

test("not-mean-reverting pair: no half-life number, and EG/Johansen disagree side by side (AC-6)", async ({ page }) => {
  const [a, b] = facts().not_mean_reverting_pair;
  await page.goto(`/pairs/${a}/${b}`);
  await expect(page.getByTestId("pairs-detail-heading")).toContainText(`${a} / ${b}`);
  await expect(page.getByTestId("pairs-not-mean-reverting")).toHaveText("Not mean-reverting — no half-life");
  // Seeder asserts BH p >= 0.05 while Johansen rank >= 1 for this pair; both are shown, neither merged.
  await expect(page.getByTestId("pairs-eg-a-on-b")).toBeVisible();
  await expect(page.getByTestId("pairs-eg-b-on-a")).toBeVisible();
  await expect(page.getByTestId("pairs-johansen-verdict")).toContainText("Yes");
  await expect(page.getByTestId("pairs-bh-p")).toBeVisible();
});

test("unknown ticker shows the API's 404 reason", async ({ page }) => {
  const a = facts().significant_pair[0];
  await page.goto(`/pairs/${a}/NOPE`);
  const err = page.getByTestId("pairs-api-error");
  await expect(err).toHaveAttribute("data-kind", "http");
  await expect(err).toContainText("404");
  await expect(err).toContainText("NOPE is not in the pair-screener universe");
});

test("self-pair shows the API's 422 reason", async ({ page }) => {
  const a = facts().significant_pair[0];
  await page.goto(`/pairs/${a}/${a}`);
  const err = page.getByTestId("pairs-api-error");
  await expect(err).toContainText("422");
  await expect(err).toContainText("a and b must be different coins");
});

// UI-ONLY check (see header): the real response is fetched, then only its
// computation_status/stale_reason are overridden in the browser.
test("stale banner shows the API's reason verbatim [UI-only, response intercepted]", async ({ page }) => {
  const reason = "CINTA has newer bars (cache 2026-09-28, results 2026-09-27) — re-run compute_pairs.py";
  await page.route(
    (url) => url.pathname === "/api/pairs",
    async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({ response, json: { ...body, computation_status: "stale", stale_reason: reason } });
    },
  );
  await page.goto("/pairs");
  const banner = page.getByTestId("pairs-status-banner");
  await expect(banner).toHaveAttribute("data-status", "stale");
  await expect(banner).toContainText(reason);
  await expect(page.getByTestId("pairs-table")).toBeVisible(); // stale still shows the rows
});
