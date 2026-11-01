# Screener small slices: completion report (01-11-26)

## Validate contract (written before editing)

- G1: vitest pure-function tests for `sortGroup` (name, % change, RSI; tie-break by symbol; missing/non-finite last, never 0; no-op returns input) committed red first.
- G2: board component tests: a sort saves through the existing layout save path, panels re-order, announcer states how many had no value.
- G3: `pnpm test` green apart from the known Windows `plot-ink.test.ts` quirk; `pnpm exec tsc --noEmit --incremental false` green.
- G4: draft PR, Linux CI green. No .github/, package, narrative or PR #211 files touched.

## 1 Task ID
screener-small-slices (backlog notes `screener-group-sort_NOTE_09-10-26.md`, `spaghetti-toggle-persistence_NOTE_09-10-26.md`; SPEC AC-8, AC-22 / AC-S6-6).

## 2 Outcome
done (sort slice built; toggle slice already present on main), pending owner PC probe.

## 3 Summary
- AC-22 / AC-S6-6 (spaghetti toggle persistence): ALREADY DONE on main by S5b. The hidden set is the saved layout's `hidden_lines` (`GET/POST /api/layout/crypto`), passed to `SpaghettiChart` as a controlled `hidden`; `api/data/layout.py` reconciles it to known coins/references. Covered by `ScreenerBoardLayout.test.tsx` "the initial hidden lines come from the layout and a toggle saves hidden_lines". Nothing built; no localStorage convention added.
- AC-8 (group sort): NOT on main; built as the note's preferred one-shot design. Each group gets three buttons (`sort-group-{name|change|rsi}-<id>`). A sort rewrites the group's saved coin order through the existing `commit` save queue, so it survives a reload and the manual move buttons keep working.
- Name: A to Z. % change: the shown timeframe's gain chip `pct`, high to low. RSI: `rsi.value`, high to low. Ties by symbol. Null, absent or non-finite values go last (ordered by symbol) and are never read as 0; a real 0 sorts as 0. The panels keep their own N/A reason labels. The announcer says e.g. "Main sorted by RSI, high to low; 1 without a value placed last."
- Buttons are disabled (aria-disabled) when the layout is not editable or the group has fewer than 2 coins. No visual redesign; existing `board-button` class.

## 4 Files changed
- `web/lib/layout-state.ts` (`SortKey`, `sortGroup`)
- `web/components/screener/CoinGroup.tsx` (sort buttons, `onSortGroup` prop)
- `web/components/screener/ScreenerBoard.tsx` (`onSortGroup` handler; `panels` added to the `latest` ref)
- `web/lib/__tests__/layout-state.test.ts`, `web/components/screener/__tests__/ScreenerBoardLayout.test.tsx`
- this report

## 5 Commits
Branch `claude/screener-small-slices` from origin/main `e1394b80` (the envelope said 1e8f59d0; main had moved on fetch).
- `dbd0d24c` red tests (6 failing, observed)
- `400f0d50` implementation
- report commit (this file)

## 6 Tests run
- `pnpm exec vitest run lib/__tests__/layout-state.test.ts components/screener/__tests__/ScreenerBoardLayout.test.tsx` at dbd0d24c: 6 failed / 27 passed (red as intended).
- `pnpm exec tsc --noEmit --incremental false` at 400f0d50 content: exit 0, no output.
- `pnpm test` (vitest) at 400f0d50 content, ~2026-11-01T14:49Z: 597 passed, 1 failed: `lib/__tests__/plot-ink.test.ts` (known Windows host quirk, unrelated).
- Linux CI on the draft PR: see PR checks.

## 7 Tests NOT run
- Playwright e2e (the note's "sort a group, reload, read the order" and "toggle, reload, aria-pressed=false"): not written/run; `PLAYWRIGHT_CHROMIUM_PATH` unset on this host. Reload persistence is evidenced only by the vitest layout-server save assertions.
- No visual check at 375/768/1280 and no live PC probe; P-S5b-1 stays owner-side.
- No API tests: no API change.

## 8 Deviations
- No e2e test added (the backlog note's "Done when" asks for one); see 7.
- % change uses the board's currently shown timeframe (the SPEC does not name one); the announcer names it.

## 9 Blockers
None. Risk: header now carries three more buttons; wrap at 375px unverified visually. Registry request: after owner merge and PC probe, move AC-8r CONDITIONAL to PASS in the batch 3 plan; AC-S6-6 can move to PASS on the existing S5b evidence (owner to confirm).

## 10 Follow-up
- One seeded Playwright e2e covering sort-then-reload and toggle-then-reload once a browser path is available.
- Archive both backlog notes after owner acceptance.

## 11 Context cost
Files loaded: 2 backlog notes, SPEC AC-8/AC-22 lines, layout-state.ts, CoinGroup.tsx, ScreenerBoard.tsx (parts), screener types, two test files (parts), master-planner section 9. Roughly 40k tokens. Tools: read/bash/edit/eval/grep; no browser.
