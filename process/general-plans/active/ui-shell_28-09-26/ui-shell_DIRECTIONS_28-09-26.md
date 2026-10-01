---
name: ui-shell-directions
description: "Three concrete UI directions for my_site plus the decisions needed to proceed. Companion to ui-shell_AUDIT_28-09-26.md. Proposal only — nothing chosen, nothing merged."
date: 28-09-26
metadata:
  node_type: report
  type: proposal
  feature: ui-shell
  branch: claude/ui-shell
  read_when: "choosing the visual direction for P3 — UI, before any conversion work starts"
---

# Three directions, and what I need decided

> **SUPERSEDED, 28 Sep 2026.** The user chose **Direction D — Dark Research Surface**
> (dark shell, light charts, Svelte 5 + LayerChart + Skeleton, owl mark). See
> `ui-shell_DIRECTION-D_28-09-26.md`. A, B and C below are kept as history; the
> palette, sequencing and testid findings in them still hold, but the plain-CSS
> recommendation is superseded by Tailwind 4, which Skeleton and LayerChart both require.

**Companion to:** `ui-shell_AUDIT_28-09-26.md`
**Rendered side-by-side:** `prototype/directions.html` — open it in a browser, or view the
published render at <https://claude.ai/artifact/9gPEQZnLuza4j8viumEHfr>
**Status:** proposal. No application code changed. `web/` is byte-identical to `origin/main`.

---

## The one-paragraph version

The app has no stylesheet, so dark mode, responsiveness and a type scale are currently
*impossible* rather than merely missing — inline `style={{}}` cannot express a media query.
Everything below therefore assumes the same foundation (a token stylesheet), and differs on what
is built on top. **A and B are competing looks; C is a layer that sits on either.** The palette
question is already settled by evidence rather than taste, and the build order is set by test risk,
not by preference.

---

## Direction A — Terminal

Dark by default, monospaced numerals, maximum density. Built for one person watching five
dashboards on a large monitor all day.

| | |
|---|---|
| **Nav** | Fixed left rail, 178px, always visible, with a per-route data-health dot. Collapses to a horizontal scrolling strip below 720px. |
| **Type** | Sans for prose, **mono with `tabular-nums` for every numeral**. Scale 10.5 / 11.5 / 12 / 13 / 15. |
| **Theme** | Dark-first; light is a toggle. |
| **Dense table** | ~22px rows, hairline rules, no zebra, sticky header, right-aligned monospace numerals. |
| **Insufficient data** | Em-dash with dotted underline + short inline reason. Severity on a 2px row rule: grey / amber / green. |
| **Charts** | Gridlines off, borders off, dark 8-slot palette. Already matches 5 of 7 charts. |
| **Cost** | Lowest chart churn. Highest information density. |
| **Risk** | The compressed uncertainty mark must be learned, and hover-only reasons don't exist on touch — which sits badly against the project's "never silently wrong" rule. The inline reason text is the mitigation, and it eats back some of the density gain. |

## Direction B — Research notebook

Light by default, generous spacing, every caveat spelled out. Built to be read, on a laptop or a
phone.

| | |
|---|---|
| **Nav** | Sticky top bar, 46px, horizontal tabs that scroll sideways rather than collapsing. |
| **Type** | One sans throughout, `tabular-nums` on numerals. Scale 12 / 13.5 / 14 / 16 / 21 / 27. |
| **Theme** | Light-first, with a *designed* dark counterpart from the same validated ramps. |
| **Dense table** | ~38px rows, zebra, 14px padding, 2px header rule. |
| **Insufficient data** | **Never abbreviated** — the full sentence from `format-unavailable-reason.ts` in an inline block with a left rule and a glyph. |
| **Charts** | Gridlines and axis border visible — today's `onchain` style promoted to all seven charts. |
| **Cost** | Least disruptive: `onchain` already looks like this. |
| **Risk** | Roughly half the rows per screen versus A. |

## Direction C — Confidence-first

Not a third skin. A layer of meaning that sits on **either A or B**: certainty stops being a
footnote and becomes a column, a gutter and a permanent strip.

| | |
|---|---|
| **The idea** | One three-level grammar — **mature / provisional / insufficient** — reused in the nav strip, a row gutter, a chip, a dashed chart line, a hollow endpoint. Learn it once, read it anywhere. |
| **Nav** | B's top bar plus a five-cell strip showing each dashboard's current data health, so you know which are worth opening. |
| **Dense table** | 4px certainty gutter, certainty chip, secondary sort by certainty, optional "hide provisional". |
| **Insufficient data** | Series that can't be computed are **named and explained below the chart**, never silently absent. |
| **Feasibility** | The backend already emits `insufficient` / `provisional` / `mature`, plus `stale` and `unavailable`. No new API field is needed for the gutters and chips. |
| **Risk** | Largest change, and the **top strip may need data the API does not yet aggregate**. It also overlaps **T10** in the master plan ("No cross-signal confidence view"), which is scheduled as its own task with its own SPEC. |

**Why C is on the table at all:** `all-context.md` states the project's purpose as turning separate
signals into a confidence level that drives position sizing, and says to *"favour showing how
strong a read is... over showing a single directional call."* Today that principle lives in the
backend and in copy, and is invisible in the layout. C is that principle made visual. It is also
the most likely of the three to be out of scope for a UI lane — which is why it is a question, not
a recommendation.

---

## Settled by evidence, not preference

Three things do not need a taste decision. They are the same under all three directions.

### 1. The palette question is already answered

`onchain`'s six chart colours are byte-identical to a reference palette that passes colour-blindness
and legibility gates. Measured with the `dataviz` validator:

