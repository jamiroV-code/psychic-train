import { expect, test } from "@playwright/test";
import { copyFile, readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";

const API = `http://127.0.0.1:${process.env.E2E_API_PORT}`;
const ROOT = process.env.E2E_CACHE_ROOT;
const SECRET = "B2_SYNTHETIC_SECRET_NEVER_PUBLIC";
const NEW_FIELDS = ["proxy_id", "proxy_state", "proxy_reason", "proxy_checked_at", "proxy_quarantine_until", "region", "connection_style", "identity_revision"];

interface Finish {
  accounts: Record<string, { state: string; text: string; never?: string }>;
  methodStates: Record<string, string>;
  methodText: Record<string, string>;
  queryids: string;
}

// Seeded by api/tests/collector_status_e2e.py (REDDIT_SCENARIOS, seed_finish); every Reddit account state is covered.
const FINISH: Record<string, Finish | undefined> = {
  "finish-a": {
    accounts: {
      r_active: { state: "active", text: "r_active active, reads today 3 / 200, rest until unknown, ready yes, session ok" },
      r_resting: { state: "resting", text: "r_resting resting (new_account_rest)" },
      r_unknown: { state: "unknown", text: "r_unknown state unknown, reads today unknown", never: "healthy" },
    },
    methodStates: { reddit_live_browser: "needs_probe", reddit_live_gql: "degraded", reddit_web: "unknown", reddit_stream: "unknown" },
    methodText: {
      reddit_live_browser: "Reddit live (browser): needs probe (probe_missing)",
      reddit_live_gql: "Reddit live (GraphQL): degraded (rate_limited), last settled unknown, lanes posts 100%, comments 40% (threads opened only), requests today 30 of 200",
      reddit_web: "Reddit web feed: unknown",
      reddit_stream: "Reddit stream: unknown",
    },
    queryids: "Query ids (sentinel): candidate pending, source bundle, active for 2 days",
  },
  "finish-b": {
    accounts: {
      r_paused: { state: "paused", text: "r_paused paused (rate_limited), reads today 9 / 200" },
      r_locked: { state: "locked", text: "r_locked locked, reads today unknown", never: "B2_SYNTHETIC" },
    },
    methodStates: { reddit_live_browser: "disabled", reddit_live_gql: "degraded", reddit_web: "unknown", reddit_stream: "unknown" },
    methodText: { reddit_live_browser: "Reddit live (browser): off (method_disabled)" },
    queryids: "Query ids (auto): candidate pending",
  },
};

async function snapshot(directory: string): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  const metadata = await stat(directory);
  result[directory] = JSON.stringify({ type: "directory", mode: metadata.mode, mtime: metadata.mtimeMs, ctime: metadata.ctimeMs });
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) Object.assign(result, await snapshot(file));
    else {
      const metadata = await stat(file);
      result[file] = JSON.stringify({
        type: "file", mode: metadata.mode, size: metadata.size,
        mtime: metadata.mtimeMs, ctime: metadata.ctimeMs,
        bytes: (await readFile(file)).toString("base64"),
      });
    }
  }
  return result;
}

