---
name: plan:deployability
description: "P2 — make my_site reachable from any device, not just the author's PC; SPEC only, no infra provisioned"
date: 28-09-26
feature: none
---

# Deployability (P2) — SPEC

**TL;DR:** The app currently only runs on one PC. This SPEC covers what has to change so it can run somewhere always-on and be reached from a phone or laptop, privately. Recommendation: **Fly.io** as the always-on host (or a home box + Tailscale if the user already owns a spare machine), with **Tailscale** as the access gate — both roughly **$0–10/month**, and neither requires writing any login code. Nothing gets provisioned, bought, or made publicly reachable until the user picks a target and says go. This SPEC also hands P1 a specific, unresolved problem it must solve: today, a fresh deploy would serve stale or empty data on 3 of the app's 4 screens.

---

## Summary

Right now, my_site only works if the author's own computer is turned on, running the app, and they're on the same network. To use it from a phone, or while away from that PC, the app needs to live somewhere that's always on, and the author needs a private way to reach it that doesn't require the app itself to grow a username/password system. This document lays out what has to be decided (where it runs, how it's kept private) and what has to change in the code to make either choice possible — without yet making any of those decisions or spending any money. It also flags a real gap: several of the app's data caches currently only exist on the author's PC and are never version-controlled, so a fresh copy of the app running somewhere else would show broken or empty screens until that gap is closed — that closing work belongs to a different, already-in-progress lane (P1), and this document defines exactly what P1 needs to deliver.

---

## User Stories / Jobs To Be Done

- **As the app's sole user, I want to open it on my phone from anywhere**, so that I'm not tied to being at my desktop PC to check the market screens.
- **As the app's sole user, I want my data and screens to look the same regardless of which device I use**, so that I trust the numbers whether I'm on my laptop or my phone.
- **As the app's sole user, I want the app to stay private** — reachable only by me, not indexed or open to the public internet — so that I don't have to worry about someone else poking at my trading tool or triggering costs on my behalf.
- **As the app's sole user, I want to know roughly what this will cost me every month before I commit**, so that a personal research tool doesn't turn into an open-ended expense.
- **As the app's sole user, I want a clear recommendation, not just a list of options**, so I can make this decision in five minutes instead of researching hosting providers myself.
- **As the app's sole user, I want to be told plainly what I have to decide and what happens only after I decide it**, so that nothing gets bought, deployed, or exposed to the internet without my explicit go-ahead.

---

## What The User Wants (Behavioral Outcomes)

- The app is reachable at a stable address, at any time, without the author's PC being on.
- The four existing screens (screener, pairs, regime, narrative) look and behave the same whether opened from the PC or from a phone.
- Only the author can open the app — there is no public sign-up page, and a stranger finding the address cannot see the data or use the watchlist.
- If a screen's data is temporarily stale or unavailable (which already happens today, honestly, when a data source has nothing to offer), that same honest behavior continues after deployment — nothing is silently blank or wrong.
- The author is shown, in plain dollar terms, what continuing to run this will cost per month, before anything is created.
- Nothing about where the app runs, or who can reach it, changes until the author explicitly approves a specific choice.

---

## Flow / State Diagram

```
[Author reads this SPEC]
        |
        v
  {Approves an approach?}
        |
       no --> [Stop. No infra created. Revisit later.]
        |
       yes
        v
[Author picks: WHERE it runs] --> [Author picks: HOW it stays private]
        |                                   |
        v                                   v
  (e.g. Fly.io / home box)          (e.g. Tailscale / Cloudflare Access)
        |___________________________________|
                        |
                        v
        [Next phase: INNOVATE/PLAN turns this
         into an execution plan — NOT this SPEC]
                        |
                        v
        [P1 confirms nightly-refresh + one-time
         backfill can run on the chosen target]
                        |
                        v
        [Deploy happens — still gated on explicit
         "go ahead and provision this" from the author]


Day-2 request flow, once deployed (illustrative, not yet built):

[Phone / laptop browser]
        |
        v
{On the private network / passed the gate?}
   no --> [Connection refused / login prompt — never reaches the app]
   yes
        v
[Reaches my_site frontend + API]
        |
        v
{Is the screen's data fresh?}
   no --> [Screen shows an honest "stale" / "unavailable" state, same as today]
   yes --> [Screen shows current data, same as on the PC]
```

---

## Acceptance Criteria (Testable Outcomes)

- AC1: The app's docstring/config no longer claims it only binds to `127.0.0.1` once a non-local run command is documented — the stated security posture matches what actually happens at runtime.
  proven by: config-shape unit test on the CORS-origin parser (pattern: `test_snapshot_workflow_schedules.py`'s config-shape-pinning approach), confirming the documented default is `http://localhost:3000` and an override via `SCREENER_CORS_ORIGINS` is honored.
  strategy: Fully-Automated

- AC2: When the app is reached from a second, non-default address (e.g. a phone on a different network reaching a deployed instance), the API accepts cross-origin requests from that address once it is explicitly allow-listed, and rejects addresses that are not.
  proven by: pytest test of `CORSMiddleware` origin parsing against `SCREENER_CORS_ORIGINS` (new test, same file/pattern as AC1).
  strategy: Fully-Automated

- AC3: A newly-deployed copy of the app, before any manual data refresh has run on it, tells the truth about which of its 4 screens have data and which don't — no screen silently shows blank or wrong numbers.
  proven by: existing `/pairs` "results_unavailable / stale" behavior (`pairs_response.py`) as the reference pattern, extended to document the same honest-degrade expectation for `/screener` and `/regime` on an empty gitignored cache. Real verification of "does a truly fresh checkout degrade honestly" is an Agent-Probe (spin up the API against an empty cache dir and hit each of the 4 screen endpoints) because it requires an environment this container's egress policy cannot fully replicate (live provider calls for the still-working screens).
  strategy: Hybrid — automated component behavior + one Agent-Probe end-to-end check

- AC4: A user's watchlist additions/removals made after deployment survive a redeploy of the app (are not silently reset to the default list).
  proven by: config-shape unit test confirming `SCREENER_WATCHLIST_PATH` is honored and points at the same location the persistent volume mounts (new test); the actual "survives a redeploy" claim is an Agent-Probe once a target is chosen, since it depends on the chosen platform's volume behavior.
  strategy: Hybrid

- AC5: `GET /api/health` continues to report `{"status": "ok"}` and can be used as the platform's readiness/liveness probe after deployment, exactly as it already is for local Playwright runs.
  proven by: existing `web/playwright.config.ts` readiness-probe usage as the reference; new pytest test asserting the exact response shape (currently untested — a gap this SPEC surfaces).
  strategy: Fully-Automated

- AC6: The author is shown a single clear hosting recommendation with a real monthly cost, not a bare list of options with no default.
  proven by: this SPEC document itself, reviewed and confirmed by the author.
  strategy: Agent-Probe (human review — there is no code behavior to automate here; this is a decision-document acceptance criterion)

- AC7: The author is shown a single clear access-privacy recommendation, with an explanation of what it does and does not protect against.
  proven by: this SPEC document itself, reviewed and confirmed by the author.
  strategy: Agent-Probe (human review)

- AC8: No infrastructure is created, no account is opened, and no publicly-reachable endpoint exists as a result of this SPEC being written.
  proven by: repo-state check — no new deploy config committed by this lane beyond docs/config-surface changes named in this SPEC (`git diff --stat` against this lane's allowed touchpoints); no cloud account or DNS record created.
  strategy: Fully-Automated (a diff/scope check, not a runtime test)

---

## Out Of Scope

- Building any login page, session system, or user-account/auth code inside the app itself. (The recommended approach gates access at the network layer, outside the app.)
- Choosing and provisioning the actual hosting target — this SPEC recommends one, but purchase/signup/deployment happens only after the user explicitly says go.
- Any change to `web/` (owned by the `claude/ui-shell` lane), `api/scripts/`, `.github/workflows/`, `.gitignore` (owned by `claude/p1-pipeline`), or `api/data/pytrends_adapter.py` (pending PR #6).
- Designing P1's nightly-refresh or backfill workflow mechanics — this SPEC states the requirement P1 must satisfy, not how P1 implements it.
- Multi-tenancy or supporting any user other than the app's author.
- Equity data licensing (London Strategic Edge) — a separate, already-tracked open decision, unaffected by this SPEC.
- Actually measuring the real on-disk cache size on the author's PC — that number can only be produced by the author running one command locally; this SPEC uses an estimate and says so.
- Verifying live-provider behavior (Google Trends, Reddit, CoinGecko, Hyperliquid, FRED, DefiLlama) from this environment — this sandbox's network policy blocks all of them.

---

## Constraints

- **Cost:** this is a personal tool, not a funded product — every dollar figure must be real and monthly, and free-tier-sufficient cases must be called out plainly.
- **Persistent disk is mandatory.** The app's only datastore is Parquet files on disk, read via DuckDB — no database server exists. Any hosting target without a real, redeploy-surviving writable filesystem is disqualified outright (this ruled out Vercel, Netlify, Cloudflare Workers, and plain stateless Lambda).
- **No app-level auth/login code.** `process/context/all-context.md` records auth and multi-tenancy as deliberately out of scope "until the research tooling works." The privacy requirement must be satisfied without contradicting that — by gating access outside the app, not inside it.
- **Licensing forbids full public redistribution today.** At least 3 data adapters (Farside/ETF flows, L2Beat, and — pending user confirmation — Hyperliquid) are explicitly marked non-redistributable; a fully public deployment would need per-provider legal review this SPEC does not attempt. A single-user-gated deployment sidesteps this without resolving it.
- **File ownership boundaries (this session):** this lane may only touch `api/main.py`, new deployment/config files, and deployment docs. Requirements that fall on `web/`, `api/scripts/`, `.github/workflows/`, `.gitignore`, or `api/data/pytrends_adapter.py` must be written as requirements addressed to the owning lane, not implemented here.
- **Existing env-override levers must be reused, not rebuilt.** `SCREENER_CORS_ORIGINS`, `SCREENER_CACHE_ROOT`, and `SCREENER_WATCHLIST_PATH` already exist and already do most of what a deploy needs — the code change is about wiring/documenting them for a new run context, not inventing new config plumbing.
- **The bind address is a run-command concern, not a code concern.** `api/main.py` has no `.run()` call; there's nothing to "unbind" in the source — the constraint is on how the container/process is started.
- **This sandbox cannot verify live-provider behavior or real cache size.** Both are marked accordingly rather than guessed at.

---

## Open Questions

*(Per repo convention: since this is an interactive, non-`/goal` session, these must be resolved before PLAN begins. They are listed here for the author's decision — SPEC intentionally stops short of deciding them.)*

1. **Which hosting target?** Owner: user. This SPEC recommends Fly.io by default, or a home box + Tailscale if the user already owns a suitable always-on machine (see Background for the full comparison and the decision-pivots that would change this recommendation).
2. **Which access-privacy gate?** Owner: user. This SPEC recommends Tailscale by default, or Cloudflare Access if the user wants "no app install, just a browser login" instead.
3. **Does the user already own an always-on machine (a home server / NAS / spare PC) that's on a stable connection?** Owner: user. This single answer is the strongest lever on the hosting recommendation — it can make the cost effectively $0.
4. **EU or US?** Owner: user. Materially changes the Hetzner VPS price point specifically (cheap in the EU, notably pricier for a US-region box); doesn't affect Fly/Railway/Tailscale/Cloudflare recommendations.
5. **Does the user own a domain, and is that domain (or a subdomain) willing to be pointed at Cloudflare?** Owner: user. Required only if Cloudflare Access is chosen; not required for Tailscale.
6. **Is installing a small always-running app on the phone acceptable, or does "any device" specifically mean "just a browser, nothing installed"?** Owner: user. Tailscale requires an installed app per device; Cloudflare Access does not.
7. **Has Hyperliquid's redistribution terms-of-use question (already an open item in `all-context.md`) been resolved?** Owner: research (pre-existing open question, not new to this SPEC) — relevant here only insofar as it affects how strictly "private only" must be enforced.

---

## Background / Research Findings

### 1. The "binds to localhost" claim is currently just a comment, not code

`api/main.py` has no bind/host/port logic at all — `127.0.0.1` appears only in a docstring example and as a stated intent ("binds to 127.0.0.1 only... this is a personal, single-machine tool"). The actual bind address is set by whatever command starts uvicorn — a deployment/run-command decision, not a source change. The real main.py-level work is: (a) update that docstring so it stops asserting something that becomes untrue after deployment, and (b) the CORS origin allow-list, which IS read from code.

CORS today: default origin is `http://localhost:3000`, overridable via `SCREENER_CORS_ORIGINS` (comma-separated) — this override already exists (it was built for automated browser testing) and is exactly the lever a deployment needs. One thing worth a design flag downstream: the CORS policy currently allows credentials plus wildcard methods/headers together, which is worth tightening once a deploy is real, not just local-dev.

A health-check endpoint already exists (`GET /api/health` → `{"status":"ok"}`) and is already used as a readiness probe by the existing Playwright config — it can be reused as-is by any hosting platform's health check with zero changes.

### 2. Persistent disk is mandatory — and there are two separate writable things, not one

Storage is Parquet files queried by DuckDB; there is no database server. The cache directory is already environment-overridable (`SCREENER_CACHE_ROOT`), so mounting a volume there needs no code change.

Easily missed: the user's watchlist file is also mutated live, at runtime, whenever the user adds or removes a coin from the UI. It's git-ignored today and already environment-overridable too (`SCREENER_WATCHLIST_PATH`) — but if that specific file isn't on the same persistent volume as the cache, the user's watchlist gets silently wiped on every redeploy. This SPEC treats that as a first-class requirement, not a footnote.

On size: what's currently measured in this environment (996K, 43 files across 3 of the app's caches) is not the real number — several caches that the screener, pairs, and regime screens depend on are git-ignored and only exist on the author's own PC, covering 5 timeframes across an 18-coin universe plus watchlist symbols, multiple years of daily history, and over a hundred pair-spread series. The true size can only be measured by the author running a disk-usage command on their own machine. This SPEC recommends provisioning a volume with real margin above the visible number, and says plainly that the number is an estimate.

### 3. The most important consequence: a fresh deploy would only half-work today

Of the app's cached data, some is git-tracked and refreshed automatically every night by scheduled GitHub Actions crons that commit straight to `main` (narrative, liqtide, and on-chain data). The rest — the data behind the screener, pairs, and regime screens — is git-ignored and is only ever populated by manually-run scripts on the author's own PC; it is never committed anywhere.

That means: a fresh checkout of this repo, deployed to any hosting target, would serve narrative/liqtide/on-chain data just fine on day one, but the screener, pairs, and regime screens would come up empty or stale until someone manually runs the backfill/refresh scripts on that deployed instance's own filesystem.

The good news is the app already handles this kind of gap honestly rather than crashing — the pairs screen, for example, already reports a named "results unavailable" or "stale" status with a reason instead of showing wrong numbers when its precomputed results are missing or outdated. That same honest-degrade pattern is the right shape to lean on for the other affected screens, rather than inventing a new failure mode.

**This is the exact, bounded interface handed to P1:** P1 owns `.github/workflows/`, `.gitignore`, and `api/scripts/`, and needs to decide how the gitignored-but-screen-critical caches (OHLCV, liquidity/regime inputs, pairs results) get onto a freshly-deployed instance and stay current there — whether that's widening what's git-tracked, adding new scheduled jobs, or a first-boot backfill step. This document does not choose for P1; it names the gap P1 needs to close.

### 4. Licensing makes "just make it public" the wrong default

Several data providers this app depends on are personal/private-use only under their terms — confirmed for at least Farside (ETF flows) and L2Beat, and flagged as unverified-but-likely for Hyperliquid. Separately, the equity data candidate under review elsewhere in this project (London Strategic Edge) was already found to be private-use-only with no redistribution rights. The project's own context notes that auth/multi-tenancy are deliberately deferred "until the research tooling works" — which is exactly why this SPEC recommends solving privacy at the network layer (a gate the request never gets past) instead of writing login code inside the app: it satisfies the licensing constraint without contradicting the "no auth yet" decision.

### 5. What already exists, config-wise, and what's genuinely missing

Eight environment variables are actually read by the server today (CORS origins, cache root, watchlist path, the pairs universe file, the narratives config file, two Reddit credential variables, and a manual-probe-only Dune API key) — none of them require code changes to support deployment, only correct values at deploy time. Three variables documented in `.env.example` (`API_BASE_URL`, `API_PORT`, `LIQTIDE_ATTRIBUTION_URL`) have no confirmed Python consumer at all — a pre-existing documentation gap, noted but not fixed here. Nothing loads `.env` files automatically anywhere in the codebase.

No runtime packaging exists yet at all — no Dockerfile, no compose file, no Procfile/fly.toml/railway.json/render.yaml, no root README. Python is pinned to 3.12 with dependencies locked via `uv.lock`. This is a genuinely blank slate for deployment tooling, which is why this SPEC frames it as new files to add, not existing files to fix.

### 6. Hosting comparison (all prices need reconfirming at purchase time — retrieved 2026-09-28)

Immediately disqualified: any host without a real, redeploy-surviving writable filesystem — Vercel, Netlify, and Cloudflare Workers all fall into this category structurally, and stateless AWS Lambda would require bolting on a separate managed filesystem service to even qualify.

| Target | Persistent volume? | Real $/month | Scale-to-zero | Setup effort | Note |
|---|---|---|---|---|---|
| **Fly.io (recommended default)** | Yes, cheap, survives redeploys | **~$5–10** | Partial — the volume itself bills continuously even while the app is stopped | Medium | Needs a container image + a small config file |
| Railway | Yes | ~$8–15 | Unclear with a volume attached | Low–Medium | Has built-in scheduled-job support |
| Render | Yes, but only on paid tiers | ~$7.50–13 | No, once a disk is attached | Low | Easiest to operate, priciest per GB |
| Hetzner VPS | Yes, full disk, full control | ~$6–9 **in the EU**; notably pricier for a US region | N/A (always on) | Medium–High | Cheapest real dedicated box, but only if EU is acceptable |
| DigitalOcean | Yes (add-on) | ~$6–8 | N/A | Medium–High | Comparable to Hetzner, slightly more managed tooling |
| Oracle "Always Free" ARM tier | Yes | **$0** | N/A | Medium | Free allowance was cut in half mid-2026 and over-limit instances get terminated — meaningfully riskier as a long-term free home than it used to be |
| **Home box + Tailscale (recommended if the user already owns one)** | Yes, real local disk | **~$0** (electricity only) | N/A | Medium | Zero public exposure at all; tied to the user's own power and internet reliability, no uptime guarantee from anyone |

**Why Fly.io is the default recommendation:** this workload is one user, light traffic, and one moderately CPU-heavy but infrequent job (the ~56-second, 153-pair statistics computation) — it doesn't need a beefy always-on box, but it does need a real disk that survives redeploys and a low, predictable monthly bill. Fly.io is the cheapest option that cleanly satisfies "persistent volume + doesn't require owning hardware," at roughly the price of a coffee a month.

**Decision-pivots — what would change this recommendation:**
- If the user already owns an always-on machine at home (a NAS, an old PC, a small server) → **the home-box option wins outright**, dropping real cost to near zero. This is the single biggest lever.
- If the user is fine committing to a fixed always-on box and is in the EU → Hetzner becomes competitive with Fly.io on price with more raw resources, at the cost of doing more setup and operations yourself.
- If the user is in the US specifically → Hetzner's price advantage mostly disappears; Fly.io stays the better default.
- If the user wants scheduled jobs to be a platform feature rather than something self-managed → Railway's native cron support is a genuine point in its favor over Fly, at a somewhat higher price.
- If the user is comfortable with a "riskier, could get shut off" free option → Oracle's free ARM tier is worth a second look, but this SPEC does not recommend building a plan around it as the primary target given the 2026 tightening.

### 7. Access-gate comparison

| Option | $/month | Works from a phone | Covers both frontend and backend with one gate | Main risk |
|---|---|---|---|---|
| **Tailscale (recommended default)** | $0 for personal use | Yes — install the app once, log in once, leave it running | Yes — it gates at the network layer, so both sides of the app sit on the same private network with no separate CORS/gate logic needed | If the account is compromised, the whole private network is reachable; the phone app needs to stay running (a known minor battery-life annoyance) |
| Cloudflare Access + Tunnel | $0 up to 50 users | Yes — nothing to install, just a browser login (email code or Google/GitHub) | Yes, but only for traffic routed through the tunnel — every origin needs its own policy | Requires the user to already own (or be willing to point) a domain at Cloudflare; shorter log retention on the free tier |
| Plain password lock on the web server | $0 | Yes, type it once | Yes if both sides sit behind the same reverse proxy | Weakest option — no two-factor, no per-device revoke, easy to accidentally leave one route unprotected |

**Why Tailscale is the default recommendation:** it needs zero new code in the app, gives the strongest actual privacy (the app is never reachable from the open internet at all, not even behind a login page), and is free for one person. The trade-off is a one-time "install an app on your phone" step — recommended as acceptable given the user's own stated goal is "reachable from my devices," not "reachable from any browser in the world."

**When to prefer Cloudflare Access instead:** if the user specifically wants "just open a browser on any device, nothing installed" (e.g. wants to check it from a device that isn't theirs), Cloudflare Access is the better fit — at the cost of needing a domain.

**A trap worth naming explicitly:** if the frontend and backend ever end up on two different hosts (e.g. frontend on a free static host, backend elsewhere), both hosts need their own gate, or the split defeats the privacy goal entirely — the visible frontend becomes a public door even if the API behind it is gated. Keeping frontend and backend behind exactly one gate (same box, same tunnel, or same private network) avoids that trap and avoids inventing any bespoke auth code.

### 8. What could not be verified from this environment

- No live call to any of the app's data providers (Google Trends, Reddit, CoinGecko, Hyperliquid, FRED, DefiLlama) is possible here — this sandbox's network policy blocks all of them. Nothing about deployment behavior toward those providers is confirmed end-to-end.
- The true on-disk size of the full cache (including the git-ignored OHLCV/liquidity/pairs data) can only be measured by the author running a disk-usage command on their own PC; the number used above is a visible-subset measurement plus a stated estimate, not the real figure.
- Every hosting and pricing figure above needs reconfirming at the moment of actual purchase — cloud pricing pages change, and none of these were purchased or tested live in this session.
- Whether the pinned Python dependency set (`api/uv.lock` — pandas, numpy, statsmodels, pyarrow, duckdb) installs cleanly on an ARM-based host (relevant only if Oracle's free tier is chosen) was not tested here.
- Whether the frontend's `NEXT_PUBLIC_API_BASE_URL` value can be overridden at container start time or is fixed at build time is unresolved and is called out as a question for the UI-owning lane, not answered here — it directly affects whether "reachable from any device" actually works once deployed.

### 9. What was explicitly asked for and honored

Per the requesting session: this document makes one clear hosting recommendation and one clear access-gate recommendation rather than a neutral list, names the decision-pivots that would change the recommendation, specifies main.py/config changes precisely (distinguishing the run-command-only bind-address concern from the actual CORS code change), states the interface P1 must satisfy without designing P1's own workflows, and states plainly everywhere this session could not verify something live. No infrastructure, account, or public endpoint was created as part of writing this document.

---

**Hard stop, stated plainly:** nothing beyond this document exists yet. Choosing a hosting target, choosing an access gate, and creating any paid infrastructure or public-reachable endpoint all require the user's explicit go-ahead — this SPEC is a decision point, not a green light to build.
