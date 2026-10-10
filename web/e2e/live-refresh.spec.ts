/**
 * T43 / S11b: the screener page re-checks the server every minute and updates
 * in place. The status and board are the REAL answers with edits: the e2e
 * API runs with its refresh worker off, so the status is rewritten to a
 * running worker whose last refresh finished 3 min before its server_time.
 *
 * Expected strip times come from an arithmetic oracle (the EU rule: summer
 * time from the last Sunday of March 01:00Z to the last Sunday of October
 * 01:00Z), never from Intl, so the oracle cannot share a bug with the page.
 *
 * A check is triggered either by `page.clock.runFor` (tests 2 and 3, the
 * scheduled 60 s check) or by turning the tab hidden and visible again
 * (test 4), which runs one check at once.
 */
import { expect, test, type Page, type Route } from "@playwright/test";

const MINUTE = 60_000;
const DAY = 86_400_000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

interface Bar {
  timestamp: string;
  close: number;
}
interface BoardBody {
  coins: { symbol: string; chart: { price: Bar[]; sma: Bar[]; available: boolean } }[];
}

function isoZ(ms: number): string {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

/** 01:00Z on the last Sunday of `month` (0-based) in `year`. */
function lastSundayOneZ(year: number, month: number): number {
  const lastDay = new Date(Date.UTC(year, month + 1, 0));
  return Date.UTC(year, month, lastDay.getUTCDate() - lastDay.getUTCDay(), 1);
}

function wall(ms: number) {
  const year = new Date(ms).getUTCFullYear();
  const summer = ms >= lastSundayOneZ(year, 2) && ms < lastSundayOneZ(year, 9);
  const w = new Date(ms + (summer ? 2 : 1) * 3_600_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    day: `${w.getUTCFullYear()}-${w.getUTCMonth()}-${w.getUTCDate()}`,
    prefix: `${pad(w.getUTCDate())} ${MONTHS[w.getUTCMonth()]}`,
    text: `${pad(w.getUTCHours())}:${pad(w.getUTCMinutes())} ${summer ? "CEST" : "CET"}`,
  };
}

/** The strip's time for `ms`: `HH:MM CEST`, with `DD Mon` when not on the server's Brussels day. */
function oracle(ms: number, refMs: number): string {
  const t = wall(ms);
  return t.day === wall(refMs).day ? t.text : `${t.prefix} ${t.text}`;
}

interface Live {
  serverMs: number | null;
  finishedMs: number | null;
  boardCalls: number;
  extraBar: Set<string>;
}

/** Status: a running worker, refreshed 3 min before the first answer. Board: counted, optionally one bar longer. */
async function liveRoutes(page: Page): Promise<Live> {
  const live: Live = { serverMs: null, finishedMs: null, boardCalls: 0, extraBar: new Set() };

  // A check the page aborts (StrictMode's first mount, a hidden tab) may be
  // gone before the answer is fulfilled; that is not a test failure.
  await page.route("**/api/refresh/status", async (route: Route) => {
    const response = await route.fetch().catch(() => null);
    if (!response) return;
    const body = (await response.json()) as Record<string, unknown>;
    const serverMs = Date.parse(body.server_time as string);
    if (live.finishedMs === null) live.finishedMs = serverMs - 3 * MINUTE;
    live.serverMs = serverMs;
    Object.assign(body, {
      running: true,
      disabled_reason: null,
      last_tick_started: isoZ(live.finishedMs - MINUTE),
      last_tick_finished: isoZ(live.finishedMs),
      next_tick_at: isoZ(live.finishedMs + 15 * MINUTE),
      last_tick_failed: 0,
      backoff_seconds: 0,
    });
    await route.fulfill({ response, json: body }).catch(() => {});
  });

  await page.route("**/api/screener/board?**", async (route: Route) => {
    live.boardCalls += 1;
    const response = await route.fetch().catch(() => null);
    if (!response) return;
    const body = (await response.json()) as BoardBody;
    for (const c of body.coins) {
      if (!live.extraBar.has(c.symbol) || c.chart.price.length === 0) continue;
      const last = c.chart.price[c.chart.price.length - 1];
      c.chart.price.push({ timestamp: isoZ(Date.parse(last.timestamp) + DAY), close: last.close * 1.01 });
    }
    await route.fulfill({ response, json: body }).catch(() => {});
  });

  return live;
}

/** One check now: hidden, then visible again (the poller checks on becoming visible). */
async function checkNow(page: Page) {
  await page.evaluate(() => {
    const set = (state: string) => {
      Object.defineProperty(document, "visibilityState", { configurable: true, get: () => state });
      document.dispatchEvent(new Event("visibilitychange"));
    };
    set("hidden");
    set("visible");
  });
}

function plotOf(page: Page, symbol: string) {
  return page.getByTestId(`coin-panel-${symbol}`).getByTestId("mini-chart").locator(".simple-lines");
}

async function lastBarIso(page: Page, symbol: string): Promise<string> {
  const plot = plotOf(page, symbol);
  await expect(plot).toHaveAttribute("data-visible-to", /Z$/);
  return (await plot.getAttribute("data-visible-to"))!;
}

test("strip times equal the oracle for the status instants", async ({ page }) => {
  const live = await liveRoutes(page);
  await page.clock.install();
  await page.goto("/screener");

  const refreshed = page.getByTestId("strip-refreshed");
  await expect(refreshed).toBeVisible();
  const server = live.serverMs!;
  const finished = live.finishedMs!;
  await expect(refreshed).toHaveText(`Server refreshed ${oracle(finished, server)} (3 min ago)`);
  await expect(page.getByTestId("strip-next")).toHaveText(`Next refresh ${oracle(finished + 15 * MINUTE, server)}`);
  await expect(page.getByTestId("strip-checked")).toHaveText(`Page checked ${oracle(server, server)}`);
  await expect(page.getByTestId("strip-zone")).toHaveText(/^Times are Brussels time, (CEST \(\+02:00\)|CET \(\+01:00\))\.$/);
  const zone = wall(server).text.endsWith("CEST") ? "CEST (+02:00)" : "CET (+01:00)";
  await expect(page.getByTestId("strip-zone")).toHaveText(`Times are Brussels time, ${zone}.`);
  await expect(page.getByTestId("strip-overdue")).toHaveCount(0);
});

test("a new BTC bar arrives in place on the 60 s check, with exactly one more board request", async ({ page }) => {
  test.setTimeout(150_000);
  const live = await liveRoutes(page);
  await page.clock.install();
  await page.goto("/screener");
  await page.evaluate(() => {
    (window as unknown as { __keep: number }).__keep = 1;
  });

  // The baseline check has settled before the clock moves.
  await expect(page.getByTestId("strip-refreshed")).toBeVisible();
  const before = await lastBarIso(page, "BTC");
  const calls = live.boardCalls;

  live.extraBar.add("BTC");
  await page.clock.runFor(61_000);

  await expect(plotOf(page, "BTC")).toHaveAttribute("data-visible-to", isoZ(Date.parse(before) + DAY));
  expect(live.boardCalls).toBe(calls + 1);
  expect(await page.evaluate(() => (window as unknown as { __keep?: number }).__keep)).toBe(1);
});

test("an update keeps a ctrl-wheel zoom, the scroll position and an open drill-down", async ({ page }) => {
  test.setTimeout(150_000);
  const live = await liveRoutes(page);
  await page.clock.install();
  await page.goto("/screener");
  await expect(page.getByTestId("strip-refreshed")).toBeVisible();

  // A second coin, unzoomed, shows when the new data has landed.
  await expect(plotOf(page, "BTC")).toBeVisible();
  const symbols = await page.locator('[data-testid^="open-drilldown-"]').evaluateAll((els) =>
    els
      .filter((el) => el.closest(".coin-panel")?.querySelector('[data-testid="mini-chart"] .simple-lines'))
      .map((el) => el.getAttribute("data-testid")!.replace("open-drilldown-", "")),
  );
  const other = symbols.find((s) => s !== "BTC")!;
  expect(other, "the seeded board needs a second coin").toBeTruthy();
  const otherBefore = await lastBarIso(page, other);

  await page.getByTestId("open-drilldown-BTC").click();
  await expect(page.getByTestId("drilldown-view")).toBeVisible();

  const plot = plotOf(page, "BTC");
  await plot.scrollIntoViewIfNeeded();
  const box = (await plot.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height / 2);
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -400);
  await page.keyboard.up("Control");
  await expect(plot).toHaveAttribute("data-zoomed", "true");
  const from = (await plot.getAttribute("data-visible-from"))!;
  const scrollY = await page.evaluate(() => window.scrollY);

  live.extraBar.add("BTC");
  live.extraBar.add(other);
  const calls = live.boardCalls;
  await page.clock.runFor(61_000);

  await expect(plotOf(page, other)).toHaveAttribute("data-visible-to", isoZ(Date.parse(otherBefore) + DAY));
  expect(live.boardCalls).toBe(calls + 1);
  await expect(plot).toHaveAttribute("data-zoomed", "true");
  await expect(plot).toHaveAttribute("data-visible-from", from);
  expect(await page.evaluate(() => window.scrollY)).toBe(scrollY);
  await expect(page.getByTestId("drilldown-view")).toBeVisible();
  await expect(page.getByTestId("drilldown-view")).toHaveAttribute("aria-label", "BTC drill-down");
});

test("a failed check is visible and keeps the panels; the next answer brings the strip back", async ({ page }) => {
  await liveRoutes(page);
  await page.goto("/screener");
  await expect(page.getByTestId("strip-refreshed")).toBeVisible();
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();

  const abort = (route: Route) => route.abort();
  await page.route("**/api/refresh/status", abort);
  await page.route("**/api/screener/board?**", abort);
  await checkNow(page);

  await expect(page.getByTestId("strip-failed")).toContainText("Could not check the server");
  await expect(page.getByTestId("strip-announcer")).toHaveText("Could not check the server");
  await expect(page.getByTestId("board-error")).toBeVisible();
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();
  await expect(page.getByTestId("strip-refreshed")).toBeVisible();

  await page.unroute("**/api/refresh/status", abort);
  await page.unroute("**/api/screener/board?**", abort);
  await checkNow(page);

  await expect(page.getByTestId("strip-failed")).toHaveCount(0);
  await expect(page.getByTestId("strip-refreshed")).toBeVisible();
  await expect(page.getByTestId("strip-announcer")).toHaveText("The server answered again");
  await expect(page.getByTestId("board-error")).toHaveCount(0);
  await expect(page.getByTestId("coin-panel-BTC")).toBeVisible();
});