| Palette | Verdict |
|---|---|
| `lib/onchain-view-model.ts` (6 slots) | **PASS** — all checks, light and dark |
| `MindshareView.tsx` (8 slots) | **FAIL ×3** — worst adjacent CVD ΔE **5.1**; `#a5d6ff` reads as grey |
| `RelativePerformanceChart.tsx` (8 slots) | **FAIL ×2** — `#8d6e63` reads as grey; two slots out of the lightness band |

Extending `onchain`'s six with the reference's slots 7–8 gives a validated eight in both modes:

```
light  #2a78d6 #eb6834 #1baf7a #eda100 #e87ba4 #008300 #4a3aa7 #e34948   → ALL PASS
dark   #3987e5 #d95926 #199e70 #c98500 #d55181 #008300 #9085e9 #e66767   → ALL PASS
```

**Recommendation:** promote it to a shared token file; retire the two that fail. ΔE 5.1 means a
protanopic reader cannot distinguish two of the series on the mindshare view, which is the view
whose entire job is comparing narratives against each other.

### 2. Plain CSS with custom properties, not Tailwind

**Recommendation:** `web/app/globals.css` with CSS custom properties.

- No new dependency (current runtime deps: `next`, `react`, `react-dom`, `lightweight-charts`).
- It **immediately styles the screener** — the 22 BEM class names already in the markup currently
  point at nothing, so the oldest route gets fixed with zero TSX changes and zero test risk.
- Tokens are the actual requirement; Tailwind would still need them underneath.
- Tailwind would rewrite markup across the 185 `data-testid`-bearing lines for no gain here.

Against it: Tailwind is faster for iterating on a look, and if the visual direction is going to
churn a lot, that matters. Worth overriding me if the plan is many rounds of visual revision.

### 3. Build order is set by test risk

185 source lines carry a `data-testid`; 165 assertions across 55 E2E tests select on them.
**Styling touches none of them. Restructuring touches all of them.** Two different risk profiles,
so not one step:

1. Tokens + `globals.css` + font stack — no markup change, no test risk.
2. One pilot route converted end to end — proves the system on real content.
3. The nav shell in `layout.tsx` — the first real testid risk, done alone so a failure is legible.
4. The remaining four routes.

---

## Questions I need answered

Ordered by how much they change the work. **1 and 2 block everything; the rest can be answered later.**

### Q1 — Which direction? *(blocking)*

A, B, or "B plus C's certainty layer", or a mix. Density versus readability is the real axis, and
it mostly follows from Q2.

### Q2 — What will you actually use it on, day to day? *(blocking)*

The master plan says deployed and always-on, "reachable from any device, not just the PC" — which
implies a phone matters. But a trader watching five dashboards implies a large monitor. These pull
in opposite directions and I don't want to guess.

- Mostly a big monitor → **A**.
- Phone and tablet matter → **B**.
- Both genuinely → **B**, which degrades to a phone gracefully; A does not without a second layout.

### Q3 — How should an unavailable number read?

The sharpest trade-off in the audit, because the project's own rule is at stake.

- **Compressed** (A): `—` plus a hover/inline reason. Dense, but hover does not exist on touch.
- **Full sentence** (B): the complete explanation inline, always. Costs vertical space on a screen
  that may have many such states at once.

My read: the repo goes to unusual lengths to never hide a reason — a 90-line file mapping ~30 codes
to careful sentences, with "an unknown code is shown verbatim, never hidden" written into it.
Compressing that into a hover mark on a touch device would undo it. But it is your call, and a
hybrid (dash in the cell, full reason in a panel below) is available.

### Q4 — Dark, light, or both?

And if both: follow the OS only, or also a manual toggle? A toggle is ~20 lines and one token
block; supporting both from the start is much cheaper than retrofitting.

### Q5 — Is C in scope for this lane, or is it T10?

The master plan has **T10 — "No cross-signal confidence view"** as a separate task needing its own
SPEC, and calls the cross-signal view the project's north star. C's per-table gutters and chips are
clearly UI and need no new API. C's *top strip* is arguably T10 in miniature. Options:

- Take all of C here.
- Take the gutters and chips only; leave the strip for T10.
- Leave all of C for T10 and ship A or B plain.

### Q6 — Naming

`app/page.tsx`'s `<h1>` is "Momentum Screener", and that string is also the browser-tab title on
all six routes because only the root layout exports metadata. What should the app be called, and
should each route get its own tab title? (The second half I would just do; the first needs you.)

### Q7 — Small ones I'll take silently unless you object

- **`web/tsconfig.tsbuildinfo` is committed** (master plan T20) and must be `git checkout`-ed after
  every `tsc`. It is in my lane. One `git rm --cached` + a `.gitignore` line.
- `role="dialog"` on two non-modal inline blocks with no focus management (audit §8) — either give
  them dialog behaviour or change the role.
- `board-error` in `ScreenerBoard.tsx:64` is missing the `role="alert"` its three siblings have.

---

## What I have not done, deliberately

- **No route converted.** No file under `web/` is modified; `git status` shows only this new
  `process/` folder.
- **No visual decision made.** The prototype is a standalone HTML mock-up, not a component.
- **Nothing looked at in a browser.** Every claim is from source or from the validator. The rendered
  prototype is my own mock-up, not a screenshot of the real app.

Baselines re-confirmed on this branch before and after: **193 unit tests / 24 files**, **55
Playwright tests**, `tsc --noEmit` exit 0.

> Note on the baseline: both the task brief and `MASTER-PLAN.md`'s ground-truth table record
> 181 / 22. That figure predates the PR #7 merge, which is now on main (`e9c33fe`) and brought new
> `MomentumView` / `MindshareView` tests with it. `MASTER-PLAN.md` anticipates this itself —
> *"PR #7 reports 708 / 193 on its branch — the figure to expect after it lands."* It landed. The
> master plan's ground-truth row is worth updating on its next revision.
