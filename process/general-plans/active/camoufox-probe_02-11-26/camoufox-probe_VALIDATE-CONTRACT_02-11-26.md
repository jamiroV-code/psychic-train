# Camoufox probe: validate-contract (02-11-26)

Task: camoufox-probe, a LOCAL-ONLY lifecycle/feasibility probe of Camoufox (daijro/camoufox). WORKER, direct lane.
Branch: `claude/camoufox-probe`. Worktree: `C:/Users/jamir/.herdr/worktrees/my_site/wt-camoufox-probe`.
Written BEFORE any install, download or launch (master-planner.md section 6).

## Scope

- Owned (repo): `process/general-plans/active/camoufox-probe_02-11-26/**` only (report, this contract, probe scripts, raw JSON).
- Owned (outside repo, throwaway): `C:/Users/jamir/camoufox-probe/**` (venv, browser cache, profiles, downloads, exported cookie file).
- Forbidden: `api/**`, `web/**`, `.github/**`, `api/pyproject.toml`, `api/uv.lock`, the main checkout `C:/Users/jamir/Documents/my_site`, other worktrees, scheduled tasks, live API/web/collector processes, `C:\xpool`, `C:\secrets`, any real browser cache/cookies/accounts.

## Gates (each must hold; a tripped guard = stop and report)

| # | Gate | Check | Stop condition |
|---|---|---|---|
| G1 | Disk | free GiB on C: before downloading | < 6 GiB free |
| G2 | RAM | available RAM recorded before every browser launch | < 600 MB available: skip/abort that step, report |
| G3 | Hosts | only pypi.org, files.pythonhosted.org, github.com / release-asset CDN (objects.githubusercontent.com / release-assets.githubusercontent.com) and whatever host Camoufox's own fetch names (inspected in source before any fetch) | any other host would be contacted |
| G4 | Pinning | camoufox==0.5.9 and every dependency installed with `pip --require-hashes` from hashes read from PyPI JSON; browser zip sha256 compared to the GitHub API digest | hash mismatch |
| G5 | No implicit downloads | browser + model fetched deliberately into the probe cache dir; first launch must not download anything (verified by cache listing before/after) | library starts an unplanned download |
| G6 | Live processes untouched | process kills only target PIDs that the probe itself spawned (tree rooted at the probe's own browser) | any kill would target a pre-existing PID |
| G7 | Headless, one browser at a time | only step 4's concurrent check runs two | n/a |
| G8 | Loopback only | test origin is `http.server` on 127.0.0.1; pages navigate only there | any navigation off loopback |
| G9 | No secrets | fake cookie values only (`auth_token=FAKE`, `ct0=FAKE`); exported cookie values never printed; export file lives under `C:/Users/jamir/camoufox-probe/` with restricted ACL | any real credential seen |
| G10 | Repo hygiene | staging by explicit path; diff limited to the task folder; draft PR; no merge | any file outside the task folder staged |
| G11 | CI | CI green on the final PR head (docs-only) | red CI: report |

## Retry budget

2 fix cycles per failing step; same failure twice stops (operating-instructions "Bounded retry").

## Evidence

Raw measurement JSON and the probe scripts are committed in this folder; the report cites them.
