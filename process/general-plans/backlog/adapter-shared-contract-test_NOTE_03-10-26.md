---
name: note:adapter-shared-contract-test
description: "Backlog: plan Deviations #8, shared adapter-contract test (item 4a) not extended to RFC-002/003 adapters"
date: 03-10-26
feature: general
---

# Adapter shared contract test (backlog note)

- **Problem:** Item 4a's parametrized adapter-contract test covers only the ccxt adapter; the RFC-002/RFC-003 adapters were never added as cases (plan Deviations #8).
- **Source path:** `process/general-plans/completed/momentum-screener_17-09-26/momentum-screener_PLAN_17-09-26.md` (Deviations #8), `api/tests/data/test_adapter_contracts.py`
- **Fix option:** Generalize the test's contract beyond ccxt's `fetch_ohlcv` signature and add the other adapters as parametrize cases.
