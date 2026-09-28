# onchain-activity

<!-- Part of my_site -->

## Scope

Tracks raw on-chain participant growth per chain — daily active addresses, new addresses, and
transaction count — across the major chains the user watches (Ethereum, the leading L2s including
the newly-launched Robinhood Chain, BNB Chain, Tron, and Solana), and presents them so a "this
chain hit a floor and is now ramping back up" pattern is visually obvious. This is distinct from
`cycle-regime` (macro liquidity backdrop) and `narrative-mindshare` (social/search attention
proxies) — this feature is raw, chain-native usage data, not a derived sentiment or liquidity read.

## Key Source Files

Built 2026-09-25..27 (plan `completed/chain-growth_25-09-26/`, all 6 RFCs verified 2026-09-28):

- `api/data/chains.json` — user-editable tracked-chain list (9 chains; Solana/BNB/Tron marked
  source-unavailable), loaded with skip+warn
- `api/data/growthepie_adapter.py` (primary, keyless, CC BY 4.0) and `api/data/l2beat_adapter.py`
  (transactions cross-check, display-only, `redistributable=False`)
- `api/data/cache.py` — `merge_onchain_series` (14-day revision window) writing
  `api/data/cache/onchain/{source}/{chain}/{metric}.parquet` (git-tracked carve-out)
- `api/scripts/snapshot_chain_growth.py` + `.github/workflows/chain-growth-snapshot.yml`
  (nightly, `0 22 * * *`); `api/scripts/probe_chain_sources.py` (RFC-1 feasibility probe)
- `api/analytics/onchain/{growth,comparison,response}.py` — EMA28 floor/ramp detection
  (N=180, R=0.25, M=14, S=180, 194-day history gate), index-100/log comparison
- `api/routers/onchain_activity.py`, `api/models/onchain_activity.py` —
  `GET /api/onchain/growth?metric=&start=`, `GET /api/onchain/chains`
- `web/app/onchain/page.tsx`, `web/components/onchain/` (OnchainDashboard, ChainPanel,
  ComparisonOverlay, UnavailableChainCard, …), `web/lib/{api,types}/onchain.ts`
- Tests: `api/tests/{data,analytics,routers,scripts}/…onchain…`/`…growthepie…`/`…l2beat…`,
  `web/components/onchain/__tests__/`, `web/e2e/onchain.spec.ts` (seeded by
  `seed_onchain` in `api/scripts/seed_e2e_cache.py`)

## Related Context

- `process/context/all-context.md` — root router, stack decisions, Open Decisions/Questions
- `process/context/data-sources/all-data-sources.md` — standing rules on free/keyless sources,
  redistribution flags, adapter conventions; has the "On-chain activity" provider section
  (growthepie, L2BEAT; Dune NOT-VIABLE; Etherscan V2 / Artemis rejected as paid)
- `process/context/tests/all-tests.md` — runner split (pytest/vitest/Playwright), the Standing
  Lesson table (esp. the narrative-dashboard RFC-6 real-cache-boundary bug, directly relevant to
  why this feature also needs a real-machine walkthrough AC)
- `process/features/cycle-regime/_GUIDE.md` — sibling dashboard feature; same "reproduce from
  primaries + honest gap states" philosophy, different data domain (macro liquidity, not chain
  activity)
- `process/features/narrative-mindshare/_GUIDE.md` — sibling dashboard feature; direct precedent
  for the user-editable config-file pattern (`narrative_category_map.json`) this feature's chain
  list follows

## Notes

Locked user decisions (2026-09-25) carried forward from the SPEC:

- "Robinhood" means **Robinhood Chain** (Arbitrum Orbit L2, mainnet 2026-07-01) — not Robinhood's
  brokerage app user count.
- Metrics: daily active addresses, new addresses, transaction count — all three, all chains.
- Chains: Ethereum, Robinhood Chain, Base, Arbitrum, Optimism, Polygon, BNB Chain, Tron, Solana —
  "all these above," including non-EVM, which implies at least one free-tier **keyed** source
  (most likely Dune) for Solana/BNB/Tron coverage. The user will create their own free account/API
  key as a setup step; the key is stored in env/GitHub Actions secrets, never shipped to the
  client.
- Robinhood Chain shown from launch, flagged "launched 2026-07-01, limited history"; floor/ramp
  markers only appear once a chain has enough history for the rule to mean something.
- Free sources only — no paid vendor, no exception, until a proxy demonstrably earns one (same
  standing bar the narrative feature already uses).

**As built (supersedes the SPEC notes above where they differ):** Dune proved NOT-VIABLE (HTTP 402,
read-only account), so the plan's fallback shipped: 6 live chains via growthepie (Polygon via
`polygon_pos`), Solana/BNB/Tron shown as unavailable cards, 2 metrics (active addresses,
transactions — new addresses dropped), no API key anywhere, route `/onchain`. Full reconciliation:
the plan's `## Post-EXECUTE Amendments`.

## Current Status

Status: **Complete.** `chain-growth_25-09-26` shipped (merged to `main` at `4110e3f`), AC-14
walkthrough passed and both risk-pack reviews approved by the user on 2026-09-28; task folder
archived to `completed/`.

## Folder Contents

```
process/features/onchain-activity/
  active/       -- in-progress plans (each task in a {slug}_{date}/ folder); currently empty
  completed/    -- archived plans
    chain-growth_25-09-26/   -- SPEC, PLAN, FEASIBILITY verdict, RFC reports, harness packs, CLOSEOUT
  backlog/      -- deferred/future plans; currently empty
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
