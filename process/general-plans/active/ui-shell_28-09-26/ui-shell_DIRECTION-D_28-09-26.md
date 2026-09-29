---
name: ui-shell-direction-d
description: "Direction D — Dark Research Surface + Skeleton + Svelte/LayerChart. The user's chosen UI direction, the verified stack facts behind it, the migration boundary options, and the open questions. Supersedes the A/B/C exploration."
date: 28-09-26
metadata:
  node_type: report
  type: proposal
  feature: ui-shell
  branch: claude/ui-shell
  read_when: "before any UI or frontend-stack work under web/"
---

# Direction D — Dark Research Surface

**Chosen by the user, 28 Sep 2026.** Supersedes the A/B/C exploration in
`ui-shell_DIRECTIONS_28-09-26.md`, which is kept as history.

**Rendered:** `prototype/direction-d.html` — <https://claude.ai/artifact/83wxKuq8n6agEvbM6QxNZ5>
**Evidence base:** `ui-shell_AUDIT_28-09-26.md`
**Status:** proposal and groundwork. **No application code changed.** `web/` is byte-identical to
`origin/main`; baseline re-confirmed at 193 unit / 55 E2E / `tsc` 0.

The user's own direction text says it *"does not by itself authorize application-code changes."*
I have taken that literally — nothing under `web/` is touched.

---

## The direction, as given

- **Goal:** find edge in market data. Research speed, signal clarity, data honesty and interaction
  smoothness over decorative polish.
- **Feel:** dark, clean, slightly futuristic, extremely smooth — from precision, typography,
  spacing, depth and interaction quality, **not** neon, glow, noisy gradients or cyberpunk.
- **Shell dark, charts light.** Explicit: *"the shell is dark, but charts should stay light or
  near-neutral and highly legible. Do not force dark-on-dark charts."*
- **Stack:** Svelte 5, LayerChart, Skeleton. No blind rewrite — prove the path on **one
  representative real chart** first, preserving data contracts and test surfaces, then pick the
  smallest maintainable migration boundary.
- **Motion:** smoothness is the highest priority, animation is secondary. Short and calm, no
  perpetual motion, no layout shift, respect `prefers-reduced-motion`.
- **Priority order:** edge + data integrity → smoothness + clarity → visual polish → animation.
- **Symbol:** an owl.

---

## What I verified, and what changed as a result

The direction says to use current documentation and verify installed versions before coding.
`layerchart.com` and `skeleton.dev` are both blocked by this container's egress proxy, so I
verified against the **npm registry** instead, which is authoritative for versions and peer
requirements.

| Package | Latest | Peer requirements |
|---|---|---|
| `svelte` | **5.57.1** (18 Sep 2026) | — |
| `layerchart` | **2.5.0** (09 Sep 2026) | `svelte ^5.0.0` |
| `@skeletonlabs/skeleton` | **5.0.1** | **`tailwindcss ^4.0.0`** |
| `@skeletonlabs/skeleton-svelte` | **5.0.1** | `svelte ^5.40.0` |
| `@skeletonlabs/skeleton-react` | **5.0.1** | `react ^18 \|\| ^19` |
| `@sveltejs/kit` | **2.70.3** | — |

Four findings that change the shape of the work:

### 1. Skeleton ships a first-party **React** package

`@skeletonlabs/skeleton-react` is at the same version and the same publish date as the Svelte one.
**Skeleton does not require leaving Next.** The shell — navigation, drawers, buttons, tabs,
dialogs, badges — can adopt Skeleton and the dark research theme while the app stays React. That
decouples "the look" from "the framework move", which the direction's own no-blind-rewrite rule is
trying to achieve.

### 2. LayerChart **does** require Svelte

Peer `svelte ^5.0.0`, built on `@layerstack/svelte-*`. There is no React build. Charts are the one
part that genuinely must move — exactly where the direction already points the pilot.

### 3. Tailwind 4 arrives either way

Skeleton 5 peers on `tailwindcss ^4.0.0`, and LayerChart depends on `@layerstack/tailwind`. So the
styling mechanism is settled by the stack choice. **My earlier recommendation of plain CSS with
custom properties is superseded** — noting it so the audit's §"What follows from this" is not read
as still current.

### 4. LayerChart can render to **canvas**, not only SVG

Each component ships `.svg.svelte` and `.canvas.svelte` variants, and the package contains its own
`bench/svg-vs-canvas` benchmark. This matters because the regime view syncs seven panels over
~2 000 points, which today is canvas (`lightweight-charts`). Canvas being available makes that a
configuration choice rather than a blocker — **but it is the pilot's job to prove it, not mine to
assert it.** The version note in the direction text ("LayerChart 2.0.x") is slightly stale; 2.5.0
is current and the "built on Svelte 5" claim holds.

