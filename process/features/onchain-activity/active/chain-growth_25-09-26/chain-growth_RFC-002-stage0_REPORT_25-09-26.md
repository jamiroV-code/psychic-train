---
phase: rfc-002-stage0
date: 2026-09-25
status: COMPLETE_WITH_GAPS
feature: onchain-activity
plan: process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# chain-growth RFC-2 Stage 0 — What RFC-2 builds under the locked fallback

**TL;DR** — RFC-2 builds `chains.json` (6 live chains + Solana/BNB/Tron as source-unavailable), a
growthepie adapter, an L2BEAT cross-check adapter and a config loader. No Dune code at all. Metrics
are `daa` and `tx_count` only. Two small depth/shape checks need one user-PC command before RFC-3
backfill; they do not block writing RFC-2's code. **Stopped here for go-ahead.** No source or test
files were edited.

Input: `chain-growth-feasibility_FEASIBILITY_25-09-26.md` (RFC-1 VERDICT, re-read in full).

## 1. Chain → source mapping (locked)

| id | label | state | daa / tx_count source | growthepie key | L2BEAT cross-check key | launch_date |
|---|---|---|---|---|---|---|
| ethereum | Ethereum | live | growthepie | `ethereum` | — | 2015-07-30 |
| base | Base | live | growthepie | `base` | `base` | 2023-08-09 |
| arbitrum | Arbitrum | live | growthepie | `arbitrum` | `arbitrum` | 2021-08-31 |
| optimism | Optimism | live | growthepie | `optimism` | `op-mainnet` (to verify; else none) | 2021-12-16 |
| polygon | Polygon | live | growthepie | `polygon_pos` | — | null (read from master.json at runtime) |
| robinhood | Robinhood Chain | live | growthepie | `robinhood` | `robinhood` | 2026-07-01 |
| solana | Solana | source unavailable | none | — | — | — |
| bnb | BNB Chain | source unavailable | none | — | — | — |
| tron | Tron | source unavailable | none | — | — | — |

## 2. `api/data/chains.json` schema (ADR-6, fallback form)

```json
{
  "_comment": "User-editable chain list. source: growthepie | none. 'none' = shown as source unavailable, never dropped. Attribution for growthepie is page-level.",
  "chains": [
    {
      "id": "base",
      "label": "Base",
      "enabled": true,
      "launch_date": "2023-08-09",
      "metrics": {
        "daa":      {"source": "growthepie", "source_key": "base"},
        "tx_count": {"source": "growthepie", "source_key": "base"}
      },
      "cross_check": {"source": "l2beat", "source_key": "base"}
    },
    {
      "id": "solana",
      "label": "Solana",
      "enabled": true,
      "launch_date": null,
      "metrics": {
        "daa":      {"source": "none", "unavailable_reason": "source-unavailable"},
        "tx_count": {"source": "none", "unavailable_reason": "source-unavailable"}
      }
    }
  ]
}
```

- Allowed `source` values: `growthepie`, `none`. Anything else → skip + warn (narrative map posture).
- `cross_check` is optional; allowed source `l2beat` only.
- `new_addresses` is **not** a key. The loader treats it as unknown and warns if present.
- Metric names: `daa`, `tx_count` (API side); growthepie metric keys are `daa`, `txcount`.

## 3. Adapters and loader (new files only)

| File | Signature (proposed) | Notes |
|---|---|---|
| `api/data/chain_growth_config.py` | `load_chains(path=DEFAULT) -> list[ChainConfig]` | skip+warn on bad entries; frozen dataclasses |
| `api/data/growthepie_adapter.py` | `fetch_metric_history(metric: str, chain_keys: list[str], client=None) -> dict[str, GrowthepieSeries]` | one HTTP call per metric, split per chain; each chain's result independent (`ok`/`unavailable`/`stale`), never raises; schema-checked; `REDISTRIBUTABLE = True`, `ATTRIBUTION = "Source: growthepie, https://www.growthepie.com."` |
| `api/data/l2beat_adapter.py` | `fetch_activity(project: str, range_: str = "max", client=None) -> L2beatActivity` | cross-check only; `REDISTRIBUTABLE = False`; unknown shape → `unavailable` with reason, never raises |

