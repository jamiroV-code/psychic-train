"""Transient B2 child equality proof; no keys/tags or credential hashes on disk.

The protocol is bounded private stdin only. Replies bind a nonce and revision but
never echo sensitive verifier material. This is not same-user authentication.
"""
from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from api.data.attention import x_proxy as p
from api.data.attention.x_proxy_snapshot import SensitiveRequest, attest, verify, work_envelope

REQUEST_KEYS = frozenset({"config_path", "label", "proxy_id", "identity_revision", "backend", "request_nonce",
    "admission_expires_at", "query", "kv", "attestation_key", "attestation_tag"})
ADMISSION_KEYS = ("proxy_id", "identity_revision", "checked_at", "expires_at", "feeds")


def admission_role(private, label, revision, *, now, repo_root):
    from api.data.attention.x_proxy_runtime import FeedCache, private_read
    p.require(re.fullmatch(r"[a-z0-9_]{1,24}", label) is not None and label in private.config.x_accounts
              and label in private.assignments, "proxy_assignment")
    p.require(UUID(p.opaque_id(revision)).version == 4, "proxy_revision")
    policy = private.policy
    path = policy.cache_dir / "admissions" / (label + ".json")
    try:
        canonical = path.resolve(strict=True)
        p.require(canonical == path, "proxy_private")
        path = canonical
    except OSError:
        raise p.ProxyFailure("proxy_private") from None
    raw = private_read(path, policy, repo_root, p.SMALL_LIMIT)
    record = p.exact(p.strict_json(raw), ADMISSION_KEYS)
    try:
        checked = datetime.fromisoformat(record["checked_at"])
        expiry = datetime.fromisoformat(record["expires_at"])
        p.require(checked.tzinfo is not None and expiry.tzinfo is not None
            and checked.utcoffset().total_seconds() == 0 and expiry.utcoffset().total_seconds() == 0
            and checked <= now < expiry
            and (expiry - checked).total_seconds() <= private.config.x_proxy_admission_max_age_seconds,
            "proxy_revision")
    except (ValueError, TypeError, AttributeError):
        raise p.ProxyFailure("proxy_revision") from None
    p.require(record["identity_revision"] == revision
        and record["proxy_id"] == private.assignments[label].proxy_id, "proxy_revision")
    feeds = p.exact(record["feeds"], ("spamhaus", "firehol"))
    cache = FeedCache(policy.cache_dir, policy=policy, repo_root=repo_root)
    for slot, expected in feeds.items():
        p.opaque_id(expected)
        feed, current = cache.load(slot, now)
        p.require(current == expected and expiry <= feed.expires_at, "proxy_revision")
        p.require(not feed.contains(private.assignments[label].expected_ip), "proxy_feed")
    return ("safe-admission", str(path), raw), record


def prepare(runtime, label, query, kv):
    p.require(runtime.admitted(label), "proxy_revision")
    private = runtime.snapshot_loader(runtime.config_path, repo_root=runtime.repo_root)
    p.require(private.roles == runtime.snapshot.private_snapshot.roles, "proxy_revision")
    revision = runtime.snapshot.revisions[label]
    role, record = admission_role(private, label, revision, now=runtime.clock(), repo_root=runtime.repo_root)
    request = SensitiveRequest({"config_path": private.roles[0][1], "label": label,
        "proxy_id": private.assignments[label].proxy_id, "identity_revision": revision,
        "backend": "curl", "request_nonce": secrets.token_hex(32),
        "admission_expires_at": record["expires_at"], "query": query, "kv": dict(kv)})
    work_envelope(request)
    attest((*private.roles, role), request)
    return request


def reload_verified(request, *, repo_root, now, snapshot_loader=None):
    from api.data.attention.x_proxy_snapshot import load_snapshot
    p.exact(request, REQUEST_KEYS)
    work_envelope(request)
    path = request["config_path"]
    p.require(isinstance(path, str) and Path(path).is_absolute(), "proxy_private")
    private = (snapshot_loader or load_snapshot)(Path(path), repo_root=repo_root)
    role, record = admission_role(private, request["label"], request["identity_revision"], now=now, repo_root=repo_root)
    p.require(record["expires_at"] == request["admission_expires_at"]
              and record["proxy_id"] == request["proxy_id"], "proxy_revision")
    verify((*private.roles, role), request)
    return private, record


def validate_reply(runtime, request, reply):
    p.require(isinstance(reply, dict) and reply.get("request_nonce") == request["request_nonce"]
              and reply.get("identity_revision") == request["identity_revision"], "proxy_revision")
    p.require(runtime.admitted(request["label"])
              and runtime.snapshot.revisions.get(request["label"]) == request["identity_revision"], "proxy_revision")
    private = runtime.snapshot_loader(runtime.config_path, repo_root=runtime.repo_root)
    p.require(private.roles == runtime.snapshot.private_snapshot.roles, "proxy_revision")
    role, record = admission_role(private, request["label"], request["identity_revision"], now=runtime.clock(), repo_root=runtime.repo_root)
    p.require(record["expires_at"] == request["admission_expires_at"], "proxy_revision")
    # Authenticate the reloaded roles against the same short-lived proof, too.
    verify((*private.roles, role), request)