---

## The tension I have to flag: the baseline cannot stay green as written

The direction says *"the redesign should keep that baseline green"* against 193 unit / 55 E2E.
Measured on this branch, that is only partly achievable:

| Test group | Count | Survives a Svelte migration? |
|---|---|---|
| React component tests (`@testing-library/react`, 17 files) | **125** | **No — must be rewritten** |
| Pure TypeScript lib tests (7 files) | **68** | Yes, untouched |
| Playwright E2E (5 specs) | **55** | Yes — browser-driven via `data-testid`, framework-agnostic |

**65% of the unit suite is React-bound.** Those 125 tests cannot be "kept green" through a
framework change; they can only be ported. This is not an argument against the direction — it is
the cost of it, and it should be a deliberate decision rather than a surprise in week three.

The useful consequence: **the 55 E2E tests are the real safety net for this migration.** They cover
all five routes, they select on `data-testid`, and they do not care which framework renders the
DOM. Preserving the 185 testid-bearing lines therefore matters more than preserving any component
test — and that is achievable, because testids are markup, not framework.

---

## Two migration boundaries

Both honour "no blind rewrite". They differ in how much moves and when.

### Boundary 1 — Islands *(smaller, reversible)*

Keep Next/React. Adopt Tailwind 4 + `@skeletonlabs/skeleton-react` for the shell and tokens.
Introduce Svelte only where LayerChart lives, mounted as islands inside React panels.

- **Pro:** the dark shell, tokens, owl and nav ship immediately with zero framework risk. The 125
  React tests keep running. One route's chart proves LayerChart in isolation. Reversible at any
  point.
- **Con:** two frameworks in one bundle, permanently or semi-permanently. Island boundaries need
  care around the shared chart-sync behaviour (`lib/regime-chart-sync.ts`) that today couples seven
  panels.

### Boundary 2 — SvelteKit *(larger, cleaner end state)*

Stand up SvelteKit alongside, port route by route, retire Next when the last route lands.

- **Pro:** one framework, Skeleton and LayerChart in their native home, no island seams, and the
  chart-sync problem is solved once in Svelte rather than bridged.
- **Con:** all 125 React tests rewritten; two apps in the repo during the transition; the E2E
  suite's two-server harness (`playwright.config.ts` boots uvicorn + `pnpm dev`) needs rework.
  Materially more work before anything is visible.

**My recommendation:** start with Boundary 1's *first step only* — tokens, dark shell, owl, nav in
React + Skeleton — because it delivers the visible direction now at near-zero risk, and it is
**not wasted** under either boundary: the tokens, the theme, the owl, the uncertainty grammar and
the testid discipline all port. Run the LayerChart pilot in parallel on one chart. Choose between
Boundary 1 and 2 **after** the pilot reports, with real evidence about island seams and canvas
performance instead of a guess.

That is a recommendation, not a decision — see Q1.

---

## The owl

`owl.png` is on `main` (`528c564`) and I pulled it from there. Four findings:

**1. It is a JPEG with a `.png` extension.** `file` reports *JPEG image data, Exif standard,
baseline, 1024x1024*. That is exactly why it would not decode when sent inline — the two attempts
failed with "image format png not supported". Renaming it to `.jpg`, or re-encoding it as a true
PNG, fixes that. Worth correcting in the repo either way.

**2. The brand is two colours on white**, sampled from flat interior patches to avoid JPEG ringing:

| Role | Hex | Measured |
|---|---|---|
| Body, tufts, pupils, beak | **`#32425a`** | rgb(50, 66, 90) — deep desaturated navy |
| Wings | **`#657b5b`** | rgb(101, 123, 91) — sage / olive green |
| Ground | `#ffffff` | pure white, baked in — **no alpha** |

**3. The navy cannot go on the dark shell.** Measured contrast:

| Colour | On shell `#0c0f14` | On white |
|---|---|---|
| Brand navy `#32425a` | **1.89:1** — fails (3:1 needed for a graphic) | 10.18:1 |
| Brand sage `#657b5b` | 4.15:1 — passes | 4.63:1 |
| Lifted sage `#8aa37d` | 6.96:1 | 2.76:1 |

So the mark needs **two colourways**: as-supplied on light surfaces, and on the dark shell the body
inverts to light ink `#e9ecf1` with the wings lifted to `#8aa37d`. Same drawing, one-line change.

