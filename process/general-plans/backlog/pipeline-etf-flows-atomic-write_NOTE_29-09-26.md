---
name: note:pipeline-etf-flows-atomic-write
description: "Backlog: etf_flows_adapter.merge_into_cache writes a gitignored cache parquet non-atomically in the request path; not covered by cache.py's atomic helper (KG5), P2 AC12 not fully met"
date: 29-09-26
feature: general
---

# KG5: `etf_flows_adapter.merge_into_cache` is not atomic (backlog note)

**TL;DR:** The atomic-writes plan made all 9 parquet writers in `api/data/cache.py` atomic, but `api/data/etf_flows_adapter.py:103-111` (`merge_into_cache`) still does a direct read-modify-write of a gitignored cache parquet. It runs in the request path of `GET /api/regime/components` and has no git copy to recover from. **P2's AC12 is NOT fully met until this writer is also atomic.**

**Priority:** Medium (blocks P2's atomicity prerequisite).

**Needs a USER scope decision** (the atomic-writes plan deliberately did not widen). Suggested small follow-up (~2 lines): route the write through a PUBLIC cross-module helper in `cache.py` rather than importing the private `_atomic_to_parquet`.

**Source:** `pipeline-completeness-atomic-writes_PLAN_29-09-26.md` KG5 and its PVL cycle 1 finding N1.
