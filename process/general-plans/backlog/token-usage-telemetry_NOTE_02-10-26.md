---
name: note:token-usage-telemetry
description: "Backlog: real per-session token usage is unmeasured; the entry-set savings are byte counts only"
date: 02-10-26
feature: general
---

# Measure real per-session token usage (backlog note)

**TL;DR:** The master-planner-recovery plan cuts the default session load by bytes (planner cap 64,000, worker cap 36,000), but nothing measures the tokens a session actually spends. Savings claims stay "bytes measured, tokens approximate" until this closes.

- **What is unproven:** real tokens per session, per agent, per retry and per repeated test run; whether the smaller entry sets lower real cost.
- **Why:** no usage telemetry exists in the repo; tokens are estimated as bytes/4.
- **Done so far (Gate 3, 03-10-26):** single-run headless probes measured first-request context only (old planner 78,664 tokens, new planner 37,450, worker 37,921; 0.617 USD; see the Gate 3 report). Whole-session usage, retry waste and repeated-test cost are still unmeasured.
- **Measured, Gate 5 pilot (03-10-26, platform-reported `cost_usd`):** T20 0.882417 USD (cache_read 1,996,585 / cache_write 101,308 / output 7,776); T16 0.7556444 USD (1,814,012 / 82,522 / 6,265); total 1.6380614 USD vs the 40 USD ceiling; 0 fix cycles. Two RT0 tasks only: no pre-Gate-3 comparison and no repeated-test cost yet.
- **How to close:** sample `list_events` transcripts for 3-5 past and 3-5 post-Gate-3 sessions, or record a per-task estimate in report heading 11 and compare. Record method, sample and timestamp.
- **Source:** master-planner-recovery plan, Verification Evidence known gaps; F15.
