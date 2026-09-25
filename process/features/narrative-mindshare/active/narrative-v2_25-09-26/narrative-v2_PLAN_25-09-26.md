---
name: plan:narrative-v2
description: "narrative dashboard v2 — real-data sufficiency gating, file-editable narratives (6-15), momentum view, daily mindshare view; single complex plan with 7-RFC breakdown"
date: 25-09-26
feature: narrative-mindshare
---

[MODE: PLAN]

# Narrative Dashboard v2 — Real-Data Fixes, File-Editable Narratives, Momentum & Mindshare

**Date**: 25-09-26
**Status**: DRAFT — awaiting VALIDATE
**Complexity**: COMPLEX (single plan, 7-RFC internal breakdown)

## Overview

v1 of `/narrative` (24-09-26) shipped but the user's real-data walkthrough on 25-09-26 found three
problems: (1) `scoring.normalize_within_source` returns a flat `0.5` for any all-constant or
single/zero-point series, which `history.py` then treats as a real composite reading — every
category with thin data ties at a fake `0.50` instead of admitting insufficient history; (2) there
is no way to add/rename/remove a narrative or set its coins without a code change (today's file,
`narrative_category_map.json`, only maps coins onto an already-fixed 4-category seed list in
`narrative_categories.json`); (3) there is no momentum (rising/falling + accelerating/
decelerating) or daily cross-narrative mindshare view — the two things the dashboard exists to
answer at a glance are both missing.

