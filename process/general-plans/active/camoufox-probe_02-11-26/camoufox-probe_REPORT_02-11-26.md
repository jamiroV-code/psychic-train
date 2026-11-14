# Camoufox probe: completion report (02-11-26)

## 1 Task ID

camoufox-probe: a LOCAL-ONLY lifecycle/feasibility probe of Camoufox (daijro/camoufox) on the owner's Windows 10 PC. WORKER, direct lane. Branch `claude/camoufox-probe`, worktree `C:/Users/jamir/.herdr/worktrees/my_site/wt-camoufox-probe`.

## 2 Outcome

partial

The probe **stopped at guard G3** (validate-contract): during step 4's same-profile-twice check, a process in the probe's own browser tree opened a TCP connection to a Mozilla Fastly endpoint (`151.101.65.91:80`, ESTABLISHED at 14:12:40Z). That host is not on the allowed list. The envelope says "stop and report, do not improvise", so I stopped there. Steps 1-3 and the sequential half of step 4 are done and measured. Step 5 (cookie export/re-import), the remaining parts of step 6 (exception, close twice, Python-process kill) and the exact same-profile error were **not run**. Concurrent two-profile isolation was **skipped by the RAM guard**.

Go/no-go per use (on this evidence only):

| Use | Verdict | Why |
|---|---|---|
| X cookie-session helper | **NO-GO for now (unproven, not rejected)** | Persistence, crash recovery and profile isolation pass. The core of this use, cookie export and re-import (step 5), was not run. The default identity changes on every launch, even its OS. Pinning fixes the config, but the canvas hash still changes per launch. X's acceptance of the cookies is untested. |
| Reddit browser reader | **CONDITIONAL GO**: one profile at a time, scheduled one after another, headless, background traffic sunk | One browser costs about 0.6-0.9 GB private memory and starts in 13-43 s. It closes cleanly with no orphans. Run concurrently, it does not fit beside the live site (see section 6.7). The condition: first understand the unplanned connection seen in the locked-profile path (section 9). Reddit itself was never contacted. |

## 3 Summary

- Every artifact was fetched on purpose and verified by sha256: wheel `9f063e2c…`, browser zip `2644bd14…` (matches the GitHub API digest), release `manifest.json` `c7472b03…`, fpgen model `6530b832…`. The 0.5.9 wheel pins browser `v158.0.1-beta.41` (Official) and model `model-2/2026`. The installed stack is Playwright 1.62.0 on Python 3.12.14. The first launch downloaded nothing.
- Launch time: 43.2 s for the very first launch, then 13.4-33.3 s. A Windows identity adds a hidden extra probe browser that reads the host GPU (cached per Python process; a cached launch took 3.6 s). Peak memory of the whole tree: 0.69-0.92 GB private, 0.76-0.91 GB working set. Steady idle: 632 MB private, 727 MB working set. The profile on disk is 46-82 MB.
- Persistence: cookies and localStorage survive a graceful reopen. The session cookie does not (normal Firefox behaviour).
- Crash recovery: after a hard kill of the browser, a cookie set 3 s before the kill survived, but a localStorage write from 3 s before the kill was lost. The profile reopened fine even though a stale `parent.lock` was left behind. No orphan processes after a normal close or after the kill. Every child process was gone 0.02-0.06 s after close.
- Identity: without pinning it changes on every launch. The same profile showed Windows → Linux (B) and macOS → Windows (C). Pinning with `fingerprint=` plus a saved JSON keeps all 37 config keys identical, but the canvas hash still changes from launch to launch (it is stable within one session) and `innerHeight` changed.
- Isolation: two profiles opened one after another showed no cookie, localStorage or identity leakage. Concurrent was not run: with one browser open, available RAM fell to 784 MB.
- Network: the 10 clean steps (9 with a browser, 12 main launches) sent every request through a loopback sink and watched sockets; they showed 0 background requests and 0 external sockets. The locked-profile attempt produced the one unplanned connection described above. That attempt hung until the 180 s timeout instead of failing fast.

## 4 Files changed

All files are under `process/general-plans/active/camoufox-probe_02-11-26/`. Docs and evidence only; nothing in `api/`, `web/` or `.github/` changed.