**4. The raster cannot be used as-is.** No alpha means it shows as a white tile on the dark shell,
and at 16px the eyes and beak turn to mush. I redrew it as SVG on a 64-grid, geometry taken from
measurements of the original. **The redraw is an approximation** — my body is slightly slimmer and
the wings narrower than yours, and the lids are less heavy. It is faithful enough to judge the
direction by and worth refining once you have looked at it (Q4). A transparent PNG or the original
vector, if one exists, would let me match it exactly.

**One deliberate restraint:** sage green is close in meaning to the **mature / healthy** green in
the uncertainty grammar. I have kept sage **in the mark only** so green keeps meaning one thing in
the interface. Overridable — Q4.

**The accent** is the brand navy lifted to `#6b9bd4` (6.64:1 on the shell): the owl's own hue, with
only the lightness moved, so no new colour enters a codebase that already has 37. The shell
neutrals carry a trace of that navy hue rather than being generic cool greys.

---

## What the prototype settles

- **Dark shell, light analytical panels** — the direction's central instruction, rendered.
- **Four surface steps** (page / panel / raised / hover) so depth reads as hierarchy.
- **The owl in both colourways**, at 16 / 28 / 48 / 132 px, plus a one-colour variant.
- **Chart series** use the **light** validated slots, because the plot surface is light. The four
  used — blue `#2a78d6`, orange `#eb6834`, aqua `#1baf7a`, violet `#4a3aa7` — pass every gate
  including the strict all-pairs run. The obvious fourth pick, yellow `#eda100`, fails against
  orange at ΔE 13.7 where 15 is the floor, so **violet takes slot four on any four-series chart**.
- **One uncertainty grammar** on both surfaces: severity as a left rail never a fill, always paired
  with a glyph (○ ◐ ●), amber meaning only "degraded", insufficient series named beneath the chart
  rather than drawn, provisional series dashed with an open endpoint.
- **Motion** at 120–180ms ease-out on hover/selection/panel change, with
  `prefers-reduced-motion` implemented in the page itself.

---

## Open questions

### Q1 — Which migration boundary? *(blocking the pilot's shape)*
Islands, SvelteKit, or "first step now, decide after the pilot" as recommended above.

### Q2 — Do you accept that 125 React tests get rewritten, not kept? *(blocking)*
It is unavoidable under any Svelte move. I want it acknowledged rather than discovered later.

### Q3 — Which chart is the pilot?
My recommendation: **`/pairs` → `SpreadChart.tsx`.** It is the simplest chart in the app (one
series, one `createChart`, no cross-panel sync), it sits on a route with 9 E2E tests to catch
regressions, and `/pairs` shares no code with the other four surfaces — so a failed pilot is
thrown away cleanly. The opposite choice, `/regime`'s seven synced panels, is the one that proves
the hardest case (canvas performance, sync) but risks the most.

### Q4 — Is the redraw close enough, and may sage stay out of the UI?
Your owl is now in hand (see §The owl below). Two things need your call: whether my vector redraw
is faithful enough or should be refined, and whether you accept keeping **sage green in the mark
only** rather than letting it into the interface — because the UI already uses green to mean
"mature / healthy" and a second green would blur that.

### Q5 — Name and wordmark?
`app/page.tsx`'s `<h1>` is still "Momentum Screener", and that string is the browser-tab title on
all six routes. The prototype uses `my_site` as a placeholder. What should it be called?

### Q6 — Small ones I will take silently unless you object
- `web/tsconfig.tsbuildinfo` is committed (master plan T20) and must be `git checkout`-ed after
  every `tsc`. One `git rm --cached` plus a `.gitignore` line.
- `role="dialog"` on two non-modal inline blocks with no focus management (audit §8).
- `board-error` in `ScreenerBoard.tsx:64` missing the `role="alert"` its three siblings have.

---

## Verification gaps

1. **`layerchart.com` and `skeleton.dev` are blocked by this container's egress proxy.** All stack
   facts above come from the npm registry — versions, peer dependencies and package contents are
   solid, but I have **not** read the current prose docs or the Skeleton StackBlitz demo. Anything
   about component APIs or recommended patterns is unverified.
2. **Nothing installed, nothing run.** No Svelte, LayerChart or Skeleton package was installed in
   this container; no pilot was built. The canvas-versus-SVG performance question is open.
3. **Nothing checked in a real browser.** The prototype is a hand-built mock-up, not a screenshot
   of the app, and not a LayerChart render.
4. **The owl redraw is eyeballed from measurements, not traced.** I had no vector source and no
   tracing tool in this container, so the SVG paths are hand-fitted to coordinates read off the
   raster. Colours are measured and exact; the curves are not.