This plan (COMPLEX, single plan file, 7-RFC breakdown per the SPEC and INNOVATE decision) fixes
all three without touching `/api/narrative/categories`, the `/screener` narrative strip, or the
confidence badge (AC-13, unchanged from v1's own frozen-contract rule).

Locked user decisions carried in as ADRs below: cross-sectional (vs-the-field) momentum ranking,
"blend + show each source" daily mindshare, sticky one-time caveat, and 6-15 simultaneous
narratives as the design floor/ceiling everywhere cross-narrative comparison happens.

## Quick Links

- SPEC: `process/features/narrative-mindshare/active/narrative-v2_25-09-26/narrative-v2_SPEC_25-09-26.md`
- v1 plan (structural + architectural precedent): `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
- Context: `process/context/all-context.md`, `process/context/tests/all-tests.md`,
  `process/context/data-sources/all-data-sources.md`, `process/context/planning/all-planning.md`
- Feature guide: `process/features/narrative-mindshare/_GUIDE.md`

### Status Strip

| RFC | Scope | Status |
|---|---|---|
| RFC-1 | Data-sufficiency gating (history.py + new scoring helper) + chart regression coverage | ⏳ NOT STARTED |
| RFC-2 | Unified narrative config file (`api/data/narratives.json`) + loader + migration off the 2-file seed/map split | ⏳ NOT STARTED (depends on RFC-1) |
| RFC-3 | Multi-keyword blending + anchor-chained pytrends batching (nightly job + backfill script) | ⏳ NOT STARTED (depends on RFC-2) |
| RFC-4 | Momentum view (cross-sectional, vs-the-field ranking) | ⏳ NOT STARTED (depends on RFC-3) |
| RFC-5 | Daily social-mindshare view (blend + show each source) | ⏳ NOT STARTED (depends on RFC-3, parallel to RFC-4) |
| RFC-6 | Caveat de-duplication (sticky, once per page) | ⏳ NOT STARTED (no hard dependency — may run anytime after RFC-1) |
| RFC-7 | Tripwire snapshot + AC-13 re-confirm + seeded Playwright + AC-14 handoff | ⏳ NOT STARTED (depends on all above) |

Code-only completion is `CODE DONE`, not `VERIFIED`. A phase reaches `✅ VERIFIED` only after its
own test gates are green AND regression checks against RFC-3's AC-13 contract test still pass.

## Strategy Recommendation (this plan)

Per `vc-agent-strategy-compare`: this is one COMPLEX plan with 7 internal RFCs, not a phase
program — RFCs 1→2→3 are strictly sequential (each is a hard precondition for the next: sufficiency
gating must exist before the config file changes what feeds it; the config file must exist before
multi-keyword/batching can read >4 narratives), RFC-4/RFC-5 are the only pair with genuine
independence (both consume RFC-3's batched series, touch disjoint files — `momentum.py`/`MomentumView.tsx`
vs `mindshare.py`/`MindshareView.tsx` — and neither's output feeds the other), and RFC-6/RFC-7 are
cleanup/proof passes. Score: **S3 (3+ viable directions: RFC-4/5/6 all buildable independently once
RFC-3 lands) + S7 (5+ files in blast radius) = 2/7 → MEDIUM**. Recommendation for EXECUTE: run
RFC-1→2→3 sequentially (single vc-execute-agent, one plan section at a time, matching v1's own
successful precedent), then run RFC-4 and RFC-5 as **two parallel vc-execute-agent subagents**
(disjoint files, no coordination needed — fire-and-forget parallel subagents are the correct tier,
not agent-team, because neither RFC's output depends on the other's mid-flight state), then RFC-6
and RFC-7 sequentially. This is not a phase program: one umbrella plan file was explicitly not
warranted (7 RFCs inside one feature, one shared blast radius, one shared validate-contract — same
shape v1 used successfully).

## Acceptance Criteria

This plan implements AC-1 through AC-14 as locked in
`narrative-v2_SPEC_25-09-26.md`. Each RFC's `AC mapping` line in `## 1.5 Execution Brief` states
which criteria it closes; the consolidated `## Verification Evidence` table below maps every gate
to its criterion and proving strategy. Do not restate the SPEC's AC text here — read the SPEC
directly; this plan only adds proof and implementation mapping.

## 1. Context and Goals

**Goal**: make `/narrative` tell the truth about how much data it has, let the user define their
own narrative set (6-15 narratives) without a code change, and add the two comparison views
(momentum, daily mindshare) that are the actual point of the page.

**Non-goals** (verbatim from SPEC's Out Of Scope): touching `/categories`/`/screener`/confidence
badge; paid vendors; in-app editor UI; backfilling Reddit/CoinGecko/exchange history; turning on
Reddit credentials; changing the exchange-volume formula; backtesting momentum/mindshare against
2017/2020-21; automated buy/sell signals.

**Root cause being fixed** (RFC-1): `scoring.normalize_within_source` (api/analytics/narrative/scoring.py)
returns `pd.Series(0.5, index=series.index)` whenever `hi == lo` — true for every series with 0 or
1 non-null points (min==max is trivially true, or the check on an empty/all-NaN series short-circuits
into an empty/degenerate frame that `history.build_composite` still averages against real sources).
`history.py::build_composite` has no minimum-real-point-count gate at all today — it only requires
`MIN_AVAILABLE_SOURCES` (2) composite *slots* to be present that date, not that any slot's own
series has genuine history. A category running on 1 CoinGecko point and 1 exchange-share point
"passes" the slot-count gate and gets a `0.5`-anchored composite that looks like real data.

## Phase Completion Rules

- `⏳ NOT STARTED` → `🚧 IN PROGRESS` when EXECUTE begins that RFC's checklist.
- `🚧 IN PROGRESS` → `✅ CODE DONE` when all checklist items are implemented and that RFC's own
  automated gates are green.
- `✅ CODE DONE` → `✅ VERIFIED` only after: (a) the RFC's own test gates green, (b) the AC-13
  contract-snapshot regression test (`api/tests/routers/test_narrative_categories_contract.py`)
  still passes unmodified, (c) any agent-probe scenario named for that RFC has been run.
- Do not mark `✅ VERIFIED` from code inspection alone.

## 2. Non-Goals and Constraints

Carried forward from SPEC `## Constraints` verbatim, plus:

- **No new provider adapter.** RFC-3's pytrends batching reuses the existing `pytrends_adapter.py`
  surface; it does not add a new source.
- **`narrative_categories.json` + `narrative_category_map.json` are retired by RFC-2**, replaced by
  one file (`api/data/narratives.json`); `mapping.LEGACY_COIN_CATEGORY_MAP` and
  `mapping.map_coin_to_category` (the frozen `/categories` path) are untouched — RFC-2 adds a new
  loader alongside the frozen one, it does not modify or remove `mapping.py`'s existing frozen
  functions.
- **`trigger.py`, `scoring.normalize_within_source` (existing signature/behavior), `mapping.py`'s
  frozen functions, and both legacy JSON files are never edited.** RFC-1 adds a *new* function
  (`scoring.normalize_with_sufficiency`) alongside the existing one; RFC-2 adds a *new* loader
  module function set alongside `mapping.load_category_map`/`map_coin_to_narrative_category` (those
  two functions are themselves superseded by RFC-2's new loader for `/history`'s purposes, but are
  left in place, unused-but-present, rather than deleted — deleting risks an import-time break
  somewhere the RFC-2 research pass didn't find; a deprecation note is added instead. See ADR-2 for
  the full migration decision.)

## 3. Architecture Decisions (Final)

### ADR-1: Sufficiency gating lives only in `history.py` + a new `scoring.normalize_with_sufficiency` helper

**Decision**: Add `MIN_SUFFICIENT_POINTS = 2` (insufficient-history floor) and
`MATURE_POINTS_THRESHOLD` (a documented value, e.g. 5, marking "provisional/thin" vs "mature") as
new constants in `history.py`. Add a new pure function in `scoring.py`:

```python
def normalize_with_sufficiency(series: pd.Series, min_points: int = 2) -> tuple[pd.Series, str]:
    """Returns (normalized_or_none_series, sufficiency_status).
    sufficiency_status in {"insufficient", "provisional", "mature"}.
    A series with fewer than min_points non-null values returns an all-None
    series (never 0.5) and status="insufficient" — history.py must never
    feed an insufficient series into build_composite or a rank.
    """
```

`normalize_within_source` (the existing function) is **not modified** — `trigger.py`'s
`/categories` path keeps calling it exactly as before (frozen). `history.py::normalize()` is
changed to call the new `normalize_with_sufficiency` instead, and `SeriesData`/`NarrativeHistoryPoint`
gain a `sufficiency: Literal["insufficient","provisional","mature"]` field (additive to the pydantic
model — AC-13's `/categories` model is untouched, this is `/history`'s own model). `build_composite`
gains a per-source-instance minimum-point check: an `insufficient` series never contributes a slot
value for any date, full stop — the flat-`0.5` bug (root cause above) cannot recur because the
insufficient series contributes `None`, and `None` normalized values are already skipped by
`build_composite`'s existing `if row.normalized is None: continue` line.

**Rationale**: single-owner fix (one file + one new pure function), zero risk to `trigger.py`
(the file `vc-predict` flagged CAUTION on), directly closes AC-1/AC-2/AC-3/AC-10.

**Rejected**: patching `normalize_within_source` itself (touches the frozen `/categories` path —
banned by SPEC constraint and the INNOVATE mitigation).

### ADR-2: `api/data/narratives.json` — one file, id-keyed, two-version migration window

**Decision**: RFC-2 introduces `api/data/narratives.json`:

```json
{
  "version": 2,
  "narratives": [
    {"id": "ai", "label": "AI", "keywords": ["AI crypto", "artificial intelligence crypto"],
     "coins": ["FET", "TAO", "RENDER", "WLD", "VIRTUAL", "AI16Z"], "enabled": true}
  ]
}
```

seeded from the union of today's `narrative_categories.json` (4 seeds) + `narrative_category_map.json`
(32 coins) at migration time (one-time script, `api/scripts/migrate_narrative_config.py`, run once
during RFC-2 EXECUTE, output committed — not a runtime migration). A new loader,
`api/analytics/narrative/narrative_config.py::load_narratives()`, replaces `history.py`'s calls to
`trigger.load_seed_categories` + `mapping.load_category_map`/`map_coin_to_narrative_category` for
the `/history` and `/narrative` and nightly-snapshot/backfill paths ONLY. `mapping.py`'s frozen
`LEGACY_COIN_CATEGORY_MAP` and its two frozen functions are left in place unused by the new path
(deprecation comment added, not deleted — see Non-Goals above); `trigger.py` is not touched at all.

**Series keying migration (id vs keyword)**: today pytrends/reddit archive under `keywords[0]`
(the first keyword only). RFC-3 adds multi-keyword blending, so a single "current key" no longer
exists per narrative once >1 keyword drives the fetch. **Decision: keep archiving under the
existing keyword key for the FIRST keyword in the list (backward-compatible with all already-archived
v1 data — zero data loss, zero re-migration of existing Parquet files), and additionally archive a
new *per-narrative-id* blended composite row** (`cache.write_narrative_series("pytrends-blended", narrative_id, ...)`,
new cache_key namespace, does not collide with the existing keyword-keyed rows). `/history` reads
BOTH: existing keyword-keyed single-term series (labelled per-keyword, shown as before) plus the
new id-keyed blended series (labelled "blended, N keywords") when a narrative has 2+ keywords.

**Rename/remove behavior (AC-7)**: renaming a narrative's `label` (not its `id`) has no effect on
archived history — history is keyed by `id`, never by `label`, so a label rename is purely cosmetic.
Removing a narrative (deleting its entry from `narratives.json`, or setting `enabled: false`) does
NOT delete its archived Parquet rows — `/history` simply stops returning that narrative once its
`id` is absent from the config; the archive is retained under its old `id` indefinitely and would
reappear unchanged if the entry is re-added later. This is stated once, in the loader's own
docstring and in the `_comment` field of `narratives.json` itself (mirroring `narrative_category_map.json`'s
existing in-file `_comment` convention) — no separate doc page.

**Malformed-entry handling (AC-6)**: reuses `mapping.py`'s existing validate-and-skip-with-warning
pattern (`_validate`), extended to also check: non-empty `label`, non-empty `keywords` list,
duplicate `id` (first occurrence wins, duplicates skipped with a warning naming both), duplicate
`label` (allowed but warned — labels are cosmetic, ids are the real key). A structurally invalid
top-level file (not JSON, not an object, missing `"narratives"` key) falls back to the
**last-known-good in-memory cached copy** (the existing mtime-cache pattern in `mapping.py` already
does this implicitly by returning the prior cached value on load failure — RFC-2's loader copies
that exact fallback shape) rather than an empty list, satisfying AC-6's "still renders the
last-known-good configuration" requirement.

**6-15 narrative range**: `load_narratives()` has no upper bound in code (any count works); RFC-2's
seed migration only produces 4 entries, so RFC-2's own test fixture must include a synthetic
6-narrative and 15-narrative fixture set (used again by RFC-7's tripwire) to prove nothing breaks
past 4 — this is explicitly deferred to RFC-2's + RFC-7's test plans below, not solved by the
loader alone.

**Rejected**: an in-app editor (locked user decision, out of scope). A second live-reload watcher
process (unnecessary — the existing mtime-check-on-read pattern from `mapping.py` already satisfies
"no restart needed" with zero added infrastructure).

### ADR-3: Multi-keyword blending + anchor-chained pytrends batching

**Decision**: `RFC-3` changes two call sites — `api/scripts/backfill_pytrends_history.py` and the
nightly snapshot path in `api/scripts/snapshot_narrative.py` — to batch keywords 5-at-a-time per
Google Trends request (pytrends' real per-request cap) using **anchor-keyword chaining**: request 1
uses keywords `[anchor, k1, k2, k3, k4]`; request 2 reuses `anchor` plus the next 4 keywords, so
every batch shares one common term whose value in both requests is used to rescale the second
batch's 0-100 index onto the first batch's scale (standard Trends anchor-chaining technique — the
anchor keyword's own value in each batch gives the scale factor: `scale = anchor_value_batch1 /
anchor_value_batch2`, applied to every other keyword in batch2). With N narratives contributing up
to (today) 2 keywords each, worst case 15 narratives × 2 keywords = 30 terms → 1 anchor + 29 others
÷ 4-per-batch (after reserving 1 slot for the anchor) = 8 requests per nightly run (well within
pytrends' unofficial rate tolerance — documented in `data-sources/all-data-sources.md`'s pytrends
section; RFC-3's research step must re-confirm the current rate guidance before implementation and
record it in the phase report, not assume it's unchanged).

**Zero/near-zero-anchor guard**: if the anchor keyword's value in a batch is 0 or below a small
epsilon (e.g. <1), the scale factor is undefined/unstable — every keyword in that batch is marked
`status="insufficient"` for that day rather than computing a fabricated ratio (division-by-near-zero
guard, directly enforced by the SPEC's "numbers are never silently wrong" constraint).

**Multi-keyword blending within one narrative**: today `l2s` has 2 keywords but only `keywords[0]`
is ever fetched (the bug named in the SPEC constraints). RFC-3 fetches ALL of a narrative's
keywords (subject to the batching above) and blends them into the new id-keyed blended series (ADR-2)
via a simple mean of each keyword's own within-source-normalized value for that day (never raw
cross-keyword averaging — same "normalize within source first" rule as everywhere else in this
codebase).

**Backfill**: `backfill_pytrends_history.py` gets the same batching/anchor-chaining logic — this is
the SPEC's explicit "covers the nightly job AND the backfill" requirement. Only the currently-primary
keyword per narrative (i.e. today's already-backfilled 269-day history, per ADR-2's keying decision)
is preserved as-is; net-new keywords/narratives backfill only from the day RFC-3 first runs
(consistent with v1's own "everything else starts thin and grows forward only" precedent — SPEC
Constraints carries this forward unmodified).

**Rejected**: fetching every keyword in its own single-term request (no batching) — this was
correctly ruled out by the SPEC's OQ-1 framing (5-term cap makes 6-15 narratives' worth of keywords
un-fetchable one-at-a-time within reasonable rate limits) and is the reason anchor-chaining was
selected over a naive sequential-request approach.

### ADR-4: Momentum view — cross-sectional (vs-the-field), USER DECISION 2026-09-25

**Decision**: `api/analytics/narrative/momentum.py` (new) computes, for each narrative with
sufficient data (ADR-1's `mature` status on at least one composite-eligible source), a `recent
change` value over a stated window (`MOMENTUM_WINDOW_DAYS = 7`, matching `history.py`'s existing
`CHANGE_WINDOW_DAYS` for consistency) and an `acceleration` value (the rate-of-change of that
change over a second, trailing window — `ACCELERATION_WINDOW_DAYS = 14`, i.e. compare this week's
7-day change to last week's 7-day change). Narratives are then **ranked against each other** on
recent change (not shown as an absolute number in isolation) — this is the "versus the other
narratives" framing the user locked in. Output: ranked bars (highest-to-lowest recent change) with
a gaining/slowing arrow per narrative (`↑ accelerating`, `↑ decelerating`, `↓ accelerating`, `↓
decelerating`, computed from the sign of change × sign of acceleration). A quadrant view (change ×
acceleration scatter) is optional and explicitly budgeted as a stretch item inside RFC-4's own
checklist, not required for RFC-4 to reach `✅ CODE DONE`.

**Basis fallback (`momentum_basis` field)**: momentum is computed from the id-keyed blended pytrends
series (ADR-2/ADR-3) when it has `mature` status; when a narrative's blended pytrends is `insufficient`
or `provisional`, momentum falls back to that narrative's own composite (ADR-1's composite, when
mature) instead. The response carries an explicit `momentum_basis: Literal["pytrends-blended",
"composite", "insufficient"]` field per narrative so the frontend/caller always knows which basis
produced a given ranking — never silently mixing bases without disclosure.

**Rejected**: an absolute (non-comparative) momentum score per narrative alone — explicitly
overridden by the user's 2026-09-25 decision in favor of cross-sectional ranking.

### ADR-5: Daily mindshare view — "blend + show each", USER DECISION 2026-09-25

**Decision**: `api/analytics/narrative/mindshare.py` (new) computes, for a user-selected date, each
source's own same-day cross-narrative share: pytrends share (each narrative's blended, within-source-
normalized pytrends value that day ÷ sum across all narratives with a value that day — the
shared-scale property anchor-chaining already establishes per ADR-3), CoinGecko-trending share (via
the ADR-2 config map — count of that narrative's coins appearing in trending ÷ total trending-tagged
coin appearances that day), and Reddit share (same shape, only when Reddit credentials/data exist —
`REDDIT_REDISTRIBUTABLE` gate and Reddit's existing "0 rows, no creds" reality from the SPEC context
are both honored: a day with zero Reddit rows across all narratives means Reddit is simply absent
from that day's blend, not zero-filled). The headline **mindshare %** per narrative is the mean of
whichever per-source shares are present that day (arithmetic mean across available sources — same
skipna-mean pattern `build_composite` already uses, reused rather than reinvented). Per-source
shares are returned alongside the headline (`sources: {pytrends: 0.34, coingecko: 0.28, reddit: null}`)
so disagreement between sources is visible, not hidden inside one blended number — this is the
"show each" half of the user's decision. Days where fewer than 2 sources have any data are labelled
`only_one_source: true` (or `no_sources_available` when zero) rather than silently presenting a
single-source share as if it were consensus.

**UI shape**: a 100%-stacked daily bar (one bar per narrative, stacked to sum to the headline
mindshare total — which itself always sums to 100% by construction since shares are normalized
within-day) plus a date picker defaulting to the latest archived day. Works identically at 6 or 15
narratives (no hardcoded slot count anywhere in `mindshare.py` — the narrative list length drives
everything).

**Rejected**: picking one single "best" source per day instead of blending (loses the disagreement
signal the user explicitly asked to keep visible) and a pure single-blended-number-only view with
no per-source breakdown (same reason, rejected by the user's own "show each" framing).

### ADR-6: Caveat shown once (sticky), not per view

**Decision**: `DataQualityCaveat.tsx` (existing, v1) is currently rendered once per
`CategoryHistoryPanel` instance (i.e. once per narrative, N times on the page). RFC-6 moves it to a
single instance in `NarrativeDashboard.tsx`'s own top-level layout (sticky/pinned near the page
header, matching the "prominent, once" requirement), removes the per-panel instantiation from
`CategoryHistoryPanel.tsx`, and adds a rendering regression test (AC-12) asserting exactly one
`data-testid="narrative-caveat"` element exists on the page regardless of narrative count (6 or 15
fixture, reusing RFC-2/RFC-7's fixture set).

**Rejected**: a dismissible-and-remembered caveat (adds state/localStorage complexity the SPEC
never asked for — the requirement is "once per page load," not "once ever").

### ADR-7: Test strategy — tripwire + fixture-through-real-cache-boundary, unchanged pattern from v1

**Decision**: Following the Standing Lesson in `tests/all-tests.md` ("a green suite that never
crosses a boundary is not evidence about that boundary"), RFC-7 adds:
1. A **tripwire snapshot test** on `trigger.py`'s public surface (`compute_narrative_categories`,
   `load_seed_categories`, and every symbol RFC-1/2/3 might have been tempted to touch) — asserts
   the function signatures and the exact set of exported names are byte-identical to before this
   plan, failing loudly if anyone edits the frozen file.
2. **AC-13 re-confirmation**: `api/tests/routers/test_narrative_categories_contract.py` (v1's
   existing test) re-run unmodified — no new assertions added, its continued green pass IS the
   proof.
3. Isolated-cache round-trip tests for the new `narratives.json` loader and the new
   `pytrends-blended`/composite cache-key namespace (writes through `cache.write_narrative_series`,
   reads back, asserts shape) — same `isolated_cache` fixture pattern `conftest.py` already
   provides (Standing Rule #3 in `tests/all-tests.md`).
4. A **6-15-narrative fixture** (`api/tests/fixtures/narrative_fixture_15.json` or equivalent,
   built by extending `seed_e2e_cache.py::build_narrative_fixture`) exercising momentum, mindshare,
   comparison and ranking at the stated floor (6) and ceiling (15).
5. A seeded Playwright update (`web/e2e/narrative.spec.ts`) covering the new momentum view, the new
   mindshare view, the caveat singularity check, and a config-file-edit-reflected-without-restart
   scenario (AC-4).
6. AC-14's real-machine walkthrough handoff, written in the same format as v1's AC-12 walkthrough
   (this sandbox's egress proxy blocks every provider — unchanged constraint, see Constraints).

## 1.5 Execution Brief

### RFC-1: Data-sufficiency gating

**Stage 0 (present and STOP)**: before writing any code, execute-agent must present: (a) the exact
new constants (`MIN_SUFFICIENT_POINTS`, `MATURE_POINTS_THRESHOLD` — proposed default 5, justify or
adjust), (b) the exact new `scoring.normalize_with_sufficiency` signature, (c) the exact new
`sufficiency` field addition to `NarrativeHistoryPoint`/`SeriesData`, (d) confirmation that
`normalize_within_source` and `trigger.py` remain byte-identical (grep diff against `git show
HEAD:api/analytics/narrative/scoring.py` and `trigger.py` before and after). Get explicit
confirmation before touching `build_composite`.

**Touchpoints**: `api/analytics/narrative/scoring.py` (add function, do not modify existing),
`api/analytics/narrative/history.py` (`normalize()`, `_prepare()`, `build_composite()`,
`SeriesData`, `CategoryHistory`, `NarrativeCompositePoint`-feeding code), `api/models/narrative.py`
(`NarrativeHistoryPoint.sufficiency` additive field), `web/lib/types/narrative.ts` (additive type),
`web/components/narrative/CategoryHistoryPanel.tsx` (render insufficient-history marker instead of
a plotted point).

**Blast radius**: 6 files, 0 packages beyond `api/`+`web/` (already in scope), no schema/auth/API
surface beyond an additive field on an existing response model (backward-compatible — existing
consumers ignoring an unknown field keep working; `/screener` never calls `/history` at all, so
AC-13 is unaffected by construction, not just by convention).

**AC mapping**: AC-1, AC-2, AC-3.

**Test commands**: `uv run --project api pytest api/tests/analytics/narrative/test_scoring.py
api/tests/analytics/narrative/test_history.py -q`; `pnpm --filter web test -- CategoryHistoryPanel`.

**Verification evidence**:
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_normalize_with_sufficiency_zero_points` | Fully-Automated | AC-1 |
| `test_normalize_with_sufficiency_one_point` | Fully-Automated | AC-1 |
| `test_build_composite_never_uses_insufficient_slot` (reproduces today's real-data shape: pytrends backfilled, others 0-1 points) | Fully-Automated | AC-2 |
| `test_composite_no_fake_tie_across_categories` | Fully-Automated | AC-2 |
| `CategoryHistoryPanel.test.tsx::renders provisional marker below mature threshold` | Fully-Automated | AC-3 |
| `CategoryHistoryPanel.test.tsx::renders insufficient-history marker not a line` | Fully-Automated | AC-1 |

### RFC-2: Unified narrative config file + loader + migration

**Stage 0 (present and STOP)**: present the exact `narratives.json` schema (above), the exact
migration script plan (one-time, output committed, not a runtime step), the exact fallback behavior
on a malformed file, and the id-vs-keyword keying decision (ADR-2) for explicit confirmation before
writing the loader or migration script.

**Touchpoints**: `api/data/narratives.json` (new, migrated content), `api/analytics/narrative/narrative_config.py`
(new loader, mirrors `mapping.py`'s mtime-cache pattern), `api/scripts/migrate_narrative_config.py`
(new, one-time), `api/analytics/narrative/history.py` (switch `load_category_series`/category
enumeration to the new loader instead of `trigger.load_seed_categories` + `mapping.load_category_map`
— for the `/history` path only), `api/scripts/snapshot_narrative.py` (switch category source),
`api/scripts/backfill_pytrends_history.py` (switch category source), `api/data/narrative_categories.json`
+ `api/data/narrative_category_map.json` (retired — left on disk with a deprecation `_comment`,
not deleted, per Non-Goals).

**Blast radius**: 7 files touched + 1 new file created, no schema/auth/API contract change
(`/history`'s response shape is unaffected — only its *input* category source changes),
`/categories`/`mapping.py`'s frozen functions/`trigger.py` explicitly untouched (grep-diff check
required in Stage 0 and again at EXECUTE completion).

**AC mapping**: AC-4, AC-5, AC-6, AC-7, AC-8 (partial — the loader itself; full AC-8 proof lands in
RFC-7's 15-narrative fixture).

**Test commands**: `uv run --project api pytest api/tests/analytics/narrative/test_narrative_config.py -q`.

**Verification evidence**:
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_load_narratives_add_rename_remove_reflected_on_reread` (mtime-cache round trip, no restart) | Fully-Automated | AC-4 |
| `test_narrative_coins_tagged_in_history_response` | Fully-Automated | AC-5 |
| `test_malformed_entry_empty_name_skipped_with_warning` | Fully-Automated | AC-6 |
| `test_malformed_entry_duplicate_id_skipped_with_warning` | Fully-Automated | AC-6 |
| `test_malformed_top_level_falls_back_to_last_known_good` | Fully-Automated | AC-6 |
| `test_rename_preserves_archived_history_by_id` | Fully-Automated | AC-7 |
| `test_remove_retains_archive_under_old_id` | Fully-Automated | AC-7 |
| `test_categories_contract_unchanged_after_migration` (re-run of v1's existing AC-13 test) | Fully-Automated | AC-13 |

### RFC-3: Multi-keyword blending + anchor-chained pytrends batching

**Stage 0 (present and STOP)**: present the exact batching math (5-per-request, anchor reused,
worst-case-15-narrative request count), the zero/near-zero-anchor guard behavior, the exact
cache-key namespace for the new blended series (`pytrends-blended`, keyed by narrative id — must
not collide with existing keyword-keyed rows), and re-confirmed current pytrends rate-limit
guidance from `data-sources/all-data-sources.md` (research step, record findings in the phase
report) before implementing.

**Touchpoints**: `api/data/pytrends_adapter.py` (new batched-fetch function, additive — existing
single-keyword function untouched so any other caller is unaffected), `api/scripts/snapshot_narrative.py`
(nightly job switches to batched multi-keyword fetch), `api/scripts/backfill_pytrends_history.py`
(same), `api/analytics/narrative/history.py` (reads the new blended series alongside existing
keyword-keyed series), `api/data/cache.py` (only if a new write helper is needed for the
`pytrends-blended` namespace — reuse `write_narrative_series` if its signature already supports an
arbitrary source string, confirm in Stage 0).

**Blast radius**: 5 files, no schema/API/auth surface change (internal batching only; `/history`'s
existing response shape absorbs the new series as an additional `NarrativeHistorySeries` entry, not
a breaking change).

**AC mapping**: AC-8 (multi-narrative correctness), directly enables AC-9/AC-10/AC-11 (RFC-4/5
depend on this data existing).

**Test commands**: `uv run --project api pytest api/tests/data/test_pytrends_adapter.py
api/tests/scripts/test_snapshot_narrative.py api/tests/scripts/test_backfill_pytrends_history.py -q`.

**Verification evidence**:
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_batch_5_terms_per_request` | Fully-Automated | AC-8 |
| `test_anchor_chaining_rescales_second_batch` (golden value, hand-computed scale factor) | Fully-Automated | AC-8 |
| `test_zero_anchor_marks_batch_insufficient_not_fabricated_ratio` | Fully-Automated | AC-1/AC-2 (reused rule) |
| `test_l2s_multi_keyword_blend_not_keywords0_only` (regresses the named SPEC bug) | Fully-Automated | AC-8 |
| `test_backfill_batching_matches_nightly_batching_logic` | Fully-Automated | AC-8 |
| 15-narrative worst-case request-count check against re-confirmed rate guidance | Agent-Probe | AC-8 |

### RFC-4: Momentum view (parallel with RFC-5)

**Stage 0 (present and STOP)**: present the exact `momentum.py` module contract (window constants,
`momentum_basis` field, ranked-bar output shape, gaining/slowing arrow logic) before writing.

**Touchpoints**: `api/analytics/narrative/momentum.py` (new), `api/routers/narrative.py` (new `GET
/api/narrative/momentum` endpoint), `api/models/narrative.py` (new
`NarrativeMomentumResponse`/`NarrativeMomentumEntry` models, additive), `web/lib/api/narrative.ts`
(new fetch fn), `web/lib/types/narrative.ts` (additive types), `web/components/narrative/MomentumView.tsx`
(new).

**Blast radius**: 6 files (all new or additive — no existing endpoint/model modified), new API
surface (`/api/narrative/momentum`) with no effect on `/categories`/`/history`.

**AC mapping**: AC-9, AC-10.

**Test commands**: `uv run --project api pytest api/tests/analytics/narrative/test_momentum.py
api/tests/routers/test_narrative_momentum.py -q`; `pnpm --filter web test -- MomentumView`.

**Verification evidence**:
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_momentum_golden_rising_then_flattening` (hand-computed) | Fully-Automated | AC-9 |
| `test_momentum_golden_falling_then_reversing` (hand-computed) | Fully-Automated | AC-9 |
| `test_momentum_basis_falls_back_to_composite_when_pytrends_insufficient` | Fully-Automated | AC-9 |
| `test_momentum_insufficient_history_explicit_state` | Fully-Automated | AC-10 |
| `MomentumView.test.tsx::renders populated view for pytrends-backfilled narrative` | Fully-Automated | AC-9 |

### RFC-5: Daily mindshare view (parallel with RFC-4)

**Stage 0 (present and STOP)**: present the exact `mindshare.py` module contract (per-source share
formula, blend formula, `only_one_source`/`no_sources_available` labelling rule, date-picker API
shape) before writing.

**Touchpoints**: `api/analytics/narrative/mindshare.py` (new), `api/routers/narrative.py` (new `GET
/api/narrative/mindshare?date=` endpoint), `api/models/narrative.py` (new
`NarrativeMindshareResponse`/`NarrativeMindshareEntry` models, additive), `web/lib/api/narrative.ts`
(new fetch fn), `web/lib/types/narrative.ts` (additive types), `web/components/narrative/MindshareView.tsx`
(new, 100%-stacked bar + date picker).

**Blast radius**: 6 files (all new or additive), new API surface
(`/api/narrative/mindshare`), no effect on existing endpoints.

**AC mapping**: AC-11.

**Test commands**: `uv run --project api pytest api/tests/analytics/narrative/test_mindshare.py
api/tests/routers/test_narrative_mindshare.py -q`; `pnpm --filter web test -- MindshareView`.

**Verification evidence**:
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_mindshare_golden_shares_sum_to_one` (fixture day, mixed availability) | Fully-Automated | AC-11 |
| `test_mindshare_only_one_source_labelled` | Fully-Automated | AC-11 |
| `test_mindshare_no_sources_available_labelled` | Fully-Automated | AC-11 |
| `test_mindshare_correct_at_15_narratives` | Fully-Automated | AC-8/AC-11 |
| `MindshareView.test.tsx::renders proxy-labelled caveat on this view` | Fully-Automated | AC-11 |

### RFC-6: Caveat de-duplication

**Stage 0 (present and STOP)**: present the exact placement change (which component moves the
caveat instance, which component loses it) before touching JSX.

**Touchpoints**: `web/components/narrative/NarrativeDashboard.tsx`,
`web/components/narrative/CategoryHistoryPanel.tsx`, `web/components/narrative/DataQualityCaveat.tsx`
(no internal change, only call-site move).

**Blast radius**: 3 files, no API/schema change, frontend-only.

**AC mapping**: AC-12.

**Test commands**: `pnpm --filter web test -- NarrativeDashboard DataQualityCaveat`.

**Verification evidence**:
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `NarrativeDashboard.test.tsx::exactly one caveat instance regardless of narrative count (6 and 15 fixture)` | Fully-Automated | AC-12 |

### RFC-7: Tripwire + AC-13 + seeded E2E + AC-14 handoff

**Stage 0 (present and STOP)**: present the exact tripwire assertion list (every `trigger.py`
public symbol name + signature to snapshot) and the exact 6/15-narrative fixture shape before
writing.

**Touchpoints**: `api/tests/analytics/narrative/test_trigger_tripwire.py` (new),
`api/tests/routers/test_narrative_categories_contract.py` (re-run unmodified, not edited),
`api/scripts/seed_e2e_cache.py` (extend `build_narrative_fixture`/`seed_narrative` to accept a
6-15-narrative parameter), `web/e2e/narrative.spec.ts` (extend with momentum/mindshare/caveat/config-edit
scenarios), and this plan's own `## Resume and Execution Handoff` (AC-14 checklist appended there).

**Blast radius**: 5 files, test-only (no production code change).

**AC mapping**: AC-13 (re-confirm), AC-8 (full 15-narrative proof), AC-14.

**Test commands**: `uv run --project api pytest api/ -q`; `pnpm --filter web test`; `pnpm --filter
web exec tsc --noEmit`; `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
cd web && pnpm test:e2e` (run twice per v1's own precedent for flake detection).

**Verification evidence**:
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_trigger_tripwire_signatures_unchanged` | Fully-Automated | AC-13 |
| `test_narrative_categories_contract.py` (re-run, unmodified) | Fully-Automated | AC-13 |
| `e2e/narrative.spec.ts::momentum view populated for seeded pytrends-backfilled narrative` | Fully-Automated (seeded, real cache boundary) | AC-9 |
| `e2e/narrative.spec.ts::mindshare view populated for a seeded mixed-availability day` | Fully-Automated | AC-11 |
| `e2e/narrative.spec.ts::config file edit reflected without restart` | Fully-Automated | AC-4 |
| `e2e/narrative.spec.ts::exactly one caveat on page` | Fully-Automated | AC-12 |
| AC-14 real-machine walkthrough checklist | Agent-Probe | AC-14 |

## 4. High-Level Data Flow

```
narratives.json (RFC-2, user-editable, 6-15 entries)
        │
        ▼
narrative_config.load_narratives()  ──►  snapshot_narrative.py (nightly) ──► pytrends batched
        │                                  + backfill_pytrends_history.py     fetch (RFC-3,
        │                                                                     anchor-chained)
        ▼
history.load_category_series()  ◄── reads keyword-keyed (existing) + id-keyed blended (new) series
        │
        ▼
scoring.normalize_with_sufficiency()  (RFC-1: insufficient series → None, never 0.5)
        │
        ▼
history.build_composite()  (RFC-1: insufficient slots never contribute)
        │
   ┌────┴─────────────────┬──────────────────────┐
   ▼                      ▼                      ▼
/api/narrative/history  /api/narrative/momentum  /api/narrative/mindshare
  (existing, RFC-1        (RFC-4, new,             (RFC-5, new,
   honest gaps now)         cross-sectional)          blend+show-each)
   │                      │                      │
   └──────────┬───────────┴──────────┬───────────┘
              ▼                      ▼
   /narrative page (RFC-1/6: honest gaps,   NarrativeDashboard.tsx
   one caveat, momentum+mindshare panels)

Untouched, frozen path (unchanged, grep-diff verified each RFC):
mapping.LEGACY_COIN_CATEGORY_MAP → trigger.compute_narrative_categories
  → /api/narrative/categories → /screener strip → confidence badge
```

## 5. Security Posture

No new auth/secrets surface. `narratives.json` is a repo-local config file (not user-uploaded, not
served raw to the client — read server-side only), same trust level as `narrative_category_map.json`
in v1. No new redistribution obligations (RFC-3/4/5 all consume existing adapters' already-flagged
outputs).

## Test Infra Improvement Notes

(none identified yet — to be updated during vc-test-coverage-plan execution and EVL)

## Touchpoints

Full union of all RFC touchpoints above:
`api/analytics/narrative/{scoring,history,narrative_config,momentum,mindshare}.py`,
`api/data/{narratives.json,narrative_categories.json,narrative_category_map.json,pytrends_adapter.py,cache.py}`,
`api/scripts/{migrate_narrative_config.py,snapshot_narrative.py,backfill_pytrends_history.py,seed_e2e_cache.py}`,
`api/models/narrative.py`, `api/routers/narrative.py`,
`web/components/narrative/{NarrativeDashboard,CategoryHistoryPanel,DataQualityCaveat,MomentumView,MindshareView}.tsx`,
`web/lib/{api,types}/narrative.ts`, `web/e2e/narrative.spec.ts`,
`api/tests/analytics/narrative/*`, `api/tests/routers/test_narrative_*`.

Explicitly NOT touched (verified by tripwire + AC-13 test, RFC-7): `api/analytics/narrative/trigger.py`,
`mapping.py`'s frozen `LEGACY_COIN_CATEGORY_MAP`/`map_coin_to_category` functions,
`api/routers/narrative.py::get_categories`, `web/components/screener/*` (confidence badge/strip).

## Public Contracts

- `GET /api/narrative/categories` — byte-identical, untouched (AC-13).
- `GET /api/narrative/history` — existing response shape gains one additive field
  (`NarrativeHistoryPoint.sufficiency`) and additional `NarrativeHistorySeries` entries (the
  blended pytrends series) when a narrative has 2+ keywords; backward-compatible for any consumer
  ignoring unknown fields/entries.
- `GET /api/narrative/momentum` — new endpoint (RFC-4).
- `GET /api/narrative/mindshare?date=` — new endpoint (RFC-5).
- `api/data/narratives.json` — new user-editable config file; `narrative_categories.json` +
  `narrative_category_map.json` remain on disk (deprecated, unread by the new path) for one
  migration window.

## Blast Radius

~30 files across `api/analytics/narrative/`, `api/data/`, `api/scripts/`, `api/models/`,
`api/routers/`, `web/components/narrative/`, `web/lib/`, `web/e2e/`, plus new/updated test files
under `api/tests/`. No auth/billing/schema-migration surface. Two new GET endpoints (additive, not
replacing existing ones) — classified as moderate risk per the high-risk-class table (public API
surface change) requiring at minimum a hybrid test gate per `vc-test-coverage-plan`, satisfied by
the isolated-cache round-trip + seeded E2E tests named in RFC-2/3/4/5/7 above.

## Verification Evidence

See per-RFC tables above (Section 1.5). Full-suite regression commands to run at EVL:
`uv run --project api pytest api/ -q` (expect ≥392 passed, 3 deselected, plus new RFC-1..7 test
counts), `pnpm --filter web test` (expect ≥110 passed plus new component test counts), `pnpm
--filter web exec tsc --noEmit` (expect exit 0), `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome
cd web && pnpm test:e2e` (expect ≥26 + new narrative-v2 scenarios, run twice).

## 11. Ops Runbook

No new scheduled workflow needed — RFC-3 modifies the existing `narrative-snapshot.yml` cron job's
own script (`snapshot_narrative.py`), it does not add a new workflow file. `migrate_narrative_config.py`
(RFC-2) is a one-time, manually-run script during EXECUTE — its output (`narratives.json`) is
committed, the script itself is not part of any recurring job.

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)

## Resume and Execution Handoff

1. **Selected plan file path**: `process/features/narrative-mindshare/active/narrative-v2_25-09-26/narrative-v2_PLAN_25-09-26.md`
2. **Last completed phase or step**: PLAN written, RFC-1 through RFC-7 fully specified; no EXECUTE
   work started.
3. **Validate-contract status**: pending — VALIDATE has not yet run.
4. **Supporting context files loaded during PLAN**: `process/context/all-context.md`,
   `process/context/tests/all-tests.md`, `process/context/data-sources/all-data-sources.md`,
   `process/context/planning/all-planning.md`, `process/features/narrative-mindshare/_GUIDE.md`,
   v1's `narrative-dashboard_PLAN_24-09-26.md` (structural precedent), and direct reads of
   `api/analytics/narrative/{history,scoring,trigger,mapping,exchange_attention}.py`,
   `api/data/{pytrends_adapter,narrative_categories.json,narrative_category_map.json}`,
   `api/routers/narrative.py`, `api/models/narrative.py`.
5. **Next step for a fresh agent picking up mid-execution**: run `ENTER VALIDATE MODE` on this
   plan. VALIDATE must confirm: (a) RFC ordering (1→2→3 sequential, 4∥5 parallel, 6 anytime after
   RFC-1, 7 last) is enforceable inside EXECUTE's per-section checklist; (b) the tripwire test
   design (RFC-7) is sufficient to catch any accidental `trigger.py`/`mapping.py` frozen-function
   edit before EVL; (c) the `MATURE_POINTS_THRESHOLD` default (proposed 5) is acceptable or needs
   adjustment.

## 14. AC-14 Walkthrough Checklist (draft, finalized by RFC-7)

To be run on the user's own machine (this sandbox's egress proxy blocks Google
Trends/Reddit/CoinGecko/Hyperliquid — same constraint as v1's AC-12):

1. Confirm multiple visible lines per narrative where sources have real history (no single-dot lines
   for sources that actually have data).
2. Confirm no category shows a fake tied composite value — categories with too little data show
   "insufficient history," not a shared 0.50.
3. Edit `api/data/narratives.json` (add a narrative, rename a label, remove one) and confirm
   `/narrative` reflects the change without restarting the API.
4. Confirm the momentum view is populated and ranks narratives against each other with
   gaining/slowing arrows.
5. Confirm the daily mindshare view is populated for at least one real day with more than one
   narrative having data, and that per-source shares are visible alongside the headline number.
6. Confirm exactly one data-quality caveat appears on the page.

## Post-EXECUTE Amendments

(none yet — appended during UPDATE PROCESS if EXECUTE deviates from this plan)
