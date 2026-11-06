"""Actual spawned child entrypoint with bounded stdin, HMAC and loopback TLS."""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from uuid import uuid4

import pytest
pytest.importorskip("twscrape", reason="optional xreader; mandatory frozen B2 preflight")
pytest.importorskip("curl_cffi", reason="optional xreader; mandatory B2 wire IDs")

from api.data.attention import x_proxy_runtime as runtime, x_proxy_snapshot as snapshot
from api.tests.data.attention.test_x_proxy_snapshot import write_snapshot, fixture_open
from api.tests.data.attention.test_x_proxy_policy import spamhaus, firehol
from api.tests.data.attention.proxy_wire_fixture import fixture


@pytest.mark.parametrize("tamper", [False, True], ids=["current-revision", "changed-raw-snapshot"])
def test_spawned_child_hmac_current_snapshot_both_factories_no_secret_output(tmp_path, tamper):
    now = datetime.now(UTC)
    with fixture(https_proxy=True) as wire:
        path = write_snapshot(tmp_path / "private")
        root = path.parent
        (root / "accounts").mkdir()
        (root / "accounts" / "alpha.db").write_bytes(b"")
        policy_path = root / "policy.json"
        document = json.loads(policy_path.read_bytes())
        document["allowed_origins"].append(wire.origin_url)
        policy_path.write_text(json.dumps(document), encoding="utf-8")
        marker = "SYNTHETIC_SPAWN_CREDENTIAL_MARKER"
        (root / "routes.txt").write_text(wire.proxy_url.replace("https://", "https://user:" + marker + "@") + "\nhttps://spare.example\n")
        private = snapshot.load_snapshot(path, repo_root=tmp_path / "repo", opener=fixture_open)
        # Cache contents are real production cache format, published atomically;
        # host ACL composition is tested separately with native protected files.
        cache = runtime.FeedCache(private.policy.cache_dir)
        feeds = {slot: cache.publish(slot, body, now)[1] for slot, body in
                 (("spamhaus", spamhaus(now)), ("firehol", firehol(now)))}
        revision = str(uuid4())
        admission = {"proxy_id": private.assignments["alpha"].proxy_id, "identity_revision": revision,
            "checked_at": now.isoformat(), "expires_at": (now + timedelta(minutes=30)).isoformat(), "feeds": feeds}
        admission_path = private.policy.cache_dir / "admissions" / "alpha.json"
        admission_path.parent.mkdir()
        admission_raw = json.dumps(admission).encode()
        admission_path.write_bytes(admission_raw)
        request = snapshot.SensitiveRequest({"config_path": str(path), "label": "alpha", "proxy_id": admission["proxy_id"],
            "identity_revision": revision, "backend": "curl", "request_nonce": os.urandom(32).hex(),
            "admission_expires_at": admission["expires_at"], "query": "$SOL", "kv": {"product": "Latest", "cursor": "fixture-continuation"}})
        snapshot.attest((*private.roles, ("safe-admission", str(admission_path.resolve()), admission_raw)), request)
        if tamper:
            path.write_bytes(path.read_bytes() + b"\n")
        wire.responses["/child"] = (200, {"content-type": "application/json"}, b'{"data":{"entries":[]}}')
        options = {"origin_url": wire.origin_url, "origin_root": str(wire.certs["origin"]["root"]),
                   "proxy_root": str(wire.certs["proxy"]["root"])}
        command = [sys.executable, "-m", "api.tests.data.attention.proxy_child_fixture", json.dumps(options)]
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA", "USERPROFILE", "APPDATA"}
        environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
        environment.update(TWS_TELEMETRY="0", DO_NOT_TRACK="1", TWS_LOG_LEVEL="WARNING", TWS_RAISE_WHEN_NO_ACCOUNT="1", TWS_HTTP_BACKEND="curl")
        completed = subprocess.run(command, input=json.dumps(request).encode(), capture_output=True,
            timeout=25, env=environment, cwd=Path(__file__).resolve().parents[4])
        assert completed.returncode == 0, completed.stderr.decode(errors="replace")
        reply = json.loads(completed.stdout)
        assert reply["request_nonce"] == request["request_nonce"] and reply["identity_revision"] == revision
        if tamper:
            assert reply["kind"] == "proxy" and reply["proxy_reason"] == "proxy_revision"
            assert not wire.requests and not wire.connects
        else:
            assert reply["status"] == "ok"
            assert len(wire.requests) == len(wire.connects) == 2
            assert all(item["authority"] == f"127.0.0.1:{wire.origin_port}" for item in wire.connects)
        exposed = completed.stdout + completed.stderr + repr(command).encode() + repr(environment).encode()
        for secret in (marker, request["attestation_key"], request["attestation_tag"]):
            assert secret.encode() not in exposed


