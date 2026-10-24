---
name: report:narrative-baskets-trends-t160
description: "T160/T174: qualified Trends terms for the coins the checker could not resolve to a topic id (data-only)."
date: 24-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T160 qualified Trends terms: REPORT

## 1 Task ID
T174 = T160, branch `claude/t160-trends-qualified-terms`, one draft PR to main. Not merged.

## 2 Outcome
Done. 33 entries in `api/data/trends_keywords.json` now carry a qualified `term` (25 re-termed, 2 already qualified and kept with a note, 6 new). The 41 `topic` entries are unchanged. Whether Google returns data for these terms is NOT proven; the owner runs the checker / P-RES later.

## 3 Summary
Term rule: "<project name> crypto", lower case, from the loader's qualifier list (same output as `check_trends_keywords.qualified_term`). The owner's six checker-given terms are used exactly. No earlier checker proposal for ASTER, CRO or ENA exists in the shipped tests or notes, so they follow the rule. NAME_RISK coins (TRX, ONDO, MORPHO, PEPE, CRO, APT, ...) have only qualified terms or topics. Seven unidentified coins are unchanged. Every entry keeps a label and a note giving the source.

| coin | chosen term | was | source |
|---|---|---|---|
| APT | `aptos crypto` | term 'Aptos' | checker-given |
| ASTER | `aster crypto` | no-keyword | rule '<name> crypto' |
| ATOM | `cosmos crypto` | no-keyword | checker-given |
| AVAX | `avalanche crypto` | no-keyword | checker-given |
| BDX | `beldex crypto` | none | rule '<name> crypto' |
| CC | `canton coin` | no-keyword | checker-given |
| CRO | `cronos crypto` | term 'Cronos' | rule '<name> crypto' |
| DASH | `dash crypto` | none | rule '<name> crypto' |
| ENA | `ethena crypto` | term 'Ethena' | rule '<name> crypto' |
| ETC | `ethereum classic crypto` | term 'Ethereum Classic' | checker-given |
| ETHFI | `ether fi crypto` | none | rule '<name> crypto' |
| JST | `just crypto` | no-keyword | checker-given |
| JUP | `jupiter crypto` | no-keyword | rule '<name> crypto' |
| LEO | `unus sed leo crypto` | no-keyword | rule '<name> crypto' |
| M | `memecore crypto` | none | rule '<name> crypto' |
| MNT | `mantle crypto` | no-keyword | rule '<name> crypto' |
| MORPHO | `morpho crypto` | term 'Morpho' | rule '<name> crypto' |
| NIGHT | `midnight crypto` | no-keyword | rule '<name> crypto' |
| OKB | `okb token` | term 'OKB' | rule exception (name = ticker) |
| ONDO | `ondo crypto` | term 'Ondo' | rule '<name> crypto' |
| PAXG | `pax gold crypto` | no-keyword | rule '<name> crypto' |
| PEARL | `pearl crypto` | none | rule '<name> crypto' |
| PEPE | `Pepe coin` | term 'Pepe coin' | kept (already qualified) |
| POL | `polygon crypto` | no-keyword | rule '<name> crypto' |
| QNT | `quant crypto` | no-keyword | rule '<name> crypto' |
| RENDER | `render crypto` | no-keyword | rule '<name> crypto' |
| SKY | `sky crypto` | no-keyword | rule '<name> crypto' |
| STX | `stacks crypto` | no-keyword | rule '<name> crypto' |
| SUI | `sui crypto` | no-keyword | rule '<name> crypto' |
| TRX | `tron crypto` | term 'TRON' | rule '<name> crypto' |
| VET | `vechain crypto` | none | rule '<name> crypto' |
| WBT | `WhiteBIT Coin` | term 'WhiteBIT Coin' | kept (already qualified) |
| ZRO | `layerzero crypto` | term 'LayerZero' | rule '<name> crypto' |
Notes: PAXG was no-keyword ("attention tracks gold"); the owner's rule now gives `pax gold crypto`, which may still track gold. OKB: name equals ticker, so `okb token` (rule exception). Names for DASH and VET come from `wiki_articles.json`; ETHFI, M, PEARL, BDX from CoinGecko ids in the cached universe snapshot (`ether-fi`, `memecore`, `pearl-2`, `beldex`), no guessing. PEARL and PRL share CoinGecko id `pearl-2`.

