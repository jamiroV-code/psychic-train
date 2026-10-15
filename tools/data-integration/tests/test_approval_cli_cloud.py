"""S-T8: --owner-statement path (cloud runs), record field, docs lines. Fake store in tmp_path only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_integration import approval_cli
from data_integration.approvals import ApprovalStore, StoreCorrupt
from _helpers import fixed_clock

SRC = "site-a"
HOST = "a.example.test"
STATEMENT = f"Owner approved {SRC} on {HOST} in chat, tier 2, robots read"
DOCS = Path(__file__).resolve().parents[3] / "process" / "context" / "data-sources" / "all-data-sources.md"
OLD = {"id": "old-1", "source": SRC, "allowed_tier": 2, "hosts": [HOST], "pages": ["/d/"], "rate_policy": "r",
       "robots_checked": "x", "alternatives_checked": [], "owner": "o", "approved": "2026-01-09T00:00:00Z",
       "expiry": "2026-02-09T00:00:00Z", "revision": 1}


@pytest.fixture
def store_dir(tmp_path, monkeypatch):
    d = tmp_path / "ap"
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(d))
    return d


def argv(statement=STATEMENT, source=SRC, host=HOST):
    a = ["add", "--source", source, "--tier", "2", "--host", host, "--page", "/data/", "--owner", "owner-a",
         "--rate", "1 request per 5 seconds", "--robots-checked", "2026-01-09"]
    return a + (["--owner-statement", statement] if statement is not None else [])


def run(args, capsys, isatty=False, input_fn=None):
    def boom(prompt=""):
        raise AssertionError("input_fn must not be called")

    code = approval_cli.main(args, clock=fixed_clock(), isatty=isatty, input_fn=input_fn or boom)
    return code, capsys.readouterr().out


def no_files(d) -> bool:
    return not d.exists() or not list(d.glob("*"))


def test_valid_statement_stored_verbatim(store_dir, capsys):
    code, out = run(argv(), capsys)
    assert code == 0
    assert ApprovalStore(store_dir).read(SRC).owner_statement == STATEMENT
    assert str(store_dir) not in out


def test_statement_with_tty_refused(store_dir, capsys):
    code, _ = run(argv(), capsys, isatty=True)
    assert code == 2
    assert no_files(store_dir)


def test_no_statement_tty_interactive_unchanged(store_dir, capsys):
    code, _ = run(argv(None), capsys, isatty=True, input_fn=lambda p: SRC)
    assert code == 0
    assert ApprovalStore(store_dir).read(SRC).owner_statement == ""


def test_no_statement_no_tty_refused(store_dir, capsys):
    code, _ = run(argv(None), capsys)
    assert code == 2
    assert no_files(store_dir)


@pytest.mark.parametrize("bad", [
    "too short",
    f"{SRC} {HOST} " + "x" * 500,
    f"{SRC} {HOST} café approved",
    f"approved {HOST} in chat by the owner",
    f"approved {SRC} in chat by the owner today",
    f"{SRC} {HOST}\napproved by the owner",
])
def test_bad_statement_refused_no_file(store_dir, capsys, bad):
    code, _ = run(argv(bad), capsys)
    assert code == 2
    assert no_files(store_dir)


def test_every_host_must_appear(store_dir, capsys):
    code, _ = run(argv() + ["--host", "b.example.test"], capsys)
    assert code == 2
    assert no_files(store_dir)


def test_env_var_unset_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DIT_APPROVALS_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "la"))
    code, _ = run(argv(), capsys)
    assert code == 2
    assert not (tmp_path / "la").exists()


def test_old_record_loads_with_empty_statement(store_dir):
    store_dir.mkdir()
    (store_dir / f"{SRC}.approval.json").write_text(json.dumps(OLD), encoding="utf-8")
    assert ApprovalStore(store_dir).read(SRC).owner_statement == ""


def test_non_string_statement_is_corrupt(store_dir):
    store_dir.mkdir()
    (store_dir / f"{SRC}.approval.json").write_text(json.dumps({**OLD, "owner_statement": 5}), encoding="utf-8")
    with pytest.raises(StoreCorrupt):
        ApprovalStore(store_dir).read(SRC)


def test_path_in_repo_exits_2(monkeypatch, capsys):
    from data_integration import paths

    target = paths._repo_root() / "inside-approvals"
    monkeypatch.setenv("DIT_APPROVALS_DIR", str(target))
    assert run(["status"], capsys)[0] == 2
    assert run(argv(), capsys)[0] == 2
    assert not target.exists()


def _docs_block() -> str:
    lines = DOCS.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## New dataset workflow"))
    end = next(i for i, ln in enumerate(lines) if i > start and ln.startswith("### Known limits"))
    end = next((i for i in range(end + 1, len(lines)) if lines[i].startswith("#")), len(lines))
    return "\n".join(lines[start:end])


def test_docs_ac27():
    block = _docs_block()
    assert "Workers never run live commands" not in block
    assert "stay on the owner's PC" not in block
    for needle in ("--owner-statement", "connection_failed", "scrapling install"):
        assert needle in block
    assert len(block.encode("utf-8")) <= 3500
