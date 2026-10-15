"""Approval record resource_hosts: validation, CLI, gate, provenance (AC-29, AC-31)."""
from __future__ import annotations

import json

import pytest

from _helpers import fixed_clock, make_record
from data_integration import approval_cli, paths
from data_integration.approvals import ApprovalStore, StoreCorrupt, check_resource_hosts
from data_integration.gate import FetchPass, request_access
from data_integration.provenance import build_record

GOOD = ("cdn.example.test", "static.example.test")


@pytest.mark.parametrize("bad", [
    ("*.example.test",), ("192.0.2.1",), ("0x7f.0x1",), ("cdn.example.test:443",), ("https://cdn.example.test",),
    ("cdn.example.test/x",), ("CDN.example.test",), ("localhost",), ("-a.example.test",), ("a-.example.test",),
    ("a.example.test", "a.example.test"), tuple(f"h{i}.example.test" for i in range(9)),
    ("a" * 64 + ".example.test",), ("a." * 130 + "test",), ("",), ("a..example.test",), ("a.example.test.",),
    ("2130706433",), ("1.2.3.4",),
])
def test_invalid_hosts_rejected(bad):
    with pytest.raises(ValueError):
        check_resource_hosts(bad, 2)


def test_valid_hosts_and_tier_rule():
    check_resource_hosts(GOOD, 2)
    check_resource_hosts(GOOD, 3)
    check_resource_hosts((), 1)
    check_resource_hosts(tuple(f"h{i}.example.test" for i in range(8)), 2)
    with pytest.raises(ValueError):
        check_resource_hosts(GOOD, 1)


def _store(tmp_path, **kw):
    s = ApprovalStore(tmp_path / "ap")
    s.write(make_record(**kw))
    return s


def test_old_record_loads_without_field(tmp_path):
    s = _store(tmp_path)
    path = s.path_for("example-src")
    data = json.loads(path.read_text())
    data.pop("resource_hosts", None)
    path.write_text(json.dumps(data))
    assert s.read("example-src").resource_hosts == ()


def test_roundtrip_and_corrupt_at_load(tmp_path):
    s = _store(tmp_path, resource_hosts=GOOD)
    assert s.read("example-src").resource_hosts == GOOD
    path = s.path_for("example-src")
    data = json.loads(path.read_text())
    data["resource_hosts"] = ["*.example.test"]
    path.write_text(json.dumps(data))
    with pytest.raises(StoreCorrupt):
        s.read("example-src")


def test_tier1_record_with_resource_hosts_refused(tmp_path):
    with pytest.raises(ValueError):
        ApprovalStore(tmp_path / "ap").write(make_record(tier=1, resource_hosts=GOOD))
    s = _store(tmp_path, tier=1)
    path = s.path_for("example-src")
    data = json.loads(path.read_text())
    data["resource_hosts"] = list(GOOD)
    path.write_text(json.dumps(data))
    with pytest.raises(StoreCorrupt):
        s.read("example-src")


def test_gate_passes_resource_hosts_only_for_tier2_up(tmp_path):
    s = _store(tmp_path, tier=3, resource_hosts=GOOD)
    assert request_access("example-src", 3, s, fixed_clock()).resource_hosts == GOOD
    assert request_access("example-src", 2, s, fixed_clock()).resource_hosts == GOOD
    p1 = request_access("example-src", 1, s, fixed_clock())
    assert isinstance(p1, FetchPass) and p1.resource_hosts == ()


def test_permits_unchanged_by_resource_hosts(tmp_path):
    p = request_access("example-src", 2, _store(tmp_path, resource_hosts=GOOD), fixed_clock())
    assert not p.permits("https://cdn.example.test/data/x")
    assert p.permits("https://a.example.test/data/x")


def test_provenance_lists_approved_hosts(tmp_path):
    import pandas as pd
    from datetime import datetime, timezone

    p = request_access("example-src", 2, _store(tmp_path, resource_hosts=GOOD), fixed_clock())
    rec = build_record(p, "https://a.example.test/data/x", pd.DataFrame({"d": ["1"]}), datetime(2026, 1, 10, tzinfo=timezone.utc))
    assert rec["resource_hosts"] == list(GOOD)


# --- CLI ---------------------------------------------------------------------------------------

STATEMENT = "Owner approves source example-src on a.example.test with resource hosts cdn.example.test"


def _args(*extra, statement=STATEMENT):
    a = ["add", "--source", "example-src", "--tier", "2", "--host", "a.example.test", "--page", "/data/",
         "--owner", "owner-a", "--rate", "1 per 5s", "--robots-checked", "2026-01-09"]
    if statement is not None:
        a += ["--owner-statement", statement]
    return a + list(extra)


@pytest.fixture()
def appdir(tmp_path, monkeypatch):
    d = tmp_path / "ap"
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(d))
    return d


def _run(argv, **kw):
    return approval_cli.main(argv, clock=fixed_clock(), isatty=kw.pop("isatty", False))


def test_cli_adds_resource_host(appdir):
    assert _run(_args("--resource-host", "cdn.example.test")) == 0
    assert ApprovalStore(appdir).read("example-src").resource_hosts == ("cdn.example.test",)


def test_cli_statement_must_name_each_resource_host(appdir):
    assert _run(_args("--resource-host", "cdn.example.test", "--resource-host", "img.example.test")) == 2
    assert not appdir.exists() or not list(appdir.iterdir())


@pytest.mark.parametrize("bad", ["*.example.test", "192.0.2.1", "0x7f.0x1", "cdn.example.test:8443", "https://cdn.example.test"])
def test_cli_invalid_host_exits_2_with_no_file(appdir, bad, capsys):
    stmt = STATEMENT + " " + bad
    assert _run(_args("--resource-host", bad, statement=stmt)) == 2
    assert "Traceback" not in capsys.readouterr().out
    assert not appdir.exists() or not list(appdir.iterdir())


def test_cli_duplicates_and_nine_hosts_rejected(appdir):
    assert _run(_args("--resource-host", "cdn.example.test", "--resource-host", "cdn.example.test")) == 2
    hosts = [f"h{i}.example.test" for i in range(9)]
    extra = [x for h in hosts for x in ("--resource-host", h)]
    assert _run(_args(*extra, statement=STATEMENT + " " + " ".join(hosts))) == 2
    assert not appdir.exists() or not list(appdir.iterdir())


def test_cli_tier1_with_resource_host_rejected(appdir):
    a = _args("--resource-host", "cdn.example.test")
    a[a.index("--tier") + 1] = "1"
    assert _run(a) == 2
    assert not appdir.exists() or not list(appdir.iterdir())


def test_cli_interactive_use_rejected(appdir, monkeypatch):
    assert _run(_args("--resource-host", "cdn.example.test", statement=None), isatty=True) == 2
    assert not appdir.exists() or not list(appdir.iterdir())
    assert paths is not None
