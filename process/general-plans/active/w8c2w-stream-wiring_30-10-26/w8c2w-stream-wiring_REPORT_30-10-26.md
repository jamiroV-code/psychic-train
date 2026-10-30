# W8c2w report: Reddit stream wiring PLAN

## 1 Task ID

T222 (ID free: T221 is the highest in `git log --all` subjects and PR titles; no T222 anywhere; W8c2 PRs have no T id), slice W8c2w. Phase PLAN only (RIPER-5), agent riper-sonnet, direct lane. Branch `claude/w8c2w-stream-wiring-plan`, based on `origin/main` `3cd39e26`. Plan: `w8c2w-stream-wiring_PLAN_30-10-26.md` in this folder.

## 2 Outcome

done (plan written and validated; nothing implemented; one decision is the owner's, see heading 10)

## 3 Summary

- Verified from the repo on `origin/main` (read-only): the merged stream library is called by nothing; `RedditStream._pass` runs only `reddit_web.run_pass`; `registry` already names `reddit_stream`; `sources.PC_STORES` does not; `discovery.json` already has `source_impl.reddit = [reddit_web, reddit_stream]`.
- Found four wiring problems the brief did not name, all in the plan: (1) `Stream.run_pass` returns `done` on an empty search queue and `done` waits for the next UTC day, so polls would run once a day without a schedule hook; (2) `pc_pace.state_path` accepts only `xsearch_web` and `reddit_web`, so `sources._health` raises `ValueError` for a `reddit_stream` row if only `PC_STORES` is extended, and its completeness parser reads the per-coin `reddit_web` format, not the stream's per-day format; (3) slicing the search pass at the next poll time repeats the canary attempt per slice when a canary fails without a pause; (4) `reddit_impl_order` (collector config) and `source_impl.reddit` (Discovery) are two copies of one setting, and `pick_impl` has no production caller.
- Design: stream round inside the existing Reddit pass and lock, shared `reddit_web` `PcSource`, `run_due` then `commit_day` for every `open_days`, search slice cut at the next poll due time (new outcome `stream_due`), schedule hooks, switch `SCREENER_ATTENTION_REDDIT_STREAM` exactly `1` (off by default, no new config key, so no overlap with PR #198), prune of stream day files, Sources mapping to the shared state.
- Budget (owner decision Q1): bound 124 (12 comments polls x 10 requests + 4 posts polls) to 132 (posts at the 12 cap) of 250 in BASELINE, leaving 118-126; of 150 in DEGRADED, leaving 18-26 for about 76 per-coin requests. Options (a) to (d) compared; recommended (d), polls only in BASELINE (the SPEC lists the polls under BASELINE; no key; the primary series stays whole). All figures come from code reading and are UNVERIFIED until probe P-S3.
- Differences on the #198 head (draft, not merged): new keys `reddit_stream_poll_retention_days` and `reddit_stream_max_pages_per_poll`; `stored_polls(until, retention_days)` and `stream_status(now, q, ...)` change; `run_due`, `commit_day`, `open_days`, `due_kinds`, `run_poll`, `read_completeness`, `pick_impl` do not (checked on the `def` lines). EXECUTE starts after #198 merges (gate G0).
- Collision proof: `gh pr list --state open` shows one open PR, #198; its seven files do not intersect the owned set.
- Plan validation: `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs --strict <plan>`: 0 failures, 0 warnings. The brief named `.claude/skills/vc-audit-context/scripts/validate-plan-artifact.mjs`; that file does not exist (the directory holds nine other validators); the script lives under `vc-generate-plan/scripts`.
- Validate Contract: extracted from the plan, `bash -n` OK; the part up to G3 was run against the current `origin/main` and failed where it must: `FAIL: G0 PR 198 not merged on origin/main` and `FAIL: G1 empty change set` (exit 1). G4-G9 were not run (they need the EXECUTE tree).

## 4 Files changed

- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_PLAN_30-10-26.md` (new)
- `process/general-plans/active/w8c2w-stream-wiring_30-10-26/w8c2w-stream-wiring_REPORT_30-10-26.md` (new, this file)

## 5 Commits

One commit on `claude/w8c2w-stream-wiring-plan` (docs only); hash and PR number are in the worker's final message.

## 6 Tests run

No product tests (plan only, no code). Run: the plan validator (strict, 0 failures, 0 warnings); `bash -n` and a partial run of the Validate Contract (heading 3).

## 7 Tests NOT run

- Every test of the plan's section 4 (they do not exist yet).
- Validate Contract G4 to G9.
- All owner probes P-S1 to P-S5 (live behaviour, owner's machine).

## 8 Deviations

1. The brief asked for the validator under `vc-audit-context/scripts`; it is under `vc-generate-plan/scripts` (heading 3).
2. The brief asked for "no angle-bracket placeholders" and for the origin URL to be usable; the envelope therefore carries four `FILL_IN` values (origin URL, repo for `gh -R`, the owner's budget option, #198 merged yes or no) that Main sets, as in the docs-catchup plan. The repository slug is not written in any file.
3. EXECUTE report is placed in the plan folder (`..._EXEC-REPORT_30-10-26.md`), not in the narrative-baskets folder, to avoid a second owner of that folder.
4. The shared worktree held copied parent changes at the start (a named stash, `parent-copy-planwiring`, was made in the isolated checkout, as the brief said); they were not touched.
5. I read about 65 KB of files, a little above the 60,000 B guide, because the verified-input table needed the worker loop, `reddit_web.run_pass`, `sources._health` and the #198 head signatures.

## 9 Blockers

None for this plan. EXECUTE is blocked on: #198 merged, the owner's Q1, Q2, Q6 answers, and Main filling the envelope values.

## 10 Follow-up

- Owner decision Q1 (budget, recommended (d)); also Q2 (env switch versus config key), Q6 (after #198), Q3-Q5, Q7-Q9 (listed in the plan).
- After EXECUTE, the owner runs P-S1 to P-S5; P-S3 turns the 124-132 bound into a measurement.
- If the owner picks option (b) or (c), the plan must be amended first (file set and test list change).
- Not in this slice: a second health line for the stream on a `reddit_web`-reporting row (needs model and `web/`), a window-level method choice in Discovery (Q4), engagement enrichment (W8c3).

## 11 Context and cost

Files read (partly): `reddit_stream.py` (outline, docstring, `run_due`, `commit_day`, `open_days`, `stream_status`), `attention_pc_refresh.py` (outline, `Stream`, `RedditStream`, loop), `reddit_web.py` (outline, `reddit_source`, `search_trickle`, `run_pass`), `pc_pace.py` (outline, spend and unit functions), `sources.py` (`PC_STORES`, `_health`, row builder), `registry.py` and `discovery.py` (by grep), `attention_queries.json` and `discovery.json` (by grep), the W8c2, W8e, W8f, W8g, W8e2-health reports (by grep), the collector SPEC (AC3, AC14, AC26, AC37-AC40, rules 15-16 by grep and cut), the collector PLAN (W8c2 rows by grep), the docs-catchup PLAN (envelope pattern by grep), the plan validator (checks), the #198 head (diff stat, signatures, key lines). Tools: read, grep, bash (git, gh read-only, node, bash -n), edit, write. The plan's envelope measures 4,227 B between the four-backtick fences (cap 8,000 B), first line exactly `ROLE: WORKER`, no angle brackets. Spend of this session is not measured here: UNVERIFIED. EXECUTE cost estimate in the plan: about 3 to 6 USD (UNVERIFIED, from the collector PLAN's W8c2 row).
