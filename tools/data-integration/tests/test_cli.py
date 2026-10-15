"""cli.py: exit codes, flag rules, dry-run/preview, rea branches. Fake registry and runner; no network, no npx."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from data_integration import cli, paths, pipeline, provenance, status
from data_integration.approvals import ApprovalStore
from data_integration.types import FetchOutcome

from _helpers import NOW, fixed_clock, make_record

FIX = Path(__file__).parent / "fixtures"
TOOL = Path(__file__).resolve().parents[1]
URL = "https://example.test/data/prices.html"
SEL = "table.prices"
SRC = "example-src"
OK_BODY = (FIX / "ok.html").read_bytes()
V2_BODY = (FIX / "ok_v2.html").read_bytes()


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    for name, leaf in (("DIT_APPROVALS_DIR", "appr"), ("DIT_SCRAPE_DIR", "scrape"), ("DIT_EVIDENCE_DIR", "evid")):
        monkeypatch.setenv(name, str(tmp_path / "dit" / leaf))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    return tmp_path


class Reg:
    """Fake registry: one callable per tier, counting calls and recording keyword arguments."""

    def __init__(self, st=status.OK, body=OK_BODY, detail=""):
        self.st, self.body, self.detail, self.calls = st, body, detail, []

    def fn(self, url, pass_, **kw):
        self.calls.append((url, pass_, kw))
        ok = self.st in (status.OK, status.CACHE_HIT)
        return FetchOutcome(self.st, url, 200 if ok else None, self.body if ok else b"", self.detail,
                            hashlib.sha256(self.body).hexdigest() if ok else None)

    @property
    def registry(self):
        return {1: self.fn, 2: self.fn, 3: self.fn}


def recipe_file(tmp_path, **over):
    data = {
        "schema_version": 1, "source": SRC, "tier": 1, "url": URL, "selector": SEL,
        "dataset": {"symbol": "BTC-HIST", "timeframe": "1d"}, "min_rows": 2,
    }
    data.update(over)
    p = tmp_path / "t.recipe.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def approve(allowed_tier=1, **kw):
    kw.setdefault("hosts", ("example.test",))
    kw.setdefault("pages", ("/data/",))
    ApprovalStore(paths.approvals_dir()).write(make_record(source=SRC, tier=allowed_tier, **kw))


def go(argv, reg=None, clock=None, **kw):
    reg = reg or Reg()
    return cli.main(argv, clock=clock or fixed_clock(), registry=reg.registry, **kw)


def all_files(root):
    return [p for p in Path(root).rglob("*") if p.is_file()] if Path(root).exists() else []


# ---- usage ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("flag", ["--rep", "--acc", "--dry", "--prev", "--refr"])
def test_abbreviated_flags_rejected(tmp_path, flag, capsys):
    approve()
    reg = Reg()
    assert go(["run", recipe_file(tmp_path), flag], reg) == 2
    assert reg.calls == []


def test_rea_abbreviation_rejected(capsys):
    assert go(["rea", "compare", "--conf", "x"]) == 2


@pytest.mark.parametrize("argv", [[], ["nope"], ["run"], ["rea"]])
def test_missing_or_unknown_command_is_usage_error(argv):
    assert go(argv) == 2


@pytest.mark.parametrize("flags", [
    ["--dry-run", "--preview"], ["--dry-run", "--replace"], ["--dry-run", "--accept-baseline"],
    ["--preview", "--replace"], ["--preview", "--accept-baseline"],
])
def test_exclusive_flags_exit_2_before_anything(tmp_path, flags):
    approve()
    reg = Reg()
    assert go(["run", recipe_file(tmp_path), *flags], reg) == 2
    assert reg.calls == []


def test_bad_recipe_exit_2(tmp_path, capsys):
    reg = Reg()
    p = tmp_path / "bad.json"
    p.write_text("{", encoding="utf-8")
    assert go(["run", str(p)], reg) == 2
    assert reg.calls == []
    assert str(tmp_path) not in capsys.readouterr().out


def test_missing_recipe_file_exit_2(tmp_path):
    assert go(["run", str(tmp_path / "nope.json")]) == 2


# ---- gate refusals --------------------------------------------------------------------------------------------

def _refusal_setup(reason, tmp_path):
    kw = {}
    clock = fixed_clock()
    tier = 1
    if reason == "missing":
        ApprovalStore(paths.approvals_dir()).write(make_record(source="other-src", tier=1))
    elif reason == "expired":
        approve()
        clock = fixed_clock(NOW + timedelta(days=60))
    elif reason == "tier_too_low":
        approve(allowed_tier=1)
        tier = 3
    elif reason == "store_corrupt":
        d = paths.approvals_dir()
        d.mkdir(parents=True)
        (d / f"{SRC}.approval.json").write_text("{not json", encoding="utf-8")
    elif reason == "bad_clock":
        approve()
        clock = lambda: NOW.replace(tzinfo=None)  # noqa: E731
    elif reason == "url_not_approved":
        approve(pages=("/other/",))
    return clock, tier, kw


@pytest.mark.parametrize("reason", ["missing", "expired", "tier_too_low", "store_missing", "store_corrupt", "bad_clock", "url_not_approved"])
@pytest.mark.parametrize("mode", [[], ["--dry-run"], ["--preview"]])
def test_gate_refusals_exit_3(tmp_path, reason, mode, capsys):
    clock, tier, _ = _refusal_setup(reason, tmp_path)
    reg = Reg()
    assert go(["run", recipe_file(tmp_path, tier=tier), *mode], reg, clock=clock) == 3
    assert reg.calls == []
    out = capsys.readouterr().out
    assert reason in out or reason == "url_not_approved" and "approved" in out
    assert "refused" in out.lower()


def test_url_not_approved_message_names_reason(tmp_path, capsys):
    approve(pages=("/other/",))
    assert go(["run", recipe_file(tmp_path), "--dry-run"]) == 3
    assert "url_not_approved" in capsys.readouterr().out


def test_url_with_other_port_not_permitted(tmp_path):
    approve()
    reg = Reg()
    assert go(["run", recipe_file(tmp_path, url="https://example.test:8443/data/x")], reg) == 3
    assert reg.calls == []


# ---- exit code per closed status -------------------------------------------------------------------------------

EXPECTED_CODE = {
    status.OK: 0, status.CACHE_HIT: 0, status.ROBOTS_BLOCKED: 4, status.TIMEOUT: 4, status.CONNECTION_FAILED: 4,
    status.HTTP_ERROR: 4, status.CHALLENGE_PAGE: 4, status.INVALID: 5, status.CHANGED: 6, status.UNCERTAIN: 6,
    status.REFUSED: 7,
}


def test_expected_table_covers_every_status():
    assert set(EXPECTED_CODE) == set(status.ALL_STATUSES)
    assert set(cli.STATUS_MESSAGES) == set(status.ALL_STATUSES)
    assert {k: cli.EXIT_CODES[k] for k in status.ALL_STATUSES} == EXPECTED_CODE


@pytest.mark.parametrize("st", sorted(status.ALL_STATUSES))
def test_each_status_has_exit_code_and_plain_message(tmp_path, monkeypatch, capsys, st):
    approve()
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: pipeline.PipelineResult(st, "some detail", 4))
    assert go(["run", recipe_file(tmp_path)]) == EXPECTED_CODE[st]
    out = capsys.readouterr().out
    assert st in out and cli.STATUS_MESSAGES[st] in out and "some detail" in out
    assert "Traceback" not in out and "_" not in cli.STATUS_MESSAGES[st]


@pytest.mark.parametrize("st", [status.ROBOTS_BLOCKED, status.TIMEOUT, status.CONNECTION_FAILED, status.HTTP_ERROR, status.CHALLENGE_PAGE, status.REFUSED])
def test_fetch_statuses_flow_through_pipeline(tmp_path, st):
    approve()
    reg = Reg(st=st, detail="off-list redirect" if st == status.REFUSED else "x")
    assert go(["run", recipe_file(tmp_path)], reg) == EXPECTED_CODE[st]
    assert len(reg.calls) == 1


def test_fetch_refused_message_comes_from_detail(tmp_path, capsys):
    approve()
    assert go(["run", recipe_file(tmp_path)], Reg(st=status.REFUSED, detail="redirect left the approved hosts")) == 7
    assert "redirect left the approved hosts" in capsys.readouterr().out


def test_invalid_table_exit_5(tmp_path):
    approve()
    assert go(["run", recipe_file(tmp_path)], Reg(body=(FIX / "no_table.html").read_bytes())) == 5


def test_first_run_without_accept_is_uncertain_exit_6_nothing_stored(tmp_path):
    approve()
    assert go(["run", recipe_file(tmp_path)]) == 6
    assert provenance.read_records("BTC-HIST", "1d") == []


# ---- end to end with the real pipeline ------------------------------------------------------------------------

def run_ok(tmp_path, *flags, reg=None, **over):
    return go(["run", recipe_file(tmp_path, **over), *flags], reg)


def test_accept_baseline_first_run_stores_and_prints_approval_facts(tmp_path, capsys):
    approve(id="rec-77")
    assert run_ok(tmp_path, "--accept-baseline") == 0
    out = capsys.readouterr().out
    rec = ApprovalStore(paths.approvals_dir()).read(SRC)
    assert f"id={rec.id}" in out and f"revision={rec.revision}" in out and f"expires={rec.expiry}" in out
    assert rec.rate_policy in out
    assert len(provenance.read_records("BTC-HIST", "1d")) == 1


def test_outcome_expiry_equals_approvals_status_line(tmp_path, capsys):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    out = capsys.readouterr().out
    assert go(["approvals", "status"]) == 0
    status_out = capsys.readouterr().out
    expiry = ApprovalStore(paths.approvals_dir()).read(SRC).expiry
    assert f"expires={expiry}" in out and expiry in status_out


def test_second_identical_run_is_cache_hit_exit_0(tmp_path, capsys):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    capsys.readouterr()
    assert run_ok(tmp_path) == 0
    assert "cache_hit" in capsys.readouterr().out
    assert len(provenance.read_records("BTC-HIST", "1d")) == 1


def test_fetch_tier_cache_hit_maps_to_ok(tmp_path):
    approve()
    assert run_ok(tmp_path, "--accept-baseline", reg=Reg(st=status.CACHE_HIT)) == 0


def test_target_not_empty_is_refused_exit_7(tmp_path, capsys):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    capsys.readouterr()
    assert run_ok(tmp_path, reg=Reg(body=V2_BODY)) == 7
    assert "already holds data" in capsys.readouterr().out


def test_replace_with_empty_provenance_exit_2_before_fetch(tmp_path):
    approve()
    reg = Reg()
    assert run_ok(tmp_path, "--replace", reg=reg) == 2
    assert reg.calls == []


def test_replace_with_records_is_allowed(tmp_path):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    reg = Reg(body=V2_BODY)
    assert run_ok(tmp_path, "--replace", reg=reg) == 0
    assert len(reg.calls) == 1 and len(provenance.read_records("BTC-HIST", "1d")) == 2


def test_replace_with_unreadable_provenance_exit_2(tmp_path):
    approve()
    p = provenance.provenance_path("BTC-HIST", "1d")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{broken", encoding="utf-8")
    reg = Reg()
    assert run_ok(tmp_path, "--replace", reg=reg) == 2
    assert reg.calls == []


def test_accept_baseline_with_no_store_allowed(tmp_path):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0


def test_accept_baseline_with_baseline_exit_2_no_write(tmp_path):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    before = len(provenance.read_records("BTC-HIST", "1d"))
    reg = Reg(body=V2_BODY)
    assert run_ok(tmp_path, "--accept-baseline", reg=reg) == 2
    assert reg.calls == [] and len(provenance.read_records("BTC-HIST", "1d")) == before


def test_accept_baseline_with_store_but_other_selector_allowed(tmp_path):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    assert run_ok(tmp_path, "--accept-baseline", selector="table") == 0


# ---- politeness / cache wiring ---------------------------------------------------------------------------------

def test_run_passes_cache_refresh_and_recipe_politeness(tmp_path):
    approve()
    reg = Reg()
    run_ok(tmp_path, "--refresh", reg=reg, politeness={"min_delay": 5, "max_concurrent": 1, "max_per_host": 1})
    kw = reg.calls[0][2]
    assert kw["cache"] is not None and kw["refresh"] is True
    assert kw["politeness"].min_delay == 5.0
    assert "proxy" not in kw


def test_run_without_politeness_passes_none(tmp_path):
    approve()
    reg = Reg()
    run_ok(tmp_path, reg=reg)
    assert reg.calls[0][2]["politeness"] is None and reg.calls[0][2]["refresh"] is False


def test_tier_selects_registry_entry(tmp_path):
    approve(allowed_tier=3)
    seen = []

    def make(n):
        def fn(url, pass_, **kw):
            seen.append(n)
            return FetchOutcome(status.TIMEOUT, url)
        return fn

    cli.main(["run", recipe_file(tmp_path, tier=2)], clock=fixed_clock(), registry={1: make(1), 2: make(2), 3: make(3)})
    assert seen == [2]


# ---- dry-run ---------------------------------------------------------------------------------------------------

def test_dry_run_fetches_nothing_and_writes_nothing(tmp_path, capsys):
    approve(id="rec-9")
    reg = Reg()
    assert go(["run", recipe_file(tmp_path), "--dry-run", "--refresh"], reg) == 0
    out = capsys.readouterr().out
    rec = ApprovalStore(paths.approvals_dir()).read(SRC)
    for needle in (URL, "id=rec-9", f"revision={rec.revision}", f"expires={rec.expiry}", rec.rate_policy, "baseline: none", "permitted: yes"):
        assert needle in out
    assert reg.calls == []
    assert all_files(tmp_path / "dit" / "scrape") == [] and all_files(tmp_path / "dit" / "evid") == []
    assert provenance.read_records("BTC-HIST", "1d") == []


def test_dry_run_reports_baseline_present(tmp_path, capsys):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    capsys.readouterr()
    assert go(["run", recipe_file(tmp_path), "--dry-run"]) == 0
    assert "baseline: present" in capsys.readouterr().out


# ---- preview ---------------------------------------------------------------------------------------------------

def test_preview_prints_table_and_writes_nothing(tmp_path, monkeypatch, capsys):
    approve()
    reg = Reg()
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: pytest.fail("preview must not call pipeline.run"))
    assert go(["run", recipe_file(tmp_path), "--preview", "--refresh"], reg) == 0
    out = capsys.readouterr().out
    assert "rows: 4" in out and "date" in out.lower() and "close" in out.lower()
    assert hashlib.sha256(OK_BODY).hexdigest() in out
    assert "2025-01-01" in out and "2025-01-04" in out and "baseline: none" in out
    kw = reg.calls[0][2]
    assert kw["cache"] is None and kw["refresh"] is False
    for d in ("scrape", "evid", "appr"):
        root = tmp_path / "dit" / d
        assert d == "appr" or all_files(root) == []
    assert not any("provenance" in p.name or p.suffix in (".parquet", ".sqlite") for p in all_files(tmp_path / "dit"))
    assert provenance.read_records("BTC-HIST", "1d") == []


def test_preview_shows_first_and_last_three_rows_only(tmp_path, capsys):
    approve()
    rows = "".join(f"<tr><td>2025-02-{i:02d}</td><td>1</td><td>2</td><td>1</td><td>2</td><td>5</td></tr>" for i in range(1, 11))
    body = ("<table class='prices'><tr><th>date</th><th>open</th><th>high</th><th>low</th><th>close</th><th>volume</th></tr>" + rows + "</table>").encode()
    assert go(["run", recipe_file(tmp_path), "--preview"], Reg(body=body)) == 0
    out = capsys.readouterr().out
    for day in ("01", "02", "03", "08", "09", "10"):
        assert f"2025-02-{day}" in out
    for day in ("04", "05", "06", "07"):
        assert f"2025-02-{day}" not in out


def test_preview_bad_table_exit_5(tmp_path):
    approve()
    assert go(["run", recipe_file(tmp_path), "--preview"], Reg(body=(FIX / "no_table.html").read_bytes())) == 5
    assert go(["run", recipe_file(tmp_path, min_rows=50), "--preview"]) == 5


def test_preview_fetch_failure_maps_to_exit_4(tmp_path):
    approve()
    assert go(["run", recipe_file(tmp_path), "--preview"], Reg(st=status.TIMEOUT)) == 4


def test_preview_baseline_present(tmp_path, capsys):
    approve()
    assert run_ok(tmp_path, "--accept-baseline") == 0
    capsys.readouterr()
    assert go(["run", recipe_file(tmp_path), "--preview"]) == 0
    assert "baseline: present" in capsys.readouterr().out


# ---- rea -------------------------------------------------------------------------------------------------------

def rea_output():
    out = {f"key_{i:02d}": i for i in range(13)}
    out["subject"] = {"name": "demo", "local_path": "SYNTHETIC"}
    out["normalized_result"] = {"input_path": "SYNTHETIC", "n": 1}
    return out


class Runner:
    def __init__(self, stdout=None, returncode=0, exc=None):
        self.stdout = json.dumps(rea_output()) if stdout is None else stdout
        self.returncode, self.exc, self.calls = returncode, exc, []

    def __call__(self, cmd, env):
        self.calls.append(list(cmd))
        if self.exc:
            raise self.exc
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, "")


def rea(argv, runner):
    return cli.main(["rea", *argv], rea_runner=runner)


def test_rea_ok_prints_placeholder_only(tmp_path, capsys):
    r = Runner()
    assert rea(["compare", "--", "one.json"], r) == 0
    out = capsys.readouterr().out
    assert "%LOCALAPPDATA%" in out and "compare.json" in out
    assert str(tmp_path) not in out
    assert r.calls and "one.json" in r.calls[0] and "--" not in r.calls[0]


def test_rea_split_at_double_dash_keeps_forwarded_flags_out_of_cli_parser(capsys):
    r = Runner()
    assert rea(["compare", "--", "--source", "src-a"], r) == 0
    assert "--source" in r.calls[0] and "src-a" in r.calls[0]


@pytest.mark.parametrize("argv", [["setup"], ["mcp"], ["update"], ["compare", "--", "--update"], ["compare", "--", "--evil", "x"],
                                  ["inspect-web-page"], ["compare", "--", "bad arg"]])
def test_rea_refusals_exit_2(argv, capsys):
    r = Runner()
    assert rea(argv, r) == 2
    assert r.calls == []
    assert "refused" in capsys.readouterr().out


def test_rea_live_command_with_confirmed_source_runs(tmp_path):
    findings = tmp_path / "f.json"
    findings.write_text(json.dumps({"sources": ["src-a"]}), encoding="utf-8")
    r = Runner()
    assert rea(["inspect-web-page", "--confirm-source", "src-a", "--findings", str(findings), "--", "--source", "src-a"], r) == 0
    assert len(r.calls) == 1


def test_rea_node_missing_message(capsys):
    assert rea(["compare"], Runner(exc=FileNotFoundError("npx"))) == 5
    out = capsys.readouterr().out
    assert "Node" in out and "npx" in out


def test_rea_timeout_message(capsys):
    assert rea(["compare"], Runner(exc=subprocess.TimeoutExpired("npx", 600))) == 5
    assert "timed out" in capsys.readouterr().out


@pytest.mark.parametrize("runner", [Runner(returncode=1), Runner(stdout="not json"), Runner(stdout="[1]"), Runner(exc=PermissionError("x"))])
def test_rea_other_failures_say_rea_failed(runner, capsys):
    assert rea(["compare"], runner) == 5
    assert "REA failed" in capsys.readouterr().out


# ---- redaction and top-level handler ----------------------------------------------------------------------------

@pytest.mark.parametrize("raw,gone", [
    ("see /home/someone/work/file.txt now", "/home/someone"),
    ("see C:\\Users\\someone\\x.txt now", "C:\\Users"),
    ("peer 192.168.10.20 refused", "192.168.10.20"),
    ("at 10.0.0.1:8080", "10.0.0.1"),
])
def test_safe_redacts_paths_and_ipv4(raw, gone):
    out = cli._safe(raw)
    assert gone not in out and "<" in out


def test_safe_keeps_url_and_placeholder():
    text = "https://example.test/data/prices.html %LOCALAPPDATA%\\my_site\\evidence\\2026-01-10\\x.json version 0.1.0"
    assert cli._safe(text) == text


def test_top_level_handler_prints_exception_type_only(tmp_path, monkeypatch, capsys):
    approve()
    monkeypatch.setattr(pipeline, "run", lambda *a, **k: (_ for _ in ()).throw(ValueError("C:\\secret\\path 10.1.2.3")))
    assert go(["run", recipe_file(tmp_path)]) == 1
    out = capsys.readouterr()
    text = out.out + out.err
    assert "ValueError" in text and "secret" not in text and "10.1.2.3" not in text


# ---- dispatch and subprocess -------------------------------------------------------------------------------------

def test_approvals_status_dispatched_in_process(capsys):
    assert go(["approvals", "status"]) == 0
    assert "no approvals" in capsys.readouterr().out


def _sub(args, env_dir, cwd):
    envv = {k: v for k, v in os.environ.items() if not k.startswith("DIT_")}
    envv.update(DIT_APPROVALS_DIR=str(env_dir), PYTHONPATH=str(TOOL / "src"), HOME=str(cwd), LOCALAPPDATA=str(cwd))
    return subprocess.run([sys.executable, "-m", "data_integration", *args], cwd=cwd, env=envv, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60)


def test_python_m_approvals_status(tmp_path):
    d = tmp_path / "ap"
    r = _sub(["approvals", "status"], d, tmp_path)
    assert r.returncode == 0 and "no approvals" in r.stdout


def test_python_m_approvals_add_without_terminal_refuses(tmp_path):
    d = tmp_path / "ap"
    r = _sub(["approvals", "add", "--source", "s1", "--tier", "1", "--host", "example.test", "--page", "/data/",
              "--owner", "o", "--rate", "slow", "--robots-checked", "2026-01-09"], d, tmp_path)
    assert r.returncode == 2 and all_files(d) == []


def test_python_m_usage_error_exit_2(tmp_path):
    assert _sub(["run", "--rep"], tmp_path / "ap", tmp_path).returncode == 2


def test_importing_cli_loads_no_fetch_tier_pipeline_or_wrapper(tmp_path):
    code = ("import sys, data_integration.cli;"
            "bad=[m for m in sys.modules if m.startswith(('data_integration.fetch_tier','data_integration.pipeline',"
            "'data_integration.rea','scrapling'))];"
            "print(bad); sys.exit(1 if bad else 0)")
    envv = dict(os.environ, PYTHONPATH=str(TOOL / "src"))
    r = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=envv, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout
