---
name: plan:narrative-baskets-trends-t100a
description: "T121 FAST MODE PLAN and VALIDATE for slice T100a of the Trends-by-name SPEC (T120): keyword seed file, validator/loader, owner check tool and read-only probe, all with fake transports. Corrected file:line cites on main 67baa0c, baselines, red tests by name, Validate Contract and gate. Docs only; no code changed."
date: 21-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Trends by name, slice T100a: PLAN (keyword file, validator, check tool, probe)

[MODE: VALIDATE]

Date: 21-10-26
Complexity: SIMPLE (one slice, all new files, no edit to any existing file)
Status: VALIDATED: Gate: PASS
Validation: T121 (FAST MODE: PLAN then VALIDATE in one session), 21-10-26, on `main` 67baa0c. Next step: the owner's separate ENTER EXECUTE MODE for T100a. This session builds nothing.

**Summary:** **SPEC:** `narrative-baskets-trends-by-name_SPEC_21-10-26.md` (T120, PR #149, NOT merged when this PLAN was written; read from branch `claude/t120-trends-spec` at 28fa003). T100a ships the four things the owner needs BEFORE any live Trends code is built: a keyword file with a validator, a tool that finds Google topic ids, and a probe that shows what Google returns from the owner's PC. Nothing here changes how Trends is fetched or stored today (that is T100b/T100c). Providers (Google included) are unreachable from the build container: every live fact is UNVERIFIED and has an owner probe in section 8.

## Overview and Context

Context router: `process/context/all-context.md`; tests: `process/context/tests/all-tests.md`. Phase Completion Rules: the slice is done when its red tests are green, the gates of the Validate Contract pass, and the report lists the owner probes. The runner still calls `trends.fetch_series(s, s.lower(), ...)` with the TICKER after this slice (`api/scripts/refresh_attention.py:177-178`); switching it to the keyword file is T100b.

## 1. Goal and non-goals

**Goal.** Give the owner (a) `api/data/trends_keywords.json`, one entry for each of the 75 coins placed in `api/data/attention_narratives.json`, with no invented topic id; (b) a loader/validator that enforces the SPEC section 2 rules and never crashes its caller; (c) `check_trends_keywords`, the owner-run tool that proposes topic ids; (d) `probe_trends`, the owner-run read-only probe that answers "does Google answer, how fast, daily or not, which anchor is better".

**Non-goals (NOT in T100a).** The anchored-batch fetch, backfill, `store.write_series(mode="replace-window")` (T100b). Any `.github/` change, `probe-trends` dispatch, `probe_records.json`, `--with pytrends` in a workflow, any change to `api/pyproject.toml` or `api/uv.lock` (T100c; whether `pytrends` becomes a declared dependency is a T100c decision, T100a stays on `--with pytrends`). W8 (in-API worker). Web. Source weights. Editing any SPEC. Writing any cache, store or parquet file. Live provider calls in tests.

## 2. Owner decisions (binding for T100a)

| # | Decision | Effect |
|---|---|---|
| 1 | Topic id by default, name as fallback, never the ticker (21-10-26) | The validator accepts `topic`, `term`, `no-keyword`; the checker proposes topics; the seed has NO `topic` (they need a live check) |
| 2 | History: revised series first, first-seen column only if the owner later wants backtests (SPEC question 3, 21-10-26) | Nothing to build in T100a; recorded so T100b does not add a column |
| 3 | Anchor is chosen from probe evidence, not guessed (SPEC question 1) | The probe prints raw values for BOTH candidates (Bitcoin, Ethereum) for 5 sample coins; the seed `_anchor` is a placeholder the owner edits after reading the probe |
| 4 | Worker spend ceiling 215 USD (owner-approved 21-10-26) | Planner states the slice ceiling in the EXECUTE envelope; this PLAN proposes ask at 5 and hard cap 8 USD |
| 5 | FAST MODE for T100a only (21-10-26) | This file is PLAN and VALIDATE in one; execution needs the owner's own ENTER EXECUTE MODE |

**PLAN rulings where the SPEC is silent or loose (each is small, listed so the owner can overrule at EXECUTE approval):**
- **R-A. `_anchor` and uniqueness.** `_anchor` has the same shape as a coin entry but must be `topic` or `term` (never `no-keyword`), is not counted for coverage, and is EXCLUDED from the uniqueness check, because BTC (or ETH) legitimately shares the anchor's keyword (SPEC section 3 fetches the anchor coin against a second anchor).
- **R-B. `label` on every entry.** SPEC rule "label non-empty" is applied to ALL entries including `no-keyword` (the SPEC example for XAUT omits it). Reason: the checker needs a human name to search for coins that have no keyword yet. Label: 1-60 printable characters, no control characters.
- **R-C. `note` is required for `no-keyword`**, optional otherwise (SPEC section 2, last coverage rule).
- **R-D. Layering.** The loader lives in `api/data/attention/` and `api/data/attention/*.py` imports nothing from `api/analytics` today (checked: no match). So the loader does NOT import `narratives.py`; it takes `placed_symbols` as an argument. Tests and the T100b runner pass `load_narratives()` symbols. The symbol pattern is copied (`[A-Z0-9_]{1,24}`, same as `api/analytics/attention/narratives.py:29`), with a test that fails if the two patterns differ.
- **R-E. Exit codes.** Checker: 0 normally (including a 429 stop), 2 input unreadable (SPEC), 3 `pytrends` not importable (prints the exact `uv run --project api --with pytrends ...` command). Probe: 0 whenever it printed a report (a failed request IS the evidence), 2 bad arguments, 3 `pytrends` missing.
- **R-F. Shared helper.** One small `api/scripts/trends_cli_common.py` holds `error_class(exc)`, `http_status(exc)`, `is_rate_limited(exc)` and the lazy `make_trendreq()`; checker and probe both use it. Not in the SPEC file list (SPEC section 7); additive, T100b may reuse it.

## 3. Design (verified against main 67baa0c)

**Existing behaviour T100a must not disturb.** `trends.fetch_series` (`api/data/attention/trends.py:17-35`) is unchanged and still returns at most one point with state `insufficient-history`. `pytrends` is not in `api/pyproject.toml` (dependencies, lines 6-17) and `pytrends_adapter` imports it lazily (`api/data/pytrends_adapter.py:54-57`, `:193-196`); every new module here also imports it lazily, so importing any of them works without `pytrends` (a test enforces it).

**Pattern copied, not invented.** The checker mirrors `api/scripts/check_wiki_titles.py`: `DEFAULT_FILE` 22, `INTERVAL_SECONDS` 23, `CRYPTO_WORDS` 25, `Result` dataclass 28-37, per-item function 40, `run(mapping, *, client, sleep, out)` 75-89, `main` 92-105, "writes nothing", exit 2 on unreadable input. Its tests (`api/tests/scripts/test_check_wiki_titles.py:22` `_client`, `:26` `_run`, `:65` error-class-only output, `:73` paste-ready block, `:81` injected sleep, `:99` unreadable file exit) are the model. The injectable client follows `backfill_pytrends_history._default_trendreq_factory` (`api/scripts/backfill_pytrends_history.py:83-87`) and `fetch_daily_window(..., trendreq_factory)` (`:89`). The frame checks follow `_batch_daily` (`:185`) and the `isPartial` handling at `pytrends_adapter.py:66-67` and `:204-205`.

**Library facts read from the installed source (pytrends 4.9.2, installed into a throwaway env in this session through `uv run --no-project --with pytrends`; Google itself was NOT contacted).** `pytrends.exceptions` has `ResponseError(message, response)` and `TooManyRequestsError(ResponseError)`; `TooManyRequestsError` is raised exactly when the HTTP status is 429; the exception carries the whole `requests.Response` in `.response` (headers and cookies), so tools must never print the exception text or the response. `TrendReq.suggestions(keyword)` returns the list found at `['default']['topics']` of the JSON (the keys of each item, `mid`, `title`, `type`, are UNVERIFIED until the owner runs the checker). `interest_over_time()` always returns an `isPartial` boolean column. `TrendReq(retries=..., backoff_factor=...)` builds a urllib3 `Retry(method_whitelist=...)`; that keyword was removed in urllib3 2.x, so the tools do their own sleeping and never pass `retries` or `backoff_factor` (UNVERIFIED against the version `uv` resolves on the owner's PC).

### 3.1 `api/data/attention/trends_keywords.py` (loader and validator)

- Constants: `KEYWORDS_PATH = <api>/data/trends_keywords.json`, `ANCHOR_KEY = "_anchor"`, `BAD_FILE_REASON = "bad keyword file"`, `SYMBOL_RE = [A-Z0-9_]{1,24}`, `TOPIC_RE = ^/(m|g)/[A-Za-z0-9_]+$`, `TERM_RE = [A-Za-z0-9 .'&-]{2,40}` (full match, no leading or trailing space, ASCII only: letters, digits, space, `.`, `-`, `'`, `&`; no comma, quote, slash, or non-ASCII).
- `class KeywordFileError(ValueError)`: message names the symbol and the rule (never file content beyond the symbol and the offending value's rule).
- `validate(doc, placed_symbols=None) -> dict`: raises `KeywordFileError`. Rules: object; each key is `_anchor` or matches `SYMBOL_RE`; any other key starting with `_` is an error; each entry is an object with `label` (R-B) and EXACTLY one of `topic` (matches `TOPIC_RE`), `term` (matches `TERM_RE`), `"no-keyword": true`; `no-keyword` needs a non-empty `note` (R-C); unknown fields are rejected (typo guard: allowed fields are `topic`, `term`, `no-keyword`, `label`, `note`); `topic` values unique across coins, `term` values unique case-insensitive across coins (R-A: `_anchor` excluded); `_anchor` required, `topic` or `term` only. When `placed_symbols` is given: every placed symbol must have an entry (error names the first 5 missing, sorted); symbols present but not placed are returned in a warnings list, never an error.
- `load(path=None, placed_symbols=None) -> KeywordMap` (dataclass: `entries: dict[str, dict]`, `anchor: dict`, `warnings: list[str]`; helper `keyword_for(symbol) -> str | None` returns the topic or term, `None` for `no-keyword` or unknown; `keyword_symbols()` in file order).
- `safe_load(path=None, placed_symbols=None) -> tuple[KeywordMap | None, str]`: never raises; on any failure (missing file, invalid JSON, bad type, `KeywordFileError`, `OSError`, `UnicodeDecodeError`) returns `(None, "bad keyword file")` and nothing else (no file content, no path: the reason ends up in logs and a UI line). This is what T100b's runner calls to mark the source `unavailable` (SPEC section 2).
- Pure: no network, no cache access, no `pytrends`, no import from `api.analytics`.

### 3.2 `api/data/trends_keywords.json` (seed, hand-edited, owner-owned)

`_anchor` first: `{"term": "Bitcoin", "label": "Bitcoin (placeholder: the owner picks the anchor from the probe)", "note": "..."}`. Then one entry per placed coin (75 on main today: `api/data/attention_narratives.json`, status `proposed`, as_of 2026-10-18; derived by the test, never hard-coded). 43 start as `term` where the name is distinctive; 32 start as `no-keyword` with a note and a `label` naming the coin (the ticker itself when the coin is unidentified). NO `topic` key anywhere. The `label` of a `term` entry equals the term. The seed (EXECUTE copies this; the owner reviews it once with the checker output):

**term (43):** AAVE `Aave`, ADA `Cardano`, AERO `Aerodrome Finance`, ALGO `Algorand`, APT `Aptos`, ARB `Arbitrum`, BCH `Bitcoin Cash`, BGB `Bitget Token`, BNB `BNB`, BTC `Bitcoin`, CAKE `PancakeSwap`, CRO `Cronos`, DOGE `Dogecoin`, DOT `Polkadot`, ENA `Ethena`, ETC `Ethereum Classic`, ETH `Ethereum`, FIL `Filecoin`, HBAR `Hedera`, HYPE `Hyperliquid`, ICP `Internet Computer`, INJ `Injective`, KAS `Kaspa`, KCS `KuCoin Token`, LINK `Chainlink`, LTC `Litecoin`, MORPHO `Morpho`, NEXO `Nexo`, OKB `OKB`, ONDO `Ondo`, PEPE `Pepe coin`, PUMP `Pump.fun`, SHIB `Shiba Inu`, SOL `Solana`, TAO `Bittensor`, TRX `TRON`, UNI `Uniswap`, WBT `WhiteBIT Coin`, WLD `Worldcoin`, XMR `Monero`, XRP `XRP`, ZEC `Zcash`, ZRO `LayerZero`.

**no-keyword (32), `note` text as given, `label` = common name or the ticker:**

| Symbol | note (why no keyword at seed) |
|---|---|
| AKE, BTW, GRAM, LIT, PRL, STABLE | unidentified ticker (UNVERIFIED), owner names it |
| RAIN | unidentified ticker (UNVERIFIED); common word; owner names it |
| ASTER, JST, JUP, MNT, NEAR, PI, POL, QNT, RENDER, SKY, STX, SUI, XLM | common word; needs topic id |
| ATOM, AVAX, LEO | common word (Cosmos, Avalanche, UNUS SED LEO); needs topic id |
| CC, NIGHT, VVV, WLFI, XDC | identity UNVERIFIED (Canton Coin, Midnight, Venice token, World Liberty Financial, XDC Network); needs topic id |
| GT, HTX | exchange token, ambiguous with the exchange or word; needs topic id |
| PAXG, XAUT | gold token; attention tracks gold, not the token |

Counts check: 6 + 1 + 13 + 3 + 5 + 2 + 2 = 32; 43 + 32 = 75. The seed is a proposal; the validator, not this table, is the contract. A gold token staying `no-keyword` is the SPEC example for XAUT; PAXG follows it.

### 3.3 `api/scripts/check_trends_keywords.py` (owner tool)

`uv run --project api --with pytrends python -m api.scripts.check_trends_keywords [--file MAP.json] [--symbols A,B]`.
- Input: `--file` is a `symbol -> name` JSON map; default is built from the keyword file (`symbol -> label`), so the tool needs no second file. Unreadable or non-object input: print the class only and exit 2.
- Per coin: `client.suggestions(name)` through an injected factory (default `make_trendreq()`). A candidate counts only if it has a `mid` matching `TOPIC_RE`, a `title` and a `type`. `CRYPTO_TYPE_WORDS = ("cryptocurrency", "blockchain", "token", "coin", "digital currency", "protocol", "decentralized")`, case-insensitive substring of `type` (the real vocabulary of Google's `type` field is UNVERIFIED; a miss degrades to AMBIGUOUS, which is the safe direction).
- Verdicts: `PASS` = exactly one crypto-typed candidate (proposed topic); `AMBIGUOUS` = more than one, or none crypto-typed but at least one usable candidate (owner picks; all candidates printed with `mid`, title, type); `FAIL` = no usable candidate, or the request failed (the report line says "falls back to term" when `label` passes `TERM_RE`, else "needs a human").
- Rate rules: `INTERVAL_SECONDS = 3.0` between calls via injected `sleep` (SPEC: at least 2 s); after 3 CONSECUTIVE rate-limited calls (`is_rate_limited(exc)`: class name `TooManyRequestsError`, or an int `.response.status_code == 429`) the run stops, the remaining coins print as `NOT-RUN (stopped after 3 consecutive HTTP 429)`; any success resets the streak. Other failures print the exception CLASS only (`ConnectionError`, `ResponseError(HTTP 403)`), never the message, headers or cookies.
- Output: one line per coin `SYM | name | N candidates | proposed mid "title" (type) | VERDICT`, then `PASS: n AMBIGUOUS: n FAIL: n NOT-RUN: n`, then a line `--- paste-ready JSON (PASS entries) ---` followed by ONE JSON object `{"LINK": {"topic": "/m/...", "label": "Chainlink", "note": "checker PASS 21-10-26"}}` (every entry valid for the validator; the date is `datetime.now(UTC)` formatted, injectable), then `--- needs a decision ---` with the AMBIGUOUS and FAIL coins. Writes NO file (the owner pastes the block into the keyword file by hand).

### 3.4 `api/scripts/probe_trends.py` (owner probe)

`uv run --project api --with pytrends python -m api.scripts.probe_trends [--coins SOL,LINK,AAVE,INJ,MORPHO] [--anchor-a TERM] [--anchor-b TERM] [--timeframe "today 3-m"] [--no-evidence]`. Read-only, writes nothing (no cache, no store, no file), prints no header, cookie or token.
- **Request 1 (SPEC section 4):** ONE anchored request `[anchor, c1, c2, c3, c4]`, anchor from `_anchor` of the keyword file, coins from the keyword file (their `topic` or `term`; a `no-keyword` coin is skipped with a printed note and the next default is used), timeframe `today 3-m`. Prints: `pytrends` version (`importlib.metadata`, `unknown` when absent), outcome (`ok` or the exception CLASS and the HTTP status integer when the exception carries `.response.status_code`; never `str(exc)`), latency in seconds, row count, index step (`daily` only if every index difference is exactly 1 day, else `non-daily (min..max days)`), complete-day count (rows with `isPartial` false and date before today UTC), the first 5 and last 5 rows (date, each term's value, partial flag).
- **Requests 2 and 3 (evidence for the anchor choice, owner decision 3):** `[A, B, s1, s2, s3]` and `[A, B, s4, s5]` where A = Bitcoin keyword (`--anchor-a`, default the BTC entry's keyword) and B = Ethereum keyword (`--anchor-b`, default the ETH entry's), s1-s5 = the 5 sample coins. Both anchors sit in the SAME request as the coins, so every number is on one scale. Prints per term: days, min, median, max, last, days at 100, days at 0 or 1; then per sample coin the median value as a percent of A's median and of B's median, and the line `A saturates coins above it on N days` / `B ... N days`. The reader decides; the tool prints no recommendation. `--no-evidence` skips requests 2 and 3 (1 request total).
- Pacing: 3.0 s sleep (injected) between requests, no retry, 3 requests maximum per run; if request 1 is rate-limited the evidence requests are NOT sent (print `skipped after HTTP 429`).
- Inputs from the command line (`--coins`, `--anchor-*`) are validated against `SYMBOL_RE` or `TOPIC_RE`/`TERM_RE` before any request; an invalid value exits 2 (no comma can split a request).

### 3.5 Shared test fixtures

`api/tests/trends_fixtures.py` (new, same role as `api/tests/equities_fixtures.py`): `FakeTrendReq` (records `build_payload` terms and timeframe; `suggestions` returns a scripted list or raises; `interest_over_time` returns a scripted pandas frame or raises), frame builders (daily 90-day frame with `isPartial`, weekly frame, frame with today's row), scripted exceptions (`FakeTooManyRequests` named `TooManyRequestsError` carrying a `.response` object with `status_code=429`, `headers={"Set-Cookie": SECRET}`; `FakeResponseError` with 403). A sentinel `SECRET = "tok_SECRET_SENTINEL_123456"` is placed in exception messages and response headers so tests can assert it never appears in output.

## 4. Slices, order, gates

Single slice T100a. Model **opus** (code). Tier **RT1** (new files, fake transports, one full-suite run by the tester). Estimate **2-3 USD**; the planner states the ceiling in the EXECUTE envelope (proposal: ask at 5, hard cap 8; worker spend ceiling 215 USD, owner-approved 21-10-26). Order after T100a: owner probes P-CHK and P-PRB on the PC, then T100b, then T100c (+ P-GH); W8 only if the probes say GitHub is blocked.

### File ownership and collision proof

| File | T100a | Open PR touching it |
|---|---|---|
| `api/data/trends_keywords.json` | create | none |
| `api/data/attention/trends_keywords.py` | create | none |
| `api/scripts/check_trends_keywords.py` | create | none |
| `api/scripts/probe_trends.py` | create | none |
| `api/scripts/trends_cli_common.py` | create | none |
| `api/tests/trends_fixtures.py` | create | none |
| `api/tests/data/attention/test_trends_keywords.py` | create | none |
| `api/tests/scripts/test_check_trends_keywords.py` | create | none |
| `api/tests/scripts/test_probe_trends.py` | create | none |

No existing file is edited. Collision check against the open PRs (file lists read with the GitHub tool on 21-10-26):
- **#146 (U2, T115)** touches `discovery.py`, `discovery_history.py`, `sources.py`, `universe.py`, `universe_classes.py`, `api/data/discovery.json`, `api/models/discovery.py`, `api/scripts/refresh_attention.py`, `test_discovery*.py`, `test_sources.py`, `test_universe_classes.py`, `api/tests/routers/test_discovery.py`, `api/tests/scripts/test_refresh_attention.py` and a fixture under `api/tests/analytics/attention/fixtures/`. **Disjoint** from T100a. T100a does not read `discovery.json`, `sources.py` or `universe*`. (T100b WILL edit `refresh_attention.py`'s `_run_trends`, which #146 also edits in `_run_categories`: that is a T100b rebase point, not a T100a one.)
- **#147 (T118, docs)** touches `process/MASTER-PLAN.md`, `process/context/{current-state,decisions,context-changelog}.md`, two `process/archive/` files and the universe-narratives PLAN. **Disjoint** (this PLAN is a new file in the same folder; registry rows are requested in the report, not written here).
- **#148 (T119)** changes one line of `api/data/attention_narratives.json` (`status` proposed to reviewed) and one test in `test_narratives.py`. **No overlap**: T100a reads that file only through `load_narratives()` symbols, which a status flip does not change, so the 75-coin coverage count stays 75. If a later G-OWN edit adds or removes a coin, the coverage test (derived from the file, section 5 test 2) fails loudly until `trends_keywords.json` is updated: intended.
- **#149 (T120, the SPEC)** adds the SPEC file only. **No file overlap**, but this PLAN cites the SPEC by section; if #149 changes section 2 (keyword rules) or the T100a row of section 7 before EXECUTE, this PLAN must be re-validated (hard stop).

## 5. Red tests (written first, each must fail before the code exists)

Counts are named test functions; parametrized cases add more. Floors in the Validate Contract use these minimums.

**`api/tests/data/attention/test_trends_keywords.py` (18)**
1. `test_shipped_file_validates_against_placed_symbols`: `load(placed_symbols=<symbols of load_narratives()>)` passes on the shipped file.
2. `test_every_placed_coin_has_an_entry`: set of placed symbols minus entry keys is empty, derived from `attention_narratives.json` (no hard-coded 75).
3. `test_placed_coin_without_entry_fails`: synthetic keyword map plus a placed set with one extra symbol raises `KeywordFileError` naming that symbol (AC-T2: fails when a coin is added without an entry).
4. `test_extra_symbol_outside_universe_warns_only`
5. `test_entry_needs_exactly_one_of_topic_term_no_keyword` (parametrized: none, topic+term, term+no-keyword, `no-keyword: false`)
6. `test_topic_regex` (valid `/m/0abc_1`, `/g/11xyz`; invalid `m/0abc`, `/x/1`, `/m/`, `/m/a b`, URL)
7. `test_term_safe_characters` (reject comma, quote, slash, backslash, `?`, `#`, newline, one char, 41 chars, leading or trailing space, non-ASCII; accept `Pump.fun`, `AT&T`, `Shiba Inu`, `O'Hara-X`)
8. `test_duplicate_topic_rejected`
9. `test_duplicate_term_rejected_case_insensitive` (`Aave` vs `aave `-stripped equivalents are caught case-insensitively)
10. `test_no_keyword_requires_note`
11. `test_label_required_and_non_empty_on_every_entry`
12. `test_symbol_keys_must_match_pattern` (lowercase, `../x`, 25 chars, empty) and `test_symbol_pattern_matches_narratives_module` (equal to `narratives.SYMBOL_RE.pattern`)
13. `test_anchor_required_and_shape` (missing, `no-keyword`, valid topic, valid term)
14. `test_anchor_may_share_keyword_with_a_coin_and_is_not_a_coin` (R-A; `_anchor` not in `keyword_symbols()`, not counted for coverage)
15. `test_unknown_underscore_key_and_unknown_field_rejected`
16. `test_safe_load_never_raises_and_returns_fixed_reason` (missing file, invalid JSON, top-level list, invalid UTF-8, validation error): result `(None, "bad keyword file")` and the reason contains no path and no file content
17. `test_keyword_for_returns_topic_over_term_none_for_no_keyword`
18. `test_module_imports_without_pytrends_or_analytics` (fresh import with `pytrends` blocked in `sys.modules`; module source has no `api.analytics` import)

**`api/tests/scripts/test_check_trends_keywords.py` (14)**
1. `test_pass_single_crypto_candidate`
2. `test_ambiguous_several_crypto_candidates`
3. `test_ambiguous_candidates_but_none_crypto_typed`
4. `test_fail_no_candidates_reports_term_fallback`
5. `test_candidate_without_valid_mid_is_not_proposed`
6. `test_sleep_is_at_least_two_seconds_between_calls` (no sleep before the first call; every injected sleep value `>= 2.0`)
7. `test_three_consecutive_429_stop_the_run` (4th and later coins `NOT-RUN`, exactly 3 calls made after the first success pattern, none after the stop)
8. `test_429_streak_resets_after_a_success`
9. `test_other_failure_prints_class_only_no_secret` (message and headers carry `SECRET`; absent from output)
10. `test_paste_ready_block_is_valid_and_only_pass_entries` (block parses as JSON; merging it into a copy of the seed passes `validate`)
11. `test_writes_no_file` (working tree snapshot and the sha256 of `trends_keywords.json` unchanged)
12. `test_unreadable_or_non_object_file_exits_2_and_empty_map_exits_0`
13. `test_default_map_comes_from_keyword_file_labels`
14. `test_pytrends_missing_exits_3_and_prints_the_command`

**`api/tests/scripts/test_probe_trends.py` (14)**
1. `test_report_has_version_outcome_latency_rows_step_complete_days` (latency from an injected clock)
2. `test_first_and_last_five_rows_printed`
3. `test_non_daily_frame_reported_as_non_daily_with_step`
4. `test_partial_and_today_rows_are_not_complete_days`
5. `test_exception_prints_class_and_status_only` (AC-T11: message and `Set-Cookie` header carry `SECRET`; output has none of `SECRET`, `Cookie`, `Authorization`, `Bearer`)
6. `test_http_429_is_reported_and_evidence_requests_are_skipped`
7. `test_version_unknown_when_metadata_missing`
8. `test_evidence_uses_two_requests_with_both_anchors_and_five_coins` (payload terms asserted: `[A,B,s1,s2,s3]` then `[A,B,s4,s5]`)
9. `test_evidence_prints_raw_stats_and_percent_of_each_anchor`
10. `test_failure_of_one_evidence_request_still_prints_the_other`
11. `test_probe_writes_nothing` (tree snapshot, no cache path touched)
12. `test_sleeps_three_seconds_between_requests_and_sends_at_most_three`
13. `test_unsafe_cli_values_exit_2_before_any_request` (comma, quote, slash, lowercase symbol)
14. `test_defaults_come_from_keyword_file_and_pytrends_missing_exits_3`

New named tests minimum: 18 + 14 + 14 = 46.

## 6. Ordered tasks (Implementation Checklist)

1. Branch from fresh `main` (`claude/<task-id>-t100a-trends-tools`, set by the planner). Re-run the baselines of the Validate Contract; any difference is a hard stop.
2. Write `api/tests/trends_fixtures.py` and `test_trends_keywords.py`; run it, confirm all fail (import error counts as red). Write `trends_keywords.py` until green.
3. Write `trends_keywords.json` from the seed in 3.2 (no `topic`); run test 1 and 2.
4. Write `test_check_trends_keywords.py` (red), then `trends_cli_common.py` and `check_trends_keywords.py` (green).
5. Write `test_probe_trends.py` (red), then `probe_trends.py` (green).
6. Run gates G1-G12 of the Validate Contract; record numbers in the report (heading 5).
7. Report with the owner probe commands (section 8). Do not edit docs or the registry (requests go in report heading 9). Do not merge.

## 7. Acceptance Criteria (mapped to the SPEC)

| SPEC AC | T100a proof |
|---|---|
| AC-T2 keyword file passes the validator; unique non-empty topic/term; safe characters; every placed coin present or `no-keyword` with a note; test fails when a coin is added without an entry | loader tests 1-15 (named test 3 is the "added without an entry" case); seed file gate G9 |
| AC-T2 (bad file never crashes; reason `bad keyword file`) | loader test 16 |
| AC-T10 `check_trends_keywords` with a fake client prints PASS/AMBIGUOUS/FAIL per coin and a paste-ready block, writes no file | checker tests 1-5, 10, 11; 429 circuit breaker tests 7-8; sleep test 6 |
| AC-T11 `probe_trends` prints status, latency, row count, step and first/last rows for a fake and an injected failure; output has no header, cookie or token | probe tests 1-6 (5 is the secret test); evidence tests 8-10 (owner decision 3) |

Not in T100a: AC-T1 (workflow, T100c), AC-T3 to AC-T9 (T100b), AC-T12 (T100c).

## 8. Owner PC probes (after the build; providers are unreachable from the build container)

1. **P-CHK:** `uv run --project api --with pytrends python -m api.scripts.check_trends_keywords` (about 75 calls, 3 s apart, roughly 4 minutes). Paste the PASS block into `api/data/trends_keywords.json`, decide the AMBIGUOUS list, report the counts. If it prints `NOT-RUN (stopped after 3 consecutive HTTP 429)`, wait and run with `--symbols` for the rest.
2. **P-PRB:** `uv run --project api --with pytrends python -m api.scripts.probe_trends`. Paste the full output. It settles: does Google answer from the PC, latency, daily or weekly at `today 3-m`, complete days (the 90-day gate), and the anchor evidence (SPEC question 1).
3. Later, in T100c: **P-GH** (same probe from a GitHub runner).

## 9. Rollback and risks

**Rollback:** revert the slice PR. All files are new, nothing imports them, no data or cache is written, no workflow or dependency changed.

**Risks.** (1) Google's suggestion `type` vocabulary is UNVERIFIED; the word list may mark real coins AMBIGUOUS (safe direction; owner picks). (2) The unofficial endpoints can change or 429 at any time (SPEC R1, R6); both tools sleep and stop early. (3) Seed identities for CC, NIGHT, VVV, WLFI, XDC and the 7 unidentified tickers are UNVERIFIED; they start `no-keyword`, so no wrong keyword can be fetched. (4) `_anchor` is a placeholder (`Bitcoin` as a plain term) until the owner reads the probe. (5) The SPEC is not merged (#149); a change to its section 2 invalidates this PLAN. (6) `pytrends` `retries` kwarg incompatibility with urllib3 2.x is a library-side risk; the tools avoid the kwargs. (7) A `term` such as `Pepe coin` or `Bitcoin` may still match unrelated searches; topic ids from P-CHK replace them.

## Touchpoints

New files only (section 4 table). Read-only references: `api/analytics/attention/narratives.py:29,91-92` (symbols, in tests only), `api/data/attention/registry.py:36-51` and `types.py:10` (the 90-day gate the probe's complete-day count is compared with), `api/data/pytrends_adapter.py:54-57,62,66-67,132-133,190-213` (lazy import, frame handling, anchor constants), `api/scripts/check_wiki_titles.py` (pattern), `api/scripts/backfill_pytrends_history.py:83-100,185` (factory and daily-frame pattern).

## Public Contracts

New importable surface: `api.data.attention.trends_keywords` (`validate`, `load`, `safe_load`, `KeywordMap`, `KeywordFileError`, constants `BAD_FILE_REASON`, `ANCHOR_KEY`); two CLI modules. No HTTP route, no response field, no config key, no workflow input changes.

## Blast Radius

None at runtime: no existing module imports a new file, and `pytrends` is never imported at module import time. Test-suite blast radius: three new test files and one fixtures module (counts in the Validate Contract). The keyword file is a data file nothing reads until T100b.

## Verification Evidence

Baselines measured on `main` 67baa0c in a scratch worktree, `UV_FROZEN=1 uv sync --project api --frozen`: attention suite 201 passed (33.3 s); `api/tests/scripts` 305 passed, 2 warnings (106.7 s); `api/tests/data/attention` 110 collected; trends group 139 passed (5.8 s); full API 1684 passed, 1 skipped, 5 deselected, 2 warnings (302.7 s). Frozen snapshot hashes: 3 lines OK. `pytrends` is not importable in the api env (`ModuleNotFoundError`), as the SPEC says. `pytrends` 4.9.2 installed in a throwaway env: exception classes and `suggestions` read from source (section 3). Google was not contacted.

## Resume and Execution Handoff

Next: the owner's ENTER EXECUTE MODE for T100a with this plan path and the planner's envelope (opus, RT1, branch `claude/<task-id>-t100a-trends-tools`, one draft PR, never merge, `needs_input` means stop). The EXECUTE worker reads CLAUDE.md, the envelope, this PLAN and (on demand) the SPEC section 2 to 4 and 6; it opens no other doc and notes any in report heading 11.

## Validate Contract

Status: PASS
Date: 2026-10-21
date: 2026-10-21
generated-by: outer-pvl
Code under test: `main` 67baa0c (PR #144 and #145 merged; PRs #146, #147, #148, #149 open and not merged). Measured in a scratch worktree of that commit, `UV_FROZEN=1 uv sync --project api --frozen`, 21-10-26 UTC. Method: FAST MODE, two layers in one session (T121): Layer 1 four dimensions on the PLAN, Layer 2 per-section feasibility with every cite re-read on 67baa0c. Findings F1-F8 are in the Validation record; each was fixed in the PLAN text above before the verdict, none is left open. The verdict is the gate line at the top of this file.

### Baselines (main 67baa0c)

| What | Command (repo root) | Result |
|---|---|---|
| Attention suite | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` | 201 passed, 33.3 s |
| Scripts tests | `UV_FROZEN=1 uv run --project api pytest api/tests/scripts -q` | 305 passed, 2 warnings, 106.7 s |
| data/attention + pytrends group | `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/data/test_pytrends_adapter.py api/tests/scripts/test_backfill_pytrends_history.py -q` | 139 passed, 5.8 s (`api/tests/data/attention` alone: 110 collected) |
| Workflow guards | `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards/test_attention_workflow_guard.py api/tests/scripts/test_ci_workflow.py -q` | 22 collected |
| Full API | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 1684 passed, 1 skipped, 5 deselected, 2 warnings, 302.7 s |
| Frozen snapshots | G7 block below | 3 OK (the signals folder holds 12 files today and grows daily) |
| `pytrends` in the api env | `uv run --project api python -c "import pytrends"` | `ModuleNotFoundError` (expected) |
| Web | not run | T100a touches no web file (G6 proves it) |

### Test gates (exact commands; Pass rule: 0 failed; skipped and deselected unchanged at 1 and 5; passed counts at least the floor, d = tests deleted or replaced, each listed in the report with its reason)

| Gate | Command | Pass criterion |
|---|---|---|
| G1 new tests | `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_trends_keywords.py api/tests/scripts/test_check_trends_keywords.py api/tests/scripts/test_probe_trends.py -q` | 0 failed; at least 46 passed (18 + 14 + 14 named). Red-first evidence: the report quotes the failing run before the code existed |
| G2 trends group | the baseline command of the 139 row | 0 failed; at least 139 + 18 = 157 passed |
| G3 scripts suite | `UV_FROZEN=1 uv run --project api pytest api/tests/scripts -q` | 0 failed; at least 305 + 28 = 333 passed |
| G4 attention suite | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` | exactly 201 passed (nothing there is touched) |
| G5 full API (once, by the tester) | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 0 failed; at least 1684 + 46 = 1730 passed, 1 skipped, 5 deselected |
| G6 forbidden paths and exact file set | `git fetch origin main && git diff --name-only origin/main...HEAD \| sort` | prints exactly the 9 paths of the section 4 table, nothing else (no `.github`, `web`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache`, SPEC or other process file) |
| G7 frozen snapshots | `cd api/data/cache/attention/signals && sha256sum -c` over the three hashes: `eb4730e44d5f7f17d86fc1e704a87c69b1a247d4fc1ab41aca0555f226bbcdde  2026-10-17_w30.json`, `597fb394fcfc3207c5f8adfc35e57827f39cf81e6cff031787678a2e76d6aef1  2026-10-17_w7.json`, `09946558044b0bfa7093dfeb5fe1ab586eca6b762fd89301b807eb01ec9909ac  2026-10-17_w90.json` | three lines `OK` |
| G8 hygiene | `git diff --check origin/main...HEAD` and `git diff -U0 origin/main...HEAD \| grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}\|(API_?KEY\|SECRET\|TOKEN\|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"` | `diff --check` exit 0; scan prints nothing (EXECUTE builds the test sentinel from two string parts, `"tok_" + "SECRET_SENTINEL_123456"`, and writes no `Bearer <12+ chars>` literal, so the scan prints nothing) |
| G9 seed invariants | `UV_FROZEN=1 uv run --project api python -c "import json; from api.data.attention import trends_keywords as k; from api.analytics.attention import narratives as n; m=k.load(placed_symbols={c['symbol'] for x in n.load_narratives()['narratives'] for c in x['coins']}); print(len(m.entries), sum('term' in e for e in m.entries.values()), sum('no-keyword' in e for e in m.entries.values()), sum('topic' in e for e in m.entries.values()))"` | prints `75 43 32 0` (a changed placed set after #148 or a G-OWN edit changes the first number: then the first two must still sum to it and the last must be 0) |
| G10 no network, no pytrends at import | `UV_FROZEN=1 uv run --project api python -c "import api.data.attention.trends_keywords, api.scripts.check_trends_keywords, api.scripts.probe_trends, api.scripts.trends_cli_common"` and `grep -nE "^\s*(import\|from) +(requests\|httpx\|socket\|urllib\|pytrends)" api/data/attention/trends_keywords.py api/scripts/check_trends_keywords.py api/scripts/probe_trends.py api/scripts/trends_cli_common.py` | import exit 0; grep prints nothing (the only `pytrends` import is inside `make_trendreq()`) |
| G11 CLI smoke, no network | `UV_FROZEN=1 uv run --project api python -m api.scripts.check_trends_keywords --file /nonexistent.json; echo $?` then `... python -m api.scripts.check_trends_keywords; echo $?` then `... python -m api.scripts.probe_trends; echo $?` | first exit 2; second and third exit 3 and print the `--with pytrends` command (the api env has no `pytrends`) |
| G12 plan validator | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-trends-t100a_PLAN_21-10-26.md` | 0 failures; warnings recorded in the validation record |
| G13 named end-to-end | the test `test_paste_ready_block_is_valid_and_only_pass_entries` (checker output merged into a copy of the seed, then `validate`) and `test_report_has_version_outcome_latency_rows_step_complete_days` (probe, fake client) | pass; these are the two automated end-to-end paths of this slice (fake transport, no network) |

### Owner probes and rollback

Probes: section 8 (P-CHK, P-PRB; P-GH belongs to T100c). Rollback: revert the slice PR (section 9).

### Hard stops (verbatim for the /goal block)

- Any change under `.github/`, `web/`, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache/`, any existing file under `api/` or `process/`, or any SPEC: stop and report.
- Any `topic` value in `api/data/trends_keywords.json` that was not produced by the owner's checker run: stop and report (no invented topic ids).
- A test, tool or script that opens a network connection, or that prints an exception message, header, cookie or token: stop and report.
- A frozen snapshot hash of G7 differs: stop and report.
- A baseline on fresh main differs from the table above by anything other than a merged earlier PR (#146 to #149): stop and report the numbers.
- The SPEC (#149) changed section 2 or the T100a row of section 7 since 28fa003: stop and re-validate.
- A needed edit outside the nine files of the section 4 table: stop and report, do not widen the slice.
- `needs_input`: stop; do not merge; do not open a new PR. Never merge any PR.
- Slice cost at the ask threshold the planner sets (proposal 5 USD): ask; hard cap per the planner (proposal 8 USD).

### Dimension findings (after the fixes in this PLAN)

| Dimension | Status | Evidence |
|---|---|---|
| infra/setup-fit | PASS | every read target exists on 67baa0c with the cite in this file; baselines recorded; the pattern file, test helpers and the factory pattern exist; `uv run --with pytrends` resolves pytrends 4.9.2 in a throwaway env (library only); F1, F2, F4 fixed in the text |
| test-coverage | PASS | 46 named red tests across three files; the coverage test is derived from `attention_narratives.json`, not from a number; fake transports only; named end-to-end per tool (G13); live behaviour is a recorded known gap with owner probes |
| breaking-changes | PASS | no existing file is edited (G6); `trends.fetch_series` and the runner keep the ticker path until T100b; imports of the new modules work without `pytrends` (G10); the collision proof against #146 to #149 is empty; F3, F5 fixed |
| security-surface | PASS | symbols and terms are validated with strict patterns before any use (the symbol pattern is the same trust boundary as `narratives.py:29` because T100b builds store paths from it); CLI values validated before a request; output policy: exception class and integer HTTP status only, never message, headers or cookies (pytrends keeps the whole `requests.Response` on the exception); no secrets in files; nothing under `.github/`; no cache write (F6, F7) |

### Open gaps

None blocking. Recorded known gaps: (1) every live Google behaviour is UNVERIFIED and covered by P-CHK and P-PRB only: the `suggestions` item keys (`mid`, `title`, `type`), the `type` vocabulary, the 429 threshold, whether `today 3-m` returns daily rows from a given IP, the real `TrendReq` constructor behaviour on the owner's resolved versions; (2) identity of 12 seeded coins; (3) the anchor value of the seed is a placeholder; (4) SPEC #149 is not merged.

### What This Coverage Does NOT Prove

The gates read committed files and drive fakes; none calls Google. They do not prove that Google's suggestion endpoint returns the keys the checker reads, that its `type` strings contain any word of `CRYPTO_TYPE_WORDS`, that 3 s pacing avoids a 429, that a residential IP is answered while a runner IP is not, that `today 3-m` is daily and has at least 90 complete days, that the frame columns match the term strings (Google may rewrite a topic id in the frame column names), or that a Bitcoin or an Ethereum anchor is the better one. They also do not prove the 12 UNVERIFIED seed identities, or that a keyword that passes the validator returns useful interest. These are exactly the questions P-CHK and P-PRB answer, and the reason T100b must not start before the owner has run them.

### Accepted by

session (T121 worker, 21-10-26, docs only), on the planner's envelope; no concern is accepted by the owner yet: the section 2 rulings R-A to R-F, the seed table of 3.2 and the proposed cost thresholds are the owner's to overrule at ENTER EXECUTE MODE.

## Validation record (T121, 21-10-26)

Layer 1 (infra, test coverage, breaking changes, security, run on a scratch worktree of 67baa0c) and Layer 2 (feasibility of the single slice; every cite below re-read on 67baa0c). Findings, all fixed in the text above:

| # | Finding | Severity | Fix |
|---|---|---|---|
| F1 | The SPEC says a bad keyword file makes "the Trends source unavailable", but the runner wiring is T100b | CONCERN | T100a ships `safe_load` returning `(None, "bad keyword file")` and proves it at loader level (test 16); the runner wiring and its end-to-end test are T100b |
| F2 | The loader belongs to the data layer, which imports nothing from analytics; the coverage rule needs the placed symbols | CONCERN | R-D: `placed_symbols` argument; test 18 forbids the import |
| F3 | BTC (or ETH) and `_anchor` may legitimately share a keyword; the SPEC uniqueness rule would reject it | CONCERN | R-A: `_anchor` excluded from uniqueness |
| F4 | The checker needs a name for `no-keyword` coins; the SPEC example has no label there | CONCERN | R-B: `label` on every entry; default checker map = labels |
| F5 | The coverage count (75) can change with #148 or a later G-OWN edit | CONCERN | count derived in tests, never hard-coded; #148 only flips `status`; G9 tolerates a changed total |
| F6 | `pytrends` exceptions carry the full `requests.Response` (headers, cookies); `str(exc)` may expose them | CONCERN | output policy: class name and integer status only; test sentinel in message and `Set-Cookie`; probe test 5 and checker test 9 |
| F7 | `TrendReq(retries=..., backoff_factor=...)` is known to break on urllib3 2.x (`method_whitelist`) | CONCERN | tools never pass those kwargs; own sleeps; stated as UNVERIFIED on the owner's versions |
| F8 | The SPEC's "75 placed coins" and its file list omit `trends_cli_common.py` and the fixtures module | CONCERN | added to the section 4 table as additive files (R-F, 3.5) |

**Cite verification on 67baa0c (Layer 2).** Verified as written in the SPEC: `refresh_attention.py:34` (`CIRCUIT_BREAKER_AFTER = 5`), `:177-178` (`_run_trends`); `trends.py:33-35`; `pytrends_adapter.py:34-35`, `:37`, `:54-57`, `:62`, `:66-73`, `:132`, `:133`, `:145`, `:159-187`; `registry.py:39-40`, `:49-51`; `types.py:10`; `check_wiki_titles.py:25`; `attention-refresh.yml:207` and the `timeout-minutes: 8` step at `:204`; `narrative-snapshot.yml:59`; `pyproject.toml` dependencies `:6-17`. One off-by-one in the SPEC: `store.py:41-56` is `store.py:41-57` (`write_series`, ends with `return added` at 57). Cites added by this PLAN, all verified: `check_wiki_titles.py:22,23,28-37,40,75-89,92-105`; `backfill_pytrends_history.py:54,83-87,89,185`; `narratives.py:29,32,91-92`; `refresh_attention.py:92`; `pytrends_adapter.py:190-213`; `test_check_trends_keywords` model tests `test_check_wiki_titles.py:22,26,65,73,81,93,99`; `test_pytrends_adapter.py:108` (`_install_fake_pytrends`).

**Validator output (G12).** `validate-plan-artifact.mjs` on this file at the commit of this PR: 0 failures, 0 warnings, 337 lines. Commands also exercised on main 67baa0c in the scratch worktree: `import api.scripts.check_wiki_titles` and `narratives.load_narratives()` (75 distinct symbols), `import pytrends` (`ModuleNotFoundError`), `python -m api.scripts.check_wiki_titles --file /nonexistent.json` (prints the class, exit 2: the model for G11's first line).
