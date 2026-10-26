## 1 Task ID
T195 (Trends keyword reverts; narrative-baskets-trends)
## 2 Outcome
done
## 3 Summary
Data-only fix of api/data/trends_keywords.json, owner-approved stage 1 (26-10-26).
- OKB reverted to the T160 entry `okb token` (exact historical term, label and note from 235268e), note extended: "reverted 26-10-26: 'okb crypto' returned 99% zero days, 'okb token' median 65".
- PEARL reverted to `pearl crypto` (exact T160 term, label, note) plus "reverted 26-10-26: 'pearl ai crypto' 98% zero days, 'pearl crypto' median 7".
- PYTH added: `pyth network crypto`, label Pyth Network, note "owner-approved 26-10-26 fallback term, untested; name from CoinGecko id".
- PRL keeps `pearl ai coin`; eligibility untouched; loader (trends_keywords.py) untouched.
- PYTH needs no guard exemption: it is outside the pinned eligible set, so it only appears as a "not a placed coin" warning (same as PRL, STABLE, STX today). Tests updated to expect that warning.
## 4 Files changed
- api/data/trends_keywords.json (OKB, PEARL edited, PYTH added)
- api/tests/data/attention/test_trends_keywords.py (T195 tests; OKB/PEARL removed from T192_TERMS; PYTH added to expected warnings)
- api/tests/data/attention/test_trends_keyword_guard.py (PYTH outside pinned set, warns only)
- this report
## 5 Commits
Branch claude/t195-keyword-reverts from origin/main a155901. SHA in the PR and in the message to the planner.
## 6 Tests run
- RED first: new T195 tests failed on the old data (3 new tests + the meta test) before the data change.
- keyword tests (test_trends_keywords.py, test_trends_keyword_guard.py): 92 passed.
- `pytest api/tests/data/attention api/tests/scripts api/tests/analytics/attention`: 1379 passed.
- full `pytest api`: 2472 passed, 1 skipped, 5 deselected. Main was not re-run; the diff adds 4 tests, so main is expected at 2468 passed.
- ruff on the two touched test files: clean. JSON loads. `git diff --check`: clean. Secret scan of the diff (grep patterns): nothing.
- File-set check: only the files in heading 4.
## 7 Tests NOT run
Main baseline run (cost/time; arithmetic above). No network, no Google contact: the owner's probe is the live check:
`uv run --project api --with pytrends==4.9.2 python -m api.scripts.probe_trends --alone 'OKB,PEARL,PYTH'`
## 8 Deviations
- The brief says 40 topic entries; the shipped file has 41 and the existing test already pins 41 (`ALL_TOPICS`). The new test asserts all topic entries equal that pinned map, so none changed.
- Test constant T192_TERMS no longer lists OKB and PEARL (T195 supersedes them).
- Report placed in a new task folder under process/general-plans/active/.
## 9 Blockers
None. PYTH's term is untested; it may be empty like `okb crypto` was. Run the probe above after merge.
## 10 Follow-up
- Probe OKB, PEARL, PYTH and record medians.
- Owner decision pending: merge PRL and PEARL into one row (same CoinGecko project).
## 11 Context cost
Loaded: CLAUDE.md, the envelope, trends_keywords.py (partial), two test files, git history of the keyword file, master-planner.md section 9. About 40k tokens; spend well under the 2 USD ask. Tools: Bash, Read, Edit, Write, GitHub MCP; no network probe.
