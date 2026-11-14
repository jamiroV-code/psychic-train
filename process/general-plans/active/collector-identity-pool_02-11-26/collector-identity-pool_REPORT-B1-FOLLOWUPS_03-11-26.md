---
name: report:collector-identity-pool-b1-followups
description: "B1.1 bounded enabled-only coherence and B1.2 offline loopback capture evidence."
date: 03-11-26
metadata:
  node_type: memory
  type: report
  feature: narrative-baskets
  phase: B1-followups
---

## 1 Task ID
B1.1 and B1.2 only, owner-authorized follow-ups to merged B1 PR #239. Branch `claude/identity-followups`, fresh worktree `C:/Users/jamir/.herdr/worktrees/my_site/wt-identity-followups`, origin/main base `33c9a7b5` (displayed git abbreviation `33c9a7b`). EXECUTE lane; deliver for **review**, never merge/deploy.

## 2 Outcome
B1.1 implemented red-first; offline focused config, transport, parser and all tooling guards pass. B1.2 **VIABLE** for bounded local capture; independent browser matching **NOT VERIFIED**. Defaults remain `x_identity_enabled=false`, `x_connection_style=plain`. No new runtime networking or dependency changes. [Draft PR #240](https://github.com/jamiroV-code/psychic-train/pull/240) is open for **review**; API and web CI passed on implementation head `e0a23fbce9c31b02f26fb73ba2fcf220cc2278ff`. Final documentation-head SHA/checks are recorded in the PR evidence comment and worker handoff; local results here are not represented as CI results.

## 3 Summary
- Conservative invariant: OS never implies country/timezone. Compare explicit alpha-2 country claims among declared region, local IANA country-table memberships and the primary language tag only. Regionless primary language and secondary preferences do not assert residence. Use many-to-many memberships from the union of zone.tab/zone1970.tab, system TZPATH first per table, otherwise installed tzdata resources. Valid alias/neutral zones not listed are unknown, not false mismatches. No offset/DST heuristic or invented geography. Enabled validation refuses if all tables are unavailable; disabled returns before table access.
- Compare recognizable literal-UA platform markers only to B1's four observed targets (chrome131/safari170/firefox133 macOS; edge101 Windows) and explicit mobile suffixes. Platform-neutral UAs and unmeasured target platforms remain unknown. Family validation and target uniqueness are unchanged. This is bounded contradiction detection, not full identity or geography proof.
- Test-only loopback tooling captures raw ClientHello and separately negotiated h2 initial SETTINGS for four exact curl targets. Length/record bounds, socket deadlines, malformed/truncated vector checks, extension ordering/GREASE and ordered SETTINGS tests are included. Client failures after deliberate endpoint close are expected, not used as sole evidence. No browser, real accounts, proxies or external fingerprint services.

## 4 Files changed
- `api/data/attention/web_queries.py`: enabled-only coherence validation and local tzdb country lookup.
- `api/tests/data/attention/test_web_queries.py`: red-first contradictions, disabled behavior, shared zones, region-neutral/alias zones, secondary/regionless languages, observed target platforms, local table absence/system-table parsing, seasonal/non-DST/broad-US-zone cases.
- `api/tests/data/attention/test_identity_fingerprint.py`: test-only bounded parser/capture and reproducible standalone probe; no runtime caller.
- `api/tests/tooling_guards/test_pc_collector_guards.py`: allow exact static `importlib.resources` for local package data; keep all general importlib/dynamic-import/network prohibitions and planted-import regression checks. No other guard relaxed.
- This task folder: PLAN/SPEC dated additions, this report, FEASIBILITY verdict and raw WIRE JSON.
- Canonical `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_SPEC_21-10-26.md`: appended dated bounded contract; history preserved. No launcher/adapter/runtime transport behavior change.

## 5 Commits
Red commit `78fa4b4d`: eight new contradictions failed with DID NOT RAISE before implementation, 23 other coherence cases passed (89 deselected). Subsequent implementation/docs commits are on the draft PR; the exact final head is reported in the PR/worker handoff to avoid a self-referential commit hash in this file.

## 6 Tests run
All commands run only in the isolated follow-up worktree; uv uses `--offline --frozen --group xreader` and no dependency update.

1. Red: `uv run --offline --project api --frozen --group xreader pytest api/tests/data/attention/test_web_queries.py -k coherence -q` => **8 failed, 23 passed, 89 deselected**. Committed red before implementation.
2. First focused config/transport/parser/reader/two-guard run => **278 passed, 1 skipped, 1 failed**. Root cause: pure-module guard deliberately banned all importlib, including static resources. Changed only the precise static-resource exception plus a regression preserving general dynamic import rejection; no networking introduced.
3. Corrected focused run: `uv run --offline --project api --frozen --group xreader pytest api/tests/data/attention/test_web_queries.py api/tests/data/attention/test_identity_transport.py api/tests/data/attention/test_identity_fingerprint.py api/tests/data/attention/test_twscrape_reader.py api/tests/data/attention/test_x_reader.py api/tests/tooling_guards -q` => **386 passed, 1 skipped, 2 warnings**, 38.30 seconds. The skip is POSIX mode-bit checking on Windows. Two curl_cffi Proactor/add_reader warnings use the library's selector-thread fallback, not a new failure; not suppressed.
4. Standalone smoke: `uv run --offline --project api --frozen --group xreader python api/tests/data/attention/test_identity_fingerprint.py` => exit 0; complete output preserved in the WIRE JSON. All targets offered h2/http1.1; four independent TLS connections negotiated h2 and emitted ordered SETTINGS. Existing config tests smoke valid/rejected validation paths locally.
5. [GitHub Actions run 41612136852](https://github.com/jamiroV-code/psychic-train/actions/runs/41612136852) on implementation head `e0a23fbce9c31b02f26fb73ba2fcf220cc2278ff`: **api — pytest PASS (5m1s)**, **web — vitest, tsc, island build PASS (1m3s)**. Observed with `gh pr checks 240 --watch --interval 30`, exit 0. This report's CI-result-only documentation update is followed by a final-head CI wait and evidence comment on PR #240 (the final commit cannot contain its own hash).

Observed SETTINGS: chrome131 `[1=65536,2=0,4=6291456,6=262144]`; safari170 `[2=0,4=4194304,3=100]`; firefox133 `[1=65536,2=0,4=131072,5=16384]`; edge101 `[1=65536,3=1000,4=6291456,6=262144]`. These are observations, not browser baseline data. FEASIBILITY has environment, source references and limitations.

## 7 Tests NOT run
No local broad API/web suite, live X/Reddit requests, real accounts, proxies, public fingerprint service, browser, collector restart/deployment, B2/B3 or production cache/process access. No reference-browser baseline, JA4, HTTP2 pseudo-header/priority/window-update fingerprint, resumption, hostname/SNI comparison or cross-host/version stability. B1's original NOT-PERFORMED TLS statement remains historical; this probe does not prove browser equivalence or anti-ban outcomes. CI may skip optional xreader tests if its environment lacks that group; the Windows offline run exercised them explicitly.

## 8 Deviations
The plan's phrase “target platform against timezone/region plausibility” cannot justify any OS-to-location rule. Implemented only evidence-backed explicit contradictions and documented unknowns rather than arbitrary mappings. No unique timezone-to-country claim. B1.2 captures direct curl_cffi on two separate connections per target, not the full adapter/bootstrap/fallback TLS paths; existing B1 tests prove those factory headers separately. Temporary local test certificate trusted explicitly, never verify=false. Existing libraries suffice; no added dependency.

## 9 Blockers
No implementation blocker. Independent browser-fingerprint equality remains unproven by design, not a success claim. Baselines recorded without modification: live main `ed5b371b205049ae14aadccdd2bfaeea0b8f5925`, main behind origin/main by 30 with modified `api/data/attention_queries.json` and untracked charting task folder; quiet-forest `7e3ca4fefd746f017ac5acaf88096ed0bdb8992b`, branch `claude/x-rollover-test`, behind by 143 with modified same queries file and untracked identity/daily-data-gap folders. Only read-only git status/worktree discovery ran there; no source/test/runtime work ran there. Protected data files, C:/xpool, C:/secrets, scheduled tasks and live collector processes/caches were not touched. Worktree retained.

## 10 Follow-up
Review the one draft PR and its final-head checks. No authorization to merge/deploy or perform a live comparison; no B2/B3/browser work included. Unknown target platforms and unlisted alias/neutral timezone country claims remain explicitly unknown. A matching browser fingerprint would require separately scoped independent baseline evidence, not inferred from this library capture.

## 11 Context cost
Read only scoped merged plan/report/SPEC, required current configuration/adapter/tests/guards, installed library/tzdb resources and dependency declaration needed for offline feasibility. No subagents/orchestration, broad repository mapping or repeated broad suites. Captured eight loopback connections in the standalone probe plus targeted test captures. No secrets or real-account data included in evidence.
