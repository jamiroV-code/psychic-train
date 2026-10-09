# T39 Worker Report: fix the S6 zoom E2E after S7

## 1 Task ID

T39 (RT1, test-only fix), branch `claude/t39-fix-zoom-e2e`, base `main` at `38fe860`.

## 2 Outcome

**done, at review.** The test is green after option (a) plus one extra line the planner approved after T39-B1 (see headings 8 and 9). I have not merged; the PR is waiting for review.

## 3 Summary

- Reproduced the failure on the untouched base (`38fe860`). The test fails in `exerciseZoom` on the BTC coin-box plot: after Ctrl + wheel, `data-zoomed` is `"false"`.
- Applied option (a): `exerciseZoom` re-reads `plot.boundingBox()` after the plain-wheel step and moves to the recomputed point before the Ctrl + wheel. The test still failed with the same assertion (commit `5eb202e`).
- Diagnosis (temporary logging, reverted): `window.scrollY` stays `0`, so a scroll container other than the window scrolls. The plain `wheel(0, -400)` moves the plot down 63 px (box y 599.7 -> 662.7, height 120). The recomputed centre y is about 722.7, below the 720 px viewport, and `document.elementFromPoint` there returns `null`.
- Reported this as T39-B1 (needs_input). The planner approved adding `await plot.scrollIntoViewIfNeeded();` before the re-read. With that line, screener (10) and contrast (7) all pass.

## 4 Files changed

- `web/e2e/screener.spec.ts`: in `exerciseZoom`, after the plain-wheel step, `scrollIntoViewIfNeeded()`, then re-read the box and move to the recomputed point before the Ctrl + wheel (+5/-2, comment included).
- this report.

## 5 Commits

- `5eb202e` `fix(e2e): re-read plot box before ctrl-wheel in exerciseZoom (T39)`: option (a) plus the first version of this report.
- follow-up commit `fix(e2e): scroll plot into view before ctrl-wheel in exerciseZoom (T39)`: the approved line plus this report update. See the PR for the SHA.

## 6 Tests run

| Gate | Command | Result | Tree / time (UTC) |
|---|---|---|---|
| Red repro | `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e screener.spec.ts` | 1 failed (`ctrl-wheel zooms...`, `toHaveAttribute("data-zoomed","true")` at line 299), 9 passed | untouched `38fe860`, 2026-10-09T07:16:32Z |
| After (a) only | same command with `screener.spec.ts contrast.spec.ts` | RED: 1 failed (same test, same assertion), 16 passed | `38fe860` + option (a), 2026-10-09T07:17:55Z |
| CI on (a) | GitHub Actions `api — pytest`, `web — vitest, tsc, island build` | both success (they do not run Playwright) | `5eb202e`, 2026-10-09T07:24Z |
| **Final E2E** | `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e screener.spec.ts contrast.spec.ts` | **17 passed** (screener 1-10, contrast 7 routes) | `5eb202e` + the approved line (the tree of the follow-up commit), 2026-10-09T07:32:43Z |
| Typecheck | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 | same tree, 2026-10-09T07:34Z |
| Whitespace | `git diff --check` | exit 0 | same tree |

Notes: the envelope command `pnpm --filter web exec tsc ...` prints "No projects matched the filters" (there is no workspace root `package.json`), so I ran `pnpm exec tsc` inside `web/` instead. `web/node_modules` was missing in this container, so I ran `pnpm install --frozen-lockfile` in `web/` first (no lockfile change).

## 7 Tests NOT run

- None of the gates the envelope lists were skipped. CI does not run the Playwright E2E tests, so the local run in heading 6 is the only evidence for them.

## 8 Deviations

- Scope: one line beyond option (a), `await plot.scrollIntoViewIfNeeded();`. The planner approved it after T39-B1. No assertion was weakened: the plain-wheel "does not zoom" check still runs before it.
- tsc ran as `pnpm exec tsc` in `web/` rather than `pnpm --filter web exec`. The reason is in heading 6.
- Two diagnostic runs used temporary edits to the spec, and both were reverted.

## 9 Blockers

None open. T39-B1 (option (a) alone did not fix the test) was resolved when the planner approved the `scrollIntoViewIfNeeded` line.

## 10 Follow-up

- CI does not run the Playwright E2E. A CI job for `screener.spec.ts` would have caught this when S7 merged.

## 11 Context cost

Read: `CLAUDE.md`, the envelope, `web/e2e/screener.spec.ts` (`exerciseZoom` and the test), S7 report heading 9, and one grep in the batch-2 plan for the E2E command. No other context docs opened.