@pytest.mark.parametrize("mutation", ["valid", "omitted", "required", "partial", "malformed"])
def test_spawned_explicit_direct_off_predicate_never_implicit_or_configured(tmp_path, mutation):
    from api.data.attention import twscrape_reader as tr
    from api.tests.data.attention.test_x_proxy_snapshot import query_document
    document = query_document(tmp_path, labels=("alpha",), required=False)
    for key in ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"):
        document["collector"][key] = None
    path = tmp_path / "queries.json"
    if mutation == "required":
        document["collector"]["x_proxy_required"] = True
    if mutation == "partial":
        document["collector"]["x_proxy_list_path"] = str(tmp_path / "missing-list")
    path.write_text("{" if mutation == "malformed" else json.dumps(document), encoding="utf-8")
    request = {"config_path": str(path.resolve()), "label": "alpha", "backend": "curl",
        "identity_revision": tr.identity_revision({}), "query": "$SOL",
        "kv": {"product": "Latest", "cursor": "fixture-continuation"}}
    if mutation == "omitted":
        request.pop("config_path")
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA", "USERPROFILE", "APPDATA"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(TWS_TELEMETRY="0", DO_NOT_TRACK="1", TWS_LOG_LEVEL="WARNING",
                       TWS_RAISE_WHEN_NO_ACCOUNT="1", TWS_HTTP_BACKEND="curl")
    options = {"predicate_only": True}
    completed = subprocess.run([sys.executable, "-m", "api.tests.data.attention.proxy_child_fixture", json.dumps(options)],
        input=json.dumps(request).encode(), capture_output=True, timeout=15, env=environment,
        cwd=Path(__file__).resolve().parents[4])
    assert completed.returncode == 0
    reply = json.loads(completed.stdout)
    expected = {"valid": "ok", "omitted": "fail", "required": "refused", "partial": "refused", "malformed": "fail"}
    assert reply["status"] == expected[mutation]
    if reply["status"] == "refused":
        assert reply == {"status": "refused", "reason": "request"}


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_parent_capture_limits_kill_real_child_without_disclosing_stdin(tmp_path, monkeypatch, stream):
    from api.data.attention import twscrape_reader as tr, x_proxy as p
    original = subprocess.Popen
    marker = "SYNTHETIC_PRIVATE_STDIN_MARKER"
    limit = p.CHILD_STDOUT_LIMIT if stream == "stdout" else p.CHILD_STDERR_LIMIT
    script = f"import sys; sys.stdin.buffer.read(); sys.{stream}.buffer.write(b'x' * {limit + 1}); sys.{stream}.flush()"
    commands = []
    def launch(command, **kwargs):
        commands.append((command, kwargs["env"]))
        return original([sys.executable, "-c", script], **kwargs)
    monkeypatch.setattr(subprocess, "Popen", launch)
    reply = tr.run_child({"attestation_key": marker}, os.environ, timeout=15)
    assert reply["kind"] == "proxy" and reply["proxy_reason"] == "proxy_response"
    assert marker not in repr(reply) + repr(commands)


