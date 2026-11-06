"""Synthetic sequential admission, durable raw cache and provider provenance."""
import hashlib
import json
from functools import partial
from pathlib import Path

import pytest

from api.data.attention import x_proxy as p, x_proxy_runtime as runtime, x_proxy_snapshot as snapshot
from api.tests.data.attention.test_x_proxy_snapshot import NOW, fixture_open, write_snapshot
from api.tests.data.attention.test_x_proxy_policy import spamhaus, firehol


class Pool:
    def __init__(self, root):
        self.path = root / "state.json"
        self.result = []
        self.provider_starts = 0
    def _acct(self, label):
        return {"proxy_quarantine_until": None}
    def proxy_result(self, label, **kwargs):
        self.result.append((label, kwargs))
    def provider_request(self, request):
        self.provider_starts += 1
        return request()


def setup(tmp_path, monkeypatch, *, provider=None, failure=None):
    path = write_snapshot(tmp_path / "private")
    policy_path = path.parent / "policy.json"
    doc = json.loads(policy_path.read_bytes())
    doc["baseline"]["sha256"] = hashlib.sha256(b"trusted baseline").hexdigest()
    doc["metadata_provider"] = provider
    policy_path.write_text(json.dumps(doc), encoding="utf-8")
    loader = partial(snapshot.load_snapshot, opener=fixture_open)
    private = loader(path, repo_root=tmp_path / "repo")
    # Only the low-level filesystem ACL boundary is synthetic; cache publication,
    # raw bytes/hash reload, request ordering and admission are production code.
    monkeypatch.setattr(runtime, "private_read", lambda path, policy, repo, limit: runtime.read_bounded(Path(path), limit))
    original_atomic = runtime.atomic_json
    original_bytes = runtime.atomic_bytes
    monkeypatch.setattr(runtime, "atomic_json", lambda path, value, **kw: original_atomic(path, value))
    monkeypatch.setattr(runtime, "atomic_bytes", lambda path, value, **kw: original_bytes(path, value))
    monkeypatch.setattr(runtime, "secure_directory", lambda path, **kw: path.mkdir(parents=True, exist_ok=True))
    calls = []
    async def request(route, policy, url, limit):
        calls.append(url)
        if url == failure:
            raise p.ProxyFailure("proxy_timeout")
        return {policy.echo: b'{"ip":"8.8.8.8"}', p.SPAMHAUS: spamhaus(), p.FIREHOL: firehol(),
            p.IPAPI: b'{"ip":"8.8.8.8","country_code":"US","region_code":"NY","timezone":"America/New_York"}',
            policy.baseline: b"trusted baseline"}[url]
    resolver = runtime.ProxyRuntime(private.config, config_path=path, repo_root=tmp_path / "repo",
        clock=lambda: NOW, snapshot_loader=loader, request=request)
    resolver.snapshot = runtime.Snapshot(private.config, private.policy, private.assignments,
        {label: "c92163a0-a06d-4ae1-bbe4-2f36c308a250" for label in private.assignments}, path, private)
    resolver._revisions = dict(resolver.snapshot.revisions)
    return resolver, Pool(tmp_path), calls


def test_unselected_provider_zero_requests_order_cache_reload_and_expiry(tmp_path, monkeypatch):
    resolver, pool, calls = setup(tmp_path, monkeypatch)
    resolver.admit("alpha", pool)
    policy = resolver.snapshot.policy
    assert calls == [policy.echo, p.SPAMHAUS, p.FIREHOL, policy.baseline]
    assert pool.provider_starts == 0 and resolver.admitted("alpha")
    admission = resolver.admissions["alpha"]
    assert admission.expires_at > NOW
    cache = runtime.FeedCache(policy.cache_dir, policy=policy, repo_root=resolver.repo_root)
    for slot, revision in admission.feeds:
        feed, loaded_revision = cache.load(slot, NOW)
        assert loaded_revision == revision and not feed.contains("8.8.8.8")
        body = policy.cache_dir / slot / revision / "body"
        body.write_bytes(body.read_bytes() + b"tampered")
        with pytest.raises(p.ProxyFailure, match="proxy_feed"):
            cache.load(slot, NOW)
    resolver.admit("alpha", pool)
    assert len(calls) == 4  # fresh admission performs no extra health requests


def test_selected_provider_is_one_serial_request_before_baseline(tmp_path, monkeypatch):
    resolver, pool, calls = setup(tmp_path, monkeypatch, provider="ipapi")
    resolver.admit("alpha", pool)
    assert calls == [resolver.snapshot.policy.echo, p.SPAMHAUS, p.FIREHOL, p.IPAPI, resolver.snapshot.policy.baseline]
    assert pool.provider_starts == 1 and resolver.admitted("alpha")


def test_selected_provider_failure_never_owner_fallback_or_baseline(tmp_path, monkeypatch):
    resolver, pool, calls = setup(tmp_path, monkeypatch, provider="ipapi", failure=p.IPAPI)
    with pytest.raises(p.ProxyFailure, match="proxy_timeout"):
        resolver.admit("alpha", pool)
    assert pool.provider_starts == 1 and calls[-1] == p.IPAPI
    assert resolver.snapshot.policy.baseline not in calls
    assert not resolver.admitted("alpha")
    assert pool.result[-1][1]["reason"] == "proxy_timeout"


@pytest.mark.parametrize("observed", [
    {}, {"ip": "8.8.8.8", "region_code": "NY", "country_code": "US"},
    {"ip": "1.1.1.1", "region_code": "NY", "country_code": "US", "timezone": "America/New_York"},
    {"ip": "8.8.8.8", "region_code": "NY", "country_code": "GB", "timezone": "America/New_York"},
    {"ip": "8.8.8.8", "region_code": "NY", "country_code": "US", "timezone": "Europe/London"},
])
def test_selected_provider_unknown_or_mismatched_observation_never_owner_fallback(tmp_path, monkeypatch, observed):
    resolver, pool, calls = setup(tmp_path, monkeypatch, provider="ipapi")
    original = resolver.request
    async def request(route, policy, url, limit):
        if url == p.IPAPI:
            calls.append(url)
            return json.dumps(observed).encode()
        return await original(route, policy, url, limit)
    resolver.request = request
    with pytest.raises(p.ProxyFailure, match="proxy_region"):
        resolver.admit("alpha", pool)
    assert pool.provider_starts == 1 and calls[-1] == p.IPAPI
    assert resolver.snapshot.policy.baseline not in calls and not resolver.admitted("alpha")