- `camoufox-probe_VALIDATE-CONTRACT_02-11-26.md`: the gate list, written before anything was installed or run
- `camoufox-probe_REPORT_02-11-26.md`: this report
- `probe/camoufox_probe.py`: the probe harness (loopback origin, loopback sink, process-tree monitor, steps)
- `probe/run_step.sh`: the step runner (redirects caches and temp into the probe root)
- `probe/evidence/*.json`: raw measurements per step, plus `artifacts.json` (hashes, pairing, locations, hosts)
- `probe/evidence/requirements.lock.txt`, `probe/evidence/probe-tools.lock.txt`: the hash-pinned install locks

## 5 Commits

Branch `claude/camoufox-probe`:

- `39030645` docs(camoufox-probe): validate-contract before probe
- `2d9941b7` docs(camoufox-probe): probe harness and raw measurement evidence
- report commit: see the PR (this file)

## 6 Tests run

All steps ran on the owner's PC, headless, against the loopback origin `http://127.0.0.1:18765` served by the probe itself. Firefox proxy prefs pointed every request at a loopback sink on `127.0.0.1:18766`, which logs the target host and answers 403 without forwarding. The sink settings were `network.proxy.type=1`, http/ssl `127.0.0.1:18766`, `no_proxies_on=127.0.0.1,localhost`, `failover_direct=false` and `network.trr.mode=5`. A socket watcher (psutil, every 1 s) listed every non-loopback socket held by the process tree. Commands were run from `probe/` as `bash run_step.sh <step>`. Each step's evidence is in `probe/evidence/<step>.json`.

The steps ran on base commit `f5194a5c`. The harness was committed later in `2d9941b7`. Between runs I made two edits to the harness: I added the `config_determinism` and `canvas_stability` steps, and I added the extra-browser RAM headroom guard before `isolation_concurrent`. The earlier steps' code paths did not change.

| Step (UTC 02-11-26) | Result |
|---|---|
| lifecycle 14:00:21-14:01:26 | ok |
| reopen 14:01:41-14:02:09 | ok |
| pinned_create 14:02:20-14:02:45 | ok |
| pinned_reopen 14:02:47-14:03:08 | ok |
| config_determinism 14:04:03-14:04:42 (no browser) | ok |
| canvas_stability 14:04:46-14:05:11 | ok |
| crash 14:05:41-14:06:06 | ok |
| after_crash 14:06:10-14:06:49 | ok |
| isolation_seq 14:07:00-14:08:06 | ok |
| isolation_concurrent 14:08:51-14:09:24 | RAM guard: second browser not launched |
| same_profile_twice 14:09:55-14:13:20 | error: child attempt hung until `TimeoutExpired(180)`; **G3 tripped**, probe stopped |

### 6.1 Artifacts and setup (step 1)

| Item | Value |
|---|---|
| Disk free (C:) | 31.93 GiB before, 27.65 GiB after (14:15:51Z). The guard required at least 6 GiB. |
| Python | uv-managed CPython 3.12.14 (already on the PC) in venv `C:/Users/jamir/camoufox-probe/venv` |
| Install | `uv pip compile requirements.in --generate-hashes` (pins `camoufox==0.5.9`), then `pip install --require-hashes --no-deps --only-binary :all: -r requirements.lock.txt`. Separately, `psutil==7.2.2` was installed the same hash-pinned way, for measurement only. |
| Resolved | camoufox 0.5.9, playwright 1.62.0, fpgen 1.3.0, plus 39 transitive packages (lock in evidence) |
| Wheel | `camoufox-0.5.9-py3-none-any.whl`, 222,658 B, sha256 `9f063e2c0356491221a53dc93148174f5fe854382eda9570e30572f10759f577`, equal to the PyPI JSON digest |
| Pairing | `camoufox/browser-pin.json`: `v158.0.1-beta.41`, Official, daijro/camoufox. Installed `application.ini`: Version `158.0.1-beta.41`, BuildID `20261029202019` |
| Browser zip | `camoufox-158.0.1-beta.41-win.x86_64.zip`, 1,320,075,455 B, sha256 `2644bd14f1cc345c768f6a70b576bcc87eb3d0bf0df54856d6fe0bbc3027515f`, equal to the GitHub API digest. Download took 666 s. |
| Model | fpgen `model-2/2026` `model-release.zip`, 1,564,571 B, sha256 `6530b8322cdaa4ec042921c8d9a0369a0e6e0269ba636c01a7203e4a2f109936`, equal to the wheel's `fpgen-model.json` |
| Browser install | I ran the library's own `CamoufoxFetcher.install()` / `install_versioned()`, fed from the verified local zip: `download_file` was intercepted and `requests.get` was stubbed to raise. The library re-checked the sha256, extracted the build and set it active. It took 48.9 s. |
| Model install | `ensure_fpgen_model()`, fed from the local zip (`webdl` intercepted). The library checked the archive and each member's sha256 and wrote the stamp. |
| Cache location | Camoufox's `INSTALL_DIR` is platformdirs `user_cache_dir("camoufox")`. I redirected it with platformdirs' supported override `WIN_PD_OVERRIDE_LOCAL_APPDATA` to `C:/Users/jamir/camoufox-probe/localappdata/camoufox/camoufox/Cache`. `TEMP`/`TMP` pointed at `C:/Users/jamir/camoufox-probe/tmp`; `PLAYWRIGHT_BROWSERS_PATH` pointed at the probe root and stayed empty. |