for (const width of [375, 768, 1280]) {
  test(`B2 real status API to screen at ${width}px: all route states, legacy and no secrets`, async ({ page, request }, testInfo) => {
    test.setTimeout(180_000);
    expect(process.env.B2_E2E, "Run this acceptance with B2_E2E=1 and explicit isolated API/web ports").toBe("1");
    expect(ROOT).toBeTruthy();
    const privateRoot = path.join(ROOT!, "collector-private");
    const poolRoot = path.join(ROOT!, "attention", "_pc_state");
    const current = path.join(privateRoot, "queries.json");
    for (const scenario of ["configured", "direct", "finish-a", "finish-b"]) {
      await copyFile(path.join(privateRoot, `queries-${scenario}.json`), current);
      const before = { ...await snapshot(privateRoot), ...await snapshot(poolRoot) };
      const response = await request.get(`${API}/api/narrative/sources`);
      expect(response.ok(), await response.text()).toBeTruthy();
      const body = await response.json();
      const wire = JSON.stringify(body);
      expect(wire).not.toContain(SECRET);
      expect(wire).not.toMatch(/collector-private|routes\.txt|assignments\.json|policy\.json|expected_ip|192\.0\.2\.1|user:password/);
      // S-StatusUI: no private path, profile name or doctor check text reaches the wire.
      expect(wire).not.toMatch(/surface\.json|browser\.exe|profiles|p_r_|check text/);
      const finish = FINISH[scenario];
      const redditRow = body.sources.find((row: { id: string }) => row.id === "reddit");
      const collectorReddit = body.collector.sources.find((s: { id: string }) => s.id === "reddit");
      if (!finish) {
        // Default off: no Reddit account or method rows on the wire.
        expect(redditRow?.health?.methods).toBeUndefined();
        expect((redditRow?.health?.accounts ?? []).filter((a: { site?: string }) => a.site === "reddit")).toEqual([]);
        expect(collectorReddit.methods).toBeUndefined();
      } else {
        const wireAccounts = Object.fromEntries(redditRow.health.accounts.map((a: { label: string; state: string }) => [a.label, a.state]));
        expect(wireAccounts).toEqual(Object.fromEntries(Object.entries(finish.accounts).map(([l, s]) => [l, s.state])));
        const methods = Object.fromEntries(collectorReddit.methods.map((m: { method: string; state: string }) => [m.method, m.state]));
        expect(methods).toEqual(finish.methodStates);
      }
      const accounts = body.sources.find((row: { id: string }) => row.id === "xsearch").health.accounts;
      expect(accounts).toHaveLength(5);
      const expected: Record<string, string> = scenario === "direct"
        ? { legacy: "direct", unknown: "direct", healthy: "direct", quarantined: "direct", blocked: "direct" }
        : { legacy: "unknown", unknown: "unknown", healthy: "healthy", quarantined: "quarantined", blocked: "blocked" };
      for (const account of accounts) {
        // Historical unknown may omit the new state entirely; never infer direct.
        expect(account.proxy_state ?? "unknown").toBe(expected[account.label]);
        for (const field of NEW_FIELDS) {
          if (field in account) expect(account[field]).not.toBeNull();
        }
        expect(account.state).toMatch(/^(active|locked|inactive|suspect)$/);
        expect(account).toHaveProperty("last_used", null);
      }
      // Repeat the actual GET to prove it does not migrate/write state, open
      // malformed private admission files, reserve provider budget or collect.
      expect((await request.get(`${API}/api/narrative/sources`)).ok()).toBeTruthy();
      expect({ ...await snapshot(privateRoot), ...await snapshot(poolRoot) }).toEqual(before);
      await page.setViewportSize({ width, height: 900 });
      const statusResponse = page.waitForResponse((r) => r.url() === `${API}/api/narrative/sources` && r.status() === 200);
      await page.goto("/narrative");
      await page.getByRole("tab", { name: "Discovery", exact: true }).click();
      await statusResponse;
      for (const [label, state] of Object.entries(expected)) {
        const line = page.getByTestId(`collector-account-${label}`);
        await expect(line).toBeVisible();
        await expect(line).toContainText(`proxy ${state}`);
        await expect(line).toContainText("reads today");
        expect(await line.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
      }
      await page.getByTestId("sources-summary").click();
      const details = page.getByTestId("sources-health-xsearch");
      await expect(details).toBeVisible();
      for (const state of new Set(Object.values(expected))) await expect(details).toContainText(`proxy ${state}`);
      await expect(page.getByTestId("collector-status")).not.toContainText(SECRET);
      await expect(details).not.toContainText(SECRET);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
      if (finish) {
        const box = page.getByTestId("collector-status");
        for (const [label, { text, never }] of Object.entries(finish.accounts)) {
          const line = page.getByTestId(`collector-reddit-account-${label}`);
          await expect(line).toBeVisible();
          await expect(line).toContainText(text);
          if (never) await expect(line).not.toContainText(never);
          expect(await line.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
        }
        await expect(page.getByTestId("collector-reddit-accounts")).toContainText("Reddit accounts:");
        for (const [method, text] of Object.entries(finish.methodText)) {
          const line = page.getByTestId(`collector-method-${method}`);
          await expect(line).toContainText(text);
          expect(await line.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
        }
        await expect(page.getByTestId("collector-queryids")).toContainText(finish.queryids);
        await expect(page.getByTestId("collector-doctor")).toContainText("Doctor: warnings");
        await expect(page.getByTestId("collector-doctor")).toContainText("0 failures, 2 warnings");
        await expect(page.getByTestId("collector-browser")).toHaveText(
          "Browser profile: policy not satisfied; relay refused edge.microsoft.com 3");
        await expect(page.getByTestId("collector-daily-report")).toContainText("incomplete");
        await expect(page.getByTestId("collector-daily-report")).toContainText(
          "reddit/reddit_live_gql: eligible 10, stored 8, exact 7, estimated 1, missing 2 (blocked 2)");
        await expect(page.getByTestId("sources-health-reddit-accounts")).toContainText("Reddit accounts:");
        await expect(box).not.toContainText(/check text|192\.0\.2\.1|undefined|NaN/);
      } else {
        await expect(page.getByTestId("collector-reddit-accounts")).toHaveCount(0);
        await expect(page.locator("[data-testid^='collector-method-']")).toHaveCount(0);
      }
      await page.screenshot({ path: testInfo.outputPath(`${scenario}-${width}.png`), fullPage: true });
      expect({ ...await snapshot(privateRoot), ...await snapshot(poolRoot) }).toEqual(before);
    }
  });
}
