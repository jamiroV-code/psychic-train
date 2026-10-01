---
name: note:pipeline-cache-hardening-followups
description: "Backlog: leftover cache-write hardening items from P1 (KG3 pairs_response fsync, KG4 fixed temp name in cache.py JSON writers, watchlist loader fallback)"
date: 01-10-26
feature: general
---

# Cache hardening follow-ups left by P1 (backlog note)

**Priority:** Low-Medium. Both KG items are naturally done together in the T21 `cache.py` refactor.

- **KG3:** `api/analytics/cointegration/pairs_response.py` writes its tmp files without fsync (out of the atomic-writes lane).
- **KG4:** the two JSON writers in `api/data/cache.py` use a fixed temp name, so two concurrent writers would collide.
- **SQ1 (deferred):** the `watchlist.py` loader falls back to the example file when `watchlist.json` is missing; revisit whether that fallback should stay now that `bootstrap_watchlist.py` exists.
- Also open from the same lane (not in this note, own notes/plan text): KG1 real power-loss durability + no directory fsync; KG2 Windows `os.replace` with an open reader.
- No all-context pointer item remains: the routing row for `api/scripts/BOOTSTRAP.md` was added 2026-10-01.

**Source:** `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md`.
