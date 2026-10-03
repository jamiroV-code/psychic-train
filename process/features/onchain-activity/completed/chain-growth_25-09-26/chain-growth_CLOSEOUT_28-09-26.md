---
name: report:chain-growth-closeout
description: "Final closeout packet for the chain participant growth (/onchain) program — all 6 RFCs verified, archived"
date: 28-09-26
metadata:
  node_type: memory
  type: report
  feature: onchain-activity
  phase: closeout
---

# chain-growth — Closeout Packet (2026-09-28)

**Verdict:** Ready for UPDATE PROCESS archival — done and archived. All 6 RFCs are verified, AC-14
passed on the user's PC, and the user approved both high-risk review decisions.

1. **Selected plan path:** `process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md`
   (moved from `active/` in this session).
2. **Closeout classification:** Ready for UPDATE PROCESS archival.
3. **What was finished:**
   - RFC-1: feasibility probe + VERDICT (Dune NOT-VIABLE → fallback: growthepie + L2BEAT).
   - RFC-2: `api/data/chains.json`, `growthepie_adapter.py`, `l2beat_adapter.py`.
   - RFC-3: `cache.merge_onchain_series` (14-day revision window), `snapshot_chain_growth.py`,
     `.github/workflows/chain-growth-snapshot.yml` (22:00 UTC), `api/data/cache/onchain/` carve-out.
   - RFC-4: `api/analytics/onchain/{growth,comparison,response}.py`, `GET /api/onchain/growth`, `/chains`.
   - RFC-5: `/onchain` page (`web/app/onchain/`, `web/components/onchain/`).
   - RFC-6: seeded fixture (`seed_onchain`), `web/e2e/onchain.spec.ts` (16 scenarios).
4. **Verified:** pytest 516 passed / 5 deselected; vitest 138 (19 files); tsc exit 0; Playwright
   42/42 twice (RFC-6 report). AC-14 real-archive walkthrough passed on the user's PC, 2026-09-28
   ("looks good , approve both"). **Unverified:** none within scope. The GitHub cron runs ~2h late
   (accepted; follow-up task exists).
4b. **Validate-contract:** present, inline in the plan, Gate: PASS (25-09-26).
5. **Cleanup done:** plan Status Strip + `## Post-EXECUTE Amendments` + handoff; both
   `harness/rfc-00{3,4}/review-decision.json` set to `approved` (validator: 0 failures each);
   context docs (`all-context.md`, `data-sources/all-data-sources.md`, `tests/all-tests.md`, the
   feature `_GUIDE.md`). **Still needed:** the process commit (orchestrator).
6. **Next valid state:** commit these process changes (orchestrator via vc-git-manager), then pick
   the next task (for example the narrative-v2 program on `claude/narrative-v2`, or the cron-timing
   follow-up).
7. **Commit checkpoint:** Process commit belongs after UPDATE PROCESS. The source is already on
   `main` (`4110e3f`); this session changes only `process/` files.
8. **Regression status:** the RFC-6 E2E ran all 26 pre-existing specs green twice, and the
   route-list snapshot proves `/regime`, `/narrative` and `/screener` unchanged.
9. **SPEC achievement:**

| AC | Result | Proven by |
|---|---|---|
| AC-1, AC-2 | met | E2E scenarios 1, 2, 13, 14 |
| AC-3 | met | growth/comparison tests + real-data regression fixture; E2E 4, 7, 8; AC-14 |
| AC-4 | met | E2E 3, 15 |
| AC-5, AC-6 | met | E2E 5, 6 |
| AC-7 | met | E2E 9; RFC-3 merge tests |
| AC-8, AC-9 | met | E2E 10; adapter redistributable tests |
| AC-10 | met | E2E 11 |
| AC-11, AC-12 | met (on the reduced scope) | E2E 10, 12 (missing-archive proof replaces the Dune-key revoke) |
| AC-13 | met | comparison type-level test; E2E 7 |
| AC-14 | met | user walkthrough, 2026-09-28 |

Scope reductions fixed by the RFC-1 VERDICT (not unmet ACs, but recorded): Solana/BNB/Tron render
as unavailable; the new-addresses metric is dropped.

**Drift score:** 4 — files touched (+1), ≥10 files (+1), memory-worthy observations ≥3 (+1),
task folder archived (+1). HIGH.
Strongly recommend UPDATE PROCESS -- harness/protocol files touched.
(This packet is produced by that UPDATE PROCESS. Note: no harness or protocol file actually changed; the score is HIGH because of the file count and archival.)

TL;DR: chain-growth is verified and archived; only the process commit remains.
