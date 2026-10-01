import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import os from "node:os";

const REPO_ROOT = path.resolve(__dirname, "..");

// A disposable cache tree, outside the repo, that the seeder fills and the
// API serves from. `seed_e2e_cache.py` refuses to run if this is unset or
// equal to the real cache root — the E2E must never be able to overwrite live
// market data (three live-data incidents in two days made that explicit).
const E2E_CACHE_ROOT = path.join(os.tmpdir(), "screener-e2e-cache");
const E2E_WATCHLIST = path.join(E2E_CACHE_ROOT, "watchlist.json");
// Pair-screener fixture universe (RFC-005). The seeder writes it and refuses
// to run if this resolves to the real api/data/pairs_universe.json.
const E2E_PAIRS_UNIVERSE = path.join(E2E_CACHE_ROOT, "pairs_universe.json");
// narrative-v2 fixture config (RFC-7). The seeder copies the real
// api/data/narratives.json here and refuses to run if this resolves to the
// real file, so the AC-4 config-edit spec only ever edits this disposable copy.
const E2E_NARRATIVES = path.join(E2E_CACHE_ROOT, "narratives.json");

const CHROMIUM_PATH = process.env["PLAYWRIGHT_CHROMIUM_PATH"] || undefined;

const API_PORT = 8001; // NOT 8000 — see the port note below
const WEB_PORT = 3100; // NOT 3000 — ditto
const API_BASE_URL = `http://127.0.0.1:${API_PORT}`;

const apiEnv = {
  SCREENER_CACHE_ROOT: E2E_CACHE_ROOT,
  SCREENER_WATCHLIST_PATH: E2E_WATCHLIST,
  PAIRS_UNIVERSE_PATH: E2E_PAIRS_UNIVERSE,
  NARRATIVES_PATH: E2E_NARRATIVES,
  // CORS in api/main.py is origin-exact and hardcoded to localhost:3000. The
  // E2E runs the web server on another port, so the allowed origin has to be
  // widened for this process only — never in main.py itself.
  SCREENER_CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
};

export default defineConfig({
  testDir: "./e2e",
  // These specs drive two real servers; a flaky-retry would hide a genuine
  // ordering bug rather than surface it.
  retries: 0,
  fullyParallel: false,
  workers: 1,
  // 15 s, not the 5 s default: the screener board takes 2-5 s on a cold local
  // backend and flaked at 5 s both here and at the pre-feature commit 35e646f
  // (pair-screener RFC-005 report). Assertion logic is unchanged.
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    // localhost, NOT 127.0.0.1. The browser's page origin is what CORS checks,
    // and the two spellings are different origins. Using 127.0.0.1 here makes
    // every request fail CORS and every spec fail for a reason unrelated to
    // what it is testing.
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  // PLAYWRIGHT_CHROMIUM_PATH (optional): launch an already-installed Chromium
  // when the build @playwright/test expects is not downloaded (e.g. a sandbox
  // with a different pre-installed build). Unset = Playwright's own browser.
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(CHROMIUM_PATH ? { launchOptions: { executablePath: CHROMIUM_PATH } } : {}),
      },
    },
  ],

  // Ports deliberately differ from the dev defaults (3000/8000). A dev server
  // already running would otherwise be silently reused, and the E2E would run
  // against the developer's REAL cache — the failure mode this whole setup
  // exists to prevent. `reuseExistingServer: false` makes a port clash a loud
  // startup error instead.
  webServer: [
    {
      // Seed, then serve. Chained rather than run from `globalSetup` because
      // Playwright's ordering of globalSetup vs. webServer has changed between
      // versions; chaining makes the dependency explicit and version-proof.
      command:
        `uv run --project api python api/scripts/seed_e2e_cache.py && ` +
        `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: REPO_ROOT,
      url: `${API_BASE_URL}/api/health`,
      env: apiEnv,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // The Svelte/LayerChart island is built by Vite, not by Next, and
      // `next dev` does not build it. Without this the pair detail view
      // would 404 on /islands/spread-chart.js in a clean checkout.
      command: `pnpm build:islands && pnpm dev --port ${WEB_PORT}`,
      cwd: __dirname,
      url: `http://localhost:${WEB_PORT}/screener`,
      env: { NEXT_PUBLIC_API_BASE_URL: API_BASE_URL },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});

export { API_BASE_URL, E2E_CACHE_ROOT, WEB_PORT };
