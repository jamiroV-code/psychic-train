# Backlog NOTE — point-in-time FRED data (ALFRED vintages) for the insights engine

**Date**: 24-09-26
**Status**: backlog (NEW PLAN REQUIRED — when the insights engine starts testing patterns against history)
**Raised by**: user suggestion (fredapi), assessed during VALIDATE of `regime-dashboard_PLAN_24-09-26.md`

## Assessment of `mortada/fredapi`

| | |
|---|---|
| Licence | Apache-2.0 |
| Key needed | Yes — free FRED API key (the repo's FRED path is keyless on purpose: data-sources Standing Rule 1, RFC-002) |
| Latest release | 0.5.2, 2024-05-05 (PyPI) — no release since |
| Adds for the dashboard | Nothing: WALCL, WTREGEN, RRPONTSYD, DTWEXBGS already arrive with full history via `fredgraph.csv` |
| Adds in general | ALFRED vintages — `get_series_as_of_date`, `get_series_first_release`, `get_series_all_releases`; server-side date filtering; series search |

Decision (24-09-26): not adopted for the regime dashboard.

## Why keep this note

When the insights engine checks "does X usually precede Y?" against history, it should use values
**as they were known at the time**. Using today's revised series can make a pattern look stronger
than it was in real time (look-ahead bias). ALFRED is the free source for that.

## Proposed approach (when needed)

- Measure first: pull vintages for the series the engine scans and check how much they are actually
  revised (H.4.1 balances are rarely revised; the broad dollar index occasionally is). If revisions
  are negligible, record that and skip.
- If needed, call the ALFRED REST endpoints (`series/observations` with `realtime_start`/`realtime_end`
  or `vintage_dates`) from `api/data/fred_adapter.py` with `httpx` — already a dependency — rather
  than adding an unmaintained wrapper. This introduces the first API key: store it in `.env`
  (`FRED_API_KEY`), document it in `.env.example`, and keep the keyless path as the default for
  non-vintage reads.