Implicit downloads I found in the library source (all avoided here):

- `camoufox_path()` installs the browser from api.github.com plus the release asset when none is installed. That covers the first launch.
- `release_interface()` GETs the release's `manifest.json`.
- `ensure_fpgen_model()` downloads the model from github.com on the first fingerprint generation.
- fpgen on its own fetches from api.github.com with `verify=False` and no checksum; camoufox bypasses this by pinning the model.
- With `geoip=`, it calls ipify, amazonaws, ipinfo, icanhazip, ifconfig.co, ipecho, api6.ipify.org, v6.ident.me and ip-api.com, and refreshes the GeoIP database weekly from github.com/daijro/geoip-all-in-one. This was not used.
- The default uBlock Origin add-on is bundled (`addons/UBO`), not downloaded. In 10 steps it sent nothing to the sink.

### 6.2 Launch lifecycle (step 2, profile A, `lifecycle.json`)

| Metric | Value |
|---|---|
| Free RAM before launch | 1,843 MB |
| Launch (`Camoufox(...).__enter__`) | 43.23 s (first launch ever; includes the host-GPU probe browser) |
| First page load (loopback) | 0.59 s |
| Process tree | 2 `node.exe` (Playwright driver; one belongs to the GPU-probe launch) plus up to 9 `camoufox.exe`. 19 PIDs over the step, at most 11 at once. |
| Memory, startup window | peak 777 MB private, 846 MB working set (mean 344 / 423) |
| Memory, steady idle 20 s | mean 632 MB private, 727 MB working set (max 804 / 864) |
| Memory, step peak | 916 MB private, 914 MB working set |
| CPU time, whole tree | 60.7 CPU-s for launch, 20 s idle and close |
| Profile disk | 0 → 47.4 MB |
| Close | `__exit__` 0.55 s; every child gone 0.02 s later; 0 survivors |

Other launches: 13.4-33.3 s (median about 21.7 s), and 3.56 s when the GPU probe was cached in the same process (`isolation_seq` C-reopen). Peak private memory per step was 687-855 MB. CPU per launch-plus-short-session was 39-73 CPU-s.

Cause of the slow launches: when the identity's OS is the host's OS (Windows), `launch_options()` starts a whole extra browser to read the host GPU (`host_rendering._host_gpu`, `lru_cache` per process). This happens before the real launch and is hidden from the caller.

### 6.3 Persistence and identity (step 3)

Profile A, unpinned (`reopen.json`, `after_crash.json`):

- After a graceful reopen, the cookies `acct`, `auth_token`, `ct0` and the localStorage keys were retained. The session cookie `sess_marker` was dropped.
- The server saw `auth_token`/`ct0` with value `FAKE`, checked by booleans only.

Identity with no pinning:

- `launch_options()` called twice gives 31 of 37 config keys different (`config_determinism.json`): UA, platform, screen, WebGL, fonts, voices and media devices.
- Measured in the browser, the same profile reopened with a different identity:
  - B went from Windows 1366×768 to **Linux** 3840×2160.
  - C went from **macOS** 1920×1080 to Windows 1920×1080.
  - A kept Windows each time, but the screen changed (2560×1440 to 1366×800) and so did the window size and the canvas hash.
- Cookies stay with the profile while the device changes underneath them. **Profile persistence does not pin identity.**

Identity with pinning (`pinned_*.json`, `config_determinism.json`, `canvas_stability.json`):

