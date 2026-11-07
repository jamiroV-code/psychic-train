---
slug: collector-identity-pool-finish-probes-2
date: 2026-11-07
verdict: NOT-VIABLE
originating-phase: execute-stage-0
probes:
  BP1c: NOT-VIABLE
  BP3c: VIABLE-WITH-AMENDMENT
gates:
  BG-1: FAIL
  BG-3: NOT-MET (SID identified; A10(ii) scope refuted; O-1 pending)
---

# Collector finish — Stage-0 probes BP1c and BP3c

## Hypothesis

- **BP1c:** with the A5/A8 corrected flags (`--proxy-bypass-list=<-loopback>`, `--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1`, `--webrtc-ip-handling-policy=disable_non_proxied_udp`, QUIC off), every Edge network path goes through the loopback CONNECT relay or fails. That covers redirects, IP literals, service workers, WebSocket, WebRTC, DNS, background hosts and proxy outage. Allowed traffic leaves as a numeric CONNECT with the original SNI.
- **BP3c (H-CE1):** the AppContainer capability SID that Edge adds under `Default\Network` (BP3b) is derived from a Chromium network-sandbox capability name. It is the same on every fresh profile and after a restart, and A10(ii)'s narrow exception CE-1 describes the browser-made ACL tree completely.

## Mechanism Under Test

Plan revision 3 (`collector-identity-pool-finish_PLAN_06-11-26.md`), A5, A6, A6c, A8, A10(ii) and gates BG-1 and BG-3. The installed browser is now **Edge 157.0.4341.42**. It auto-updated from the 156.0.4314.58 that BP1/BP2/BP3b used, so this run is also a first cross-version check.

## Probe Family

- BP1c: **6 — Browser / CDP capture**, with real disposable headless Edge and loopback fixtures. No CDP was needed: the hostile page POSTs its results to the fixture origin through the relay.
- BP3c: **1 — Local process** (native Win32 `DeriveCapabilitySidsFromName`, process-token inspection and ACL reads) plus **6** (real Edge sessions).

## Probe Cost Class

**needs-browser** and **cheap-local**. Only loopback fixtures and disposable `%TEMP%` directories were used. The browser profiles were new, so the user's Edge profile was never opened. The probes sent no request to X, Reddit or a provider, used no accounts or credentials, and changed no trust store, firewall, Edge policy registry or ACL outside the new temp roots. One unintended egress happened: the browser itself opened non-proxied connections (see BP1c). The probe recorded them; it did not ask for them.

## Probe Method

Interpreter: `C:/Users/jamir/.herdr/worktrees/my_site/wt-b2-validate/api/.venv/Scripts/python.exe`. Scripts were `bp1c.py` and `bp3c.py` under `C:/Users/jamir/AppData/Local/Temp/collector-bp-probes2/`, and both were deleted afterwards. Each script made its own `tempfile.mkdtemp` root (`bp1c-*`, `bp3c-*`) and removed it in `finally`. Every run printed `temp_removed True`.

**BP1c topology:** Edge → loopback relay that accepts only `CONNECT allowed.test:443`, logs every other request line by authority and answers 403 before any dial → loopback fake upstream that accepts only `CONNECT 93.184.216.34:443` → loopback TLS origin. The fixture dialer maps the numeric token to loopback. The certificate is synthetic, made in-process with `cryptography`, and pinned with `--ignore-certificate-errors-spki-list`; nothing went into the trust store. The script also ran:

- a loopback TCP sentinel (any accept counts as a direct hit);
- a loopback UDP sentinel (used as the STUN target);
- 1 Hz polls of `Get-NetTCPConnection` for every `msedge.exe` whose command line contains the probe's `--user-data-dir`, recording non-loopback remote endpoints and the owning process type. This is an OS-level, per-process signal, not packet capture;
- a `Get-DnsClientCache` check for a unique random sentinel name after the run.

The hostile page sends these requests:

- same-origin fetch;
- a 302 redirect to `off.test`, by fetch and by iframe;
- fetches to `off.test`, plus the background hosts `edge.microsoft.com` and `www.bing.com`;
- loopback literals `https://127.0.0.1:<S>`, `http://127.0.0.1:<S>` and `https://localhost:<S>`;
- non-loopback literals `https://192.0.2.1`, `http://198.51.100.7`, `http://169.254.169.254`, `https://93.184.216.34` and `http://[2001:db8::1]`;
- the DNS sentinel `https://bp1c-dns-<rand>.test`;
- WebSockets to `wss://allowed.test/ws` (real 101), `wss://off.test` and `ws://127.0.0.1:<S>`;
- a service worker whose fetches go to the allowed origin, `off.test`, `127.0.0.1:<S>` and `192.0.2.1`;
- WebRTC ICE gathering with `stun:127.0.0.1:<U>`, `stun:192.0.2.1:3478` and no servers.

