---
name: spec:narrative-baskets-coin-onboarding
description: "Automatic coin onboarding: what happens, without a session, when a coin enters or leaves the top 100. Probation before a coin joins the universe, hysteresis on exit, automatic detection of pegged and wrapped tokens, automatic finding of search names for Wikipedia, Google Trends, Reddit and X, narrative proposals the owner approves, and a visible new-coins page. Product SPEC only; no code changed."
date: 01-11-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

# Narrative Baskets: automatic coin onboarding (01-11-26)

Status: SPEC for owner review. Nothing in this file has been built. The facts about today's behaviour come from a read-only reading of the code (no run, no network); anything not read is marked UNVERIFIED.

## Summary

Today a coin that enters the top 100 by market cap is counted in the universe the same day, then shows up as gaps: no Wikipedia title, no Google Trends keyword, no Reddit or X query, no narrative. Someone must notice and fill each in by hand, a new pegged token is scored until someone adds it to a list, and one place (a placed coin with no Reddit and X entry) can turn the test run red. This SPEC makes the whole path automatic and safe. A new coin first sits in a visible "watching" state for 14 days in the top 100, so a one-day pump never reaches the universe. During that time the system classifies it (pegged, wrapped, gold-backed or normal), finds its search names for Wikipedia, Google Trends, Reddit and X, and proposes a narrative. Names that pass every automatic check go live on their own; anything borderline waits for the owner. A narrative is only ever proposed, never placed without approval. A coin leaves only after 7 days outside the top 120. Everything runs on a schedule on the owner's PC, none of it needs a working session, and nothing a new coin does can stop the daily run.

## User Stories / Jobs To Be Done

- US1. As the owner, I want a coin that suddenly enters the top 100 not to count until it has held its place for 14 days, so that a one-day pump or a listing spike cannot distort the universe or the scores.
- US2. As the owner, I want a coin near rank 100 to stay in until it has really left (7 days outside the top 120), so that coins do not flip in and out and break their history.
- US3. As the owner, I want new stablecoins, wrapped copies and gold-backed tokens recognised automatically, and any coin the system cannot classify kept out of scoring, so that a pegged token is never scored by accident.
- US4. As the owner, I want the system to find each new coin's Wikipedia title and Google Trends keyword by itself, and Reddit and X search names too, and to use them when every check passes, so that I do not do this by hand.
- US5. As the owner, I want anything the system is unsure about to wait for me with its evidence, so that a wrong name never becomes a believable fake signal.
- US6. As the owner, I want a narrative proposed for each new coin that I approve, so that placement stays my call.
- US7. As the owner, I want one page that lists every new, watching and pending coin and what each source has for it, so that I can see the state without reading files.
- US8. As the owner, I want all of this to run on its own on my PC, and a new coin never to stop the daily run or turn tests red, so that I only act on the items that wait for me.

## What The User Wants (Behavioral Outcomes)

1. Every day the system compares today's top-100 list with yesterday's and records who entered and who left, with dates.
2. A coin that enters is "watching": it is visible, its data is collected from day one, and it is not scored and not part of the reference universe. It becomes a member after 14 consecutive daily snapshots in the top 100. A missed snapshot day does not reset the count; a day outside the top 100 does.
3. A member stays a member until it has been outside the top 120 for 7 days. Then it becomes inactive. Its stored history and its name entries are kept. A coin that comes back goes through the 14 days again and resumes with its kept history and entries.
4. When a coin starts watching, the system classifies it as pegged (stablecoin), wrapped or staked copy, gold or commodity backed, tokenized fund, or normal, from public category and name evidence. A coin it cannot classify with confidence stays out of scoring until the owner confirms or classes it. The evidence is shown.
5. During watching, the system looks for the coin's names:
   - the Wikipedia article title;
   - the Google Trends topic or search term;
   - the Reddit and X search names.
   Each candidate is checked automatically: it must really be about this coin (not a word or another project), have a usable series, not be carried by a spike, and where trading volume exists, follow the coin's own volume.
6. If every check passes and the name is not ambiguous, the name goes live without the owner. If any check is borderline, the name is held as pending with its evidence and the coin's signal for that source reads missing with the reason, never 0. If nothing passes, the coin has no name for that source and the reason is shown.
7. An ambiguous name (a common word or a name shared by several entities) is accepted only as an unambiguous topic or article, or after the owner approves it, the same rule as for the existing ambiguity list. A name resolved by the system never bypasses that list.
8. A narrative is proposed from public category evidence and shown as pending. It is placed only when the owner approves it. Until then the coin reads as unassigned.
9. A new-coins page lists, per coin: state (watching, member, inactive), days in the top 100, class and its evidence, each source's name or missing reason, and anything pending for approval.
10. Every automatic change is written to a log with its evidence and can be reversed by the owner.
11. A new coin with a missing name or entry in any source never fails the daily run and never turns the test suite red; it shows as a gap with a reason.
12. The probation length, the exit rule, and every check threshold are named settings the owner can change in a file, not hidden numbers.
13. The resolver runs on a schedule on the owner's PC; when the PC is off it simply catches up on the next run.