- API: generate `fp = camoufox.fingerprints.generate_fingerprint(os="windows")` once and save it as JSON next to the profile (`profiles/P.identity.json`, 587 KB). Then launch with `Camoufox(headless=True, persistent_context=True, user_data_dir=<profile>, fingerprint=json.load(...), i_know_what_im_doing=True)`. Passing a fingerprint seeds `identity_salt`, so fonts, voices, media devices and the GPU draw follow it.
- Result: `launch_options()` twice gives **0 of 37** config keys different and 0 prefs different.
- In the browser, UA, platform, oscpu, hardwareConcurrency, screen, outerWidth/Height and the WebGL vendor/renderer were identical across reopen.
- **Not stable:** the canvas hash differed across all three pinned launches (`a9ea…`, `959a…`, `6cd3…`) but was identical 4 of 4 times within one session (same page twice, after reload, in a second page). `innerHeight` also changed (1067 vs 1026).
- The library has no canvas pin: `canvas:seed` is listed as removed since `156.0.1-beta.32` in the build's `properties.json`. Canvas noise is off for a native Windows identity on this host. The cause of the per-launch canvas change is **unproven**.
- Every identity reported the host's timezone, including the Linux and macOS ones, because no locale or geoip was given. The values are redacted in the committed JSON because the repo is public.

Crash (`crash.json`, `after_crash.json`):

- I hard-killed the 7 `camoufox.exe` processes of the tree (TerminateProcess). They were gone in 0.16 s.
- Playwright raised `TargetClosedError('Page.evaluate: Target page, context or browser has been closed')`. `__exit__` then took 0.02 s and left 0 survivors (the driver exited by itself).
- `parent.lock` was left in the profile, but the next launch opened the profile normally. It was not locked or corrupted.
- The cookie `precrash_marker`, set 3 s before the kill, was **recovered**. The localStorage key `precrash_ls`, written 3 s before the kill, was **lost**. The older localStorage was intact.

### 6.4 Isolation (step 4)

Sequential (`isolation_seq.json`):

- Profiles B and C were each created, then each reopened.
- Each one saw only its own `acct` cookie and `probe_acct` localStorage, both in `context.cookies()` and in what the server received.
- The identities were unrelated.

Concurrent (`isolation_concurrent.json`): **skipped by guard.**

- Before profile B launched, 1,299 MB of RAM was available. With B open (a tree of 787 MB private), only 784 MB remained.
- A second browser needs about 800 MB on top of the 600 MB floor, so C was not launched.
- B's reopen check passed in that step.

Same profile twice (`same_profile_twice.json`): **not cleanly measured.**

- B was held open, and a child process then tried `Camoufox(user_data_dir=B, os="linux")`.
- The attempt did not raise a rejection error. It hung until my 180 s subprocess timeout, which is also Playwright's default launch timeout, so the exact error text was not captured.
- During the hang, the unplanned external connection happened.
- Because the step ended with an exception, the holder was not closed by the step. Its driver and browser (8 PIDs) exited by themselves after the probe's Python process ended; a check minutes later found no probe processes.

### 6.5 Cookie export (step 5)

Not run (stopped at G3). No cookie file was written. `C:/Users/jamir/camoufox-probe/private` does not exist.

### 6.6 Cleanup and robustness (step 6, measured part)

- Normal close: 10 of 10 graceful `__exit__` closes took 0.47-1.25 s, every child was gone within 0.00-0.06 s after, and there were 0 orphans. `isolation_concurrent` closed through `context.close()`; its tree was gone 0.02 s later.
- After a browser kill: the browser was gone in 0.16 s; the driver exited when `__exit__` ran; 0 orphans.
- After the Python process ended abnormally (the same-profile step): the driver and browser exited by themselves. The exit time was not measured precisely.
- Not run: exception inside the `with` block, closing twice, and a hard kill of the Python process alone.

### 6.7 Cost summary (step 7)

| Cost | Measured |
|---|---|
| Download (browser zip) | 1,258.9 MiB (1,320,075,455 B) |
| Extracted browser | 2,468 MB, 2,241 files; `fonts/` alone is 2,057 MB in 1,513 files |
| venv | 209 MB (5,031 files) |
| Profile | about 47 MB after one session; 82 MB for B after 5 sessions |
| Pinned identity file | 587 KB per profile |
| Memory per browser (1 profile, 1 loopback page) | steady about 630 MB private / 730 MB working set; peak 0.69-0.92 GB |
| Extra profile, concurrent | another full browser (no sharing between separate `launch_persistent_context` calls); expect +0.7-0.9 GB |
| Startup | 43 s cold first launch; 13-33 s typical; 3.6 s when the host-GPU probe is cached in the process |
| CPU | 39-73 CPU-s per launch plus a short session |

