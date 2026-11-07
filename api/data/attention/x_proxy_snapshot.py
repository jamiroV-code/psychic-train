"""ACL-verified immutable private snapshot and transient child attestation.

Verifier material and credential bytes have no public representation and are never
persisted. HMAC proves snapshot equality, not trust against a same-user attacker.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from api.data.attention import web_queries, x_proxy as p
from api.data.attention.x_proxy_private import handle_bytes, read_bounded, verified_open

DOMAIN = b"collector-b2-child-v2\0"
ROLES = ("query-config", "policy", "assignments", "list", "safe-admission")
HEX32 = re.compile(r"[0-9a-f]{64}")


class SensitiveRequest(dict):
    def __repr__(self):
        return "<private child request>"


@dataclass(frozen=True, repr=False)
class PrivateSnapshot:
    config: web_queries.CollectorConfig
    policy: p.Policy
    assignments: dict
    roles: tuple = field(repr=False)


def load_snapshot(config_path: Path, *, repo_root: Path, opener=verified_open):
    p.require(config_path.is_absolute(), "proxy_private")
    # Discovery bytes select only the root/SID to inspect; they are never used
    # to construct a client, resolve a route or execute a request.
    discovery_config = read_bounded(config_path, 1024 * 1024)
    try:
        discovered = web_queries.validate(p.strict_json(discovery_config, limit=1024 * 1024)).config
        p.require(discovered.x_proxy_policy_path is not None, "proxy_config")
        policy_path = Path(discovered.x_proxy_policy_path)
        discovery_policy = read_bounded(policy_path, p.SMALL_LIMIT)
        policy = p.parse_policy(discovery_policy, policy_path.parent)
        root = policy_path.parent
        paths = (config_path, policy_path, Path(discovered.x_proxy_assignments_path), Path(discovered.x_proxy_list_path))
        p.require(all(path.is_absolute() and path.resolve(strict=True) == path for path in paths), "proxy_private")
        roles = []
        with contextlib.ExitStack() as stack:
            streams = [stack.enter_context(opener(path, root, repo_root=repo_root, service_sid=policy.service_sid)) for path in paths]
            for role, path, stream, limit in zip(ROLES, paths, streams,
                    (1024 * 1024, p.SMALL_LIMIT, p.SMALL_LIMIT, 1024 * 1024)):
                roles.append((role, str(path), handle_bytes(stream, limit)))
            p.require(roles[0][2] == discovery_config and roles[1][2] == discovery_policy, "proxy_revision")
            config = web_queries.validate(p.strict_json(roles[0][2], limit=1024 * 1024)).config
            policy = p.parse_policy(roles[1][2], root)
            assignments = p.parse_assignments(roles[2][2], roles[3][2], config.x_accounts,
                required=config.x_proxy_required,
                identities=config.x_account_identities if config.x_identity_enabled else None)
        return PrivateSnapshot(config, policy, assignments, tuple(roles))
    except (OSError, web_queries.QueriesError, TypeError, ValueError):
        raise p.ProxyFailure("proxy_config") from None


def work_envelope(request):
    p.require(isinstance(request.get("label"), str) and re.fullmatch(r"[a-z0-9_]{1,24}", request["label"]), "proxy_config")
    p.opaque_id(request.get("proxy_id"))
    p.opaque_id(request.get("identity_revision"))
    p.require(request.get("backend") == "curl" and isinstance(request.get("request_nonce"), str)
              and HEX32.fullmatch(request["request_nonce"]) is not None, "proxy_config")
    query, kv = request.get("query"), request.get("kv")
    p.require(isinstance(query, str) and 0 < len(query.encode("utf-8")) <= 4096
              and isinstance(kv, dict) and set(kv) <= {"product", "cursor"}
              and kv.get("product") == "Latest", "proxy_config")
    cursor = kv.get("cursor")
    p.require(cursor is None or isinstance(cursor, str) and len(cursor.encode("utf-8")) <= 4096, "proxy_config")
    query_id = request.get("query_id")
    p.require("query_id" in request and (query_id is None or isinstance(query_id, str)
              and re.fullmatch(r"[A-Za-z0-9_-]{16,32}", query_id)), "proxy_config")
    expiry = request.get("admission_expires_at")
    p.require(isinstance(expiry, str) and len(expiry) <= 64, "proxy_config")
    return (request["label"].encode(), request["proxy_id"].encode(), request["identity_revision"].encode(),
            request["backend"].encode(), request["request_nonce"].encode(), expiry.encode(),
            query.encode("utf-8"), b"Latest", b"null" if cursor is None else b"present", b"" if cursor is None else cursor.encode("utf-8"),
            b"null" if query_id is None else b"present", b"" if query_id is None else query_id.encode("ascii"))


def digest(key: bytes, roles, request) -> str:
    p.require(len(key) == 32 and tuple(role for role, _, _ in roles) == ROLES, "proxy_revision")
    mac = hmac.new(key, DOMAIN, hashlib.sha256)
    def frame(value):
        mac.update(len(value).to_bytes(8, "big"))
        mac.update(value)
    for role, path, raw in roles:
        frame(role.encode("ascii"))
        frame(path.encode("utf-8"))
        frame(raw)
    for value in work_envelope(request):
        frame(value)
    return mac.hexdigest()


def attest(roles, request):
    key = secrets.token_bytes(32)
    request["attestation_key"] = key.hex()
    request["attestation_tag"] = digest(key, roles, request)


def verify(roles, request):
    key, tag = request.get("attestation_key"), request.get("attestation_tag")
    p.require(isinstance(key, str) and isinstance(tag, str) and HEX32.fullmatch(key) is not None
              and HEX32.fullmatch(tag) is not None, "proxy_revision")
    expected = digest(bytes.fromhex(key), roles, request)
    p.require(hmac.compare_digest(expected, tag), "proxy_revision")
