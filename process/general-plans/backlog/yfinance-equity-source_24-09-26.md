# Backlog NOTE — yfinance as an equity/index source

**Date**: 24-09-26
**Status**: backlog — revisit only if the "crypto only for now" equities decision changes
**Raised by**: user suggestion; assessed in `process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard-rfc002-stage0_REPORT_24-09-26.md`

- `ranaroussi/yfinance`: Apache-2.0, no key, actively released (1.7.0 on 2026-08-26). Not
  affiliated with Yahoo; Yahoo's API is "intended for personal use only".
- Tested 24-09-26 from the user's PC: chart endpoint returns DXY (from 1985), BTC-USD (2014),
  IBIT (2024-01-08), ^GSPC (1984). `range=max` silently downgrades to monthly bars.
- Not needed by the regime dashboard: LiqTide's dollar input is FRED DTWEXBGS; Yahoo has no ETF
  flow or BTC-dominance data.
- If equities come back: it would plausibly solve history depth for personal use, but it is
  personal-use-only (same redistribution wall as London Strategic Edge) and
  `all-data-sources.md` currently says to avoid Yahoo as unsupported. Any adoption goes behind its
  own adapter with `redistributable=false` and a scheduled breakage check.
