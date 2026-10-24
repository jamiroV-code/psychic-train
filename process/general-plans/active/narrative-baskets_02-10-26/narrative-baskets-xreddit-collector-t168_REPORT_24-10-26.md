## 1 Task ID
T168 (owner answers Q20, Q24-Q27; curl-cffi fallback), docs only, same branch claude/t163-reddit-engagement-spec and draft PR #167.
## 2 Outcome
done (docs only).
## 3 Summary
Q20 (accept all four), Q25 (2 accounts now, owner creates, third after a clean fortnight), Q26 (least recently used) and Q27 (25 percent and 0.6) are marked decided by the owner on 24-10-26. Q24 is decided YES for the curl-cffi backend as a FALLBACK only: new SPEC rule 19 and AC53 (53 ACs): the default backend is tried first for every unit; the curl backend is used only after a Cloudflare or HTML block on the default and only when the owner flag x_allow_curl_backend is true (default false); one retry, then the UTC day is paused for the whole pool; never for rate-limit, login or ban codes; no user-agent override, no proxy, no other disguise; every use logged in the evidence and the health line; reads count against the global budget; curl_cffi is pinned (exact version and hash) in the optional dependency group, imported lazily only with the flag on, with an exact-name guard. PLAN: W8a2 now also vets the curl_cffi supply chain (3-4 USD), W8d2 carries the fallback (6-8 USD), W8d1 carries the decision logic; total 43-57 USD. Re-validated: Gate: PASS.
## 4 Files changed
SPEC (amended), PLAN (amended, T168 validation record), this report, in `process/general-plans/active/narrative-baskets_02-10-26/`.
## 5 Commits
Branch claude/t163-reddit-engagement-spec, PR #167 (SHA in the PR).
## 6 Tests run
No code. Docs gates 24-10-26 UTC: plan validator failures []; only the collector docs changed; no .github/; secret scan clean; git diff --check exit 0; 53 ACs, AC1..AC53 mapped; banned names only in ban sentences.
## 7 Tests NOT run
All code gates (no code). Not proven: that the curl backend gets past the block, that curl_cffi is safe (its wheels bundle compiled impersonation binaries: W8a2 vets it), the twscrape API names, and the owner's approval of the T166-T168 changes (relayed by the planner, not seen here).
## 8 Deviations
Honest note: browser TLS impersonation is a detection-evasion technique that rules 5, 8 and 17 excluded. I wrote it as the single narrow exception the owner decided (accepting the ban and terms-of-service risk on throwaway accounts) and edited rules 8, 17 and 18 so the text says so instead of contradicting itself; it stays narrow: a flag defaulting to off, one retry after a block, no user-agent override, no proxy, no other disguise. Q20's four items are assumed exactly as I proposed them (3-6 minutes as the minimum with units spread evenly, Reddit 250 per day, t=week, addenda approved).
## 9 Blockers
Owner: nothing new open from Q20 and Q24-Q27; Q21-Q23 and Q1's remainder (creating the two accounts) still open. W8a2 needs add_repo read access to vladkens/twscrape and curl_cffi's project, and the pending reference file. Registry request: T168 done.
## 10 Follow-up
W8a2 (vet twscrape and curl_cffi), then W8d1 and W8d2; the owner sets x_allow_curl_backend only after the W8a2 verdict.
## 11 Context cost
Re-read the lines being amended; about 35k tokens. Scripts and this report written with the file tool; no hook setting was changed.
