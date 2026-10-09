# T39 Worker Report: fix the S6 zoom E2E after S7

## 1 Task ID

T39 (RT1, test-only fix), branch `claude/t39-fix-zoom-e2e`, base `main` at `38fe860`.

## 2 Outcome

**needs_input.** The sanctioned option (a) edit is applied but does not make the test green. A second, test-only line would fix it, and it is outside the approved scope. Do not merge until the planner decides.

## 3 Summary

- Reproduced the failure on the untouched base (`38fe860`). The test fails in `exerciseZoom` on the BTC coin-box plot: after Ctrl + wheel, `data-zoomed` is `"false"`.
- Applied option (a): `exerciseZoom` re-reads `plot.boundingBox()` after the plain-wheel step and moves to the recomputed point before the Ctrl + wheel. The test still fails with the same assertion.
- Diagnostic (temporary logging, reverted): `window.scrollY` stays `0`, so a scroll container other than the window scrolls. The plain `wheel(0, -400)` moves the plot down 63 px (box y 599.7 -> 662.7, height 120). The recomputed centre y is about 722.7, below the 720 px viewport, and `document.elementFromPoint` there returns `null`. The re-read coordinates are correct but off-screen, so the Ctrl + wheel never reaches the plot.
- Second diagnostic (not committed): adding `await plot.scrollIntoViewIfNeeded();` just before the re-read makes the test pass (1 passed, 26.8 s).

## 4 Files changed

- `web/e2e/screener.spec.ts`: the option (a) edit in `exerciseZoom` (+4/-2, comment included).
- this report.

## 5 Commits

- `fix(e2e): re-read plot box before ctrl-wheel in exerciseZoom (T39)`: the test edit plus this report. See the PR for the SHA.

## 6 Tests run

| Gate | Command | Result | Tree / time (UTC) |
|---|---|---|---|
| Red repro | `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e screener.spec.ts` | 1 failed (`ctrl-wheel zooms...`, `toHaveAttribute("data-zoomed","true")` at line 299), 9 passed | untouched `38fe860`, 2026-10-09T07:16:32Z |
| After fix (a) | same command with `screener.spec.ts contrast.spec.ts` | **RED**: 1 failed (same test, same assertion), 16 passed | `38fe860` + option (a) edit, 2026-10-09T07:17:55Z |
| Diagnostic: (a) + `scrollIntoViewIfNeeded` | same command, `screener.spec.ts -g "ctrl-wheel"` | 1 passed | uncommitted, reverted after the run |
| Typecheck | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 | `38fe860` + option (a), 2026-10-09T07:21Z |
| Whitespace | `git diff --check` | exit 0 | same |

Notes: the envelope command `pnpm --filter web exec tsc ...` prints "No projects matched the filters" (there is no workspace root `package.json`), so I ran `pnpm exec tsc` inside `web/` instead. `web/node_modules` was missing in this container, so I ran `pnpm install --frozen-lockfile` in `web/` first (no lockfile change).

## 7 Tests NOT run

- The whole screener + contrast suite was not re-run with the `scrollIntoViewIfNeeded` variant. It is not committed, so that run belongs to the follow-up once the planner approves it.

## 8 Deviations

- tsc ran as `pnpm exec tsc` in `web/` rather than `pnpm --filter web exec`. The reason is in heading 6.
- Two diagnostic runs used temporary edits to the spec. Both were reverted; the committed diff is option (a) only.

## 9 Blockers

**T39-B1: option (a) alone does not fix the test (needs_input).**

- **Cause:** the plain wheel scrolls an inner container that pushes the plot's centre below the viewport. Re-reading the box gives off-screen coordinates, so Playwright's wheel event goes to no element.
- **Proposed fix (test-only, inside `exerciseZoom`):** add one line before the re-read:

  ```ts
  await plot.scrollIntoViewIfNeeded();
  const zb = (await plot.boundingBox())!;
  ```

  This was verified locally to pass the test. It does not weaken any assertion: the plain-wheel "does not zoom" check still runs before it.
- **Options for the planner:** (1) approve the extra line (recommended); (2) choose another approach, for example aim the pointer at a point inside the visible part of the plot.

## 10 Follow-up

- When (1) is approved: add the line, re-run `screener.spec.ts contrast.spec.ts` in full and tsc, then update this report and the PR.

## 11 Context cost

Read: `CLAUDE.md`, the envelope, `web/e2e/screener.spec.ts` (`exerciseZoom` and the test), S7 report heading 9, and one grep in the batch-2 plan for the E2E command. No other context docs opened.
