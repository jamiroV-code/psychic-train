# Windows API gate repair: execute report

Date: 2026-11-06. Plan: `windows-api-gate-repair_PLAN_04-11-26.md`.

## Changes
- Five fixtures (`test_attention`, `test_discovery`, `test_discovery_history`, `test_discovery_price`, `test_universe_classes`): socket connect guard forwards numeric IPv4/IPv6 loopback tuples only; both HTTP transport blockers retained.
- `test_equities_store.py`: removed native-separator default-path assertion; added open-reader/atomic-replace exclusion regression (add and remove) and a read-error lock-release regression.
- `test_twscrape_reader.py`: removed the assertion that the owner's `x_accounts_db_path` default is empty (the owner's local config is deliberately non-empty).
- `equities_store.py`: `_LOCK` is an `RLock`; `load_tickers` holds it for the whole read; lock scope documented.
- `test_equities_router.py`: 35-request concurrency test is bounded, captures exceptions, asserts exactly thirty 200s and five 409s with the cap text, and persisted symbols equal accepted symbols.
- `api/data/attention_queries.json` untouched (owner-local edit from 2026-11-02, not committed here).

## Verification (disposable tracked snapshot, same-process import/store preflight, git-initialised throwaway repo)
- Preflight: namespace paths, cache/equities/watchlist origins and effective paths, `api.main` and deploy conftest origins all inside the snapshot; no editable finders.
- Scoped selection: 172 passed, 1 skipped (POSIX-only mode-bits test).
- Full gate `pytest.main(["-c","api/pyproject.toml","api/","-q"])`: **3722 passed, 5 skipped, 5 deselected, 0 failed** in 985 s. Previous Windows baseline: 44 failed, 1 error.
- The first full run had 4 failures that were harness-only (snapshot was not a git repo for `git check-ignore` / `git ls-files` tests); fixed in the runner, not in repo code.
- The 35-request concurrency check is the hardened router test (real TestClient, exact outcomes); no separate throwaway smoke was run.

## Not yet done
- GitHub CI on the published repair head.
- The runner lives outside the repo (`%TEMP%/winrepair/run.py`) and is not committed.
