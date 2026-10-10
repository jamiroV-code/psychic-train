# T41 / S5b worker report: layout UI

## 1. Task ID

T41 (batch 3, slice S5b): layout UI (groups, add/remove coins, rename, move, reorder, 30-coin cap) on top of the S5a layout API. Branch `claude/t41-s5b-layout-ui` from `origin/main` 43369ec (it contains fc12f27).

## 2. Outcome

PASS. G-S5b-1 through G-S5b-11 all pass on code commit 71e90e4, and the seeded e2e gates G-S5b-9 and G-S5b-10 ran on that SHA. No needs_input and no blocker. The PR was opened as a draft, as the envelope says, and is not merged.

## 3. Summary

- **Groups (U1):** each group is a `<section aria-labelledby>` with an `h2` (tabIndex -1), its coin count, and Rename, Up, Down and Delete buttons. The names include the group, e.g. "Rename group Main". The coins sit in a grid per group, and `screener-board-grid` stays on the container that holds the groups. A new group, or a rename, uses an inline input: Enter saves, Escape cancels, and errors show in `role="alert"`. Names are unique ignoring case, 1-40 characters, and there can be at most 12 groups. Deleting a group moves its coins to the previous group (the next one if it was first), and the last group cannot be deleted.
- **Coin actions:** in the `CoinPanel` `actions` slot, memoised per coin in `CoinGroup`'s `CoinCell`. They are Earlier, Later, a native "Move to group" `<select>`, and Remove with an inline Confirm/Cancel. Every name includes the coin and the group. Edge controls get `aria-disabled="true"` and do nothing. After a move the same control is refocused and `board-announcer` says the result. After Confirm-remove or a group delete, focus goes to the heading of the group that held or received the coins. Escape or Cancel puts focus back on Remove.
- **Loading (U2):** a `board-loading` skeleton with `aria-busy` shows until the first board answer and the first layout answer (or failure). `layout-notice`, `layout-save-error` and `board-announcer` exist from the first render. If the layout fails to load, the board shows one default group, a notice, a Retry button, and aria-disabled editing. A `recovered` layout gets its own notice. An empty watchlist shows `board-empty` and the add form. A board failure before any success shows `board-error` and no groups; a failure after one keeps the panels.
- **Saving (U3):** `use-board-layout.ts` saves optimistically through a serial queue, and each save carries the revision the last one returned. A failed save rolls back and shows `layout-save-error`. A 409 refetches the layout and says "Layout changed elsewhere; reloaded."
- **Add and remove (U4):** the add form has the symbol, a group menu (default: the last group), "Add coin", and `n / 30 coins`. At 30 or more coins the button is aria-disabled, the cap message stays on screen, and a click sends nothing. A server 409, 422 or network error shows in `role="alert"`. After a successful add or Confirm-remove, the board and layout are refetched once and the spaghetti `reloadToken` goes up by one. While an added coin's chart is unavailable, the board is refetched at +4 s and +12 s. These are the only timers, and they are cleared on unmount.
- **Toggles (U5):** `SpaghettiChart` takes `hidden`, `onToggle` and `reloadToken`. Its controlled Set is keyed on the sorted list, so an equal list in a different order neither re-mounts the chart nor calls `update`. The board passes `layout.hidden_lines` and saves each toggle.
- **Live refresh and shared zoom (U6/U7):** the order is derived with `useMemo` and never stored. Callbacks are stable (they read from refs) and `actions` is memoised. The `SpaghettiChart` container stays mounted. `sharedRange` stays on the board and only a timeframe change clears it.
- **RSI:** each panel has an `rsi-readout-<SYM>` row: `RSI 14 (<tf>)`, then one decimal, or `N/A` with the reason as the title; a value's title gives the time in Brussels time. The drill-down shows `RsiChart` (`drilldown-rsi-chart`) and `drilldown-rsi-value`; an empty series shows `drilldown-rsi-na` and does not mount the chart.
- **CSS:** uses existing tokens only. aria-disabled controls keep their text colour, get a dashed border and `cursor: not-allowed`. Inputs and selects are coloured with tokens, and the RSI row and status region have a `min-height`.

## 4. Files

New: `web/components/screener/{AddCoinForm,CoinActions,CoinGroup,RsiChart}.tsx`, `web/lib/{layout-state,rsi-format,use-board-layout}.ts`, `web/lib/api/{layout,watchlist}.ts`, the tests `web/components/screener/__tests__/{ScreenerBoardLayout,CoinPanel,CoinActions,AddCoinForm}.test.tsx` and `web/lib/__tests__/{layout-state,rsi-format,layout-api}.test.ts`, `web/e2e/layout.spec.ts`, and this report.

Edited: `web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView,SpaghettiChart}.tsx`, `web/app/globals.css`, `web/components/screener/__tests__/{ScreenerBoard,ScreenerBoardLive,ScreenerBoardLinkedZoom,DrillDownView,SpaghettiChart}.test.tsx`, and `web/e2e/screener.spec.ts` (test 1 only).