## Flow / State Diagram

```
                 daily top-100 snapshot
                         |
                  new in top 100?
              yes/                       \no
               v                          v
         [WATCHING] <------ re-entry ---- [INACTIVE]
   (visible, data collected,                  ^
    not scored)                               |
        | classify + resolve names            | out of top 120
        |                                     | for 7 days
   out of top 100 -> counter resets           |
        |                                     |
   14 consecutive days in top 100             |
        v                                     |
     class known and not pegged/wrapped? --no--> [OUT: stays out of scoring,
        |yes                                       shown with its class]
        v
    [MEMBER] ---------------------------------+

  names (Wikipedia, Trends, Reddit, X) per watching coin:
     candidates -> identity check -> series check -> volume check -> ambiguity check
          | all pass                  | borderline            | none pass
          v                           v                       v
     [go live]               [pending for owner]        [no name, reason shown]
     (logged, reversible)    (signal missing, reason)

  narrative: proposed -> [pending for owner] --approve--> placed   (never automatic)
```

## Acceptance Criteria (Testable Outcomes)

- AC1. A coin that enters the top 100 is listed as watching the same day, is not scored and is not in the reference universe.
  proven by: new-entrant scenario on a snapshot sequence fixture
  strategy: Fully-Automated
- AC2. A coin that stays in the top 100 for 14 consecutive daily snapshots becomes a member; a coin that drops out on day 13 does not, and its count restarts if it comes back.
  proven by: probation boundary scenarios (13, 14, drop-and-return)
  strategy: Fully-Automated
- AC3. A missing snapshot day does not reset a coin's count or make it leave.
  proven by: snapshot-gap scenario
  strategy: Fully-Automated
- AC4. A member between rank 101 and 120 stays a member; it becomes inactive only after 7 consecutive days outside the top 120, and a return to the top 120 within that time cancels the exit.
  proven by: hysteresis scenarios (stay, exit at 7, cancelled exit)
  strategy: Fully-Automated
- AC5. When a coin becomes inactive its history and name entries are kept, and a returning coin resumes with them after probation.
  proven by: inactive-and-return scenario that reads the kept series and entries
  strategy: Fully-Automated
- AC6. A new stablecoin, wrapped or staked copy, or gold-backed token on the fixture list is classified as such with its evidence and never scored, and a normal coin is classified normal.
  proven by: classification scenarios on fixture categories and names
  strategy: Fully-Automated
- AC7. A coin the classifier cannot place with confidence stays out of scoring and is shown as unclassified until the owner confirms it.
  proven by: unclassified-coin scenario
  strategy: Fully-Automated
- AC8. For a watching coin, a Google Trends candidate that passes the identity, series, volume and ambiguity checks goes live without the owner; the change is logged with its evidence.
  proven by: Trends resolver scenario with fakes for the suggestions and the series
  strategy: Fully-Automated
- AC9. For a watching coin, a Wikipedia candidate that passes its checks goes live without the owner; a disambiguation page or an article that is not about the coin is refused.
  proven by: Wikipedia resolver scenarios with fakes
  strategy: Fully-Automated
- AC10. A borderline candidate (several equally likely entities, weak volume agreement, or an ambiguous name) is held as pending, the source reads missing with the reason, and nothing goes live.
  proven by: borderline scenarios for each source
  strategy: Fully-Automated
- AC11. When no candidate passes, the coin has no name for that source, the reason is shown, and the signal reads missing, never 0.
  proven by: no-candidate scenario
  strategy: Fully-Automated
- AC12. A name found by the system for a coin on the ambiguity list is never used unless it is a topic or the owner has approved it.
  proven by: ambiguity-list scenario against the resolver output
  strategy: Fully-Automated
- AC13. A narrative is proposed from category evidence and shown as pending; the coin stays unassigned until the owner approves, and approval places it.
  proven by: narrative proposal scenarios (propose, no auto-place, approve)
  strategy: Fully-Automated
- AC14. The new-coins page shows, per coin, state, days in the top 100, class with evidence, each source's name or reason, and pending items; a coin with nothing pending shows none.
  proven by: page scenarios in the web tests plus one fixture-backed load of the data behind it
  strategy: Fully-Automated
- AC15. Every automatic change is logged with its evidence, and reversing one restores the previous state.
  proven by: log-and-reverse scenario
  strategy: Fully-Automated
- AC16. A new coin with a missing entry in any source does not fail the daily run and does not make the test suite fail.
  proven by: missing-entry scenario through the daily run and the shipped-file tests
  strategy: Fully-Automated
