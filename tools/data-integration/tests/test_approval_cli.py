"""approval_cli: status listing and guarded add."""
from __future__ import annotations

import re
from datetime import timedelta

import pytest

from data_integration import approval_cli
from data_integration.approvals import ApprovalStore
from _helpers import NOW, fixed_clock, make_record


@pytest.fixture
def env(tmp_path, monkeypatch):
    d = tmp_path / "ap"
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(d))
    return d


def run(argv, capsys, **kw):
    kw.setdefault("clock", fixed_clock())
    code = approval_cli.main(argv, **kw)
    return code, capsys.readouterr().out


def test_status_empty(env, capsys):
    code, out = run(["status"], capsys)
    assert code == 0
    assert "%LOCALAPPDATA%\\my_site\\approvals" in out
    assert "override: active" in out
    assert str(env) not in out
    assert "no approvals" in out


def test_status_lists_days_left(env, capsys):
    s = ApprovalStore(env)
    s.write(make_record("src-a", tier=2, expiry=NOW + timedelta(days=30)))
    s.write(make_record("src-b", tier=1, expiry=NOW - timedelta(days=1)))
    code, out = run(["status"], capsys)
    assert code == 0
    assert re.search(r"src-a\s+2\s+2026-02-09T12:00:00Z\s+30", out)
    assert re.search(r"src-b\s+1\s+\S+\s+expired", out)


def test_status_override_inactive(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("DIT_APPROVALS_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "la"))
    _, out = run(["status"], capsys)
    assert "override: inactive" in out
    assert str(tmp_path) not in out


def test_status_no_secret_like_strings(env, capsys):
    ApprovalStore(env).write(make_record("src-a", owner="owner-a"))
    _, out = run(["status"], capsys)
    assert not re.search(r"(?i)token|secret|password|key=|[A-Za-z0-9+/]{32,}", out)
    assert "owner-a" not in out
    assert "/" not in out.replace("%LOCALAPPDATA%\\my_site\\approvals", "")


def test_status_corrupt_reported(env, capsys):
    env.mkdir()
    (env / "src-a.approval.json").write_text("{", encoding="utf-8")
    _, out = run(["status"], capsys)
    assert "src-a" in out and "corrupt" in out


ADD = ["add", "--source", "src-a", "--tier", "2", "--host", "a.example.test", "--page", "/data/",
       "--owner", "owner-a", "--rate", "1 per 5s", "--robots-checked", "2026-01-09", "--alternative", "none found"]


def test_add_refuses_without_tty(env, capsys):
    code, out = run(ADD, capsys, isatty=False, input_fn=lambda p: "src-a")
    assert code != 0 and "interactive" in out
    assert not env.exists()


def test_add_requires_typed_source(env, capsys):
    code, _ = run(ADD, capsys, isatty=True, input_fn=lambda p: "wrong")
    assert code != 0
    assert not env.exists()


def test_add_writes_with_default_ttl(env, capsys):
    code, _ = run(ADD, capsys, isatty=True, input_fn=lambda p: "src-a")
    assert code == 0
    rec = ApprovalStore(env).read("src-a")
    assert rec.allowed_tier == 2 and rec.hosts == ("a.example.test",)
    assert rec.approved == "2026-01-10T12:00:00Z"
    assert rec.expiry == "2026-04-10T12:00:00Z"


def test_add_bad_source_and_tier(env, capsys):
    bad = ["../x" if a == "src-a" else a for a in ADD]
    assert run(bad, capsys, isatty=True, input_fn=lambda p: "../x")[0] != 0
    bad = ["9" if a == "2" else a for a in ADD]
    assert run(bad, capsys, isatty=True, input_fn=lambda p: "src-a")[0] != 0
    assert not env.exists()


def test_add_days_cap(env, capsys):
    ok = ADD + ["--days", "366"]
    assert run(ok, capsys, isatty=True, input_fn=lambda p: "src-a")[0] == 0
    assert ApprovalStore(env).read("src-a").expiry == "2027-01-11T12:00:00Z"
    env2 = ["--days", "367"]
    code, out = run(ADD[:2] + ["src-b"] + ADD[3:] + env2, capsys, isatty=True, input_fn=lambda p: "src-b")
    assert code != 0 and "between 1 and 366" in out
    assert "src-b" not in ApprovalStore(env).list_sources()


def test_add_days_below_one_refused(env, capsys):
    for d in ("0", "-5"):
        code, out = run(ADD + ["--days", d], capsys, isatty=True, input_fn=lambda p: "src-a")
        assert code != 0 and "between 1 and 366" in out
    assert not env.exists()