def test_composed_direct_plain_to_spawned_curl_wire_cursor_charges_and_daily_cap(tmp_path, monkeypatch, attention_cache):
    """Real child API.search_raw/QueueClient/DB and both direct TLS factories."""
    import asyncio
    from urllib.parse import parse_qs, urlsplit
    from twscrape import API
    from api.data.attention import twscrape_reader as tr, x_reader as xr, x_pool
    from api.tests.data.attention.test_x_pool import Clock, DAY, SOL, QUERY, cfg, day_pages, source
    from api.data.attention import x_filters
    import random

    with fixture() as wire:
        directory = tmp_path / "accounts"
        directory.mkdir(mode=0o700)
        config = cfg(x_accounts_db_path=str(directory), x_accounts=("alpha",),
                     x_allow_curl_backend=True, x_account_daily_cap=1000)
        document = {"version": 1, "note": "composed direct fixture", "collector": config.as_dict(),
            "subreddits": ["Bitcoin"], "ambiguous": {"reddit": [], "x": []}, "coins": {}}
        from api.data.attention import web_queries
        document["ambiguous"] = {key: [] for key in web_queries.SOURCES}
        path = tmp_path / "queries.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        web_queries.load(path)  # fixture errors must fail before spawning
        async def initialize_account():
            await API(str(directory / "alpha.db")).pool.add_account_cookies(
                "alpha", "auth_token=SYNTHETIC_AUTH_TOKEN; ct0=SYNTHETIC_CSRF")
        asyncio.run(initialize_account())
        (directory / "alpha.db").chmod(0o600)

        first = day_pages(1)[0]
        first.body["entries"].append({"entryId": "cursor-bottom",
            "content": {"cursorType": "Bottom", "value": "fixture-continuation"}})
        child_body = day_pages(1)[0].body
        for index, entry in enumerate(child_body["entries"]):
            # TwscrapeReader derives raw timestamps from real snowflake-form IDs.
            stamp = datetime.fromisoformat(entry["tweet"]["date"])
            identifier = ((int(stamp.timestamp() * 1000) - 1288834974657) << 22) + index
            entry["entryId"] = f"tweet-{identifier}"
            entry["tweet"]["id"] = identifier
        child_body["entries"].append({"entryId": "cursor-bottom",
            "content": {"cursorType": "Bottom", "value": "after-fallback"}})
        observed = []
        def response():
            request = wire.requests[-1]
            target = urlsplit(request["path"])
            if target.path == "/bootstrap":
                observed.append("bootstrap")
                return 200, {"content-type": "text/html"}, b"synthetic transaction fixture"
            assert target.path.startswith("/gql/") and target.path.endswith("/SearchTimeline")
            variables = json.loads(parse_qs(target.query)["variables"][0])
            assert variables["cursor"] == "fixture-continuation"
            assert variables["rawQuery"] == QUERY and variables["product"] == "Latest"
            observed.append(variables)
            return 200, {"content-type": "application/json", "x-rate-limit-remaining": "40",
                         "x-rate-limit-limit": "50"}, json.dumps(child_body).encode()
        wire.responses["*"] = response
        options = {"direct_wire": True, "origin_url": wire.origin_url,
                   "origin_root": str(wire.certs["origin"]["root"]),
                   "proxy_root": str(wire.certs["proxy"]["root"])}
        original_popen = subprocess.Popen
        launches = []
        diagnostics = bytearray()
        class DiagnosticPipe:
            """Observe bounded child diagnostics for the credential-marker assertion."""
            def __init__(self, pipe):
                self.pipe = pipe
            def read(self, size):
                chunk = self.pipe.read(size)
                if len(diagnostics) + len(chunk) <= 1024 * 1024:
                    diagnostics.extend(chunk)
                return chunk
            def close(self):
                self.pipe.close()
        def launch(command, **kwargs):
            assert command == [sys.executable, "-m", tr.__name__, "--curl-fallback"]
            actual = [sys.executable, "-m", "api.tests.data.attention.proxy_child_fixture", json.dumps(options)]
            launches.append((actual, kwargs["env"]))
            process = original_popen(actual, **kwargs)
            process.stderr = DiagnosticPipe(process.stderr)
            return process
        monkeypatch.setattr(subprocess, "Popen", launch)

        class ParentReader(xr.FakeXReader):
            cursor = None
            _remaining = None
            _read = 0
            def search_raw(self, query, kv, page):
                raw = super().search_raw(query, kv, page)
                if raw is not None:
                    self.cursor = tr.bottom_cursor(raw.body)
                return raw
            def parse_tweets(self, body):
                return super().parse_tweets({"entries": [entry for entry in body["entries"] if "tweet" in entry]})
            def _close_gen(self):
                pass  # this test's plain parent is a scripted reader, not an async generator
            def page_from(self, body, headers):
                return tr.TwscrapeReader.page_from(self, body, headers)
            def adopt(self, body, headers):
                return tr.TwscrapeReader.adopt(self, body, headers)
        blocked = lambda: xr.ReaderFailure("abort", text=xr.CLOUDFLARE_PREFIX)
        parent = ParentReader("alpha", [first, blocked()])
        clock = Clock()
        pool, src = x_pool.XPool(["alpha"], clock=clock, cap=1000), source(clock)
        routing = runtime.ProxyRuntime(config, config_path=path, repo_root=tr.REPO_ROOT, clock=clock)
        routing.reconcile(pool)
        pool.set_canary_passed(labels=["alpha"])
        child_replies = []
        def run_child(request, environment):
            reply = tr.run_child(request, environment)
            child_replies.append(reply)
            return reply
        tr.private_tmp().mkdir(parents=True, exist_ok=True, mode=0o700)
        fallback = tr.CurlFallback({"alpha": parent}, directory, {**os.environ, **tr.REQUIRED_ENV},
            run=run_child, runtime=routing)
        def unit(symbol):
            return x_pool.run_unit(pool, {"alpha": parent}, src, config, symbol=symbol, day=DAY,
                query=QUERY, coin=SOL, policy=x_filters.FilterPolicy(), rng=random.Random(1),
                sleep=lambda _: None, fallback=fallback)
        outcome = unit("SOL")
        assert outcome.result is not None and outcome.reads == 40 and outcome.pages == 2, {
            "child_replies": child_replies, "requests": wire.requests, "connects": wire.connects,
            "stderr": diagnostics.decode(errors="replace").replace("SYNTHETIC_AUTH_TOKEN", "<redacted>")
                .replace("SYNTHETIC_CSRF", "<redacted>")}
        assert parent.cursor == "after-fallback"
        assert src.used == pool.reads_today("alpha") == 40
        assert pool.curl_used_today() and len(launches) == 1
        assert observed[0] == "bootstrap" and len(observed) == 2
        assert len(wire.requests) == 2 and wire.connects == []  # actual direct, never a proxy
        assert wire.origin_sni == ["origin.test", "origin.test"]
        assert all(request["host"] == f"origin.test:{wire.origin_port}" for request in wire.requests)
        clock.advance(minutes=10)
        parent.items = [blocked()]
        second = unit("ETH")
        assert second.result is None and second.reason == "cloudflare_block"
        assert pool.is_paused() and len(launches) == 1 and len(wire.requests) == 2
        assert src.used == pool.reads_today("alpha") == 40  # no refund, duplicate charge or second child
        exposed = repr(launches) + repr(child_replies) + diagnostics.decode(errors="replace")
        assert "SYNTHETIC_AUTH_TOKEN" not in exposed and "SYNTHETIC_CSRF" not in exposed