On this 8 GiB PC, with the live API, web app and collector running, available RAM was 1.0-1.9 GB during the probe. One Camoufox fits. Two at once would leave about 0-200 MB, below the 600 MB floor. **2-3 profiles are feasible only one after another. The safe concurrency is 1**: one profile at a time, scheduled sequentially, with a launch budget of about 15-45 s per profile.

### 6.8 Licences, supply chain and network (step 8)

What I read from the actual files:

- Wheel: `camoufox-0.5.9.dist-info/licenses/LICENSE` is MIT. Its METADATA says "The browser itself is MPL-2.0".
- Dependencies (package metadata): MIT, BSD, Apache-2.0, MPL-2.0 (certifi, ansicon, jinxed, orjson) and PSF; fpgen is Apache-2.0. The full list is in this session's command output.
- Browser bundle: Firefox's `about:license` (`omni.ja` `chrome/toolkit/content/global/license.html`) is present.
  - It includes the Disconnect.me blocklist notice: licensed for use **outside Firefox** under **CC BY-NC-SA 4.0** (NonCommercial). Camoufox is a Firefox fork, so this is a second non-commercial caveat.
  - uBlock Origin (`addons/UBO/LICENSE.txt`) is GPL-3.0.
- **Fonts:** `fonts/` holds 1,513 files (2,057 MB), including proprietary families such as Arial, Georgia, Tahoma and Courier New (Microsoft) and Baskerville and Rockwell. It has **no licence file** for these fonts. This matches the owner-accepted caveat: personal use only, **never redistribute the browser or its fonts**. I could not verify the upstream non-commercial wording locally, because no file in the bundle states it; it comes from the prior research.

Telemetry and network: in the 10 clean steps (12 main launches plus their hidden host-GPU probe launches), idle on the loopback page, the sink logged **0** requests and the socket watcher saw **0** non-loopback sockets. In the locked-profile attempt, the watcher saw 5 records from PID 21584 in the probe tree:

- SYN to `151.101.1.91:80`
- SYN to `[2a04:4e42:400::347]:80`, `[2a04:4e42:600::347]:80` and `[2a04:4e42:200::347]:80`
- **ESTABLISHED** to `151.101.65.91:80` at 14:12:40Z

To attribute it, I resolved 39 candidate hostnames by DNS only, with no connections. Those IPs belong to Mozilla's shared Fastly endpoints: `addons.mozilla.org`, `services.addons.mozilla.org` and `tracking-protection.cdn.mozilla.net` resolve to exactly `151.101.{1,65,129,193}.91` and `2a04:4e42:{200,400}::347`. The exact host, URL and process name were **not captured**. The likely cause is that the second Firefox instance, refused by the profile lock, ran without the sink prefs, but that is not proven.

### 6.9 Hosts contacted

| Host | Purpose |
|---|---|
| github.com | `git fetch origin main`; release asset URLs |
| release-assets.githubusercontent.com | redirect target for the browser zip, manifest and model |
| api.github.com | release metadata, and the `gh` CLI for this PR |
| pypi.org | package JSON; simple index for uv and pip |
| files.pythonhosted.org | wheels |
| Mozilla Fastly IP 151.101.65.91:80 | **unplanned**, by the browser tree; SYN-only to 151.101.1.91 and 3 IPv6 addresses (section 6.8) |

DNS-only lookups: 39 names, listed in this session's command output (Mozilla, uBO list, OCSP and ip-lookup hosts).

## 7 Tests NOT run

- Step 5, cookie export with a restricted ACL and re-import into a fresh profile: not run because the probe stopped at G3. The harness step `cookie_export` exists but is unexecuted.
- Step 4, concurrent two-profile isolation: skipped by the RAM headroom guard (784 MB available with one browser open).
- Step 4, the exact error for the same profile opened twice: not captured. The attempt hung for 180 s instead of raising an error.
- Step 6, exception inside `with`, close twice, and a hard kill of the Python process alone (`exception`, `close_twice`, `kill_python`): not run because of G3.
- Never proven, by design: no contact with X or Reddit. Whether X accepts exported or re-imported cookies, and how X or Reddit react to Camoufox fingerprints, is **unproven**.
- Font coverage: the `document.fonts.check()` probe returned true for every family, which tells nothing, so the font list was compared only through the config (`config_determinism`).
- The cause of the per-launch canvas change under a pinned identity was not established.
- Headed mode and proxies: out of scope.
- No repo test suites were run; this is a docs-only change.

