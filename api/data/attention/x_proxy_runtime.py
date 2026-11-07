"""Collector-owned B2 resolver, immutable snapshots and sequential admission.

Only the reader imports this module. API/status readers use XPool.health alone.
Network dependencies are imported within request execution, never pure decisions.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from api.data.attention import web_queries, x_proxy as p
from api.data.attention.x_proxy_private import atomic_bytes, atomic_json, read_bounded, state_lock, verified_open, handle_bytes, secure_directory
from api.data.attention.x_proxy_snapshot import load_snapshot


@dataclass(frozen=True)
class Snapshot:
    config: web_queries.CollectorConfig
    policy: p.Policy | None
    assignments: dict = field(repr=False)
    revisions: dict
    config_path: Path | None
    private_snapshot: object | None = field(default=None, repr=False)
    reddit_assignments: dict = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Admission:
    proxy_id: str
    revision: str
    checked_at: datetime
    expires_at: datetime
    feeds: tuple[tuple[str, str], ...] = ()


class ProviderBudget:
    """The single ipapi reservation authority (contract F): the X pool state file and its lock.

    Reddit admission reserves through the same X pool; nothing creates a second budget. Without an
    X pool there is no budget, so a provider request is refused before any send."""

    def __init__(self, x_pool):
        self._pool = x_pool

    def request(self, send):
        p.require(self._pool is not None, "proxy_budget")
        return self._pool.provider_request(send)


class RedditRouteView:
    """Reddit side of the site-scoped account view over `reddit_accounts.RedditAccounts`.

    Implements the B2 route protocol `ProxyRuntime` already drives for the X pool (reconcile, result,
    unknown, provider request, lock path), so Reddit admission, quarantine and replacement reuse the
    runtime unchanged. Writes go through `RedditAccounts.set_proxy` (the seven B2 fields only)."""

    def __init__(self, accounts, budget: ProviderBudget, *, clock=lambda: datetime.now(UTC)):
        self.accounts, self.budget, self.clock = accounts, budget, clock
        self.path = accounts.path

    def __repr__(self):
        return "RedditRouteView(<private>)"

    def labels(self):
        return tuple(self.accounts.labels)

    def _acct(self, label):
        from api.data.attention.reddit_accounts import B2_ACCOUNT_KEYS
        p.require(label in self.accounts.labels, "proxy_assignment")
        with state_lock(self.accounts.path):
            entry = self.accounts._load()["accounts"][label]
        return {key: entry[key] for key in B2_ACCOUNT_KEYS}

    def reconcile_proxy(self, label, proxy_id, revision):
        p.opaque_id(revision)
        if proxy_id is not None:
            p.opaque_id(proxy_id)
        current = self._acct(label)
        if current["proxy_id"] == proxy_id and current["identity_revision"] == revision:
            return False
        self.accounts.set_proxy(label, proxy_id=proxy_id, identity_revision=revision, proxy_health="unknown",
                                proxy_checked_at=None, proxy_quarantine_until=None, proxy_reason=None,
                                proxy_changed_at=_utc(self.clock()).isoformat())
        return True

    def proxy_result(self, label, *, reason, quarantine_seconds=3600):
        p.require(reason is None or reason in p.REASONS, "proxy_config")
        now = _utc(self.clock())
        self.accounts.set_proxy(label, proxy_health="healthy" if reason is None else "quarantined",
                                proxy_reason=reason, proxy_checked_at=now.isoformat(),
                                proxy_quarantine_until=None if reason is None else
                                (now + timedelta(seconds=quarantine_seconds)).isoformat())

    def proxy_unknown(self, label, reason, *, wake_at=None):
        p.require(reason in p.REASONS, "proxy_config")
        self.accounts.set_proxy(label, proxy_health="unknown", proxy_reason=reason,
                                proxy_quarantine_until=None if wake_at is None else _utc(wake_at).isoformat())

    def provider_request(self, send):
        return self.budget.request(send)


def _utc(value):
    p.require(value.tzinfo is not None and value.utcoffset() == timedelta(0), "proxy_config")
    return value.astimezone(UTC)


def _stamp(value, now):
    try:
        stamp = _utc(datetime.fromisoformat(value))
        p.require(stamp <= now, "proxy_feed")
        return stamp
    except (ValueError, TypeError):
        raise p.ProxyFailure("proxy_feed") from None


def private_read(path, policy, repo_root, limit):
    with verified_open(path, policy.private_root, repo_root=repo_root, service_sid=policy.service_sid) as stream:
        return handle_bytes(stream, limit)


class FeedCache:
    def __init__(self, directory: Path, *, policy=None, repo_root=None):
        self.directory, self.policy, self.repo_root = directory, policy, repo_root

    def read(self, path, limit):
        return (private_read(path, self.policy, self.repo_root, limit) if self.policy is not None
                else read_bounded(path, limit))

    def publish(self, slot, body, now):
        feed = p.parse_feed(slot, body, now)
        revision = str(uuid4())
        root = self.directory / slot / revision
        sid = self.policy.service_sid if self.policy is not None else None
        if sid:
            secure_directory(root, service_sid=sid)
        else:
            root.mkdir(parents=True, mode=0o700)
        atomic_bytes(root / "body", body, service_sid=sid)
        atomic_json(root / "metadata.json", {"retrieved_at": now.isoformat(),
            "source_version": list(feed.source_version), "sha256": hashlib.sha256(body).hexdigest()}, service_sid=sid)
        atomic_json(self.directory / slot / "current.json", {"revision": revision}, service_sid=sid)
        return feed, revision

    def load(self, slot, now):
        p.require(slot in ("spamhaus", "firehol"), "proxy_feed")
        pointer = p.exact(p.strict_json(self.read(self.directory / slot / "current.json", p.SMALL_LIMIT)), ("revision",))
        revision = p.opaque_id(pointer["revision"])
        root = self.directory / slot / revision
        body = self.read(root / "body", p.FEED_DECODED_LIMIT)
        metadata = p.exact(p.strict_json(self.read(root / "metadata.json", p.SMALL_LIMIT)), ("retrieved_at", "source_version", "sha256"))
        retrieved = _stamp(metadata["retrieved_at"], now)
        p.require(now - retrieved <= timedelta(days=1) and metadata["sha256"] == hashlib.sha256(body).hexdigest(), "proxy_feed")
        feed = p.parse_feed(slot, body, now)
        p.require(metadata["source_version"] == list(feed.source_version), "proxy_feed")
        return feed, revision


async def one_shot(route, policy, url, limit, *, headers=None):
    """Dedicated one-shot HTTP client; (None, None) explicitly selects direct."""
    from api.data.attention.x_proxy_transport import client, direct_client
    reason = None
    try:
        p.require((route is None) == (policy is None), "proxy_policy")
        async with asyncio.timeout(10):
            session_client = (direct_client(headers=headers) if route is None else
                              client(route, policy, headers=headers, limit=limit, allow_content_encoding=True))
            async with session_client as session:
                async with session.stream("GET", url, headers={"accept-encoding": "identity"}) as response:
                    p.require(response.status_code == 200, "proxy_response")
                    import zlib
                    body = bytearray()
                    decoded_limit = p.FEED_DECODED_LIMIT if url in (p.SPAMHAUS, p.FIREHOL) else limit
                    encoding = response.headers.get("content-encoding", "identity")
                    decoder = zlib.decompressobj(31 if encoding == "gzip" else 15) if encoding != "identity" else None
                    async for chunk in response.aiter_raw():
                        remaining = decoded_limit - len(body)
                        decoded = decoder.decompress(chunk, remaining + 1) if decoder else chunk
                        p.require(len(decoded) <= remaining and (decoder is None or not decoder.unconsumed_tail), "proxy_response")
                        body.extend(decoded)
                    if decoder:
                        remaining = decoded_limit - len(body)
                        final = decoder.flush(remaining + 1)
                        p.require(len(final) <= remaining and decoder.eof and not decoder.unused_data, "proxy_response")
                        body.extend(final)
                    return bytes(body)
    except TimeoutError:
        reason = "proxy_timeout"
    except Exception as exc:
        reason = exc.reason if isinstance(exc, p.ProxyFailure) else "proxy_transport"
    raise p.ProxyFailure(reason) from None


class ProxyRuntime:
    def __init__(self, config, *, config_path=None, repo_root, clock=lambda: datetime.now(UTC),
                 snapshot_loader=load_snapshot, request=one_shot):
        self.initial_config = config
        self.config_path = Path(config_path) if config_path is not None else None
        self.repo_root, self.clock = Path(repo_root), clock
        self.snapshot_loader, self.request = snapshot_loader, request
        self._effective, self._revisions, self.admissions = {}, {}, {}
        self.snapshot = None

    def reconcile(self, pool, *, reddit=None):
        """Site-scoped reconciliation (contract F); returns the changed X labels.

        `pool` is the X pool, `reddit` the optional `RedditRouteView`. Each site reconciles only its own
        labels: a Reddit assignment edit never re-revisions an X account and vice versa."""
        config = self.initial_config
        if self.config_path is not None:
            p.require(self.config_path.is_absolute(), "proxy_private")
            try:
                body = read_bounded(self.config_path, 1024 * 1024)
                config = web_queries.validate(p.strict_json(body, limit=1024 * 1024)).config
            except (web_queries.QueriesError, OSError, ValueError):
                raise p.ProxyFailure("proxy_config") from None
        paths = (config.x_proxy_list_path, config.x_proxy_assignments_path, config.x_proxy_policy_path)
        if all(path is None for path in paths):
            p.require(not config.x_proxy_required, "proxy_config")
            changed = set()
            for label in config.x_accounts:
                safe = config.as_dict()
                safe["x_account_identities"] = {label: safe["x_account_identities"].get(label)}
                safe["x_accounts"] = [label]
                effective = ("direct", json.dumps(safe, sort_keys=True))
                baseline = label not in self._effective and not config.x_identity_enabled and pool._acct(label)["proxy_id"] is None
                effective_changed = self._effective.get(label) != effective
                if effective_changed:
                    self._effective[label] = effective
                    self._revisions[label] = str(uuid4())
                    self.admissions.pop(label, None)
                    if not baseline:
                        changed.add(label)
                if effective_changed and not baseline and pool.reconcile_proxy(label, None, self._revisions[label]):
                    changed.add(label)
            for label in set(self._effective) - set(config.x_accounts):
                self._effective.pop(label, None)
                self._revisions.pop(label, None)
                self.admissions.pop(label, None)
            self.snapshot = Snapshot(config, None, {}, dict(self._revisions), self.config_path)
            pool.proxy_direct, pool.proxy_required = True, False
            return changed
        p.require(all(paths) and self.config_path is not None, "proxy_config")
        private = self.snapshot_loader(self.config_path, repo_root=self.repo_root)
        config, policy, union = private.config, private.policy, private.assignments
        reddit_labels = tuple(a["label"] for a in config.reddit_browser_accounts)
        assignments = {label: item for label, item in union.items() if label in config.x_accounts}
        reddit_assignments = {label: item for label, item in union.items() if label in reddit_labels}
        p.require(set(assignments) == set(config.x_accounts), "proxy_assignment")
        effective_accounts = {}
        for label, assignment in assignments.items():
            # Credential-bearing comparison is process memory only; persisted revision is opaque.
            safe_config = {k: v for k, v in config.as_dict().items() if not k.startswith("reddit_")}
            safe_config["x_account_identities"] = {label: safe_config["x_account_identities"].get(label)}
            safe_config["x_accounts"] = [label]
            effective_accounts[label] = (assignment, policy, json.dumps(safe_config, sort_keys=True))
        route_config = {k: v for k, v in config.as_dict().items() if k.startswith("x_proxy_")}
        reddit_effective = {label: (reddit_assignments.get(label), policy, json.dumps(route_config, sort_keys=True))
                            for label in reddit_labels}
        changed = {label for label, effective in effective_accounts.items()
                   if self._effective.get(label) != effective}
        reddit_changed = {label for label, effective in reddit_effective.items()
                          if self._effective.get(label) != effective}
        previous_private = self.snapshot.private_snapshot if self.snapshot is not None else None
        if previous_private is not None and previous_private.roles != private.roles and not (changed or reddit_changed):
            # A raw-only publication still changes the trusted snapshot. Semantic
            # per-account changes above evict only the affected account instead.
            changed.update(assignments)
            reddit_changed.update(reddit_labels)
        for label in reddit_labels:
            if label in reddit_changed:
                self._effective[label] = reddit_effective[label]
                self._revisions[label] = str(uuid4())
                self.admissions.pop(label, None)
            if reddit is not None:
                item = reddit_assignments.get(label)
                reddit.reconcile_proxy(label, None if item is None else item.proxy_id, self._revisions[label])
        for label, assignment in assignments.items():
            effective = effective_accounts[label]
            if label in changed:
                self._effective[label] = effective
                self._revisions[label] = str(uuid4())
                self.admissions.pop(label, None)
                changed.add(label)
            if pool.reconcile_proxy(label, assignment.proxy_id, self._revisions[label]):
                changed.add(label)
        previous_reddit = ({a["label"] for a in self.snapshot.config.reddit_browser_accounts}
                           if self.snapshot is not None else set())
        for label in set(self._effective) - set(assignments) - set(reddit_labels):
            self._effective.pop(label, None)
            self._revisions.pop(label, None)
            self.admissions.pop(label, None)
            if label not in previous_reddit:
                changed.add(label)
        pool.proxy_direct, pool.proxy_required = False, True
        pool.connection_style = config.x_connection_style
        pool.proxy_regions = {label: item.region for label, item in assignments.items()}
        self.snapshot = Snapshot(config, policy, assignments, dict(self._revisions), self.config_path, private,
                                 reddit_assignments)
        for label, admission in list(self.admissions.items()):
            try:
                cache = FeedCache(policy.cache_dir, policy=policy, repo_root=self.repo_root)
                current = tuple((slot, cache.load(slot, _utc(self.clock()))[1]) for slot, _ in admission.feeds)
                p.require(current == admission.feeds, "proxy_feed")
            except p.ProxyFailure:
                self.admissions.pop(label, None)
                if label in assignments:
                    pool.proxy_unknown(label, "proxy_feed")
                elif reddit is not None and label in reddit_labels:
                    reddit.proxy_unknown(label, "proxy_feed")
        return changed

    def route_admission(self, site, label):
        """Reddit admission provider (`reddit_accounts` seam): pure lookup, never a network call.

        'direct' only under the all-null direct configuration; 'proxy' only for a currently admitted,
        current-revision Reddit assignment; everything else is 'unadmitted' (default deny)."""
        snapshot = self.snapshot
        if site != "reddit" or snapshot is None:
            return "unadmitted"
        if label not in {a["label"] for a in snapshot.config.reddit_browser_accounts}:
            return "unadmitted"
        if snapshot.policy is None:
            return "direct" if not snapshot.config.x_proxy_required else "unadmitted"
        return "proxy" if label in snapshot.reddit_assignments and self.admitted(label) else "unadmitted"

    def admitted(self, label):
        now = _utc(self.clock())
        item = self.admissions.get(label)
        return bool(item and item.revision == self._revisions.get(label) and item.checked_at <= now < item.expires_at)

    def next_health(self, label):
        policy = self.snapshot.policy
        now = _utc(self.clock())
        path = policy.cache_dir / "health" / (label + ".json")
        if not path.exists():
            return now
        record = p.exact(p.strict_json(private_read(path, policy, self.repo_root, p.SMALL_LIMIT)), ("attempts",))
        p.require(isinstance(record["attempts"], list) and len(record["attempts"]) <= 24, "proxy_budget")
        stamps = [_stamp(value, now) for value in record["attempts"]]
        return max(stamps) + timedelta(seconds=self.snapshot.config.x_proxy_health_interval_seconds) if stamps else now

    def _health_reserve(self, label, pool):
        now = _utc(self.clock())
        path = self.snapshot.policy.cache_dir / "health" / (label + ".json")
        with state_lock(pool.path):
            history = []
            if path.exists():
                record = p.exact(p.strict_json(private_read(path, self.snapshot.policy, self.repo_root, p.SMALL_LIMIT)), ("attempts",))
                p.require(isinstance(record["attempts"], list) and len(record["attempts"]) <= 24, "proxy_budget")
                history = [_stamp(value, now) for value in record["attempts"]]
            latest = max(history) if history else None
            history = [stamp for stamp in history if stamp.date() == now.date()]
            interval = timedelta(seconds=self.snapshot.config.x_proxy_health_interval_seconds)
            p.require(len(history) < 24 and (latest is None or now - latest >= interval), "proxy_budget")
            atomic_json(path, {"attempts": [stamp.isoformat() for stamp in history] + [now.isoformat()]},
                        service_sid=self.snapshot.policy.service_sid)

    def admit(self, label, pool):
        snapshot = self.snapshot
        p.require(snapshot is not None, "proxy_revision")
        if snapshot.policy is None:
            return
        if self.admitted(label) and _utc(self.clock()) < self.admissions[label].checked_at + timedelta(seconds=snapshot.config.x_proxy_health_interval_seconds):
            return
        assignment = snapshot.assignments.get(label) or snapshot.reddit_assignments.get(label)
        p.require(assignment is not None, "proxy_assignment")
        state = pool._acct(label)
        now = _utc(self.clock())
        if state["proxy_quarantine_until"]:
            p.require(now >= datetime.fromisoformat(state["proxy_quarantine_until"]), "proxy_quarantine")
        self._health_reserve(label, pool)
        policy = snapshot.policy
        started = time.monotonic()
        expires = [now + timedelta(seconds=snapshot.config.x_proxy_admission_max_age_seconds)]
        calls = 0
        def fetch(url, limit):
            nonlocal calls
            calls += 1
            p.require(calls <= 6 and time.monotonic() - started < 60, "proxy_timeout")
            async def run():
                async with asyncio.timeout(min(10, max(0, 60 - (time.monotonic() - started)))):
                    return await self.request(assignment.route, policy, url, limit)
            try:
                return asyncio.run(run())
            except TimeoutError:
                raise p.ProxyFailure("proxy_timeout") from None
        try:
            echo = p.strict_json(fetch(policy.echo, p.SMALL_LIMIT))
            p.require(isinstance(echo, dict) and isinstance(echo.get("ip"), str)
                      and p.normalized_ip(echo["ip"]) == assignment.expected_ip, "proxy_exit")
            cache = FeedCache(policy.cache_dir, policy=policy, repo_root=self.repo_root)
            feed_revisions = {}
            for slot, url in (("spamhaus", p.SPAMHAUS), ("firehol", p.FIREHOL)):
                try:
                    feed, revision = cache.load(slot, now)
                except p.ProxyFailure:
                    feed, revision = cache.publish(slot, fetch(url, p.FEED_WIRE_LIMIT), now)
                p.require(not feed.contains(assignment.expected_ip), "proxy_feed")
                expires.append(feed.expires_at)
                feed_revisions[slot] = revision
            if policy.metadata_provider == "ipapi":
                data = p.strict_json(pool.provider_request(lambda: fetch(p.IPAPI, p.SMALL_LIMIT)))
                p.require(isinstance(data, dict) and all(isinstance(data.get(k), str) for k in
                    ("ip", "region_code", "country_code", "timezone")), "proxy_region")
                p.require(p.normalized_ip(data["ip"]) == assignment.expected_ip
                    and data["country_code"].upper() == assignment.region.split("-", 1)[0]
                    and ("-" not in assignment.region or data["region_code"].upper() == assignment.region.split("-", 1)[1])
                    and data["timezone"] == assignment.timezone, "proxy_region")
            baseline = fetch(policy.baseline, p.BASELINE_LIMIT)
            p.require(hashlib.sha256(baseline).hexdigest() == policy.baseline_sha256, "proxy_baseline")
            p.require(time.monotonic() - started <= 60, "proxy_timeout")
            self.admissions[label] = Admission(assignment.proxy_id, snapshot.revisions[label], now, min(expires), tuple(feed_revisions.items()))
            atomic_json(policy.cache_dir / "admissions" / (label + ".json"),
                {"proxy_id": assignment.proxy_id, "identity_revision": snapshot.revisions[label],
                 "checked_at": now.isoformat(), "expires_at": min(expires).isoformat(),
                 "feeds": feed_revisions}, service_sid=policy.service_sid)
            pool.proxy_result(label, reason=None)
        except p.ProxyFailure as failure:
            self.admissions.pop(label, None)
            pool.proxy_result(label, reason=failure.reason,
                              quarantine_seconds=snapshot.config.x_proxy_quarantine_seconds)
            raise p.ProxyFailure(failure.reason) from None
