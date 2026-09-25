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

Not started — no code exists yet. Planned/target locations (final choices are an
INNOVATE/PLAN decision — see the SPEC's Open Questions):

- `api/data/{growthepie,l2beat,etherscan_v2,dune}_adapter.py` (TBD — exact source-per-chain
  mapping is OQ-1 in the SPEC) — one adapter per provider, common adapter shape, following the
  project's "providers live behind adapters" pattern
- `api/analytics/onchain/` (TBD) — normalization, floor/ramp detection, cross-chain comparison
  maths; Python-only, per the project's "one source of numerical truth" rule
- `api/routers/onchain_activity.py` (TBD), `api/models/onchain_activity.py` (TBD)
- `api/data/chain_growth_config.json` (TBD) — user-editable tracked-chain list, same "option B"
  pattern as `narrative_category_map.json`
- `web/app/onchain-activity/page.tsx` (TBD)
- `web/components/onchain-activity/` (TBD) — per-chain panels, normalized comparison/overlay view,
  drill-down
- `web/lib/api/onchain-activity.ts`, `web/lib/types/onchain-activity.ts` (TBD)
- Possible scheduled workflow, `.github/workflows/onchain-activity-snapshot.yml` (TBD — whether a
  nightly archive is needed is left to INNOVATE, same open question shape as the narrative and
  regime dashboards' own nightly snapshots)

## Related Context

- `process/context/all-context.md` — root router, stack decisions, Open Decisions/Questions
- `process/context/data-sources/all-data-sources.md` — standing rules on free/keyless sources,
  redistribution flags, adapter conventions; does **not** yet list any chain-activity provider —
  this feature introduces that provider category (growthepie / L2BEAT / Etherscan V2 / Dune are
  candidates, none yet added to that file — see the SPEC's Background section)
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

None of the candidate providers (growthepie, L2BEAT activity API, Etherscan V2, Dune) have been
live-probed yet — this sandbox's egress proxy blocks all of them, same constraint every other
dashboard feature in this repo has hit. Feasibility and exact per-chain source assignment is
INNOVATE/PLAN work, not resolved by the SPEC.

## Current Status

Status: **Not started.** SPEC written and locked (`chain-growth_25-09-26`); INNOVATE has not run.
No adapters, endpoints, or UI exist yet.

## Folder Contents

```
process/features/onchain-activity/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
    chain-growth_25-09-26/   -- SPEC written; awaiting INNOVATE
  completed/    -- archived completed plans; currently empty
  backlog/      -- deferred/future plans; currently empty
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
