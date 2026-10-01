---
name: note:pipeline-live-fetch-canary
description: "Backlog: no live ccxt/Hyperliquid/FRED fetch was ever run in the P1 container; first real nightly run is the first live check (AC-14)"
date: 01-10-26
feature: general
---

# First live fetch of the scheduled refresh scripts (backlog note)

**TL;DR:** `refresh_cache.py` / `backfill_primaries.py` exit codes and the new workflows were only tested offline (AC-14 Known-Gap). The container egress proxy blocks the providers.

**Priority:** Medium.

**Do:** treat the first real nightly run of `pairs-refresh-snapshot.yml` and `liquidity-backfill-snapshot.yml` (or a manual run on the user's PC following `api/scripts/BOOTSTRAP.md`) as the first live check. Read the job log for exit codes 0/2/1 and the `::warning::` lines.

**Still unobserved:** Hyperliquid bulk rate-limit/backoff behaviour across ~20+ sequential fetches (18 deep fetches earlier had no throttling; the nightly refresh adds more calls). Also unverified: a GitHub-hosted `compute_pairs` only sees <=500 bars per coin, so its result is a canary, not a quality result.

**Source:** `process/general-plans/active/pipeline-completeness_28-09-26/` (AC-14, D4, D7).