After the report arrives, the harness closes the relay listener and every open tunnel. Six seconds later the page makes outage fetches and a navigation. The harness watches for 12 s.

Three runs:

- **R1:** the exact A5/A8 flags.
- **R2:** R1 again, with process attribution added.
- **R3:** R1 plus `--disable-features=DnsOverHttps,AsyncDns,MediaRouter,DialMediaRouteProvider,CastMediaRouteProvider,GlobalMediaControls,msImplicitSignin,msEdgeAutoSignIn,msSingleSignOnOSForPrimaryAccountIsShared --media-router=0`. Chromium honours only the LAST `--disable-features`, so the base list is merged into it.

Other flags in every run: `--headless=new --disable-quic --disable-background-networking --disable-component-update --disable-sync --disable-extensions --disable-domain-reliability --no-first-run --no-default-browser-check`.

**BP3c:** two roots, `pa` and `pb`, created natively with SDDL `O:<user>D:P(A;OICI;FA;;;<user>)` through `CreateDirectoryW`. There were three headless sessions: `pa` first, `pa` restart and `pb` first. Each pointed at a dead proxy (`127.0.0.1:9`) with the A5 bypass and resolver flags, ran for 10 s, and was then killed with `taskkill /T`. For each session the script read:

- the token capabilities (`TokenCapabilities`) and AppContainer SID of every process in the tree;
- the ACLs of the named sensitive paths;
- every non-owner ACE in the whole tree, via a recursive `Get-Acl`.

For the candidate names, it took a curated list plus every UTF-16 identifier in `157.0.4341.42\msedge.dll`/`msedge_elf.dll` that matched `lpac|Network|Sandbox|Capabilit` (57 names), ran `DeriveCapabilitySidsFromName` on each, and compared the results with the observed SIDs.

## Evidence Captured

| Probe | Verdict | Decisive observation |
|---|---|---|
| BP1c | NOT-VIABLE | The relay refused everything off the allowlist, and the loopback TCP and UDP sentinels got 0 hits. But the OS TCP table showed **direct, non-proxied connections owned by the disposable Edge**: the NetworkService opened `192.168.10.213:8009` (Cast on the LAN), and the **browser process** opened `52.97.x:443` / `40.99.x:443` (Microsoft ranges). Disabling the media router removed the Cast connection. The browser-process connection to Microsoft stayed in every run. |
| BP3c | VIABLE-WITH-AMENDMENT | The observed SID = `DeriveCapabilitySidsFromName("lpacEdgeStableNetworkSandbox")`. It was identical on both profiles, after the restart and on Edge 156 (BP3b) and 157. No running process held it. The ACEs reach **beyond `Default\Network`**, and Edge also adds **Everyone (S-1-1-0) rights 32** ACEs to LevelDB files. A10(ii) as written would refuse every Edge profile. |

## Verdict

**NOT-VIABLE overall.** BG-1 fails: BP1c observed a direct external connection from the browser process that the relay flags do not control. BG-3 stays unmet. The SID is now identified, which is the precondition BP3c was meant to settle, but CE-1's scope in A10(ii) is refuted by observation and has to be amended before O-1 can be put to the owner meaningfully.

## Resulting Design Constraint

- **Licenses:**
  - Inside Chromium's net stack, the corrected flags hold on Edge 157: no direct loopback TCP, no UDP, no ICE candidates, no OS DNS lookup, a hard proxy failure on outage, a numeric upstream CONNECT and the original SNI.
  - CE-1 can be pinned by **derivation**, not by first sight: expected SID = `DeriveCapabilitySidsFromName("lpacEdgeStableNetworkSandbox")`.
- **Forbids:**
  - Claiming `containment: tested_channels` or "no direct path" for Edge on the strength of the relay flags.
  - Treating `--disable-background-networking` or any feature flag as egress control.
  - The A10(ii) wording "only on `Default\Network` and its descendants".
  - Rejecting every group SID without first deciding what to do about Everyone `FILE_EXECUTE` on LevelDB files.
- **Required plan changes** are listed in the BP1c and BP3c sections.

## BP1c — Corrected-flag relay leak probe

**Evidence (R1 and R2 match; R3 differs only where noted):**

