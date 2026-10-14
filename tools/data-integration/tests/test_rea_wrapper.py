"""S-T5a: REA wrapper. Every test uses a fake runner; npx is never started."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from data_integration import paths, status
from data_integration.rea import allowlist, wrapper

STATIC = [
    "analyze-javascript-application", "recover-javascript-sources", "compare-javascript-export-shapes",
    "compare-application-versions", "compare-source-to-bundle", "trace-javascript-semantics",
    "trace-application-feature", "inspect-analysis-view", "inspect-evidence-bundle", "compare",
    "compare-web-captures", "compare-web-screenshots", "inspect-web-network-capture",
    "trace-web-module-imports", "trace-web-source-location", "export-web-scripts",
]
LIVE = ["analyze-web-bundle", "capture-web-screenshot", "capture-browser-scenario", "inspect-web-page"]
REFUSED_NAMES = [
    "setup", "update", "uninstall", "mcp", "completions", "analyze-apk", "adb", "firmware", "analyze-native",
    "process", "apple", "jeb", "managed", "runtime-capture", "electron", "totally-unknown", "",
    "Compare", "COMPARE", "compare ", " compare", "compare-web", "compare-web-captures2", "analyze",
    "setup; compare", "compare&&setup",
]


def sample_output() -> dict:
    out = {f"key_{i:02d}": i for i in range(13)}
    out["subject"] = {"name": "demo", "local_path": "SYNTHETIC-LOCAL-PATH"}
    out["normalized_result"] = {"input_path": "SYNTHETIC-INPUT-PATH", "n": 1}
    return out


class FakeRunner:
    def __init__(self, stdout: str | None = None, returncode: int = 0):
        self.calls: list[tuple[list[str], dict]] = []
        self.stdout = json.dumps(sample_output()) if stdout is None else stdout
        self.returncode = returncode

    def __call__(self, cmd, env):
        self.calls.append((list(cmd), dict(env)))
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, "")


@pytest.fixture(autouse=True)
def evidence(tmp_path, monkeypatch):
    root = tmp_path / "evidence-root"
    monkeypatch.setenv("DIT_EVIDENCE_DIR", str(root))
    return root


def findings_file(tmp_path, names) -> str:
    p = tmp_path / "findings.json"
    p.write_text(json.dumps({"sources": list(names)}), encoding="utf-8")
    return p.as_posix()


def test_constants_pinned():
    assert allowlist.REA_VERSION == "6.4.0"
    assert allowlist.STATIC_COMMANDS == frozenset(STATIC)
    assert allowlist.LIVE_COMMANDS == frozenset(LIVE)
    assert allowlist.ALLOWED_COMMANDS == frozenset(STATIC + LIVE)
    assert isinstance(allowlist.ALLOWED_COMMANDS, frozenset)


@pytest.mark.parametrize("cmd", STATIC)
def test_static_commands_accepted(cmd):
    r = FakeRunner()
    res = wrapper.run_rea(cmd, ["demo/app.js"], runner=r)
    assert res.status == status.OK
    argv = r.calls[0][0]
    assert argv[-3:] == [cmd, "demo/app.js", "--json"]
    assert "rea-agents@6.4.0" in argv and argv[argv.index("rea-agents@6.4.0") - 1] == "-y"


@pytest.mark.parametrize("cmd", LIVE)
def test_live_commands_need_confirmation(cmd, tmp_path):
    r = FakeRunner()
    res = wrapper.run_rea(cmd, ["https://example.invalid/x"], runner=r)
    assert isinstance(res, wrapper.Refusal) and res.reason == "live_unconfirmed"
    res = wrapper.run_rea(cmd, ["x"], confirm_source="other", findings=findings_file(tmp_path, ["demo"]), runner=r)
    assert res.reason == "live_unconfirmed"
    res = wrapper.run_rea(cmd, ["x"], confirm_source="demo", findings=None, runner=r)
    assert res.reason == "live_unconfirmed"
    res = wrapper.run_rea(cmd, ["x"], confirm_source="demo", findings=str(tmp_path / "missing.json"), runner=r)
    assert res.reason == "live_unconfirmed"
    assert r.calls == []
    res = wrapper.run_rea(cmd, ["x"], confirm_source="demo", findings=findings_file(tmp_path, ["demo"]), runner=r)
    assert res.status == status.OK and len(r.calls) == 1


def test_live_source_flag_must_match_confirmation(tmp_path):
    r = FakeRunner()
    f = findings_file(tmp_path, ["demo"])
    res = wrapper.run_rea("inspect-web-page", ["--source", "demo2"], confirm_source="demo", findings=f, runner=r)
    assert res.reason == "bad_argument" and r.calls == []
    res = wrapper.run_rea("inspect-web-page", ["--source", "demo"], confirm_source="demo", findings=f, runner=r)
    assert res.status == status.OK


@pytest.mark.parametrize("cmd", REFUSED_NAMES)
def test_non_allow_listed_refused_without_subprocess(cmd):
    r = FakeRunner()
    res = wrapper.run_rea(cmd, [], runner=r)
    assert isinstance(res, wrapper.Refusal) and res.reason == "not_allow_listed"
    assert res.status == status.REFUSED
    assert r.calls == []


@pytest.mark.parametrize("flag", ["--update", "--mcp", "--update=x", "--setup", "-y", "--JSON", "--json=1", "--source=x", "-"])
def test_forbidden_flags_rejected(flag):
    r = FakeRunner()
    res = wrapper.run_rea("compare", [flag], runner=r)
    assert isinstance(res, wrapper.Refusal) and res.reason == "bad_flag"
    assert r.calls == []


@pytest.mark.parametrize("bad", ['a"b', "a%b", "a^b", "a&b", "a|b", "a<b", "a>b", "a b", "a;b", "a$(x)", "a`b`", "a\nb", "a\\b", "", "x" * 201, "a*b"])
def test_injection_characters_rejected(bad):
    r = FakeRunner()
    res = wrapper.run_rea("compare", [bad], runner=r)
    assert isinstance(res, wrapper.Refusal) and res.reason == "bad_argument"
    assert r.calls == []


def test_max_length_argument_accepted():
    r = FakeRunner()
    assert wrapper.run_rea("compare", ["x" * 200], runner=r).status == status.OK


def test_source_flag_validated():
    r = FakeRunner()
    assert wrapper.run_rea("compare", ["--source", "bad name"], runner=r).reason == "bad_argument"
    assert r.calls == []
    assert wrapper.run_rea("compare", ["--source", "ok.name-1"], runner=r).status == status.OK
    r2 = FakeRunner()
    assert wrapper.run_rea("compare", ["--source"], runner=r2).reason == "bad_argument"
    assert wrapper.run_rea("compare", ["--source", "a b"], runner=r2).reason == "bad_argument"
    assert r2.calls == []


def test_windows_drive_path_converted():
    assert wrapper.normalize_path_arg("C:\\work\\app.js") == "C:/work/app.js"
    assert wrapper.normalize_path_arg("a\\b") == "a\\b"  # not a drive path: stays, then fails the regex
    r = FakeRunner()
    assert wrapper.run_rea("compare", ["a\\b"], runner=r).reason == "bad_argument"
    res = wrapper.run_rea("compare", ["C:\\work\\app.js"], runner=r)
    assert res.status == status.OK
    assert "C:/work/app.js" in r.calls[0][0]


def test_output_path_pinned_inside_evidence(evidence):
    r = FakeRunner()
    ok = wrapper.run_rea("compare", ["--output", "out.json"], runner=r)
    assert ok.status == status.OK
    out = r.calls[0][0][r.calls[0][0].index("--output") + 1]
    assert Path(out).resolve().is_relative_to(evidence.resolve())
    for bad in ["../../escape.json", "/etc/out.json", "a/../../../b.json"]:
        r2 = FakeRunner()
        res = wrapper.run_rea("compare", ["--output", bad], runner=r2)
        assert isinstance(res, wrapper.Refusal) and res.reason == "bad_output_path"
        assert r2.calls == []


def test_shell_false_and_env(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, json.dumps(sample_output()), "")

    monkeypatch.setattr(wrapper.subprocess, "run", fake_run)
    res = wrapper.run_rea("compare", ["x"])
    assert res.status == status.OK
    assert seen["shell"] is False and isinstance(seen["cmd"], list)
    assert seen["env"]["npm_config_ignore_scripts"] == "true"


def test_ignore_scripts_in_runner_env():
    r = FakeRunner()
    wrapper.run_rea("compare", [], runner=r)
    assert r.calls[0][1]["npm_config_ignore_scripts"] == "true"


def test_npx_resolution(monkeypatch):
    monkeypatch.setattr(wrapper.shutil, "which", lambda n: "RESOLVED-" + n)
    assert wrapper.npx_executable("nt") == "RESOLVED-npx.cmd"
    assert wrapper.npx_executable("posix") == "npx"
    monkeypatch.setattr(wrapper.shutil, "which", lambda n: None)
    assert wrapper.npx_executable("nt") == "npx.cmd"


def test_redaction_and_deterministic_save(evidence):
    r = FakeRunner()
    res = wrapper.run_rea("compare", ["x"], runner=r, today="2026-10-14")
    assert res.output["subject"]["local_path"] == wrapper.REDACTED
    assert res.output["normalized_result"]["input_path"] == wrapper.REDACTED
    saved = res.evidence_path.read_text(encoding="utf-8")
    assert "SYNTHETIC" not in saved
    assert res.evidence_path.parent == evidence / "2026-10-14"
    res2 = wrapper.run_rea("compare", ["x"], runner=FakeRunner(), today="2026-10-14")
    assert res2.evidence_path.read_text(encoding="utf-8") == saved
    keys = list(json.loads(saved))
    assert keys == sorted(keys) and len(keys) == 15


def test_redact_function_leaves_other_fields():
    out = wrapper.redact({"subject": {"local_path": "p", "k": 1}, "normalized_result": {"input_path": "q"}, "z": {"local_path": "keep"}})
    assert out["z"]["local_path"] == "keep" and out["subject"]["k"] == 1


@pytest.mark.parametrize("stdout", ["not json", "[1,2]", json.dumps({"a": 1}), ""])
def test_bad_output_is_invalid(stdout):
    res = wrapper.run_rea("compare", [], runner=FakeRunner(stdout=stdout))
    assert res.status == status.INVALID and res.evidence_path is None


def test_nonzero_exit_is_invalid():
    res = wrapper.run_rea("compare", [], runner=FakeRunner(returncode=2))
    assert res.status == status.INVALID


def test_evidence_folder_outside_repo(evidence):
    res = wrapper.run_rea("compare", [], runner=FakeRunner(), today="2026-10-14")
    repo = paths._repo_root().resolve()
    assert not res.evidence_path.resolve().is_relative_to(repo)


def test_evidence_inside_repo_refused(monkeypatch):
    monkeypatch.setenv("DIT_EVIDENCE_DIR", str(paths._repo_root() / "scratch-evidence"))
    r = FakeRunner()
    res = wrapper.run_rea("compare", [], runner=r)
    assert isinstance(res, wrapper.Refusal) and res.reason == "evidence_in_repo"
    assert r.calls == []
    assert not (paths._repo_root() / "scratch-evidence").exists()
