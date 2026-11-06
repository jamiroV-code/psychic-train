# /narrative Discovery tab: 8px horizontal overflow at 375px

Date: 2026-11-06. Status: backlog, not started.

## Finding
Two Playwright specs fail at a 375px viewport, with and without the BTC signals work (checked on the base):
- `e2e/narrative.spec.ts` "every state at 375px: no horizontal scroll, screenshots"
- `e2e/narrative.spec.ts` "coin and category charts at 375px (routed data)"

Both fail in `noHorizontalScroll`: `documentElement.scrollWidth` is 383 against `clientWidth` 375 (8px too wide) on the Discovery tab.

## What was ruled out
Listing every element whose right edge passes 375, with its nearest clipping ancestor, gave only:
- `A.app-rail__link` inside `NAV.app-rail` (`overflow-x: auto`, own scroll area)
- `TABLE.discovery-coins` inside `DIV.discovery-scroll` (`overflow-x: auto`, own scroll area)

No element outside a scroll container passes the viewport edge, so the 8px comes from something the right-edge check does not see (a box with negative margin, a transformed or positioned element, or a container min-width). Not isolated.

## Next step
Open `/narrative` Discovery at 375px in browser dev tools, find what sets the document's scrollable width to 383, then fix and keep the two specs as the regression.

## Not related
`daily-data-gap.spec.ts` also fails in a default E2E run, but only because it needs its own mode (`D18_E2E=1`, `E2E_CACHE_ROOT=%TEMP%/d18-e2e-*`, ports 18001/13100); it passes there.
