---
name: ui-shell-audit
description: "Audit of the my_site frontend as it stands before any redesign: every UI inconsistency worth fixing, with file references and measured evidence. Groundwork for P3 — UI."
date: 28-09-26
metadata:
  node_type: report
  type: audit
  feature: ui-shell
  branch: claude/ui-shell
  read_when: "before proposing or executing any UI change under web/"
---

# UI Audit — my_site frontend, pre-redesign

**Branch:** `claude/ui-shell` · **Base:** `ac1ebc1` (fast-forwarded to `origin/main`)
**Scope:** `web/` only. Nothing under `api/` was read for modification or touched.
**Status:** audit only. **No rendering code was changed.**

---

## Bottom line

The app is not under-designed. It is **undesigned** — there is no stylesheet of any
kind in the repository, so roughly half the UI renders in the browser's default
serif at default sizes, and the other half is held together by 113 inline
`style={{…}}` objects that no two features agree on.

Three findings matter more than the rest:

1. **All 22 `className` usages are dangling.** They are BEM names
   (`coin-panel__gain-chip`, `confidence-badge--${state}`) pointing at a stylesheet
   that was never written. The screener — the oldest and most-developed route —
   is therefore *entirely unstyled*.
2. **Two of the app's three chart palettes fail colour-blindness and legibility
   gates**, measured, not eyeballed. The third one passes because it already
   adopted a validated reference palette. That palette is confined to one of five
   features.
3. **The honest-uncertainty machinery is rigorous in its copy and arbitrary in its
   appearance.** ~30 reason codes are mapped to careful human sentences in one
   file; they then render through at least three unrelated visual idioms, so a
   reader cannot learn what "amber" means.

None of this requires touching a calculation or an API contract to fix.

---

## Verified ground truth (and two corrections to the brief)

Measured on this branch, this container.

| Check | Command | Result |
|---|---|---|
| Frontend unit | `pnpm --filter web test` | **193 passed, 24 files** |
| Typecheck | `pnpm --filter web exec tsc --noEmit` | exit 0 |
| Stylesheets in `web/` | `git ls-files web \| grep -c css` | **0** |
| Playwright E2E | `pnpm test:e2e` | **55 passed (2.4m)** |

