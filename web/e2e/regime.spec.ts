/**
 * End-to-end proof for /regime (plan RFC-006, AC-8 / AC-11 automated part).
 *
 * Real browser, real Next.js page, real API client, real FastAPI route, real
 * adapters and DuckDB reads. The only thing absent is the network to the
 * providers: `seed_e2e_cache.py` writes fresh FRED / DefiLlama / Farside /
 * LiqTide caches so every adapter answers from cache. Fixture facts (first
 * dates, the deliberate hole, the ETF start) come from the seeder's manifest,
 * never retyped here.
 *
 * Observability hooks are DOM attributes only (no window globals):
 * - `data-visible-range` on each panel's chart container: JSON
 *   {from, to, fromDate, toDate}, written by the sync group on every range change;
 * - `data-gap-dates` / `data-gap-count`: grid dates where a line is broken by
 *   the API's `gap_before` flag.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

interface RegimeFacts {
  today: string;
  input_first_dates: Record<string, string>;
  gap: { series: string; component: string; hole_start: string; hole_end_exclusive: string; expected_gap_date: string };
  etf_first_date: string;
  default_years: number;
  panel_ids: string[];
}

const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, ".fixture-manifest.json"), "utf-8")) as {
  regime: RegimeFacts;
  seeded_at: string;
};
const facts = manifest.regime;

interface ComponentsResponse {
  grid_dates: string[];
  components: {
    id: string;
    status: string;
    first_date: string | null;
    last_fetched_utc: string | null;
    notes: string[];
    points: { date: string; gap_before: boolean }[];
  }[];
  composite: { reproduced: { points: unknown[] }; published: { status: string; points: unknown[] } };
}

interface VisibleRange {
  from: number;
  to: number;
  fromDate: string;
  toDate: string;
}

function chart(page: Page, id: string): Locator {
  return page.getByTestId(`regime-chart-${id}`);
}

async function ranges(page: Page): Promise<VisibleRange[]> {
  const out: VisibleRange[] = [];
  for (const id of facts.panel_ids) {
    const raw = await chart(page, id).getAttribute("data-visible-range");
    expect(raw, `panel ${id} has no data-visible-range`).not.toBeNull();
    out.push(JSON.parse(raw as string) as VisibleRange);
  }
  return out;
}

function daysBetween(a: string, b: string): number {
  return Math.abs(Date.parse(`${a}T00:00:00Z`) - Date.parse(`${b}T00:00:00Z`)) / 86_400_000;
}

function shiftYears(iso: string, years: number): string {
  const [y, m, d] = iso.split("-");
  return `${String(Number(y) - years).padStart(4, "0")}-${m}-${d}`;
}

/** Opens /regime and returns the real /api/regime/components response body. */
async function openRegime(page: Page, consoleErrors: string[]): Promise<ComponentsResponse> {
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const url = msg.location().url ?? "";
    if (/favicon/i.test(url) || /favicon/i.test(msg.text())) return; // Next dev serves no favicon
    consoleErrors.push(`${msg.text()} (${url})`);
  });
  page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));
  const responsePromise = page.waitForResponse((r) => r.url().includes("/api/regime/components"));
  await page.goto("/regime");
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const body = (await response.json()) as ComponentsResponse;
  await expect(page.getByTestId("regime-dashboard")).toBeVisible();
  for (const id of facts.panel_ids) {
    await expect(chart(page, id).locator("canvas").first()).toBeVisible();
    await expect(chart(page, id)).toHaveAttribute("data-visible-range", /fromDate/);
  }
  return body;
}