```text
Edge 157.0.4341.42
relay accepted CONNECT allowed.test:443 = 3; upstream: 3 x CONNECT 93.184.216.34:443 HTTP/1.1; TLS SNI = {allowed.test}
origin paths: / /api /redirect /favicon.ico /redirect /ws /sw.js /sw-signal /report
relay refused (authority only):
  off.test:443 x5; 127.0.0.1:<S> x3; localhost:<S>; GET 127.0.0.1:<S>; 192.0.2.1:443 x2;
  93.184.216.34:443 (literal URL, refused like any IP literal); GET 169.254.169.254; GET [2001:db8::1];
  bp1c-dns-<rand>.test:443; GET edge.microsoft.com
  background: edge.microsoft.com, www.bing.com, nav-edge.smartscreen.microsoft.com, go.microsoft.com,
              prod.rewardsplatform.microsoft.com, mss.office.com, substrate.office.com
loopback TCP sentinel direct hits = 0; loopback UDP sentinel packets = 0
WebRTC candidates: stun loopback [], stun 192.0.2.1 [], no servers []
ws_allowed=open; ws_off=error; ws_loop=error; SW: allowed ok, off/loop/testnet err
OS DNS cache entries for sentinel name = 0
outage: new origin paths = 0; new direct sentinel hits = 0; relay attempts = 0 (listener closed)
OS TCP table, non-loopback remotes owned by the probe's Edge tree:
  R1: 192.168.10.213:8009, 52.97.202.66:443
  R2: 192.168.10.213:8009 [NetworkService], 52.97.211.210:443 [browser]
  R3 (media router off, msImplicitSignin etc. off): 40.99.218.82:443 [browser]
     (mss.office.com / substrate.office.com no longer appear at the relay in R3)
```

**Interpretation:**

- Within the scope the earlier BP1 tested, the corrected flags work. Every redirect, subresource, iframe, SW fetch, WebSocket, IP literal (loopback, TEST-NET, link-local, IPv6 documentation) and unresolvable name reached the relay as a proxy request and was refused before any dial. WebRTC produced no candidates and no UDP. Edge did no OS DNS lookup of its own. During the outage nothing fell back to a direct connection. Plain-HTTP literals reach the proxy as absolute-form `GET` and must be refused as non-CONNECT; the relay saw them as `GET <host>`.
- The NetworkService opens **raw sockets outside the proxy** for Cast discovery and channels (`:8009`), even in headless mode and with `--disable-background-networking`. The R3 flags removed it in this run.
- The **browser process** (not the NetworkService) opens TLS connections to Microsoft cloud ranges in every run. That traffic does not use Chromium's proxy configuration, so the relay can never see or refuse it. [INFERENCE] The likely source is Edge's OS-integrated identity/SSO or another Edge-specific service that uses a Windows networking stack. The guessed `ms*` feature names changed which background hosts showed up at the relay but did not stop the direct connection. The endpoint hostnames were not resolved, so that no extra live request would be made.
- Polling once per second gives only a **lower bound**. Short-lived connections, UDP to non-loopback addresses and other processes Edge might spawn under different command lines are not covered.

**Verdict: NOT-VIABLE.** BG-1 fails on Edge 157 with the A5/A8 flags.

**Design constraints:**

- Relay flags are necessary but **not sufficient**. S-Relay and the browser slices stay BLOCKED until one of these holds:
  - (a) an owner-approved OS-level egress control (BP1b / O-2), for example a per-program outbound rule that allows only `127.0.0.1` for the Edge executable while the session runs. This changes firewall state and needs owner approval; or
  - (b) a verified Edge switch or policy that stops the browser-process connection. Setting Edge policy means writing to the registry, which is out of scope for an unapproved probe; or
  - (c) the owner explicitly accepts a residual ("browser-process Microsoft connections, not account-linked") in O-2.
- A5 must add `MediaRouter,DialMediaRouteProvider,CastMediaRouteProvider,GlobalMediaControls` to the single merged `--disable-features` list, plus `--media-router=0`. The argv guard must reject a second `--disable-features` occurrence, because the last one wins and silently drops `DnsOverHttps,AsyncDns`.
- The A19 admission self-test must include the **OS TCP-table sentinel**: no non-loopback remote endpoint owned by the session's process tree for the whole test window. Today it would fail on Edge 157 and refuse admission, which is the honest outcome.
- A6c: these background hosts were observed at the relay: `go.microsoft.com`, `prod.rewardsplatform.microsoft.com` and `nav-edge.smartscreen.microsoft.com`, in addition to the BP1 list. Classification remains refuse-only.
- Edge auto-updated between probe days. Admission has to run per version, and a version change must invalidate the admission record before the next session.

## BP3c — Capability SID identification and stability

**Evidence:**

