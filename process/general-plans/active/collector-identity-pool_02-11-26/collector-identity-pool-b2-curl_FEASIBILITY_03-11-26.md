---
slug: collector-identity-pool-b2-curl
date: 2026-11-03
verdict: VIABLE
originating-phase: pvl
---

# B2 curl_cffi numeric CONNECT feasibility

## Hypothesis
A correctly owned libcurl `CONNECT_TO` slist can route a proxy tunnel to a numeric destination while retaining the original origin hostname for HTTP Host, TLS SNI, and certificate verification; pinned curl_cffi can express this for HTTP and HTTPS proxies.

## Mechanism Under Test
Pinned curl_cffi 0.16.3 `Curl.setopt` and request `set_curl_options`; twscrape 0.20.1 `twscrape.http.CurlClient` / `make_client` factory. Generic `Curl.setopt` does not convert Python lists into slists for `CONNECT_TO`; explicit slist branches exist for `HTTPHEADER`, `PROXYHEADER`, and `RESOLVE`. `CONNECT_TO` accepts a libcurl `curl_slist*`.

## Probe Family
1 — Local process / Node script (Python equivalent).

## Probe Cost Class
cheap-local. Safety gate met: synthetic HTTP/TLS origins and proxies bound only to 127.0.0.1 ephemeral ports. No live endpoints, accounts, real proxies, or external network targets. Temporary local certs were used as explicit trust roots where appropriate; verification was never disabled. Temporary keys/certs were held in `TemporaryDirectory` and removed automatically.

## Probe Method
From `C:/Users/jamir/.herdr/worktrees/my_site/wt-b2-validate`:

```text
uv run --offline --project api --frozen --group xreader python -c "import curl_cffi,inspect; from curl_cffi import Curl; import curl_cffi.requests.session as s; print(curl_cffi.__version__); print(inspect.getsource(Curl.setopt)); print(inspect.getsource(s.set_curl_options))"
uv run --offline --project api --frozen --group xreader python -c "import inspect,twscrape.http; print(inspect.getsource(twscrape.http))"
uv run --offline --project api --frozen --group xreader python b2-probe-curl.py
uv run --offline --project api --frozen --group xreader python b2-probe-https-proxy.py
```

Both probes passed a retained slist in `AsyncSession(..., curl_options={CurlOpt.CONNECT_TO: slist})`, freeing it after completion. The HTTP-proxy probe forced HTTP/1.1, used a bounded TLS origin that recorded SNI and complete request headers and returned a length-delimited 200 response, and used a loopback CONNECT relay. Its wrong-name case kept URL and CONNECT_TO rule at `origin.test` while switching the origin to a separately trusted certificate with SAN `other.test`. An earlier attempt checked an untrusted origin root. The HTTPS-proxy probe used distinct self-signed origin and proxy roots: `verify=origin_cert` plus `curl_options[PROXY_CAINFO]=proxy_cert`. Its proxy TLS listener handled handshake failures without terminating the accept loop.

## Evidence Captured
Pinned runtime: curl_cffi 0.16.3; twscrape 0.20.1. Source inspection confirms generic Python lists are not a supported `CONNECT_TO` slist route. `AsyncSession` constructor accepts `curl_options`; its request method does not accept that option as a request kwarg. Twscrape CurlClient constructs one AsyncSession in its constructor, forwards request kwargs, and retries NetworkError up to `_CURL_MAX_RETRIES + 1` (default four attempts). Constructor-level options were proven in both proxy modes below, but account/concurrent request isolation and fallback-child behavior are not established by this probe.

Corrected HTTP proxy / HTTPS origin output:

```text
trusted OK 200 ok
trusted CONNECT ['127.0.0.1:65281'] TRACE [('sni', 'origin.test'), ('request', 'GET / HTTP/1.1\r\nHost: origin.test:65281\r\nAccept-Encoding: gzip, deflate, br\r\n\r\n')]
wrong-name ERR CertificateVerifyError 60 Failed to perform, curl: (60) SSL: no alternative certificate subject name matches target hostname 'origin.test'. See https://curl.se/libcurl/c/libcurl-errors.html first for more details.
wrong-name CONNECT ['127.0.0.1:65281'] TRACE [('request', 'GET / HTTP/1.1\r\nHost: origin.test:65281\r\nAccept-Encoding: gzip, deflate, br\r\n\r\n'), ('sni', 'origin.test')]
```

Both requests used numeric CONNECT authority; the successful response captured origin Host and SNI, and the wrong-SAN certificate was rejected under the same origin URL and CONNECT_TO rule.

HTTPS proxy / HTTPS origin output:

```text
separate-roots-trusted OK 200 ok
separate-roots-trusted PROXY_CONNECT ['127.0.0.1:65313'] ORIGIN ['GET / HTTP/1.1\r\nHost: origin.test:65313\r\nAccept-Encoding: gzip, deflate, br\r\n\r\n']
proxy-untrusted ERR CertificateVerifyError 60 Failed to perform, curl: (60) SSL certificate OpenSSL verify result: self signed certificate (18). See https://curl.se/libcurl/c/libcurl-errors.html first for more details.
proxy-untrusted PROXY_CONNECT ['127.0.0.1:65313'] ORIGIN ['GET / HTTP/1.1\r\nHost: origin.test:65313\r\nAccept-Encoding: gzip, deflate, br\r\n\r\n']
```

The trusted HTTPS-proxy exchange used separate origin and proxy trust roots: the origin cert was session `verify`, and proxy cert was `PROXY_CAINFO`. The untrusted-proxy case omitted the proxy trust root, kept origin trust configured, and failed TLS with error 60 before forwarding a second CONNECT or reaching the origin. HTTPS proxy SNI/certificate identity for proxy hostname (the probe used numeric proxy URL 127.0.0.1) was not separately tested. An earlier origin-untrusted attempt returned certificate error 60 for a self-signed certificate; one later rerun timed out because the fixture TLS accept loop did not handle handshake failure, so that rerun is disregarded.

## Verdict
VIABLE

**VIABLE, mechanism scope.** Pinned curl_cffi with a retained CONNECT_TO slist in AsyncSession constructor options successfully requests numeric CONNECT authority through both loopback HTTP and HTTPS proxies. For an HTTPS origin, the successful HTTP-proxy case preserves origin Host/SNI, returns HTTP 200 with the trusted origin cert, and rejects a trusted wrong-SAN certificate. HTTPS-proxy mode succeeded with separate origin/proxy trust roots; omitting proxy trust rejected the proxy certificate.

## Resulting Design Constraint
- **What this licenses:** further design may use a retained `curl_slist` passed through AsyncSession constructor `curl_options` for numeric CONNECT authority via HTTP and HTTPS proxies, with package-managed origin verification and separately configured HTTPS-proxy trust via `PROXY_CAINFO`. The tested HTTP-proxy mode also preserved the URL-derived origin Host/SNI.
- **What this forbids:** passing a Python list through generic `Curl.setopt` as a CONNECT_TO slist; using `RESOLVE` as a substitute CONNECT-authority rewrite; claiming this proves a malicious proxy's actual remote routing; or treating these tests as production twscrape child/retry/concurrency proof.
- **What remains uncertain (known-gap):** production factory lifecycle, per-account/per-request concurrent isolation and slist ownership, fallback child propagation, retries, proxy URL hostname SNI/hostname verification (HTTPS proxy probe used 127.0.0.1), and adversarial proxy routing. A loopback proxy proves requested numeric authority and TLS authentication, not actual remote routing by a malicious proxy.