All 28 code and test files plus this report are in the S5b-scope list; the `S5b-scope` and `FORBIDDEN` greps print nothing.

## 5. Commits

- 71e90e4 feat(screener): layout UI with groups, coin moves, add/remove, 30-coin cap and RSI display (T41 / S5b)
- (next) docs: S5b worker report

## 6. Tests run (SHA, UTC)

| Gate | SHA | UTC | Result |
|---|---|---|---|
| Baseline vitest | 43369ec | 17:43Z | 335 passed in 43 files |
| G-S5b-11 red (scoped) | 43369ec + stubs and tests, uncommitted | 17:48Z | 116 in 14 files: 65 failed, 51 passed (as planned) |
| G-S5b-11 red (full) | same | 17:48Z | 400 in 50 files: 65 failed, 335 passed (as planned) |
| G-S5b-1 | 71e90e4 | 17:58Z | 116 passed in 14 files |
| G-S5b-2 | 71e90e4 | 17:58Z | 400 passed in 50 files |
| G-S5b-3 tsc | 71e90e4 | 17:58Z | exit 0 |
| G-S5b-4 build:islands | 71e90e4 | 17:58Z | exit 0 |
| G-S5b-5 verdict scan | 71e90e4 | 17:58Z | 2 passed |
| G-S5b-6 diff --check | 71e90e4 | 17:58Z | exit 0, no output |
| G-S5b-7 scope/forbidden/secret | 71e90e4 | 17:58Z | print nothing |
| G-S5b-8 words/nostore/cap | 71e90e4 | 17:58Z | words and nostore print nothing; CAP-MESSAGE prints 1 and 1 |
| G-S5b-9 e2e screener+contrast+layout | 71e90e4 | 17:59Z | 24 passed (10 + 7 + 7) |
| G-S5b-10 e2e full suite | 71e90e4 | 18:00Z | 79 passed; `playwright test --list`: 79 tests in 9 files |
| pytest full (`uv run --project api pytest api/ -q`) | 71e90e4 | 18:03Z | 1016 passed, 2 skipped, 5 deselected |

One development run of G-S5b-9 (24 passed) took place before a one-line comment rewording in `CoinGroup.tsx`. Every gate above ran once after that last edit.

## 7. Tests NOT run

- P-S5b-1: this is the user's manual probe and was not run.
- CI does not run Playwright; the seeded e2e above is the evidence.

## 8. Deviations

1. **Add form when the layout fails to load.** The add form stays enabled, because it edits the watchlist, not the layout. Only the layout-editing controls (coin moves, group menu, Remove, group controls, New group) are aria-disabled.
2. **New testids:** `board-action-error` (a `role="alert"` line for a failed remove), `layout-retry`, `new-group-button`/`-input`/`-error`, `coin-group-<id>`, `group-heading-<id>`, `group-count-<id>`, `group-empty-<id>`, `rsi-value-<SYM>`, `add-coin-*`, `coin-actions-<SYM>`, `move-earlier-`/`move-later-`/`move-to-group-`/`remove-`/`confirm-remove-`/`cancel-remove-<SYM>`, and the group control ids. None starts with `coin-panel-`.
3. **Existing-test edits:** besides the planned `fetchLayoutStub` const and the `fetchLayout={fetchLayoutStub}` prop at every site (10, 2 and 3 sites), each of the three files gained one `import type { Layout }` line so the stub is typed. No assertion changed.
4. **Plain-language copy.** The 409 notice goes in `layout-notice`. Save and reload failures go in `layout-save-error` ("The layout was not saved: ..."). The RSI reason copy is: "Not enough history for RSI 14", "Symbol configuration issue", "Data source unavailable", "Price did not change in this window".
5. **Spaghetti chart after a first board failure.** Once the board and layout have both answered, the spaghetti chart renders even if the board failed; the groups do not.

## 9. Blockers

None.

## 10. Follow-up

- In the e2e server logs (Next dev), each page load fetches spaghetti and btc-legs twice. Every effect runs twice, which looks like React StrictMode in dev; I did not compare this against the base.
- P-S5b-1 (user probe) is still open.

## 11. Context cost

- Loaded: CLAUDE.md, the envelope, and the plan's line ranges named in the envelope (read with git show; nothing from the planner branch was checked out or committed).
- Code reads beyond the envelope list, needed to implement and keep the existing tests green: the screener components and their tests, `web/lib/{api/screener,use-simple-lines,same-data,island-loader,brussels-time,format-unavailable-reason,chart-palette}.ts`, `LiveProvider.tsx`, `MiniChart.tsx` (read only), `web/playwright.config.ts`, `web/e2e/{screener,contrast}.spec.ts`, `web/app/globals.css`, `api/tests/analytics/test_no_verdict_symbols.py`, and greps of `api/scripts/seed_e2e_cache.py` and `api/data/watchlist.py`.
- No on-demand protocol docs were opened.
- No subagents were used (direct lane).
- Spend was not metered in this session; it is roughly within the 5.5-8 USD budget, and the planner measures it.
