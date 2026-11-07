"""B2 private snapshot/HMAC protocol regressions; sensitive values are synthetic."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from api.data.attention import web_queries as wq, x_proxy as p
from api.data.attention import x_proxy_snapshot as snapshot
from api.tests.data.attention.test_x_proxy_policy import assignment_doc, policy_doc

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


def query_document(root, labels=("alpha", "beta"), required=True):
    return {"version": 1, "note": "synthetic B2 fixture", "collector": {**wq.DEFAULTS,
        "x_accounts": list(labels), "x_accounts_db_path": str(root / "accounts"),
        "x_proxy_required": required, "x_proxy_list_path": str(root / "routes.txt"),
        "x_proxy_assignments_path": str(root / "assignments.json"), "x_proxy_policy_path": str(root / "policy.json")},
        "subreddits": ["Bitcoin"], "ambiguous": {key: [] for key in wq.SOURCES}, "coins": {}}


@contextlib.contextmanager
def fixture_open(path, root, *, repo_root, service_sid):
    # Dependency-level synthetic inspector: no production environment/CLI bypass.
    assert path == root or root in path.parents
    assert service_sid == "S-1-5-21-1-2-3-1001"
    assert repo_root != root and repo_root not in path.parents
    with path.open("rb") as stream:
        yield stream


def write_snapshot(root):
    root.mkdir(mode=0o700, exist_ok=True)
    query = query_document(root)
    for name, value in (("queries.json", query), ("policy.json", policy_doc(root)), ("assignments.json", assignment_doc())):
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    (root / "routes.txt").write_text("https://user:SYNTHETIC_CREDENTIAL_MARKER@first.example\nhttps://second.example\n", encoding="utf-8")
    return root / "queries.json"


def test_snapshot_parses_only_verified_handle_bytes_and_hides_private_repr(tmp_path):
    root = tmp_path / "private"
    path = write_snapshot(root)
    value = snapshot.load_snapshot(path, repo_root=tmp_path / "repo", opener=fixture_open)
    assert tuple(role for role, _, _ in value.roles) == snapshot.ROLES[:4]
    assert value.assignments["alpha"].route.auth == ("user", "SYNTHETIC_CREDENTIAL_MARKER")
    assert "CREDENTIAL_MARKER" not in repr(value)
    assert all(role_path == str(__import__("pathlib").Path(role_path).resolve()) for _, role_path, _ in value.roles)


def test_discovery_policy_change_is_not_used_after_verification(tmp_path):
    root = tmp_path / "private"
    path = write_snapshot(root)
    changed = False
    @contextlib.contextmanager
    def race(path, root, **kwargs):
        nonlocal changed
        if not changed:
            changed = True
            doc = policy_doc(root)
            doc["baseline"]["sha256"] = "b" * 64
            (root / "policy.json").write_text(json.dumps(doc), encoding="utf-8")
        with fixture_open(path, root, **kwargs) as stream:
            yield stream
    with pytest.raises(p.ProxyFailure, match="proxy_revision"):
        snapshot.load_snapshot(path, repo_root=tmp_path / "repo", opener=race)


def proof(tmp_path, query_id=None):
    roles = tuple((role, str(tmp_path / (str(index) + ".private")), b"raw-" + role.encode()) for index, role in enumerate(snapshot.ROLES))
    request = snapshot.SensitiveRequest({"label": "alpha", "proxy_id": str(UUID(int=1)), "identity_revision": str(uuid4()),
        "backend": "curl", "request_nonce": "1" * 64, "admission_expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "query": "$SOL", "kv": {"product": "Latest"}, "query_id": query_id})
    snapshot.attest(roles, request)
    return roles, request


def test_envelope_v2_domain_and_query_id_frame_follow_the_cursor(tmp_path):
    assert snapshot.DOMAIN == b"collector-b2-child-v2\0"
    _, absent = proof(tmp_path)
    _, present = proof(tmp_path, "vLHjqbDv7TPFMBkIIO1nOA")
    assert snapshot.work_envelope(absent)[-2:] == (b"null", b"")
    assert snapshot.work_envelope(present)[-2:] == (b"present", b"vLHjqbDv7TPFMBkIIO1nOA")
    assert snapshot.work_envelope(present)[-4:-2] == (b"null", b"")  # cursor frame stays in place


@pytest.mark.parametrize("value", ["short", "x" * 33, "bad id with space!", 7, "", "vLHjqbDv7TPFMBkIIO1nOA\n"])
def test_envelope_v2_malformed_query_id_refused(tmp_path, value):
    _, request = proof(tmp_path)
    request["query_id"] = value
    with pytest.raises(p.ProxyFailure, match="proxy_config"):
        snapshot.work_envelope(request)


def test_envelope_v1_request_without_query_id_is_refused(tmp_path):
    roles, request = proof(tmp_path)
    request.pop("query_id")
    with pytest.raises(p.ProxyFailure, match="proxy_config"):
        snapshot.verify(roles, request)


def test_envelope_v1_tag_does_not_verify_under_v2(tmp_path, monkeypatch):
    roles, request = proof(tmp_path)
    monkeypatch.setattr(snapshot, "DOMAIN", b"collector-b2-child-v1\0")
    snapshot.attest(roles, request)
    monkeypatch.undo()
    with pytest.raises(p.ProxyFailure, match="proxy_revision"):
        snapshot.verify(roles, request)


def test_attestation_exact_frame_matches_independent_hmac_and_is_redacted(tmp_path):
    roles, request = proof(tmp_path)
    framed = bytearray(snapshot.DOMAIN)
    for role, path, raw in roles:
        for value in (role.encode(), path.encode(), raw):
            framed.extend(len(value).to_bytes(8, "big"))
            framed.extend(value)
    for value in snapshot.work_envelope(request):
        framed.extend(len(value).to_bytes(8, "big"))
        framed.extend(value)
    expected = hmac.new(bytes.fromhex(request["attestation_key"]), framed, hashlib.sha256).hexdigest()
    assert expected == request["attestation_tag"]
    snapshot.verify(roles, request)
    assert request["attestation_key"] not in repr(request) and request["attestation_tag"] not in repr(request)
    other = snapshot.SensitiveRequest({key: value for key, value in request.items() if not key.startswith("attestation_")})
    snapshot.attest(roles, other)
    assert request["attestation_key"] != other["attestation_key"]
    assert request["attestation_tag"] != other["attestation_tag"]


@pytest.mark.parametrize("field,value", [("label", "beta"), ("proxy_id", str(UUID(int=2))),
    ("identity_revision", str(uuid4())), ("backend", "httpx"), ("request_nonce", "2" * 64),
    ("admission_expires_at", "2026-11-04T14:00:00+00:00"), ("query", "$BTC"),
    ("kv", {"product": "Top"}), ("kv", {"product": "Latest", "cursor": ""}),
    ("kv", {"product": "Latest", "cursor": "continuation"}), ("attestation_tag", "0" * 64),
    ("query_id", "vLHjqbDv7TPFMBkIIO1nOA"), ("query_id", "BYppgupFFS2yqVmmRNjlsw"),
    ("attestation_key", "a" * 64), ("attestation_key", "A" * 64), ("attestation_key", "a" * 63)])
def test_work_envelope_and_sensitive_pair_tampering_fails_before_clients(tmp_path, field, value):
    roles, request = proof(tmp_path)
    changed = snapshot.SensitiveRequest(copy.deepcopy(request))
    changed[field] = value
    with pytest.raises(p.ProxyFailure):
        snapshot.verify(roles, changed)


@pytest.mark.parametrize("index,part", [(i, part) for i in range(5) for part in range(3)])
def test_role_order_path_and_exact_raw_byte_tampering_fails(tmp_path, index, part):
    roles, request = proof(tmp_path)
    changed = list(roles)
    item = list(changed[index])
    item[part] += b"changed" if part == 2 else "changed"
    changed[index] = tuple(item)
    with pytest.raises(p.ProxyFailure):
        snapshot.verify(tuple(changed), request)


@pytest.mark.parametrize("query,cursor", [("a" * 4097, None), ("界" * 1366, None), ("ok", "a" * 4097), ("ok", "界" * 1366)])
def test_work_bounds_are_utf8_bytes_not_characters(tmp_path, query, cursor):
    roles, request = proof(tmp_path)
    request["query"] = query
    request["kv"] = {"product": "Latest", "cursor": cursor}
    with pytest.raises(p.ProxyFailure):
        snapshot.verify(roles, request)