test.describe("/regime end to end", () => {
  let consoleErrors: string[];

  test.beforeEach(() => {
    consoleErrors = [];
  });

  test.afterEach(() => {
    expect(consoleErrors, "browser console errors").toEqual([]);
  });

  test("seven panels render from a real, cache-served /api/regime/components", async ({ page }) => {
    const body = await openRegime(page, consoleErrors);

    for (const id of facts.panel_ids) await expect(page.getByTestId(`regime-panel-${id}`)).toBeVisible();
    expect(body.components.map((c) => c.id)).toEqual(facts.panel_ids.filter((id) => id !== "composite"));
    for (const c of body.components) expect(c.status, `${c.id}: ${c.status}`).toBe("ok");
    expect(body.composite.reproduced.points.length).toBeGreaterThan(0);
    expect(body.composite.published.status).toBe("ok");

    // No provider was contacted: every cached input is at most as new as the
    // seed. A live FRED/DefiLlama refresh would have rewritten its file later.
    const seededAt = Date.parse(manifest.seeded_at);
    for (const c of body.components) {
      expect(c.last_fetched_utc, `${c.id} last_fetched_utc`).not.toBeNull();
      expect(Date.parse(c.last_fetched_utc as string), `${c.id} was re-fetched after seeding`).toBeLessThanOrEqual(seededAt);
    }

    // Different first dates per series, never before the seeded input began.
    const firstDates = new Set(body.components.map((c) => c.first_date));
    expect(firstDates.size).toBeGreaterThan(3);
    const dollar = body.components.find((c) => c.id === "broad_dollar");
    expect(dollar?.first_date && dollar.first_date >= facts.input_first_dates.DTWEXBGS).toBeTruthy();
  });

  test("default view is the last three years, identical on every panel", async ({ page }) => {
    const body = await openRegime(page, consoleErrors);
    const last = body.grid_dates[body.grid_dates.length - 1];
    const cutoff = shiftYears(last, facts.default_years);
    // The grid must be longer than the default window, or this proves nothing.
    expect(body.grid_dates[0] < cutoff).toBe(true);

    const all = await ranges(page);
    for (const r of all) expect(r).toEqual(all[0]);
    expect(all[0].toDate).toBe(last);
    expect(all[0].fromDate >= cutoff).toBe(true);
    expect(daysBetween(all[0].fromDate, cutoff)).toBeLessThanOrEqual(7);
  });

  test("zooming one panel moves all seven to the same new range", async ({ page }) => {
    await openRegime(page, consoleErrors);
    const before = (await ranges(page))[0];

    const target = chart(page, "stablecoin_supply").locator("canvas").first();
    await target.scrollIntoViewIfNeeded();
    const box = await target.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    await page.mouse.wheel(0, -400); // zoom in

    await expect
      .poll(async () => JSON.stringify((await ranges(page))[0]), { timeout: 10_000 })
      .not.toBe(JSON.stringify(before));
    // Let any trailing wheel frames settle, then require all seven to agree.
    await expect
      .poll(async () => {
        const all = (await ranges(page)).map((r) => JSON.stringify(r));
        return new Set(all).size;
      })
      .toBe(1);
    const after = (await ranges(page))[0];
    expect(after.to - after.from).toBeLessThan(before.to - before.from);
  });

  test("hovering a panel moves the readout off the latest date", async ({ page }) => {
    const body = await openRegime(page, consoleErrors);
    const last = body.grid_dates[body.grid_dates.length - 1];
    const readoutDate = page.getByTestId("regime-readout-date-net_liquidity");
    await expect(readoutDate).toHaveText(`as of ${last}`);

    const canvas = chart(page, "composite").locator("canvas").first();
    await canvas.scrollIntoViewIfNeeded(); // seventh panel sits below the fold
    const box = await canvas.boundingBox();
    expect(box).not.toBeNull();
    await page.mouse.move(box!.x + box!.width * 0.5, box!.y + box!.height / 2);
    await page.mouse.move(box!.x + box!.width * 0.3, box!.y + box!.height / 2, { steps: 8 });

    await expect(page.getByTestId("regime-readout")).toHaveAttribute("data-hovering", "true");
    await expect(readoutDate).not.toHaveText(`as of ${last}`);
    const hovered = ((await readoutDate.textContent()) ?? "").replace("as of ", "").trim();
    expect(body.grid_dates).toContain(hovered);
    // Every readout cell is on the same date.
    await expect(page.getByTestId("regime-readout-date-published")).toHaveText(`as of ${hovered}`);

    await page.mouse.move(0, 0, { steps: 4 });
    await expect(readoutDate).toHaveText(`as of ${last}`);
  });

  test("the seeded hole is flagged by the API and breaks the line on the panel", async ({ page }) => {
    const body = await openRegime(page, consoleErrors);
    const component = body.components.find((c) => c.id === facts.gap.component);
    expect(component).toBeDefined();
    const flagged = component!.points.filter((p) => p.gap_before).map((p) => p.date);
    expect(flagged).toContain(facts.gap.expected_gap_date);
    // Nothing inside the hole was plotted.
    expect(component!.points.some((p) => p.date >= facts.gap.hole_start && p.date < facts.gap.hole_end_exclusive)).toBe(false);

    const panel = chart(page, facts.gap.component);
    const drawn = ((await panel.getAttribute("data-gap-dates")) ?? "").split(",").filter(Boolean);
    expect(drawn).toContain(facts.gap.expected_gap_date);
    expect(drawn).toEqual(flagged);
    await expect(chart(page, "net_liquidity")).toHaveAttribute("data-gap-count", "0");
  });

  test("ETF panel explains it does not apply before launch", async ({ page }) => {
    const body = await openRegime(page, consoleErrors);
    await expect(page.getByTestId("regime-panel-notes-etf_flows")).toContainText(`Not applicable before ${facts.etf_first_date}`);
    const etf = body.components.find((c) => c.id === "etf_flows");
    expect(etf?.first_date && etf.first_date >= facts.etf_first_date).toBeTruthy();
  });
});
