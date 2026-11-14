---
slug: collector-identity-pool
date: 2026-11-03
verdict: VIABLE
originating-phase: pvl
---

# B1.2 local capture feasibility

### Hypothesis
The installed locked curl_cffi targets can expose a raw ClientHello and initial HTTP/2 SETTINGS to bounded loopback-only test tooling without a dependency change.

### Mechanism Under Test
curl_cffi 0.16.3 exact targets chrome131, safari170, firefox133 and edge101. This is the deferred B1 validation feasibility gate, probed during its authorized EXECUTE follow-up, not a new live-provider validation. Installed twscrape 0.20.1 `http.py:194-210` constructs AsyncSession and strips literal UA; the maintained B1 adapter assigns the exact session impersonation target. The new probe uses curl_cffi directly, not twscrape retries, accounts or bootstrap. Existing B1 transport tests separately exercise those factories.

### Probe Family
1 — Local process / Node script (Python equivalent).

### Probe Cost Class
cheap-local. Safety gate met: all eight listeners bound to 127.0.0.1 ephemeral ports, no redirects, environment proxies disabled, no external hostnames, accounts or real cookies. Offline uv installs used only cached locked packages. TLS uses a temporary self-signed loopback-IP certificate explicitly trusted by the client, not verify=false. The temporary private key/certificate are removed with TemporaryDirectory, not checked in.

### Probe Method
From `C:/Users/jamir/.herdr/worktrees/my_site/wt-identity-followups`:

```text
uv run --offline --project api --frozen --group xreader python api/tests/data/attention/test_identity_fingerprint.py
```

For each target, a raw TCP listener reads at most eight TLS records and 64 KiB accumulated handshake data, then closes after ClientHello. A separate TLS listener advertises h2 using stdlib ssl, reads the connection preface and first SETTINGS frame with bounded exact reads, then closes. Five-second socket/client deadlines and a joined capture thread bound the probe. Expected client errors are intentional: curl 35 after raw TLS capture, curl 56 after initial h2 capture, since no HTTP response is sent. These codes alone are not the proof; parsed captured bytes and negotiated ALPN are.

Test-only parsers are length-checked and cover fragmented records, malformed/truncated vectors, duplicate extensions, GREASE filtering, ordered settings, and every truncated prefix of synthetic ClientHello/captured H2 initial bytes. This is a small purpose-specific capture parser, not a full TLS/HTTP2 validator or HPACK implementation.

### Evidence Captured
The complete stdout JSON is checked in as `collector-identity-pool_WIRE-B1-FOLLOWUPS_03-11-26.json` alongside this verdict, including raw TLS-record hex, ordered cipher/extension/group lists, ALPN, GREASE-filtered JA3-style input strings and raw initial h2 bytes. Windows CPython 3.12.14, curl_cffi 0.16.3, twscrape 0.20.1, cryptography 50.0.1, server OpenSSL 3.5.9 (29 Sep 2026).

All four ClientHellos offered `h2,http/1.1`; all four independent TLS connections negotiated h2. Observed SETTINGS, in wire order (numeric IDs, not a published browser baseline):

| Target | Observed ordered SETTINGS (id=value) |
|---|---|
| chrome131 | 1=65536, 2=0, 4=6291456, 6=262144 |
| safari170 | 2=0, 4=4194304, 3=100 |
| firefox133 | 1=65536, 2=0, 4=131072, 5=16384 |
| edge101 | 1=65536, 3=1000, 4=6291456, 6=262144 |

Source layouts: [RFC 8446 section 4.1.2](https://www.rfc-editor.org/rfc/rfc8446#section-4.1.2), [RFC 9113 sections 3.4/6.5](https://www.rfc-editor.org/rfc/rfc9113#section-6.5), [RFC 8701](https://www.rfc-editor.org/rfc/rfc8701). These are protocol references, not checked browser captures. No public fingerprint service or browser baseline was contacted/read/adopted for this probe. Locally available source was the installed locked curl_cffi/twscrape code and B1's checked-in header observations; neither is an independent browser TLS baseline. Chrome extension order/GREASE and random/key-share bytes can vary; the artifact is one observation, not a stable expected digest.

### Verdict
**VIABLE** for bounded local raw ClientHello and initial HTTP/2 SETTINGS capture only. Browser fingerprint equivalence remains **INCONCLUSIVE / NOT VERIFIED**.

### Resulting Design Constraint
- **What this licenses:** retaining the test-only loopback capture/parser, reproducing the enumerated target observations, and reporting exactly those bytes/settings.
- **What this forbids:** runtime capture/network changes, treating a library claim as independent evidence, asserting a matching JA3/JA4/full HTTP2/browser fingerprint, or using this to authorize deployment/live requests/proxies/B2/B3.
- **What remains uncertain (known-gap):** no independent reference-browser capture, hostname/SNI comparison (the local destination is an IP), JA4, ECH details, resumption, HTTP2 pseudo-header/priority/window-update fingerprint, cross-platform/version stability, or live-service acceptance. TLS and h2 were captured on separate connections. The probe is direct curl_cffi; it does not upgrade the existing twscrape factory header proofs into end-to-end TLS equivalence.
