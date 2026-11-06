---
slug: collector-identity-pool-b2-httpx
date: 2026-11-03
verdict: VIABLE
originating-phase: pvl
---

## Hypothesis
A bounded HTTPX/httpcore transport seam can send a numeric CONNECT authority while retaining the original hostname for origin SNI, Host and certificate verification.

## Mechanism Under Test
Pinned HTTPX 0.28.1/httpcore 1.0.9. An application-owned `httpx.AsyncBaseTransport` can adapt HTTPX request/response objects to a directly owned `httpcore.AsyncHTTPProxy`, constructed with `network_backend=...`, `ssl_context=origin_ctx`, `proxy_ssl_context=proxy_ctx`, and `retries=0`. This uses the public httpcore constructor, not HTTPX's private pool field or global patching. The injected backend wraps TCP streams; its bounded one-time CONNECT framing handler validates request line and exactly one matching Host, substitutes both authority fields with the fixture origin's numeric loopback address, then permanently passes bytes through. `start_tls` wraps the TLS-upgraded stream, so the same behavior covers HTTPS-proxy TLS before CONNECT and the origin TLS upgrade after CONNECT; explicit state disables all rewriting after CONNECT.

## Probe Family
1 — Local process / Node script (Python local process; cheap-local).

## Probe Cost Class
cheap-local — safety gate met. Only loopback listener sockets and temporary self-signed certificates were used; no external connections.

## Probe Method
From repository root, with the frozen xreader environment:

```powershell
uv run --project api --frozen --group xreader python -m py_compile process/general-plans/active/collector-identity-pool_02-11-26/probe_b2_httpx_transport.py
uv run --project api --frozen --group xreader python process/general-plans/active/collector-identity-pool_02-11-26/probe_b2_httpx_transport.py
```

The probe used a public `AsyncBaseTransport` adapter around `httpcore.AsyncHTTPProxy`, an injected backend, a TLS loopback origin, plaintext and TLS loopback HTTP proxies, and temporary roots/certificates. The HTTPS proxy fixture mapped the `proxy.test` name to a loopback listener in the test backend. It exercised trusted origin, untrusted origin root, wrong origin hostname, and untrusted HTTPS-proxy root. No external network, production source, shared docs or dependency changes were used.

## Evidence Captured
Compilation succeeded. The actual runtime matrix output:

```text
http trusted ('ok', 200) core= CONNECT origin.test:443 HTTP/1.1 proxy_received= 127.0.0.1:49245 origin_host= origin.test tls_names= ['origin.test']
http bad-origin-root ('ConnectError', '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1010)') core= CONNECT origin.test:443 HTTP/1.1 proxy_received= 127.0.0.1:49245 origin_host= origin.test tls_names= ['origin.test']
http wrong-name ('ConnectError', "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, certificate is not valid for 'wrong.test'") core= CONNECT wrong.test:443 HTTP/1.1 proxy_received= 127.0.0.1:49245 origin_host= origin.test tls_names= ['wrong.test']
https trusted ('ok', 200) core= CONNECT origin.test:443 HTTP/1.1 proxy_received= 127.0.0.1:49245 origin_host= origin.test tls_names= ['proxy.test', 'origin.test']
https bad-origin-root ('ConnectError', '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1010)') core= CONNECT origin.test:443 HTTP/1.1 proxy_received= 127.0.0.1:49245 origin_host= origin.test tls_names= ['proxy.test', 'origin.test']
https wrong-name ('ConnectError', "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, certificate is not valid for 'wrong.test'") core= CONNECT wrong.test:443 HTTP/1.1 proxy_received= 127.0.0.1:49245 origin_host= origin.test tls_names= ['proxy.test', 'wrong.test']
https untrusted-proxy-root ('ConnectError', '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate (_ssl.c:1010)') proxy_tls= ['proxy.test']
VERSIONS 0.28.1 1.0.9
```

The proxy independently observed `127.0.0.1:49245` as CONNECT authority in each case; that ephemeral listener was the TLS origin's numeric loopback address and port. The core generated CONNECT from the original hostname and the adapter changed it only at the outgoing framed-header boundary. Successful cases reached the origin, whose captured HTTP Host was `origin.test`; SNI records show `origin.test` for origin TLS. HTTPS proxy TLS separately used SNI `proxy.test`, and the untrusted proxy certificate failed before CONNECT. Origin untrusted-root and wrong-name checks failed as expected through both proxy schemes. The numeric CONNECT target is a requested proxy authority; this does not prove a malicious proxy actually dialed that destination.

## Verdict
VIABLE

## Resulting Design Constraint
- **What this licenses:** A maintained app-owned HTTPX `AsyncBaseTransport` adapter over the public `httpcore.AsyncHTTPProxy` constructor and custom `AsyncNetworkBackend` can implement the tested framing seam for both HTTP and HTTPS proxies while preserving original origin SNI/Host and certificate verification.
- **What this forbids:** No direct mutation of HTTPX private pool fields, global monkeypatch, `verify=False`, ambient-trust substitution, unbounded/partial-header rewriting, or claim that requested CONNECT proves proxy upstream routing.
- **What remains uncertain (known-gap):** This probe establishes the mechanism, not production lifecycle, cancellation, redirect/address-policy, adversarial-framing, connection-pool, or parent/child coverage. Those require the later implementation acceptance tests. A malicious proxy's actual dial target cannot be proven by this client-side fixture.