- AC17. Probation length, exit band, exit days and the check thresholds come from a settings file, and a bad settings file is refused with a plain message.
  proven by: settings and bad-file scenarios
  strategy: Fully-Automated
- AC18. On the owner's PC the scheduled task runs the resolver unattended for several days and resolves a real new or unnamed coin end to end.
  proven by: owner probe P-O1 (run for three days on the real PC and read the log)
  strategy: Agent-Probe
  Justification: the real Google Trends and Wikipedia answers and the PC's task scheduler cannot be reached from the build environment.

## Out Of Scope

- Changing the scoring weights, the Discovery formulas or the percentile reference rules (the weights are the owner's, D-22 and D-24).
- Automatically placing a narrative; narratives are proposed only.
- Deleting history or entries for coins that left the universe.
- A minimum listing-age rule (the owner chose days in the top 100 only).
- A market-cap or volume outlier hold; probation by time is the only filter in this SPEC.
- Reddit and X collection changes beyond finding the per-coin search names, and the Reddit stream budget.
- Backfilling history for a coin before it started watching.
- Replacing the unofficial Google Trends library or adding a paid search-volume source.
- Equities, other asset classes and exchange-token rules (D-27 unchanged).

## Constraints

- Owner decisions of 01-11-26, closed: 14 consecutive days in the top 100 before a coin joins; exit after 7 days outside the top 120; no minimum listing age; "watching" is visible and collects data; unknown class stays out of scoring; names that pass every check go live automatically, borderline ones wait; narratives are proposed and the owner approves; kept history and entries for inactive coins; the resolver runs on the owner's PC through the task scheduler.
- Missing data is never 0, never carried forward, never guessed (existing project rule).
- The owner merges every change to the repository (D-28). Automatic name entries are written only to the files and records the plan names for that purpose, and every automatic change is logged and reversible.
- Google and Wikipedia are reachable only from the owner's PC and from GitHub's runners, not from the build environment; every automated test uses fakes.
- The Google Trends library is unofficial and can break; a failing resolver leaves coins pending and never blocks the daily run.
- The resolver must back off when rate-limited and retry on the next scheduled run, never loop.
- Existing rules stay: the ambiguity list and per-coin approvals for Google Trends terms, pegged and gold-backed exclusions (D-29), and the one-request-per-coin daily run.

## Open Questions

None. Decisions the owner already took are under Constraints. Items for the PLAN, not the owner: where the per-coin state and the automatic entries are stored, how the settings file is laid out, how the classifier weighs category against name evidence, the exact check thresholds, how the new-coins page is laid out, and how the log is shown.

## Background / Research Findings

- **How the top 100 is made today (read, not run):** a daily workflow stores the CoinGecko top-100 by market cap; the universe takes the first 100 with no class filter. A coin enters the day it appears; the coin that falls to 101 disappears with no record.
- **How a coin is judged in or out today:** only by hand-kept symbol lists for stablecoin, wrapped or staked, gold or commodity backed and tokenized fund, plus a zero-volume or no-market check. Nothing detects pegged tokens automatically, so a new stablecoin is scored until someone adds it. There is no probation and no exit band.
- **Narratives:** placed only by hand in the narratives file. A coin with no entry reads "unassigned" in the excluded list. UNVERIFIED: whether an unassigned in-universe coin is still scored.
- **Per source today:** Wikipedia gives "no article mapped" and skips without error until a title is added. Google Trends gives "no keyword mapped" and skips. CoinGecko works from the snapshot. The Reddit and X queries file raises an error when a coin placed in a narrative has no entry, which makes the test run red; a test also pins the placed-coin count (75). The Trends guard test reports a new live coin as a gap and does not fail.
- **Daily runs:** a missing entry for one coin does not fail the workflow; only a failed universe fetch does. The Trends step already runs on GitHub's runners.
- **Existing owner-run tools that already do pieces of this:** a checker that proposes Google Trends topic IDs from a coin name using the suggestions endpoint, a checker that tests candidate Wikipedia titles against crypto words, and the Trends campaign tester that scores a term (usable, spike, volume agreement). They write nothing; they are the starting point for the resolver.
- **Evidence available per new coin:** the snapshot carries id, name, symbol, market cap and volume. UNVERIFIED: whether volume series exist for a coin in its first days, how reliable the suggestions endpoint's entity types are, and whether stored daily snapshots are enough to count consecutive days (the PLAN verifies this first).
- **Not verified in the first read:** exchange volume, DefiLlama and GitHub development sources, and Discovery scoring of unassigned coins.
- **Related decisions and work:** D-27 (exchange tokens in), D-29 (pegged and gold-backed out), the Trends stage 2 SPEC (ambiguity list and approvals, merged), the ambiguity list rule, the Reddit stream (separate).
- **Test grounding:** the Discovery universe and classification tests, the Sources and Discovery response tests, the keyword and campaign tests, and the web narrative tests; see `process/context/tests/all-tests.md`. AC18 is the only live check.
