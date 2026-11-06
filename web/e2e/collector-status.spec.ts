import { expect, test } from "@playwright/test";
import { copyFile, readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";

const API = `http://127.0.0.1:${process.env.E2E_API_PORT}`;
const ROOT = process.env.E2E_CACHE_ROOT;
const SECRET = "B2_SYNTHETIC_SECRET_NEVER_PUBLIC";
const NEW_FIELDS = ["proxy_id", "proxy_state", "proxy_reason", "proxy_checked_at", "proxy_quarantine_until", "region", "connection_style", "identity_revision"];

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
    test.setTimeout(90_000);
    expect(process.env.B2_E2E, "Run this acceptance with B2_E2E=1 and explicit isolated API/web ports").toBe("1");
    expect(ROOT).toBeTruthy();
    const privateRoot = path.join(ROOT!, "collector-private");
    const poolRoot = path.join(ROOT!, "attention", "_pc_state");
    const current = path.join(privateRoot, "queries.json");
    for (const scenario of ["configured", "direct"]) {
      await copyFile(path.join(privateRoot, `queries-${scenario}.json`), current);
      const before = { ...await snapshot(privateRoot), ...await snapshot(poolRoot) };
      const response = await request.get(`${API}/api/narrative/sources`);
      expect(response.ok(), await response.text()).toBeTruthy();
      const body = await response.json();
      const wire = JSON.stringify(body);
      expect(wire).not.toContain(SECRET);
      expect(wire).not.toMatch(/collector-private|routes\.txt|assignments\.json|policy\.json|expected_ip|192\.0\.2\.1|user:password/);
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
      await page.screenshot({ path: testInfo.outputPath(`${scenario}-${width}.png`), fullPage: true });
      expect({ ...await snapshot(privateRoot), ...await snapshot(poolRoot) }).toEqual(before);
    }
  });
}