Unidentified, unchanged (CoinGecko ids found in `api/data/cache/attention/universe.json` and `coingecko/*.parquet`):

| coin | CoinGecko id |
|---|---|
| AKE | akedo |
| BTW | bitway |
| GRAM | the-open-network |
| LIT | lighter |
| PRL | pearl-2 (same id as PEARL) |
| RAIN | rain |
| STABLE | stable-2 |

## 4 Files changed
- `api/data/trends_keywords.json`
- `api/tests/data/attention/test_trends_keywords.py` (+7 T160 tests; two older tests updated)
- `api/tests/scripts/test_check_trends_keywords.py`, `api/tests/scripts/test_probe_trends.py` (expectations tied to the old file data)
- this report

## 5 Commits
`235268e` data and tests; report commit follows (see PR head).

## 6 Tests run
Red first: 4 of the 7 new tests failed on the old file. After the change: `test_trends_keywords.py` 65 passed; `pytest api/tests/data/attention api/tests/scripts` 670 passed; full `pytest api` 2028 passed, 1 skipped, 5 deselected, 0 failed. `git diff --check` clean, JSON valid, secret scan clean, file set = the four files above plus this report. New tests cover: topics unchanged, no bare name or ticker for NAME_RISK symbols, every term has a qualifier word, every eligible Discovery symbol except the seven has an entry, `safe_load` passes.

## 7 Tests NOT run
No network, no provider contact. Google data for the new terms is unverified.

## 8 Deviations
- BDX (Beldex) is an eligible Discovery coin with no entry and was not on the owner's list; added by the same rule so check (d) holds.
- Three existing tests were edited because they read the shipped file: the placed-symbol warnings list (now the six extras), "label equals term" (now term starts with label), and in `api/tests/scripts` the APT/ATOM/count expectations. The envelope named only the shipped-file tests; these are the minimum needed to keep the suite green.
- `attention_queries.json` does not exist in the repo; names came from the file labels, `wiki_articles.json` and CoinGecko ids.
- The eligible set in check (d) is pinned (placed coins plus six extras from the 2026-10-24 snapshot), so later daily snapshots cannot break the test.

## 9 Blockers
None.

## 10 Follow-up
Owner runs the checker on the new terms; terms that fail should move to topic ids. Identify the seven unidentified tickers.

## 11 Context cost
Extra docs opened: `api/data/attention/trends.py`, `api/scripts/check_trends_keywords.py`, `api/analytics/attention/discovery.py`, `universe_classes.py`, `universe.py`, `wiki_articles.json`, `cache/attention/universe.json`. Not CLAUDE.md-listed docs.

## T185 update
Merged `origin/main` (PR #166, checker block-stop, d968e44) into this branch as a merge commit; no rebase, history append-only.
- Conflict in `api/tests/scripts/test_check_trends_keywords.py` (`test_rev_coverage_with_symbols_counts_unchecked_coins_apart`): kept main's new `not run` field and this PR's new counts, giving `term: 1 | nothing: 0 | not run: 0 | not checked: 2`. Main's T161 tests are otherwise unchanged.
- `test_t161_coverage_counts_not_run_apart_from_nothing` failed after the merge because AVAX now has a term in `trends_keywords.json`, so it counts as `term` and is no longer checked under `--only-unresolved`. Test expectations only: `term: 1 | nothing: 3` and `nothing: 2 | not run: 1`. This is a legitimate data effect, not a data problem. No data, checker or other file changed.
- Result: `tests/scripts` + `tests/data/attention` 710 passed; full `pytest api` 2074 passed, 1 skipped, 5 deselected, 0 failed.

T183 review table, 10 WEAK terms (likely junk Trends results, 0 WRONG): JST, PEARL, DASH, ASTER, SKY, NIGHT, RENDER, QNT, PAXG, ETHFI.
Owner runs the checker (`check_trends_keywords.py --only-unresolved`) to confirm; no term changed here.
