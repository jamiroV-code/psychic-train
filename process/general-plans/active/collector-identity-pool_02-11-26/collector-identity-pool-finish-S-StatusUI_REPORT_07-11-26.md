# S-StatusUI slice report (07-11-26)

## 1. Status
CODE-COMPLETE for the status frontend (AC13 UI side). Stage 6, branch `claude/b2-validate`. Not pushed.

## 2. Scope
Plan §S-StatusAPI / S-StatusUI (UI half): web types, formatters, `CollectorStatus.tsx`, the panel wiring, vitest, the seeded real-server Playwright spec and the first link of `api/tests/collector_status_e2e.py`. No production Python was touched.

## 3. Changed paths
- `web/lib/types/discovery.ts`: optional types mirroring the S-StatusAPI models. X account `endpoint_state|behaviour|harvest|ct0_rotations_seen`; `DiscoveryRedditAccountHealth` (its own model, `site: "reddit"`); `DiscoveryQueryIdHealth`; `DiscoveryRedditMethodHealth`; `DiscoveryDailyReportStatus`; `DiscoveryDoctorStatus`; `DiscoveryBrowserHealth`; `health.queryids|methods`; `collector.sources[].methods`; `collector.daily_report|doctor|browser`.
- `web/lib/source-health.ts`: new formatters `redditAccountText`, `methodText`, `queryIdText`, `doctorText`, `reportLines`, `browserText` and the type guard `isRedditAccount`. `accountText` now appends the X fields only when the API sends them. The row accounts line is labelled per site ("X accounts" / "Reddit accounts"). The row also gets `queryids` and `method-<method>` lines when they are present.
- `web/components/narrative/CollectorStatus.tsx`: Reddit methods are nested under the Reddit source line. Added an X accounts head line, a query-id line, a Reddit accounts block (new `redditHealth` prop), and daily-report, doctor and browser lines. Each new element appears only when its field is present.
- `web/components/narrative/DiscoverySourcesPanel.tsx`: passes `sources[reddit].health` as `redditHealth`.
- Tests: new `web/lib/__tests__/source-health-finish.test.ts` and `web/components/narrative/__tests__/CollectorStatusFinish.test.tsx`. `CollectorStatus.test.tsx` changed only in its fixture typing, because the accounts union made a spread ambiguous. No assertion changed.
- `api/tests/collector_status_e2e.py` (first chain link): `REDDIT_SCENARIOS` writes `queries-finish-a.json` and `queries-finish-b.json`, each validated by `web_queries.validate`. `seed_finish` writes the producer files in the S-StatusAPI §7 layouts. It also plants a secret marker, an IP literal and check text where a reader has to drop or count them.
- `web/e2e/collector-status.spec.ts`: two scenarios added (`finish-a`, `finish-b`). The timeout is now 180 s.

## 4. Behaviour
- Unknown is never shown as healthy. Every closed code goes through a table lookup. A code that is not in the table, or a null, reads `unknown`. An unknown Reddit account reads "state unknown". Doctor `UNKNOWN` reads "Doctor: unknown" and never "pass". Absent counts read `unknown` and are never shown as 0. A daily report without counts reads "counts unknown".
- Default-off compatibility: when the new fields are absent (an older API, or producers off), the box and the rows render exactly as before. A test asserts that none of the new test ids exist.
- No secrets, paths or IPs: the UI shows only API codes, counts, UTC times, opaque labels and validated public hostnames. The e2e test also checks that the wire contains no fixture path, profile name, doctor check text, secret marker or the `192.0.2.1` literal.
- Accessibility: plain text inside the existing `role="status"` / `aria-live="polite"` box. The methods are a nested list with an `aria-label`.
- Layout: the box has `overflowWrap: anywhere` and `minWidth: 0`. At 375, 768 and 1280 px, every new line and the whole document are checked for no horizontal overflow.

## 5. Tests (red first, then green)
- Red (before any implementation): `pnpm --filter web exec vitest run lib/__tests__/source-health-finish.test.ts components/narrative/__tests__/CollectorStatusFinish.test.tsx` → 38 failed, 2 passed (40).
- Green: `pnpm --filter web exec vitest run lib/__tests__/source-health-finish.test.ts components/narrative/__tests__/CollectorStatusFinish.test.tsx lib/__tests__/source-health.test.ts components/narrative/__tests__/CollectorStatus.test.tsx components/narrative/__tests__/DiscoverySourcesPanel.test.tsx components/narrative/__tests__/ProxyStatus.test.tsx` → 6 files, 75 passed.
- `pnpm --filter web exec tsc --noEmit --incremental false` → clean.
- Browser: `B2_E2E=1 E2E_API_PORT=18141 E2E_WEB_PORT=18142 E2E_CACHE_ROOT=<fresh mktemp -d> pnpm test:e2e -- collector-status.spec.ts --workers=1` (from `web/`) → 3 passed (375/768/1280 × 4 scenarios: configured, direct, finish-a, finish-b), 2.0 min.

## 6. Evidence
Screenshots were inspected: `web/test-results/*/finish-a-375.png` and `finish-b-1280.png`. All lines wrap, nothing overflows horizontally, the Reddit and X account blocks are labelled separately, and no secret marker, IP or check text appears. The e2e test also covers: all five Reddit account states across the two scenarios (active, resting, unknown / paused, locked); the method states needs_probe, degraded, disabled ("off") and unknown; the query-id state candidate; doctor WARN with counted lists; browser profile `policy_unsatisfied` with the IP-literal and secret refusals dropped; an incomplete daily report. All seven method states, all six query-id states and all four doctor states are covered exhaustively in vitest. The no-write snapshot check still holds for every scenario.

## 7. Deviations
- `discovery_history.method_switches()` (S-RDisc) is a Python read-only diagnostic. It is not on the `/api/narrative/sources` wire, and S-StatusAPI added no field for it, so the UI cannot show it without an API change, which this slice does not own. Not consumed. S-Report or a later status amendment can surface it.
- X finish account fields (`endpoint_state`, `behaviour`, `harvest`, `ct0_rotations_seen`) are not produced by `x_pool.health()` yet. They are proven in vitest only, not in the seeded browser run.
- The e2e spec was not run red before the UI change. Red-first was done at the vitest level. The browser run was done once, at the end, as instructed.

## 8. Risks
The method states ok, blocked and stale and the query-id states other than candidate are not exercised in the browser, only in vitest. If producer layouts drift from S-StatusAPI §7, the UI shows `unknown`, never a false success.

## 9. Rollback
Revert the commit. The changes are web-only plus a test fixture, with no state or migration.

## 10. Open questions
None blocking.

## 11. Next
S-E2E-UI extends `collector_status_e2e.py` (second link) over the cycle cache. S-Report / S-OpsDoctor / S-Relay producers must write the §7 layouts that these screens read.