The E2E run used
`PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, as
the pinned `@playwright/test` version and the installed browser disagree.
`screener.spec.ts:103` — the known intermittent flake tracked in
`process/general-plans/backlog/screener-weekly-bars-flake_NOTE_28-09-26.md` —
**passed** on this run (1.8s). One clean run is not proof the flake is gone; it is
only evidence that it did not fire here.

**This is the baseline the conversion phase must hold: 193 unit / 55 E2E / tsc 0.**

**Correction 1 — the test baseline is 193/24, not 181/22.** The brief and
`MASTER-PLAN.md`'s ground-truth table both record 181/22. That figure predates the
PR #7 (narrative-v2) merge. `MASTER-PLAN.md` itself anticipates this: *"PR #7
reports 708/193 on its branch — the figure to expect after it lands."* It landed
(`e9c33fe`). 193/24 is correct for this branch.

**Correction 2 — the `data-testid` surface is larger than 106.** 106 is the count
of *distinct static* values. The full restructuring surface is:

| Measure | Count |
|---|---|
| Distinct static `data-testid="…"` values | 106 |
| Distinct dynamic `` data-testid={`…`} `` patterns | 62 |
| Total source lines carrying a `data-testid` | **185** |
| `getByTestId(...)` calls across the 5 E2E specs | 165 |

The dynamic patterns (e.g. `` `coin-panel-${panel.symbol}` ``,
`` `onchain-panel-${chain.id}-limited-history` ``) are the ones a careless
refactor breaks silently, because grepping for the literal string finds nothing.

**Branch note:** `claude/ui-shell` was one commit behind `origin/main` and did not
contain `process/MASTER-PLAN.md` at all. I fast-forwarded (no merge commit, no
conflict) to read it. The lanes `claude/p1-pipeline` and `claude/p2-deploy` named
in the master plan **do not exist on the remote yet** — only this lane has been
pushed.

---

## 1. There is no stylesheet

```
$ git ls-files web | grep -E '\.(css|scss)$'
(no output)
```

No `globals.css`, no Tailwind, no CSS Modules, no PostCSS config, no CSS-in-JS
dependency. `web/package.json` has four runtime dependencies: `next`, `react`,
`react-dom`, `lightweight-charts`.

`web/app/layout.tsx` is 14 lines and imports nothing:

```tsx
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>          // ← no stylesheet, no font, no reset
    </html>
  );
}
```

Consequences that follow directly from this and are not separately fixable:

- **No font is ever specified.** `grep -rn 'fontFamily' web/` returns nothing. With
  no reset, the whole app renders in the UA default — a serif on most browsers —
  including every number in a nine-column statistics table.
- **No `tabular-nums` anywhere**, so digits in a column do not align.
- **Media queries are structurally impossible.** Inline `style={{}}` cannot express
  `@media`. `grep -rn '@media' web/` returns nothing, and it cannot return anything
  until styling moves out of inline objects. **The app is not responsive and cannot
  be made responsive without that move.**
- **Dark mode is structurally impossible** for the same reason
  (`prefers-color-scheme` never appears).

### 1a. The dangling BEM class names

All 22 `className` usages reference rules that do not exist:

| File | Classes |
|---|---|
| `web/components/screener/CoinPanel.tsx` | `coin-panel`, `__header`, `__symbol`, `__unavailable`, `__signals`, `__gain-row`, `__gain-chip`, `__gain-chip-label`, `__gain-chip-value` |
| `web/components/screener/ScreenerBoard.tsx` | `screener-board__toolbar`, `__benchmark`, `__grid` |
| `web/components/screener/SignalDetailPanel.tsx` | `signal-detail-panel`, `__content` |
| `web/components/screener/ConfidenceBadge.tsx` | `` confidence-badge confidence-badge--${state} `` |
| `web/components/screener/DrillDownView.tsx` | `drilldown-view__header` |
| `web/components/screener/RelativePerformanceChart.tsx` | `relative-performance-chart__note` |
| `web/components/narrative/CategoryHistoryPanel.tsx` | `narrative-notice`, `narrative-notice--stale` |
| `web/components/regime/ComponentPanel.tsx` | `regime-notice`, `regime-notice--stale` |

`CoinPanel.tsx:66` is the clearest illustration — the comment describes a design
that was never delivered:

```tsx
{/* Amendment 2 (AC-20): a compact 5-chip row, visually distinct from
    (not merged into) the momentum PASS/FAIL badge above … */}
<div data-testid="gain-readout-row" className="coin-panel__gain-row">
```

With no CSS, "a compact 5-chip row" renders as five bare `<span>`s of serif text
running together on one line. The design intent survives only in the comment and
the class name.

**This is also the opportunity:** the screener's markup is already
semantically classed. A stylesheet alone would style it, changing zero TSX and
breaking zero tests.

---

## 2. Colour: 37 hexes, 3 competing palettes, no tokens

37 distinct hex values appear across `web/`, with no token layer. Near-duplicates
are the tell — the app has **six greens** (`#008300`, `#3fb950`, `#1baf7a`,
`#199e70`, `#26a69a`, `#9ccc65`), **four reds** (`#f85149`, `#ef5350`, `#ff7b72`,
`#d55181`) and **eight ambers/oranges**.

`#8a8f98` ("muted text") is hardcoded 27 times.

### 2a. Three unrelated categorical palettes — two of them measurably broken

| Where | Slots | Validator verdict (light) |
|---|---|---|
| `web/lib/onchain-view-model.ts` `LIGHT_SLOTS`/`DARK_SLOTS` | 6 | **PASS** all checks, both modes |
| `web/components/narrative/MindshareView.tsx:9` `PALETTE` | 8 | **FAIL** ×3 |
| `web/components/screener/RelativePerformanceChart.tsx:19` `PALETTE` | 8 | **FAIL** ×2 |