```text
observed capability SIDs anywhere in tree (3 sessions): exactly one
  S-1-15-3-1024-3239966617-1410756637-3494353204-65451782-2225605771-3526040376-1730753648-3419555762
equals BP3b SID (Edge 156): true
DeriveCapabilitySidsFromName match (57 candidates): lpacEdgeStableNetworkSandbox -> same SID
pa first / pa restart / pb first: identical SID, identical masks, identical placement
token capabilities of every live process: [] ; renderers AppContainer S-1-15-2-3251537155-...-129201922 (no caps)
NetworkService runs --service-sandbox-type=none (unsandboxed) -> no live holder of the capability SID
Default\Network: explicit Allow 1245631 (0x001301BF, this object) + explicit Allow 0xE0010000 (3758161920, OICI inherit-only)
Default\Network\Cookies: inherited Allow 1245631
same pair of explicit ACEs (+ inherited descendants) also on:
  Default\Cache, Default\Shared Dictionary,
  Default\Storage\ext\<extension-id>\def\{Cache, Network, Shared Dictionary}
additional non-owner principal: Everyone S-1-1-0, explicit Allow rights 32 (FILE_EXECUTE/traverse) on
  Default\Local Storage\leveldb\*, Default\Session Storage\*, Default\Storage\ext\<id>\def\Local Storage\leveldb\*
Local State, Default\Preferences: owner-only (inherited)
```

**Interpretation:**

- H-CE1 is **confirmed for identification**. The SID belongs to Edge Stable's LPAC network-sandbox capability. It is deterministic: derived from the capability name, not from the profile or the session. It was stable across two fresh profiles, a restart and the 156→157 update.
- The "held only by the browser's sandboxed network service" part is **not observable today**. The NetworkService ran unsandboxed and no process held the capability. Edge grants the ACEs in advance for when the network sandbox runs. [INFERENCE] A capability SID is not a security boundary against the same user, because any same-user process can start an LPAC process that holds it. It therefore grants nothing the owner-session boundary does not already grant. Code running as another user cannot get that capability in its token without starting such a process itself, which needs that user's own logon.
- [INFERENCE] The capability name contains the channel, so Beta, Dev and Canary would derive different SIDs.
- A10(ii) as written is **refuted** in two ways:
  1. The CE-1 ACEs also appear on `Default\Cache`, `Default\Shared Dictionary` and the per-extension `Storage\ext\*\def\{Cache,Network,Shared Dictionary}` trees.
  2. A group SID (Everyone) receives `FILE_EXECUTE` (32) on LevelDB files.

  Under the current wording, every profile Edge creates would be refused `profile_policy_unsatisfied` or `profile_acl_drift`.

**Verdict: VIABLE-WITH-AMENDMENT.** The SID is identified and stable. CE-1's scope needs an amendment, and O-1 then has to be put to the owner with the amended scope.

**Design constraints (the A10(ii) amendment this evidence licenses):**

- CE-1 principal = exactly `DeriveCapabilitySidsFromName("lpacEdgeStableNetworkSandbox")`, computed at runtime and compared on every session. It must **not** be "the first `S-1-15-3-1024-*` seen". Pinning per profile becomes a redundant check. Any other capability SID is refused, including other channels unless they are derived the same way.
- CE-1 locations = the explicit pair on `Default\{Network,Cache,Shared Dictionary}` and `Default\Storage\ext\<id>\def\{Network,Cache,Shared Dictionary}`, plus inherited descendants. Masks:
  - directory pair: explicit 0x001301BF with no inheritance flags, and explicit 0xE0010000 with OICI inherit-only;
  - descendants: inherited 0x001301BF on files; directories also carry the inherited 0xE0010000.
- A second narrow exception, **CE-2**, is needed if Edge profiles are to be admitted at all: Everyone `S-1-1-0`, explicit Allow mask exactly 32 (`FILE_EXECUTE`), only on LevelDB files under `Local Storage\leveldb`, `Session Storage` and `Storage\ext\<id>\def\Local Storage\leveldb`. That needs its own owner decision (O-1b), because it is a group-SID grant. The plan currently forbids it outright. Whether it exposes anything: `FILE_EXECUTE` gives no read, write or delete [INFERENCE from the access mask], but its origin was not determined.
- Recursive admission and the post-session sweep must cover the extension storage subtrees too.
- Deny ACEs, conditional ACEs and any other principal or mask stay refused. The sandbox is never disabled.

## Cleanup and handoff

All Edge trees were killed (`left: {}` after every run). The loopback listeners closed when the event loop ended. Every temp root was removed (`temp_removed True` ×5). The script directory was deleted afterwards. This artifact is the only file written; no source or plan file was changed, and nothing was committed or pushed. Main should:

1. record BG-1 = FAIL and BG-3 = NOT-MET, with the reasons above;
2. amend A5, A10(ii) and A19 and the O-1/O-2 decision text, and add O-1b (CE-2);
3. tell the owner that Edge 157 makes a direct browser-process connection to Microsoft that only OS-level egress control (BP1b) can close.