@pytest.mark.parametrize("mode", ["required-no-paths", "partial", "configured", "configured-optional"])
def test_spawned_configured_route_never_uses_available_direct_wire(tmp_path, mode):
    from api.data.attention import twscrape_reader as tr, web_queries
    from api.tests.data.attention.test_x_proxy_snapshot import query_document
    with fixture() as wire:
        document = query_document(tmp_path, labels=("alpha",), required=mode != "configured-optional")
        if mode in ("required-no-paths", "partial"):
            for key in ("x_proxy_list_path", "x_proxy_assignments_path", "x_proxy_policy_path"):
                document["collector"][key] = None
        if mode == "partial":
            document["collector"]["x_proxy_list_path"] = str(tmp_path / "missing-list")
        path = tmp_path / "queries.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        request = {"config_path": str(path.resolve()), "label": "alpha", "backend": "curl",
            "identity_revision": tr.identity_revision({}), "query": "$SOL",
            "kv": {"product": "Latest", "cursor": "fixture-continuation"}}
        options = {"direct_wire": True, "origin_url": wire.origin_url,
                   "origin_root": str(wire.certs["origin"]["root"]),
                   "proxy_root": str(wire.certs["proxy"]["root"])}
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LOCALAPPDATA", "USERPROFILE", "APPDATA"}
        environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
        environment.update(TWS_TELEMETRY="0", DO_NOT_TRACK="1", TWS_LOG_LEVEL="WARNING",
                           TWS_RAISE_WHEN_NO_ACCOUNT="1", TWS_HTTP_BACKEND="curl")
        completed = subprocess.run([sys.executable, "-m", "api.tests.data.attention.proxy_child_fixture", json.dumps(options)],
            input=json.dumps(request).encode(), capture_output=True, timeout=15, env=environment,
            cwd=Path(__file__).resolve().parents[4])
        assert completed.returncode == 0
        reply = json.loads(completed.stdout)
        if mode in ("required-no-paths", "partial"):
            assert reply == {"status": "refused", "reason": "request"}
        else:
            assert reply["status"] == "fail" and reply["kind"] == "proxy" and reply["proxy_reason"] == "proxy_config"
        assert wire.requests == [] and wire.connects == [] and wire.origin_sni == []
