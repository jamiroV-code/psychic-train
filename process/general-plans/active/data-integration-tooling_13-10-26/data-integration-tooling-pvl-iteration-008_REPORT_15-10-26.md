---
name: report:data-integration-tooling-pvl-iteration-008
description: "PVL 008 of Amendment A3 (S-T9, T65) vs origin/main bbe5e8b"
date: 15-10-26
metadata:
  node_type: memory
  type: report
  feature: data-integration-tooling
---

# PVL 008: Amendment A3 (S-T9, T65)

**Verdict: CONDITIONAL (0 FAIL, 8 CONCERN).** Plan 364-381. `Gate: PASS` count stays 1.

OK: `cli.py` already prints `detail` (118-120, 149, 216): not owned, delete the conditional in 370. Tier 3 inherits. Cost 102.5-104.5 USD (115.5 with queued work) of 130. Disjoint; no worker lane.

## CONCERN

1. **Not CI-visible (378).** CI runs `pytest api/` only. Own `api/tests/tooling_guards/test_resource_host_guard.py`: load `route_guard.py` and `approvals.py` by path (stdlib, duck-typed pass) and test `decide`, handler, record checks.
2. **Diagnostics (370).** Put `host_label`, `summarise`, `make_handler(pass_, blocked)` in `route_guard.py`. IP gives `(ip)`, odd chars `(invalid)`, max 20, detail max 600 B. `fetch_tier2.py:68` stores full URLs, and 95/98 set `blocked_url` from them: store hosts only; pass `blocked_hosts` at both returns; `log.info` after 159. Read 45-100.
3. **Host rule (371).** `0x7f.0x1` passes "not all digits": last label starts with a letter; labels <= 63; no duplicates. Add `check_resource_hosts` in `approvals.py`, called by `_add` before write (`approvals.py:148` raises raw ValueError); refuse (exit 2) when `statement is None and args.resource_host`.
4. **`decide` (372).** Mirror `permits` (`gate.py:47-58`: non-str, backslash, `@`, port error). Table test: empty `resource_hosts` equals today's guard (`fetch_tier2.py:64`).
5. **Tier 1 (373).** `gate.py:95`: pass `rec.resource_hosts if tier >= 2 else ()`.
6. **Owned/tests (375).** Drop `test_provenance_completeness.py` (no key-set assertion); test provenance in `test_resource_hosts.py`. Browser file: module `pytest.mark.browser`; HTTPS via HTTP proxy shows only `CONNECT host:443`, so write a `do_CONNECT` recorder (`fixture_server.py` forbidden). `page.route` misses WebSockets: prove only in `decide`.
7. **Docs (377).** "delta <= 3,500 B" is wrong: `test_docs_ac27` caps 413-443 at 3,500 B, now 2,950, so +550 B. 420+438 measure 961 B, not 418. Line 438: page-host-only robots/politeness, owner's call on listed hosts, provenance lists approved not contacted hosts.
8. **Read list (381).** Corrected 34,760 B: 13,443 + 4,000 + 3,011 + plan 368-379 4,320 + `fetch_tier2` 45-100, 157-161 2,452 + `gate` 28-41, 93-96 1,198 + `approvals` 51-100 1,831 + `approval_cli` 44-end 3,544 + docs 961. Drop `provenance.py` 30-48; envelope: add key after line 47.