Run with the `dataviz` skill's `validate_palette.js` (OKLab ΔE, CVD simulation):

**`MindshareView` — FAILED**
```
[FAIL] Lightness band    outside band: #a5d6ff (L 0.856)
[FAIL] Chroma floor      below floor (reads gray): #a5d6ff (0.077)
[FAIL] CVD separation    worst adjacent #d29922↔#3fb950 ΔE 5.1 (protan)
```
ΔE 5.1 is below the 6–8 warn band and far below the ≥8 target: for a
protanopic reader the amber and green series are **the same colour**. This is the
view that ranks narratives against each other by colour.

**`RelativePerformanceChart` — FAILED**
```
[FAIL] Lightness band    outside band: #ff9800 (0.77), #9ccc65 (0.789)
[FAIL] Chroma floor      below floor (reads gray): #8d6e63 (0.043)
```

**The proposed consolidation passes.** `onchain`'s six slots are *byte-identical*
to the `dataviz` reference palette's first six. Extending with that reference's
slots 7–8 gives a validated eight:

```
light  #2a78d6 #eb6834 #1baf7a #eda100 #e87ba4 #008300 #4a3aa7 #e34948  → ALL PASS
dark   #3987e5 #d95926 #199e70 #c98500 #d55181 #008300 #9085e9 #e66767  → ALL PASS
```

Light mode carries a contrast WARN on three slots, which obliges visible direct
labels or a table view — both of which this app already has everywhere.

So the recommendation is not a matter of taste: **promote the palette the repo
already validated, retire the two that fail.**

### 2b. Dark mode exists, as dead code

`web/lib/onchain-view-model.ts:28`:

```ts
export function chainColor(id: string, mode: "light" | "dark" = "light"): string
```

Every one of the four production call sites
(`ComparisonOverlay.tsx:92,168,196`, `onchain-view-model.ts:143`) omits `mode`.
`DARK_SLOTS` is reached **only** by `lib/__tests__/onchain-view-model.test.ts:22`.
There is no `prefers-color-scheme` and no `matchMedia` anywhere in `web/`. The
sibling `INK` token block (`onchain-view-model.ts:35-43`) has no dark counterpart
at all.

`onchain` is nonetheless the most mature feature by a distance: it is the only one
with named tokens, the only one that considered dark mode, and its palette comment
cites a `palette.md` §Chart chrome & ink. **That file does not exist in this
repo** — it is the `dataviz` skill's reference. A dangling doc reference, minor,
but it explains where the good work came from.

---

## 3. Type and spacing: no scale, in either

**Type.** Every size is set inline and unitless; headings inherit UA defaults.

| `fontSize` | Occurrences |
|---|---|
| `12` | 40 |
| `13` | 6 |
| `11` | 4 |
| `16` | 2 |
| `"0.9em"` / `"0.8em"` | 2 / 2 |

Four px sizes plus two `em` values, mixed in the same codebase. Everything
non-heading is 11–13px; there is no step between body text and an `<h1>` other
than whatever the UA picks.

**Spacing.** Padding, margin and gap values in use:
`0, 2, 4, 5, 6, 8, 10, 12, 14, 16` — essentially every even number plus 5. A
4px-based scale would be 4/8/12/16; the presence of 5, 6, 10 and 14 shows each
value was chosen independently at the call site. Compound strings are equally ad
hoc: `"6px 0"`, `"0 4px"`, `"8px 12px"`, `"8px 10px"`, `"4px 8px"`, `"0 5px"`,
`"8px 0 4px"`, `"4px 0 8px"`, `"16px 0 4px"`.

---

## 4. Layout: five routes, no shell

`web/app/layout.tsx` provides no navigation, no container, no max width, no
header. Every route is the same shape:

```tsx
<main>
  <h1>…</h1>
  <TheOneDashboardComponent />
</main>
```