**No Dune adapter, not even a stub.** Why: the locked fallback says ship growthepie/L2BEAT chains only
and forbids improvising; the plan's stub precedent (E5) is for L2BEAT only. A Dune stub would add an
always-unavailable module, a config source value and tests for zero behaviour; Solana/BNB/Tron are
already honest via `source: "none"`. A future plan can add a real Dune (or other) adapter by adding a
source value. Minimal and consistent with "no third option".

## 4. growthepie history endpoint

- Use the per-metric endpoint **`https://api.growthepie.xyz/v1/metrics/{metric}.json`** (`daa`,
  `txcount`), one call per metric covering all chains. Not `fundamentals_full.json` (403).
- Fallback candidate if that path fails: the per-chain `https://api.growthepie.xyz/v1/chains/{key}.json`.
- Both paths are from growthepie's public frontend/API usage, **not yet confirmed** from this
  container (egress blocked). The adapter's schema check makes a wrong shape `unavailable`, never
  silent. Depth is recorded by the backfill (ADR-3), not assumed.

**User-PC check (read-only, keyless, one line, from repo root):**

```bash
uv run --project api python -c "import httpx;r=httpx.get('https://api.growthepie.xyz/v1/metrics/daa.json',timeout=60);print(r.status_code);d=r.json();c=(d.get('data') or {}).get('chains') or {};print('top keys:',list(d)[:10]);[print(k,(c[k].get('daily') or {}).get('types'),(c[k].get('daily') or {}).get('data',[[None]])[0][:1],len((c[k].get('daily') or {}).get('data',[]))) for k in ('ethereum','base','arbitrum','optimism','polygon_pos','robinhood') if k in c]"
```

Send back the output. It gives status, shape, first timestamp and row count per chain (= depth).

## 5. L2BEAT range param and Optimism

- Request `.../activity/{project}?range=max` for backfill, `?range=30d` (default) nightly. The
  `range` parameter name/value is L2BEAT's frontend convention; unverified here.
- Optimism: L2BEAT lists OP Mainnet as `op-mainnet`, which likely explains the FAIL on `optimism`.
  Config uses `op-mainnet`; if it still fails, drop `cross_check` for optimism (E5 per project).
- Adapter parses `chart.types` + `chart.data` by column name (`timestamp`, `count`, `uopsCount`),
  not position; any other shape → `unavailable` with reason `unexpected-shape`.

**User-PC check (one line):**

```bash
uv run --project api python -c "import httpx;[print(p,q,(lambda r:(r.status_code,len(((r.json().get('data') or r.json()).get('chart') or {}).get('data',[]))) if r.status_code==200 else r.status_code)(httpx.get(f'https://l2beat.com/api/scaling/activity/{p}?range={q}',timeout=60))) for p in ('op-mainnet','optimism','base') for q in ('max','30d')]"
```

If it throws on a shape, paste the error; it is still a finding.

## 6. Tests RFC-2 will add (no network)

