## 1 Task ID
T179 (owner answers: Q29 both platforms, curl fallback trigger Cloudflare OR HTML), docs only, same branch claude/t163-reddit-engagement-spec and draft PR #167.
## 2 Outcome
done (docs only).
## 3 Summary
Q29 is decided "both": the host OS is not decided, so the Windows and the Linux curl_cffi==0.16.3 wheel hashes (win_amd64, manylinux x86_64, musllinux x86_64, from the W8a2 report section 9.2) are all pinned in SPEC rule 19; W8d2's installer picks the wheel by platform and records its hash, the startup guard verifies the installed wheel against the matching table entry and refuses an unknown platform or architecture (fallback off, health line says so); the server guide (W8e2, now 3-5 USD) covers Windows (auto-start task, powercfg, w32tm) and Linux (systemd), with the final choice at W8e2 (new Annex J item 11). The fallback trigger is now "Cloudflare OR HTML": it also fires on "Blocked by HTML" (HTML page with status 400 or above on the default backend), with the same limits (flag x_allow_curl_backend default false, one retry in a separate process then pause the UTC day for the pool, never for rate-limit/login/ban codes, logged in evidence and health line). Rule 19, AC46, AC53, W8d1 decision-logic wording, the W8a2 section (C10 recorded as amended) and new Q30 updated; Q29 marked decided. Total 45-60 USD. Re-validated: Gate: PASS.
## 4 Files changed
SPEC (amended), PLAN (amended, T179 validation record), this report, in `process/general-plans/active/narrative-baskets_02-10-26/`.
## 5 Commits
Branch claude/t163-reddit-engagement-spec, PR #167 (SHA in the PR).
## 6 Tests run
No code. Docs gates 24-10-26 UTC: plan validator failures []; only the collector docs changed; no .github/; secret scan clean; git diff --check exit 0; 55 ACs, AC1..AC55 mapped; banned names only in ban sentences.
## 7 Tests NOT run
All code gates (no code). Not proven: that the wheel hashes are current (read from PyPI JSON as text by W8a2, not re-checked), that the Windows and Linux guide commands behave as written (examples, not run), and the owner's approval of the T166 to T179 changes.
## 8 Deviations
Flags. (1) Verifying the "installed wheel hash" cannot be done by hashing the wheel after pip unpacks it, so the startup guard checks the installer's recorded hash (taken from the hash-pinned install) plus the exact installed name and version against the table entry; a stronger check (hashing the installed files against the wheel's RECORD) is left to W8d2. (2) Auto-login: I noted that neither OS needs it because twscrape uses cookies, not a browser session (it was a browser-reader item), which differs from the earlier Annex J item 3. (3) Owner-decided widening: the HTML trigger makes the curl fallback fire more often than the Cloudflare-only trigger of T170; it is still a TLS-fingerprint impersonation that does not reduce ban risk.
## 9 Blockers
Owner: nothing new open from Q29 and Q30; Q21-Q23, Q28 and Q1's remainder (creating the two accounts) are still open. Registry request: T179 done.
## 10 Follow-up
W8d1, then W8d2 (installer by platform, startup hash guard), W8e2 (both OS guide, final choice).
## 11 Context cost
Re-read the lines being amended; about 40k tokens. Scripts and this report written with the file tool; no hook setting was changed.