- **No nav exists anywhere.** The only way between routes is the home page's bare
  list of `<Link>`s (`web/app/page.tsx`) — or the browser back button. For a
  five-area app intended as an everyday deployed tool, this is the single biggest
  usability gap.
- **`web/app/page.tsx`'s `<h1>` is "Momentum Screener"** — the name of one of the
  five areas, used as the name of the whole app.
- **Only the root layout exports `metadata`.** All six pages therefore share the
  browser-tab title *"Momentum Screener"* and the description *"Watchlist-driven
  momentum screener board"*. No route sets its own.
- **Page titles are inconsistent in register**: `Screener`, `Regime dashboard`,
  `Narrative dashboard`, `Pair screener`, `On-chain participant growth`,
  `Pair detail` — sentence case and title case mixed, two of them naming the
  product area and two naming the artefact.

---

## 5. Loading and error states

**Nine bespoke loading strings**, each its own element, with no shared component
and no shared element type — `<div>`, `<p>` and `<span>` are all used for the
same job:

| File | Element | Text |
|---|---|---|
| `onchain/OnchainDashboard.tsx:127` | `div` | Loading on-chain growth data… |
| `onchain/OnchainDashboard.tsx:137` | — | Loading… |
| `narrative/NarrativeDashboard.tsx:117` | `div` | Loading narrative history… |
| `narrative/NarrativeDashboard.tsx:186` | `div` | Loading momentum… |
| `narrative/NarrativeDashboard.tsx:194` | `div` | Loading mindshare… |
| `pairs/PairsTable.tsx:101` | `p` | Loading pairs… |
| `pairs/PairDetailView.tsx:142` | `p` | Loading pair… |
| `regime/RegimeDashboard.tsx:140` | `div` | Loading regime components… |
| `screener/LegTimelineBanner.tsx:50` | `span` | Loading leg timeline… |
| `screener/NarrativeStrip.tsx:52` | `span` | Loading narrative categories… |

No skeletons, no spinners, no layout reservation — so every panel reflows when
its data lands.

**Error states are inconsistent on accessibility.** Of five error renderings,
three carry `role="alert"` and two do not:

| File | `role="alert"`? |
|---|---|
| `onchain/OnchainDashboard.tsx:119` | ✅ |
| `onchain/OnchainDashboard.tsx:141` | ✅ |
| `pairs/ComputationStatusBanner.tsx:36` | ✅ |
| `screener/ScreenerBoard.tsx:64` (`board-error`) | ❌ |
| `regime` / `narrative` | no dedicated error branch found |

---

## 6. Uncertainty display — rigorous copy, arbitrary appearance

This is the part the brief correctly flags as a first-class design problem, and
it is where the gap between intent and delivery is widest.

**The copy layer is genuinely excellent.** `web/lib/format-unavailable-reason.ts`
is a single 90-line file holding three sibling functions and ~30 reason codes,
with an explicit, documented discipline:

> *"the same discipline `all-context.md`'s 'one source of numerical truth' applies
> to computed numbers, applied here to display copy instead."*
> *"an unknown code is shown verbatim, never hidden."*

**The visual layer has no grammar at all.** At least ten components render
uncertainty, and they invent their own treatment each time:

| Component | Treatment | Colour |
|---|---|---|
| `narrative/DataQualityCaveat.tsx` | `borderLeft: 3px solid`, pad `4px 8px`, margin `6px 0` | amber `#ff9800` |
| `onchain/LimitedHistoryFlag.tsx` | `borderLeft: 3px solid`, `paddingLeft: 6`, margin `2px 0` | grey `INK.baseline` |
| `narrative/RedistributionBadge.tsx` | outlined pill, `borderRadius: 3`, pad `0 4px` | amber `#ff9800` |
| `onchain/SourceMethodBadge.tsx` | plain text, no affordance | `INK.secondary` |
| `screener/DeadDataNotice.tsx` | **bare `<div>`**, `className` that styles nothing | — none — |

