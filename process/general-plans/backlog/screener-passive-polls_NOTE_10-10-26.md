---
name: note:screener-passive-polls
description: "Backlog: a read flag so the page's 60 s polls do not queue exchange refreshes (only if probe P-S11-5 shows too much traffic)"
date: 10-10-26
feature: general
---

# Screener live polls: passive reads (backlog note)

- **Problem:** With the refresh worker running, a board or chart read can queue an on-demand refresh of a stale pair (the refresh hook). The S11b page refetches the board and the open drill-down after every 60 s status check while the tab is visible, so a page left open adds read traffic that may queue exchange refreshes. The request rate is not measurable offline (plan U6).
- **Source path:** `process/general-plans/active/screener-batch4_10-10-26/screener-batch4_PLAN_10-10-26.md` (U6, probe P-S11-5), `web/lib/live-poll.ts` (`POLL_INTERVAL_MS`), `api/data/refresh_worker.py`.
- **Fix option:** Only if P-S11-5 shows too much traffic: a read flag (for example a `passive=1` query parameter) that the poll-driven refetches send and the API honours by serving the cache without queueing a refresh; otherwise lengthen `POLL_INTERVAL_MS`.
