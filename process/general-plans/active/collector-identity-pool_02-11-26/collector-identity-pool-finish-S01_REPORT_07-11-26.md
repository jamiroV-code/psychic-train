# collector-identity-pool-finish S01 report (Stage 0 S-Canon + Stage 1 S-Config), 07-11-26

## 1. Status
CODE-COMPLETE for S-Canon and S-Config on `claude/b2-validate` (worktree `wt-b2-validate`), committed locally, not pushed. Live gates untouched (no live request). BG-1/BG-3 gate state is recorded by Main's probes BP1c/BP3c, not by this slice.

## 2. Scope executed
- S-Canon (RT0): append-only dated notes.
- S-Config (RT2): every key of PLAN "Public Contracts -> configuration" declared optional, validated, round-tripped.

## 3. Changed paths
- `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_SPEC_21-10-26.md` (new section "Superseding finish-plan notes 07-11-26", N1-N5)
- `process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_SPEC_02-11-26.md` (note: harvest-only browser, owner-only login; covers lines 39-40, 90-91, 165)
- `process/context/decisions.md` (D-32)
- `api/data/attention/web_queries.py`
- `api/tests/data/attention/test_web_queries.py`, `api/tests/data/attention/test_x_window.py`

## 4. S-Canon content
N1 owner decisions 06-11-26; N2 Reddit live methods, `reddit_impl_order`, zero option B via C3 commit policy, Reddit pool, contract F namespace; N3 browser rules (Chrome/Edge CDP pipe, A1 method table, relay A5-A9 is not the Stage-3 gateway, harvest-only, no credential typing); N4 B3 scheduler exceptions and query-id static fetch as the only new X outbound class; N5 Reddit evasion/identity wording (Android-app impersonation, rule 8 superseded for GQL only, probe-gated). Later guard amendments cite N1-N5.

## 5. S-Config implementation
- `FINISH_OPTIONAL_DEFAULTS` (34 keys, exact contract defaults) merged into `DEFAULTS`; none in `X_DEFAULTS`; `CollectorConfig` fields added; lists -> tuples, maps copied.
- `REDDIT_METHODS` = (`reddit_live_browser`, `reddit_live_gql`, `reddit_web`, `reddit_stream`); `REDDIT_LIVE_METHODS` = (`browser`, `gql_anon`); `reddit_impl_order` code default changed to the new order (C6). Committed `attention_queries.json` still says `["reddit_web", "reddit_stream"]` (S-RDisc owns it), so runtime behaviour is unchanged.
- `_validate_finish_settings`: enums, int ranges, fraction, booleans, absolute-or-null paths, `x_surface_path` outside the repo, profile name regex, label rules (profiles/quiet-hours labels must be `x_accounts`; Reddit labels regex, unique, ≤ 3, disjoint from X), quiet-hours window shape (IANA zone, distinct HH:MM, may cross midnight), mixed targets (login or numeric id, unique, ≤ 20), live methods ordered unique subset; cross-key: non-empty `reddit_live_methods` needs `reddit_surface_path`; any browser use (X harvest, Reddit session check, `browser` live method) needs `browser_path` + `browser_profiles_dir`; X harvest needs a profile per X label; A11 profile identity unique across both sites via `profile_identity` (casefold, trailing dot/space strip).
- Reddit direct/proxy predicate: no new config rule needed; the existing B2 rule (`x_proxy_required` + the three paths together) already applies to the whole block.

## 6. Tests (red first)
Red run before implementation: `82 failed, 156 passed`. New tests: defaults/optional/not-required, enum + new default, old committed file loads, all-off baseline (AC12), rollback contract G stage-1 row (B2 key-set fixture validator rejects each new key; stripped doc accepted), valid values + `as_dict` round trip, 66 invalid-value cases, browser-use cross-key, GQL-only needs no browser, harvest profile per account, surface path rule, repo-outside rule, label disjointness, A11 uniqueness + normalization, quiet hours across midnight; `test_x_window.py` fixture touch.

## 7. Commands and results
- `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/tests/data/attention/test_web_queries.py api/tests/data/attention/test_x_window.py -q` -> `238 passed`.
- RT2 touched-file consumers: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest` over test_reddit_stream, test_reddit_web, test_reddit_metrics, test_x_pool, test_x_reader, test_x_proxy_policy, test_x_proxy_snapshot, test_x_proxy_sqlite, test_x_proxy_spawn, test_identity_transport, test_twscrape_reader, test_pc_pace, test_x_filters, test_x_raw, test_onboarding_overlay (api/tests/data/attention), api/tests/data/test_attention_pc_refresh_stream.py, api/tests/analytics/attention/test_sources_health.py, test_sources_proxy_health.py -> `678 passed, 1 skipped`.
- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <finish PLAN>` -> failures [], warnings []; `git diff --check` clean (CRLF notices only).
- Not run: full suite (by envelope); ruff (not installed in the project env).

## 8. Guard/test amendments
None needed in this slice. `test_stream_keys_committed_with_owner_defaults` and the equality test stay green because the committed order is unchanged; their amendment belongs to S-RDisc (table H).

## 9. Deviations
None from the plan design. Interpretation to note: `x_surface_path` content ("same schema rules as the Reddit surface file, `x_session` section only") cannot be checked at config time because the grammar/section validator lands in S-RCore-A (`reddit_surface.py`); S-Config validates the path rules (absolute, outside repo); content validation belongs to the surface loader. A11 final-real-path / 8.3 checks are a launch-time concern of `browser_profile.py`; config compares normalized names (regex excludes `~`, so no short-name alias is expressible).

## 10. Risks / follow-ups for later slices
S-RCore-A consumes `REDDIT_METHODS`/`REDDIT_LIVE_METHODS` without editing `web_queries.py`; S-RDisc flips the committed order. Rollback to "B2" = drop the 34 keys (old validator rejects them).

## 11. Next
Stage 2: S-Fixtures, S-Facts, S-RCore-A, S-StatusAPI.