Three different idioms (amber left-rule, grey left-rule, amber outlined pill) and
one component with no styling whatsoever. Worse, **amber means two unrelated
things**: "this is a weak signal, weight it lower" in `DataQualityCaveat`, and
"this data is licensed for personal use only" in `RedistributionBadge`. A reader
cannot learn the system because there is no system.

`DeadDataNotice` is the one that matters most — it is the screener's only
unavailable-state renderer, and it emits an unstyled `<div>`, so
*"Not enough history at this timeframe"* is visually indistinguishable from a real
reading.

**The severity axis already exists in the data and is unused in the design.** The
backend distinguishes `insufficient` / `provisional` / `mature`, plus `stale`,
`presumed-dead`, `unavailable`, `results_unavailable`. Nothing maps those to a
consistent visual weight.

---

## 7. Chart theming: six `createChart` sites, two camps

Charts are canvas (`lightweight-charts` v5), so CSS will never reach them. Every
chart must be themed explicitly in JS. There are six creation sites and no shared
theme object:

| File | Text colour | Gridlines | Axis border |
|---|---|---|---|
| `onchain/ComparisonOverlay.tsx:77` | `INK.muted` | **horz visible** `INK.gridline` | `INK.baseline` |
| `onchain/ChainPanel.tsx:57` | `INK.muted` | **horz visible** `INK.gridline` | `INK.baseline` |
| `narrative/CategoryHistoryPanel.tsx:69` | `"#8a8f98"` | hidden | hidden |
| `pairs/SpreadChart.tsx:18` | `"#8a8f98"` | hidden | hidden |
| `regime/ComponentPanel.tsx:83` | `"#8a8f98"` | hidden | hidden |
| `screener/RelativePerformanceChart.tsx:65` | `"#8a8f98"` | *not set* | hidden |
| `chart/MiniChart.tsx:36` | `"#8a8f98"` | hidden | hidden |

The two `onchain` charts show horizontal gridlines and a time-axis border; the
other five show neither. These are two visually distinct chart languages in one
application.

Other drift: `RelativePerformanceChart` hardcodes `height: 320` while every other
chart accepts a `height` prop; `MiniChart` and `RelativePerformanceChart` each
re-implement their own `window.addEventListener("resize", …)` handler rather than
sharing one.

**Every chart sets `background: { color: "transparent" }`** — which is good news:
the chart surface already inherits whatever the page background becomes, so a dark
mode needs only the `textColor` / gridline / series tokens swapped, not a
per-chart background rewrite.

---

## 8. Accessibility

Better than expected in places, with three real defects.

**Good:** 21 `aria-label`s; `role="radiogroup"`/`role="radio"` with `aria-checked`
on the range and metric pickers; `aria-pressed` on toggles; `aria-expanded` on
disclosures; exactly one `<h1>` per page (7 across 7 pages).

**Defect 1 — `role="dialog"` with no dialog behaviour.** Used at
`regime/DrillDown.tsx:37` and `screener/DrillDownView.tsx:46`. Across all of
`web/`:

```
$ grep -rn 'onKeyDown|\.focus()|tabIndex|Escape' web/app web/components
(no output)
```

No focus management, no focus trap, no Escape-to-close, no focus restoration on
close. A screen reader announces a dialog the user cannot operate as one.
`DrillDown.tsx:31`'s own comment calls it an *"inline `role="dialog"` block"* —
inline and non-modal, which means `role="dialog"` is likely the wrong role
entirely rather than a missing-behaviour bug. Either give it dialog behaviour or
make it a `region`/disclosure.

**Defect 2 — inconsistent `role="alert"` on errors** (see §5).

**Defect 3 — colour-only encoding in `MomentumView.tsx:50`:**

```tsx
background: c >= 0 ? "#3fb950" : "#f85149",
```

