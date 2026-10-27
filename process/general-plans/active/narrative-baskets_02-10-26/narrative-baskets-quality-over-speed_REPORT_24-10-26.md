---
name: report:narrative-baskets-quality-over-speed
description: "T164 report: audit of time budgets, caps and skip rules in the attention pipeline, with a host-profile design and quality metrics. Docs only."
date: 24-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T164 report: quality over speed (attention pipeline audit)

## Owner summary (plain language)

**The short answer.** Yes, many limits exist only because GitHub's runner is short and runs once a day. Removing them on your PC or laptop server helps, but the biggest losses are not about speed at all.

**What costs you the most data quality today, in order:**
1. **Google Trends, Reddit and X are not live.** They are 60 of the 95 weight points that can ever be live. Only Wikipedia and exchange volume are, and together they reach 25 points. The trigger rule needs 30, and it also needs one of Trends, Reddit or X to be rising. So today no coin can trigger. Getting Trends live (after PR #162 and the `.github/` step you must approve) is the single biggest gain.
2. **The daily snapshot is frozen too early.** It is taken in the first GitHub job. Trends, Reddit and X run in a second job after it. So the saved record for a day can never contain them. On a server the snapshot should be taken last.
3. **A cut or killed pass loses coins, and one missing day costs the whole source for that coin.** The scorer needs all 7 of the last 7 days. The Trends step is killed at 8 minutes while its own budget is 9, and results are written only at the end, so a kill loses everything fetched.
4. **X reads about 10 coins a day, and keeps 1 of the 7 days it pays for.** Storing all returned days is a small safe fix.
5. **History stops at 100 days, and forward-only sources (Hyperliquid, X, Reddit) wait 90 days.**

**What the server profile does.** No fixed pass deadline: the length is worked out from the number of coins and the spacing. A coin that does not fit is carried to the next window, never dropped. Each coin is saved as it arrives. After a 429 the whole source rests for minutes, not seconds. Spacing can only go up, never down, so the ban risk does not rise. It is chosen with `ATTENTION_HOST_PROFILE=server`; unset means `github` and nothing changes.

**One trap to know.** Running Wikipedia or CoinGecko earlier than 07:23 UTC on a server could freeze a value the provider later changes, because the first value wins. So the plan keeps their time and adds a re-check at day +3 that records a "revised" flag without overwriting.

**What no setting can fix:** Google Trends noise and whole-number resolution, X's own caps, Reddit's low volume (a 10 % change needs roughly 400 mentions to stand out from noise), and the roughly 45 coins with no Wikipedia article. The plan lists what to measure for each.

**Decisions I need from you:** O1 (one writer per source and how server data gets into the repo), O2 (service manager and sleep policy), O3 (written approval of any `.github/` text before it is written), O4 (X cap stays unless you raise it), O5 (exact Binance volume or not), O6 (a probe of the real history limits).

Note: several items in the brief (the 540 s budget, 3 s spacing, `pc_pace.py`, `density.py`, the collector block) are not on main yet. They are in PRs #162 and #161, and the plan marks each row with where it was read.

## 1 Task ID
T164 (AUDIT + PLAN, docs only). Branch `claude/t164-quality-audit` from `origin/main` 7229a80.

## 2 Outcome
done

## 3 Summary
- Inventory of 67 numbered limits in 6 groups (runner, Trends, Wikipedia/CoinGecko/exchange, Reddit/X, Discovery statistics, workflow and checkers), each with file:line, class S/R/Q/T and a server value.
- Host profile design: `api/data/attention_host.json`, selector `ATTENTION_HOST_PROFILE`, default `github`, floor rule for spacing, tick runner, test list with an injected clock.
- Quality metrics: coverage (with structural vs operational missing), completeness, sample and cap flags, freshness, partial-day, retry/backoff, revised flags, one health state; stored under `_meta/quality/`; text-only panel lines.
- Ten slices in payoff order with files, red tests, gates, model, USD and blockers; slices 1, 3, 5 can start now, 2, 4, 6 wait for #162, slice 9 (`.github/`) needs your written approval first.
- Key findings: no coin can trigger today (live weight 25 < 30, no early source); snapshot frozen before slow sources; 8-minute Trends step vs 540 s budget; X stores 1 of 7 returned days.

## 4 Files changed
- `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-quality-over-speed_PLAN_24-10-26.md` (new)
- `process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-quality-over-speed_REPORT_24-10-26.md` (new)

## 5 Commits
Branch `claude/t164-quality-audit`; the SHA is on the PR (a commit cannot name its own SHA).

## 6 Tests run
Commands from the repo root, 24-10-26 UTC, on the working tree before the commit (the git diff gates were re-run after the commit and are recorded on the PR):
- `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-quality-over-speed_PLAN_24-10-26.md`: 0 failures, 0 warnings. `Gate: PASS` is written in the plan only because this passed.
- `git diff --check`, file-set check, secret scan and banned-name grep: results are in the PR description.

## 7 Tests NOT run
- Any pytest suite: no code was changed.
- Anything against Google, Reddit, X, Wikimedia, CoinGecko or Binance: the task forbids providers. All provider behaviour in the plan is marked UNVERIFIED where it is assumed.

## 8 Deviations
- The brief asks to read items on `origin/main` that are not there (540 s budget, `pc_pace.py`, `density.py`, `web_queries.py`, `attention_queries.json`). I read them at the PR heads (#162, #161, #166) and labelled each row. `check_trends_keywords` main still has the 3-consecutive-429 stop; the 3-consecutive-failure stop and pause rules are from #166.
- Not touched: `.github/`, `trends_keywords.json`, any code.

## 9 Blockers
- Owner decisions O1 to O6 (plan section 9). None blocks slices 1, 3 and 5.
- Slices 2, 4, 6 are blocked by PR #162 (same runner file); the Reddit and X units of slice 8 by #161 and the later collector slices.
- Registry-update request: add T164 as done and the ten slices as proposed tasks, order as in plan section 7.
- Risk: the plan's arithmetic for X coverage (20 to 78 coins) depends on a cost-per-coin distribution nobody has measured yet.

## 10 Follow-up
Proposed tasks: QS1 quality record and panel (opus, ask 5 / cap 8), XS store all returned X days (2 / 4), HP1 host profile loader (4 / 6), then after #162: QS2, HP4 snapshot last, HP2 Trends server behaviour; HIST deeper history after an owner probe; TICK runner after O1 and O2; WF (`.github/`) only after your written approval; BT backtest of the thresholds after 30 days of quality records.

## 11 Context cost
Loaded: CLAUDE.md, the envelope, `refresh_attention.py`, the attention data modules, `discovery.py`, `sources.py`, the workflow, `discovery.json`, probe records, three PR heads (greps and excerpts), the T100b PLAN as a format model, `master-planner.md` section 9 and the plan validator. About 150k tokens of reading. Not opened: `all-context.md`, `north-star.md`, `current-state.md`, `MASTER-PLAN.md` (the envelope fixed the scope). Tools: shell, file tools, GitHub MCP; no providers.
