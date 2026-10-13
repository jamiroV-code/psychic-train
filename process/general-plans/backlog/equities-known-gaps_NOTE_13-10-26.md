# Equities (batch 5) known gaps and follow-ups

**Origin:** plan `process/general-plans/active/screener-batch5-equities_12-10-26/` (accepted WITH KNOWN GAPS, 13-10-26); worker reports S9A-S9F and T51 in that folder. Each item is a residual, not a delivered requirement.

- **a. Refresh timing constants are estimates (AC-S9E-1 CONDITIONAL).** `REFRESH_DELAY_MINUTES` 30 and `BAR_DUE_AFTER_MINUTES` 60 in `api/data/equities_calendar.py`. How long after the US close the final daily bar appears is unmeasured. User probe P-S9-2: after a real close, compare the fetched bar against the time and report; then adjust the two constants (tests name both).
- **b. Strip tests lack Good Friday and spring-DST cases.** `equities_calendar` / strip tests do not cover a Good Friday close or the March clock change.
- **c. POST add with an unknown `group_id` is silently ignored** on both the crypto and the equities routes (parity). Later: log it or answer 4xx, plus a test pinning today's behaviour first.
- **d. Early-close days are not modelled (AC-S9-r2).** For example 2026-11-27 and 2026-12-24; the tick runs at the normal close time.
- **e. The equities worker starts only when `LSE_API_KEY` is set at API start** (A5). Without it the status reads `missing-key`. See `lse-api-key-deploy-handling_NOTE_13-10-26.md`.
- **f. Weekly bars are asserted at least 60, not exactly 88**, in the equities tests.
- **g. Plan amendment: editable-test table.** `api/tests/routers/test_equities_router.py::test_layout_failure_is_logged_not_failed` was edited with planner approval in S9B (hidden break: it relied on "equities" being an unknown layout section; it now monkeypatches `layout_store.place_coin` to raise; original assertions kept, count effect 0). The plan's editable-test table did not list it.
- **h. Board chips and caveat text.** The gain chip means open to latest price (parity with crypto); the footnote keeps the two caveats (split-adjusted, delisted). The user may cut them (plan open choices Q2, Q3).
- **i. Older residuals remain open:** AC-8r group sort (`screener-group-sort_NOTE_09-10-26.md`), AC-S5b-8r and AC-S11b-8r contrast (`screener-ondemand-states-contrast_NOTE_10-10-26.md`, `screener-live-ondemand-states-contrast_NOTE_10-10-26.md`), `screener-passive-polls_NOTE_10-10-26.md`.
- **j. T49 and T51 were not independently tested.** Checked by CI plus the planner's diff read only, at the user's request (usage nearly exhausted). T49 also leaves the forming-bar question open: the adapter asks `order=asc`, so today's forming bar may be the last row; decide later whether to drop it.

## Open user probes

P-S9-1 done (live shape recorded in `lse-live-shape-verification_NOTE_03-10-26.md`). Open: P-S9-2 (on-PC equities page and real-close timing), P-S9-3 (phone/iPad on the equities page; phone reachability itself is confirmed). Older: P-S1-1, P-S2-1, P-S8-1, P-S4-1, P-S5a-1, P-S5b-1, P-S6-1, P-S7-1, P-S11-2 (DST change 25 Oct 2026).