- `api/tests/data/test_growthepie_adapter.py`: contract shape, redistribution flag + attribution,
  malformed payload → unavailable, **per-chain isolation** (one chain's rows malformed, another's
  fine → second still `ok`; two calls per E7's spirit).
- `api/tests/data/test_l2beat_adapter.py`: shape parse by column name, unexpected shape (optimism
  fixture) → unavailable, `redistributable=False`.
- `api/tests/data/test_chain_growth_config.py`: skip+warn, `source: none` accepted,
  `new_addresses` rejected with warning, no key fields anywhere.
- One opt-in `-m integration` test per adapter (Hybrid).

## 7. Changes to RFC-3..6 (for UPDATE PROCESS)

| RFC | Change |
|---|---|
| RFC-3 | No `DUNE_API_KEY` secret; workflow has **no secrets at all**. Snapshot script calls growthepie (2 calls) + L2BEAT (≤4 calls). Backfill = growthepie + L2BEAT only; no Dune bounded pull. Decided: no daily `status=unavailable` rows are written for Solana/BNB/Tron; those chains are reported by the API from config, not written as daily rows. Risk pack (E2) **still required** for the `contents: write` workflow, but smaller: drop secret-exfil scenarios, keep push-race, trigger scope (E1) and supply-chain scenarios. |
| RFC-4 | Metric enum = `daa`, `tx_count`. API returns Solana/BNB/Tron with `status: unavailable, reason: source-unavailable`. L2BEAT used only as a cross-check field. `redistributable` per series from adapter constants. |
| RFC-5 | Panels show two metrics. Page-level note that new-addresses is not available (no free source). `SourceAttributionFooter` string = "Source: growthepie, https://www.growthepie.com.". Remove `dune-credit-exhausted` from new `UnavailableReason` variants; add `source-unavailable`. |
| RFC-6 | AC-14 forced-failure case can no longer use a missing `DUNE_API_KEY`; use Solana/BNB/Tron (always unavailable) plus a forced growthepie/L2BEAT failure in the seeded E2E. data-sources doc covers growthepie + L2BEAT; Dune recorded as evaluated and rejected. |

## 8. Plan-text amendments for UPDATE PROCESS (not applied here)

1. ADR-1: Dune removed; growthepie also covers Polygon (`polygon_pos`); Solana/BNB/Tron source-unavailable; cite VERDICT.
2. ADR-2: marked superseded (Dune not used).
3. ADR-3: remove `DUNE_API_KEY` mapping and the Dune backfill pull.
4. ADR-6: `source` enum `growthepie|none`; optional `cross_check`; no `new_addresses` key.
5. ADR-8: growthepie `True` (attribution string), L2BEAT `False`, Dune `False`/unused.
6. RFC-2 Scope/Touchpoints/Test gates: remove `dune_adapter.py`, `dune_queries/*.sql`, `test_dune_adapter.py`; move the isolation scenario (P7/E7) to `test_growthepie_adapter.py`.
7. RFC-3 per §7; E2 stays; P5 wording "first `DUNE_API_KEY` secret" → "new `contents: write` workflow".
8. AC-1 amended: "all tracked metrics" = `daa` + `tx_count`; new-addresses deferred to a follow-up plan. AC-6 met by slug `robinhood`. AC-9 flags per §VERDICT.
9. Test Gates table: drop `chain-growth-dune-query-isolation` / `chain-growth-dune-credit-budget-probe` rows or mark superseded; add growthepie isolation row.
10. Open Question: follow-up backlog stub for a free new-addresses source and for Solana/BNB/Tron coverage.

## 9. Decisions needed from the user

- **One:** go-ahead to build RFC-2 as above. (Optional, not blocking: run the two one-liners in §4
  and §5 and send the output; RFC-2 code works either way, and RFC-3 backfill needs the depth
  answer.)

All other points were decided here (no Dune stub; `source: "none"`; L2BEAT slug `op-mainnet`;
per-metric growthepie endpoint; unavailable chains served from config, not cache rows).

## Closeout

- Classification: **Keep in active/testing** — Stage 0 presented, RFC-2 code not started.
- Follow-up stubs created: none (item 10 above is for UPDATE PROCESS).
- CONTEXT_PARTIAL: none.
- Deviations: none; the Polygon move is the plan's own anticipated exit-gate case.

## Forward Preview

### Test Infra Found
- `httpx.MockTransport` fixtures (RFC-1 precedent) fit both adapters.

### Blast Radius Changes
- RFC-2 is smaller than planned: 3 new modules + `chains.json` + 3 test files; no Dune files.

### Commands to Stay Green
- `uv run --project api pytest api/ -q` → 412 passed, 3 deselected (unchanged; no code touched).

### Dependency Changes
- None.
