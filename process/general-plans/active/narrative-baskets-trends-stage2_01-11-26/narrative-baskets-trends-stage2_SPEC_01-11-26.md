---
name: spec:narrative-baskets-trends-stage2
description: "Trends stage 2 (follows T196/T201): choose ONE Google search term per coin by evidence that it measures the coin and not something else, an owner-kept list of ambiguous names, owner approval for qualified terms, a visible waking-up watch state, and no invented keyword where nothing passes. Product SPEC only; no code changed."
date: 01-11-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Narrative Baskets: Trends stage 2, one trustworthy search term per coin (01-11-26)

Status: SPEC for owner review. Nothing in this file has been built. All numbers come from the finished campaign file the owner ran on their PC (read-only, no Google request from here).

## Summary

The Trends campaign has now tested every candidate search term for every eligible coin. It shows that the current keyword is often weak, and that some words (sky, pi, near, just, link, sol and others) also mean other things, so their "attention" is partly not about the coin. Stage 2 makes the system pick, for each coin, the one search term that most clearly measures attention to that coin and not something else; it keeps an owner-controlled list of ambiguous names that may only use an unambiguous Google topic or a term the owner approved; it shows coins that are waking up from near-zero as their own visible watch state without scoring them; and it leaves a coin with no keyword (shown as missing, never as 0) when nothing passes the checks. Pegged and gold-backed tokens are not part of the universe (PR #206), so they are not part of this work.

## User Stories / Jobs To Be Done

- US1. As the owner, I want each coin's Trends signal to come from the search term that people actually use to look for that coin, so that the number reflects interest in the coin and not in a common word.
- US2. As the owner, I want names that mean something else (sky, pi, near, just, link, sol and so on) kept on a list I control, so that a bare word is never trusted for them without my say.
- US3. As the owner, I want to approve, coin by coin, a term like "sky crypto" when I judge it fine, and have that approval recorded, so that nothing qualified slips in silently.
- US4. As the owner, I want a coin with no trustworthy keyword shown as "no keyword, needs owner" and never as a zero or a guess, so that a missing signal is never mistaken for a quiet one.
- US5. As the owner, I want coins that are suddenly waking up from almost no searches shown in a separate watch list, so that I notice early attention without it distorting the ranking.
- US6. As the owner, I want the choice to be explainable from stored evidence, so that I can see why a term was picked or refused.

## What The User Wants (Behavioral Outcomes)

1. Each coin has exactly one Trends search term (or a Google topic) used for its daily number. A few extra terms may be tested beside it only to check that it measures the same thing; they never change the number.
2. For every coin the owner can see: the chosen term, why it was chosen (it passed the checks and was best on them), and the other terms that were tested.
3. A coin passes only if its term gives a usable series (not too quiet, not empty), is not carried by a single spike, and where other terms or the coin's own trading volume exist, agrees with them.
4. Among terms that pass, the one with the fewest empty days and the most distinct values wins. "Currently rising" is not a reason to choose or refuse a term.
5. The owner keeps a list of ambiguous names. For a listed coin only a Google topic is accepted by default. A plain or qualified term is accepted only after the owner approves that exact term for that coin; the approval is stored with the term.
6. If nothing passes for a coin, the coin is marked "needs owner" with no keyword, the daily run does not fetch it, and every screen shows its Trends signal as missing with the reason, never 0.
7. A coin whose term is quiet for weeks and then jumps for a full week is shown as "waking up" in a separate watch list with how many days it has held. It is not counted as rising, does not add to any score, and does not change a ranking until the owner decides otherwise.
8. The ambiguity list and the approvals are kept in a file the owner edits; the system refuses a bad file and says why, as the keyword file already does.
9. The daily run keeps one request per coin, so the daily time budget does not change.

## Flow / State Diagram

```
          candidate terms tested (campaign, owner PC)
                         |
                         v
          each coin: terms with a usable series?
             |                         |
            no                        yes
             |                         |
   quiet then jumps full week?    spike or term moves alone? --yes--> refuse that term
        |          |                    |no
       yes         no                   v
        |          |            ranked: fewest empty days, most distinct values,
        v          v            then agreement with volume / variants
 [waking up]  [needs owner]                |
 (watch list,  (no keyword,               v
  not scored)   shown missing)      coin on ambiguity list?
                                      |            |
                                     no           yes
                                      |            |
                                      v            v
                                 [use term]   topic id?  --yes--> [use topic]
                                                  |no
                                                  v
                                       owner approved this term?
                                          |yes            |no
                                          v                v
                                     [use term]     [needs owner approval,
                                                     shown missing meanwhile]
```

## Acceptance Criteria (Testable Outcomes)

- AC1. Each coin with a usable term has exactly one term or topic used for its daily Trends number; test terms beside it never change that number.
  proven by: one-term-per-coin selection scenario with a bundle present
  strategy: Fully-Automated
- AC2. A term whose series is empty, too quiet, or whose rise is carried by one day or one term is never chosen.
  proven by: refusal scenarios (empty, quiet, one-day spike, one-term spike) on fixture series
  strategy: Fully-Automated
- AC3. Among terms that pass, the one with the fewest empty days wins, ties broken by more distinct values; whether a term is currently rising never changes the choice.
  proven by: ranking scenario with a rising-but-gappy term against a steady-but-complete term
  strategy: Fully-Automated
- AC4. When stored trading volume exists, a term whose series does not follow the coin's volume is flagged as unconfirmed and shown with that flag; where no volume exists it is shown as unchecked, never as confirmed.
  proven by: identity scenarios with and without stored volume
  strategy: Fully-Automated
- AC5. When variant terms were tested, a coin whose main term and variants do not move together is flagged as unconfirmed; with no variants tested it is shown as unchecked.
  proven by: variant-agreement scenarios (agree, disagree, none tested)
  strategy: Fully-Automated
- AC6. A coin on the ambiguity list accepts a Google topic, or a term the owner approved for that coin and recorded; an unapproved plain or qualified term is refused and the coin is shown as waiting for approval.
  proven by: ambiguity-list scenarios (topic, approved term, unapproved term, term approved for another coin)
  strategy: Fully-Automated
- AC7. The ambiguity list ships with the 23 agreed coins (TRX, ONDO, MORPHO, ICP, SHIB, PEPE, BNB, CRO, HBAR, LINK, APT, SOL, SKY, PI, JST, NEAR, GRAM, RAIN, M, CC, LIT, NIGHT, STABLE), and adding a coin to it takes effect without a code change.
  proven by: shipped-list scenario and added-coin scenario
  strategy: Fully-Automated
- AC8. A coin where nothing passes is stored as "no keyword, needs owner" with a reason; the daily run sends no request for it and every screen shows its Trends signal as missing with that reason, never 0.
  proven by: no-passing-term scenario through the daily run and the Sources and Discovery responses
  strategy: Fully-Automated
- AC9. A coin that is quiet and then holds a full week of jumps is listed as "waking up" with the number of days it has held; it adds nothing to any score, does not count as rising, and does not change any ranking.
  proven by: waking-up scenario comparing Discovery scores with and without the coin's waking-up state
  strategy: Fully-Automated
- AC10. The waking-up watch list is visible to the owner on the Sources screen (or the Discovery screen) with each coin's days held; a coin that stops jumping leaves the list.
  proven by: watch-list display scenario in the web tests plus one end-to-end load of the screen
  strategy: Fully-Automated
- AC11. A bad ambiguity file or approval record (unknown coin, approval for a term that is not the stored term, duplicate approval) is refused with a plain message that names the problem, and the Trends source reports it as unavailable instead of crashing.
  proven by: bad-file scenarios
  strategy: Fully-Automated
- AC12. The daily run still makes one request per coin and finishes inside the existing time budget on the fixture set.
  proven by: daily-run request-count and time-budget scenario
  strategy: Fully-Automated
- AC13. For each coin the owner can see the chosen term, the reason it was chosen, and the other tested terms with why each lost.
  proven by: per-coin evidence report scenario on the real campaign file shape
  strategy: Fully-Automated
- AC14. Re-ranking the finished campaign file under these rules sends no request to Google and changes no file the owner has not asked to change.
  proven by: no-network and read-only re-rank scenario
  strategy: Fully-Automated
- AC15. STABLE, which is on the ambiguity list but was not part of the campaign, is tested in a follow-up campaign run, and until then is shown as untested, not as passed.
  proven by: untested-coin scenario in the report
  strategy: Fully-Automated
- AC16. On the owner's PC, after the new rules are applied, the Trends numbers of ten coins picked by the owner match what they see in Google Trends for the chosen term.
  proven by: owner probe P-T1 (compare chosen terms with the public Trends page)
  strategy: Agent-Probe
  Justification: Google Trends cannot be reached from the build environment, so the live comparison can only be made on the owner's machine.

## Out Of Scope

- Any change to the weights (Trends stays at 25; the weights are the owner's, D-22 and D-24).
- Counting "waking up" toward any score or ranking, until the owner decides after watching real runs.
- Pegged and gold-backed tokens (USD0, PAXG, XAUT): already excluded from the universe in PR #206.
- Using several terms summed into the number, or a multi-term request in the daily run.
- A new search-volume source, a paid Trends service, or replacing the unofficial Trends library.
- X and Reddit changes, including the Reddit stream budget finding.
- Backfilling history for coins whose keyword changes (a changed keyword starts a new series; how that is shown is for the PLAN).
- Proving by itself that a term is "what the majority searches": the system gathers evidence, it does not claim ground truth.

## Constraints

- Owner decisions of 01-11-26, closed: one term per coin as the signal; extra terms only to validate it; signal quality means a real signal, not a fake one (not "currently rising"); ambiguity list of 23 coins; for a listed coin a topic, or an owner-approved term recorded per coin; no passing term means "needs owner" and no keyword; waking up is a visible watch state, not scored.
- The selection works from the finished campaign file and a small number of new campaign runs on the owner's PC. This environment never calls Google.
- Missing data is never 0, never carried forward, and never guessed (existing project rule).
- The thresholds used by the checks (how quiet counts as quiet, how much agreement counts as agreement, how long a jump must hold) start as the existing placeholders and are tuned by the owner after the first real run. They are named constants, not hidden weights.
- Only about 30 coins have stored trading volume, so the volume check is a hint for the rest, not a gate.
- The Trends source stays on the unofficial library, which can break at any time (existing risk).
- The owner merges every PR (D-28); nothing is pushed to main.
- The daily Trends step keeps its time budget of 780 seconds with an 18 minute step limit.

## Open Questions

None. Decisions the owner already took are listed under Constraints. Items for the PLAN, not the owner: the exact form of the approval record, the thresholds above, how a changed keyword's history is shown, and how the watch list is laid out on the screen.

## Background / Research Findings

- The campaign state on the owner's PC covers 81 coins; 78 remain after the pegged and gold-backed tokens (USD0, PAXG, XAUT) leave the universe. STABLE is not in the file.
- Re-rank on the 78, read-only, under the rules above (ambiguity list of 22 of the 23, the 23rd is untested):
  - 55 coins not on the list have a passing single term.
  - On the list, 8 have a passing topic (BNB, HBAR, ICP, LINK, NEAR, PI, SHIB, SOL).
  - On the list, 10 have only a qualified term and wait for the owner's approval (CC, GRAM, JST, LIT, NIGHT, ONDO, PEPE, RAIN, SKY, TRX).
  - On the list and waking up: APT, CRO, MORPHO. Not on the list and waking up: ETHFI.
  - Needs owner with no usable term: M.
- Evidence about what people type: tested bundles of three qualified terms (for example "x crypto", "x coin", "x token") share one scale, so each term's share of the total shows which was searched most. The ticker plus "crypto" often leads (HBAR 93%, ICP 94%, DOT 85%, APT 86%, WLD 94%), the full name leads for some (ETH 70%, BTC 73%, SHIB 81%, PI 70%), and some coins are close (DOGE 43%, NEAR 40%, SKY 43%). Bare names were not tested because of the ambiguity risk, so the shares compare qualified terms, not everything people type. A Google topic counts every spelling, which is why it is the default for ambiguous coins.
- The current keyword file has 82 coins, 41 with a topic and 41 with a term. The loader already refuses a bad file, already skips risky bare names (12 coins on the T125 list, qualified terms accepted), and already records the daily outcomes `ok`, `too-little-interest` and `quiet-then-surge`. Stage 2 widens the risky list to the 23 agreed coins and tightens the rule to approval per coin.
- `quiet-then-surge` ("waking up") exists in the daily run and in the campaign report; it is shown but never counted as passed, and the question of whether it counts as rising was left open in the code. The owner has now decided: visible, not scored.
- Existing checks that carry over: usable verdict, one-term spike, term-moves-alone, identity against stored volume, zero days and distinct values (T196, T201, T202).
- New work needed that does not exist today: the owner-kept ambiguity and approval record, a variant-agreement rule that does not misread weak extra variants as a bad main term (a first attempt on the real file did), a selection rule free of "clean rising", the missing-signal display for a coin with no keyword, and the waking-up watch list.
- Related, separate: PR #206 (pegged and gold-backed tokens), decision D-29.
- Test grounding: the Trends tester and campaign tests (`test_trends_groups`, `test_probe_trends_campaign`, `test_probe_trends_t202`), the keyword file tests, the daily-run tests (`test_refresh_attention_trends*`) and the Discovery and Sources response tests. See `process/context/tests/all-tests.md`.
- Owner probe P-T1 (AC16) is the only live check and is not run by the build environment.