Direction of change is carried by a red/green bar. The adjacent
`momentum-change-…` span does print the signed number, so it is not strictly
colour-alone — but the bar is the dominant visual and its two colours are a
red/green pair, the worst case for the most common CVD. The sign is available;
shape or position should carry it too.

Not checked: real contrast ratios of rendered text (no stylesheet to measure),
keyboard tab order in a browser, and screen-reader output. Those need the running
app.

---

## 9. The restructuring surface

Any shell/markup change has to move through 185 `data-testid`-bearing lines and
165 `getByTestId` assertions in 55 E2E tests:

| Spec | Tests |
|---|---|
| `e2e/narrative.spec.ts` | 18 |
| `e2e/onchain.spec.ts` | 16 |
| `e2e/pairs.spec.ts` | 9 |
| `e2e/regime.spec.ts` | 6 |
| `e2e/screener.spec.ts` | 6 |

**The mitigating fact:** `data-testid` lives on elements, not on classes or
styles. A styling-only change — adding `globals.css`, adding tokens, restyling via
the *existing* BEM class names — touches none of them. The risk is concentrated
entirely in **restructuring** work: adding a nav wrapper, changing an element's
tag, or re-nesting a panel.

This argues for a specific sequencing, independent of which visual direction is
chosen: **land the stylesheet and tokens first (zero testid risk), restructure
second (all the testid risk).**

---

## Verification gaps — what I could not confirm

Reported rather than asserted:

1. **Nothing was checked in a real browser.** No screenshots, no rendered contrast
   measurements, no keyboard tab-order walkthrough, no screen-reader pass. Every
   visual claim above is derived from source, not from pixels. The E2E suite
   exercises behaviour and test-ids, not appearance, so it does not close this gap.
2. **The flake was not re-run under repetition.** `screener.spec.ts:103` passed
   once. I did not run `--repeat-each` to characterise it, and I am not treating
   one green run as evidence it is fixed.
3. **The `api/` side is unexamined by choice.** Per the lane constraint I did not
   read `api/` for modification. Response *shapes* were taken from
   `web/lib/types/*.ts`, which is the frontend's own view of the contract — if the
   backend's real shapes differ, the audit inherits that error.
4. **Contrast ratios of body text are unmeasurable today** — there is no stylesheet
   and no font stack, so there is no rendered foreground/background pair to test.
   This becomes checkable only once tokens exist.
5. **The two sibling lanes are unverified.** `claude/p1-pipeline` and
   `claude/p2-deploy` do not exist on the remote, so I could not confirm the
   blast-radius disjointness the master plan asserts. On the evidence available,
   this lane has touched nothing outside `process/` and reads nothing from `api/`.

---

## What follows from this

The audit points at one sequencing conclusion and deliberately stops short of a
design decision:

1. **A stylesheet with tokens is the prerequisite for everything else** — dark
   mode, responsiveness, a type scale and a severity grammar are all currently
   *impossible*, not merely absent, because inline styles cannot express them.
2. **The screener can be fixed with CSS alone**, changing no TSX, because its BEM
   names already exist.
3. **The palette question is already answered** by the repo's own validated
   `onchain` slots.
4. **Uncertainty needs a severity grammar**, and the data to drive one already
   exists (`insufficient`/`provisional`/`mature`, `stale`, `unavailable`).
5. **Nav is the biggest usability gap** and the highest-testid-risk change.

**The direction has since been chosen:** *Direction D — Dark Research Surface*
(dark shell, light charts, Svelte 5 + LayerChart + Skeleton, owl mark). See
`ui-shell_DIRECTION-D_28-09-26.md` and `prototype/direction-d.html`. The A/B/C
exploration in `ui-shell_DIRECTIONS_28-09-26.md` is kept as history.

Two conclusions above are revised by that choice: point 1's styling mechanism is
**Tailwind 4**, not plain CSS, because Skeleton 5 and LayerChart both require it;
and point 2's "fix the screener with CSS alone" holds only while the app stays
React. Everything else — the palette evidence, the uncertainty grammar, the
sequencing, the testid surface — is unaffected.
