# T46 S9B report: layout section "equities"

## 1. Task ID
T46 (batch 5, slice S9B), branch `claude/t46-s9b-equities-layout`, base main `6aee5e2`.

## 2. Outcome
PASS after a planner-approved fix. The first full run showed a hidden break in an existing S9A test (needs_input, reported); the planner approved option A; after that edit all gates pass (1100/2/5). Draft PR opened; not merged.

## 3. Summary
`api/data/layout.py` now uses a section registry: `_SECTION_SOURCES` (crypto: `watchlist_store.read_watchlist`, equities: `equities_store.load_tickers`, both looked up at call time via lambdas) and `_SECTION_REFERENCES` (crypto: `REFERENCE_SYMBOLS`, equities: `()`); `SECTIONS = tuple(_SECTION_SOURCES)` = `("crypto", "equities")`. `_reconcile` keeps its signature with a new `references=REFERENCE_SYMBOLS` default; `_layout`, `save_layout`, `drop_coin` pass the section's members and references. Crypto results unchanged (G-S9B-2 green at old counts).

Hidden break: `api/tests/routers/test_equities_router.py::test_layout_failure_is_logged_not_failed` (S9A) adds AAPL with `group_id="g-missing"` and asserts the log line "layout not updated after adding AAPL". On main it passed only because "equities" was an unknown layout section, so `place_coin` raised `UnknownSectionError` and the router logged it. With the section registered, `place_coin` returns False for a missing group (same as crypto) and nothing is logged; the add still returns 200. The file is not in the plan's editable table and `api/routers/*` is Forbidden, so I did not touch either.

Options put to the planner (option A approved and applied in `f008a2c`):
- A: add `api/tests/routers/test_equities_router.py` to the S9B editable table and make the test induce a real layout failure, e.g. `monkeypatch.setattr(layout_store, "place_coin", raising_fn)`; count effect 0, end stays 1100/2/5.
- B: allow `api/routers/equities.py` to log when `place_coin` returns False (crypto router parity question; touches a Forbidden file).

## 4. Files
- `api/data/layout.py` (edit)
- `api/tests/routers/test_layout.py` (line 177: `SECTIONS == ("crypto", "equities")`, count effect 0)
- `api/tests/data/test_layout_equities.py` (new, 12 tests)
- `api/tests/routers/test_equities_layout_router.py` (new, 8 tests)
- `api/tests/routers/test_equities_router.py` (planner-approved addition: `test_layout_failure_is_logged_not_failed` now monkeypatches `layout_store.place_coin` to raise; original assertions kept; count effect 0)
- this report

## 5. Commits
- `9fff6f4` feat(layout): T46 S9B equities layout section via section registry
- `50732dd` docs: T46 S9B worker report (needs_input)
- `f008a2c` test(equities): induce a real layout failure in the S9A logging test
- report update commit on top

## 6. Tests run (SHA, UTC)
- Red run, `6aee5e2` + stubs, 2026-10-12T07:19:20Z: G-S9B-1 files as `pytest.fail` stubs: 20 failed.
- G-S9B-1, working tree on `6aee5e2`, 2026-10-12T07:20:22Z: 20 passed.
- G-S9B-2, same: 45 passed, 1 deselected (test_layout_store 15, test_layout 10, test_watchlist 5, test_watchlist_cap 11, test_board_integration 4 + 1 deselected): old counts.
- G-S9B-3, same: 1 failed, 1099 passed, 2 skipped, 5 deselected. Failure: `test_equities_router.py::test_layout_failure_is_logged_not_failed` (above). Expected 1100/2/5: count mismatch from the hidden break.
- (first pass) G-S9B-4 after commit `9fff6f4`, 2026-10-12T07:23:45Z: REAL-DATA empty; S-secret empty; `git diff --check` rc 0; FORBIDDEN empty; FIXTURES empty; S9B-scope empty; S9-words empty; added-line UTC check empty.
- After the approved edit, working tree on `50732dd`, 2026-10-12T07:24:45Z: G-S9B-1 20 passed; G-S9B-2 45 passed, 1 deselected (old counts); G-S9B-3 1100 passed, 2 skipped, 5 deselected (matches the plan).
- G-S9B-4 after commit `f008a2c`, 2026-10-12T07:27:31Z: REAL-DATA empty; S-secret empty; `git diff --check` rc 0; FORBIDDEN empty; FIXTURES empty; S9-words empty; S9B-scope lists exactly `api/tests/routers/test_equities_router.py` (the planner-approved addition). Extra added-line check for the word UTC hits only this report's required heading and its log lines, no source line.

## 7. Tests NOT run
Web gates (web untouched). No e2e (not required for S9B). Probes P-* are the user's.

## 8. Deviations
- Hidden break: `test_equities_router.py::test_layout_failure_is_logged_not_failed` (S9A) depended on "equities" being an unknown layout section; registering the section made it fail (details in Summary).
- Planner-approved test edit (option A, planner session message 2026-10-12): that one test now induces a real layout failure by monkeypatching `layout_store.place_coin` to raise; its assertions are unchanged; no router or other file touched; no new tests.
- Sources are lambdas wrapping the store functions so the lookup happens at call time (plan: "looked up at call time").

## 9. Blockers
None open. The hidden break above was resolved by the planner-approved edit.

## 10. Follow-up
Planner: review and merge the draft PR (worker does not merge). Plan's editable-test table could record the S9B row for `test_equities_router.py` at UPDATE PROCESS.

## 11. Context cost
Loaded: CLAUDE.md, envelope, plan ranges (11, 30-66, 99-107, 242-250, 253-254, 261-262, 269). Opened for code reading: `api/data/layout.py`, `api/data/equities_store.py`, `api/routers/layout.py`, `api/routers/equities.py`, parts of `test_layout.py`, `test_layout_store.py`, `test_equities_router.py`, `conftest.py`, `test_no_verdict_symbols.py`. No protocol docs opened. Subagents: none.