5. The sibling lanes `claude/p1-pipeline` and `claude/p2-deploy` still do not exist on the remote,
   so the master plan's blast-radius disjointness remains unconfirmed. This lane has touched only
   `process/`.

---

## ADR-1 — The migration boundary: islands, not SvelteKit (decided 29-09-26)

**Decision: keep React and mount charts as Svelte/LayerChart islands. Do not migrate to
SvelteKit.** Two routes (`/pairs`, `/regime`) are already shipped this way; the remaining two
chart routes follow the same pattern.

This supersedes the open question left in "What I need decided". It also **corrects an argument
made in PR #9 after the `/regime` conversion**, where the island bundle's size was offered as a
point in favour of SvelteKit. Measured, it is not one — see finding 4.

### What was measured

Production build, `next start`, real Chromium, bytes read off the wire:

| Measurement | Value |
|---|---|
| Island files actually fetched by `/regime` | **3** — not the 17 chunks on disk |
| Transferred | **732 kB raw / 178 kB gzipped**, one entry chunk + 12.5 kB CSS + a 164-byte entry |
| On disk, whole island tree | 1012 kB raw / 239 kB gzipped (the rest is never fetched) |
| `/pairs/[a]/[b]` First Load JS | 171 kB → **113 kB** |
| `/regime` First Load JS | 164 kB → **106 kB** |

### Findings

1. **Only charts have to leave React.** `@skeletonlabs/skeleton-react` 5.0.1 exists at the same
   version and publish date as the Svelte package, so the shell, theme and tokens stay on React —
   already proven, since the nav, owl mark, token layer and styled screener all shipped on React.
   LayerChart is the single package with no React build.
2. **Code splitting already works.** The browser fetches one chunk, not the seventeen on disk, and
   it is shared by every chart route and cached after the first.
3. **Each converted route gets lighter** by ~58 kB of Next JS. Against a one-off shared 178 kB,
   break-even is about two routes; at four it is a clear win, and `lightweight-charts` leaves the
   dependency tree entirely.
4. **The 178 kB is LayerChart's cost, not the island boundary's.** `layerchart@2.5.0` exports only
   its barrel — `layerchart/components/Chart.svelte` and every deep variant resolve to
   `ERR_PACKAGE_PATH_NOT_EXPORTED` — so there is no narrower import to tree-shake toward. **A
   SvelteKit app would pay exactly the same bytes.** Bundle size therefore does not favour
   SvelteKit; it is neutral between the two.
5. **SvelteKit would rewrite 125 `@testing-library/react` tests for no user-visible benefit.** The
   55 E2E tests are framework-agnostic and remain the real safety net either way.

With bundle size neutral (4) and the shell able to stay on React (1), the only genuine difference
left is developer experience against a large, risky rewrite. That is not a trade worth making.

### What this costs, honestly

- **No HMR for island code.** Editing a `.svelte` file needs `pnpm build:islands` (~5 s) and a
  reload. Mitigated by `pnpm build:islands:watch`, which rebuilds on save; the browser still needs
  a manual reload.
- **Two chart systems coexist** until `/narrative` and `/onchain` are converted.
  `lib/regime-chart-sync.ts` and `toSegmentedSeriesData` must stay until then.
- **jsdom does not mount islands**, so chart behaviour is asserted either on the pure mapping
  functions (`lib/chart-segments.ts`) or in Playwright. This is why `/regime`'s
  lightweight-charts mock was deleted rather than ported: a mock-shaped test proves the mock.

### Revisit if

LayerChart ships per-component exports (finding 4 disappears), or a future route needs SvelteKit
routing/SSR rather than just a chart.

### Consequence

Five chart components remain on `lightweight-charts`, across three routes — more than the two
routes this section first claimed, corrected here after counting:

| Component | Route | Lines |
|---|---|---|
| `components/narrative/CategoryHistoryPanel.tsx` | `/narrative` | 267 |
| `components/onchain/ComparisonOverlay.tsx` | `/onchain` | 235 |
| `components/onchain/ChainPanel.tsx` | `/onchain` | 204 |
| `components/screener/RelativePerformanceChart.tsx` | `/screener` | 149 |
| `components/chart/MiniChart.tsx` | `/screener` (drill-down) | 75 |

Only once all five are converted can `lightweight-charts`, `lib/regime-chart-sync.ts`,
`lib/regime-line-segments.ts` and the two test mocks be removed. Until then the two chart systems
coexist, which is expected rather than debt to apologise for.