## 8 Deviations

- I installed `psutil==7.2.2` (hash-pinned) into the throwaway venv for process-tree and socket measurement. The envelope names psutil as a measurement option.
- I added a loopback-only sink proxy (`127.0.0.1:18766`, never forwards) through Firefox prefs. Its purpose was to stop background traffic from leaving the host and to observe it. It is not an egress proxy. The envelope's "no proxies" was read as no outbound or residential proxies.
- I fed the browser and model installs from verified local files by intercepting the library's download functions, instead of letting the library download them itself. The library's own sha256 checks still ran.
- Concurrent RAM guard: I required 600 MB plus about 800 MB of headroom before launching a second browser, stricter than the plain 600 MB floor. With 784 MB available, a second browser would have taken the host below the floor.
- Before committing, I redacted the host timezone in the evidence JSON (public repo) and replaced it with `HOST_TZ_REDACTED`. There was exactly one distinct value, the host's own.
- The cleanup was not done. The owner has not yet approved the evidence, so the probe root was left in place: `C:/Users/jamir/camoufox-probe`, about 4.2 GB in total (downloads 1,261 MB, browser 2,468 MB, venv 209 MB, profiles 223 MB, caches 63 MB). Two **empty** directories created by the browser are also left: `%APPDATA%\camoufox\Profiles` and `%LOCALAPPDATA%\camoufox`.

## 9 Blockers

- **G3 tripped: one unplanned external connection** (section 6.8), by a browser-tree process during the locked-profile attempt. Per the envelope, I stopped and am reporting rather than continuing. The owner decides whether the remaining steps may run. A suggested mitigation for a rerun is to skip the locked-profile attempt, or to run it with Windows Firewall rules for `camoufox.exe` from the probe root; those rules need owner approval because they change config.
- Risk for any real use: a second launch on an open profile hangs instead of failing fast. A real scheduler must hold its own lock per profile.
- Risk: identity does not survive a reopen unless it is pinned, and the canvas hash changes per launch even when pinned. For a cookie-bound login like X, this is an inconsistency signal whose effect is unproven.
- Risk: launch quietly starts an extra browser to probe the host GPU, which adds time and transient memory.
- Licence risk: the bundled proprietary fonts have no licence, and the Disconnect list is CC BY-NC-SA outside Firefox. This fits personal use only; never redistribute.
- Registry update request: record camoufox-probe as `review` with outcome partial (stopped at G3), with steps 5 and 6 and concurrent isolation pending the owner's decision.

## 10 Follow-up

1. Owner decision: allow a rerun of the remaining steps (`cookie_export`, `exception`, `close_twice`, `kill_python`) with the same harness. They use the same launch configuration as the 10 clean steps. The locked-profile check would be dropped, or run under a firewall rule.
2. If the X helper is still wanted: probe canvas stability under a pinned identity (`canvas_noise=False` explicitly; one long-lived process versus fresh processes) and decide whether a per-launch canvas change is acceptable.
3. If the Reddit reader proceeds: design it for one browser at a time, a per-profile lock file, a pinned identity per profile, the background-traffic sink prefs, and a 60 s launch timeout instead of 180 s.
4. After the owner approves this evidence: delete `C:/Users/jamir/camoufox-probe` (about 4.2 GB) and the two empty `camoufox` directories under `%APPDATA%` and `%LOCALAPPDATA%`.

## 11 Context cost

Files loaded: AGENTS.md (entry set and permissions), master-planner.md sections 6-9 (on demand), `api/tests/deploy/test_lane_scope.py` and the `.github/workflows` grep (read-only, to predict CI scope), and the Camoufox wheel source (`browser_pin.py`, `pkgman.py`, `multiversion.py`, `fpgen_model.py`, `utils.py`, `sync_api.py`, `fingerprints.py`, `host_rendering.py`, `addons.py`, `repos.yml`, `fpgen.yml`) plus fpgen and platformdirs source in the venv. About 120k tokens (estimate, unmeasured). Tools: read, bash, edit, eval (Python), grep, glob, write, wait; GitHub through the `gh` CLI. No subagents.
