"""Guard for .github/workflows/attention-refresh.yml (no network, no run)."""
from __future__ import annotations

import re
import subprocess

import pytest

from api.tests.tooling_guards._common import REPO_ROOT, WORKFLOWS

yaml = pytest.importorskip("yaml")

NAME = "attention-refresh.yml"
PATH = WORKFLOWS / NAME


def _text() -> str:
    return PATH.read_text(encoding="utf-8")


def _doc() -> dict:
    doc = yaml.safe_load(_text())
    doc["on"] = doc.get("on", doc.get(True))  # PyYAML reads the bare key `on` as True
    return doc


def _steps(job: str = "refresh") -> list[dict]:
    jobs = _doc()["jobs"]
    assert set(jobs) == {"refresh", "refresh-extra"}
    return list(jobs[job]["steps"])


def _all_steps() -> list[dict]:
    return _steps("refresh") + _steps("refresh-extra")


def test_exactly_one_daily_cron_off_the_hour() -> None:
    crons = re.findall(r'^\s*-\s*cron:\s*["\']?([^"\'\n]+?)["\']?\s*$', _text(), re.M)
    assert len(crons) == 1, crons
    m = re.fullmatch(r"(\d{1,2}) (\d{1,2}) \* \* \*", crons[0].strip())
    assert m, crons[0]
    assert int(m.group(1)) != 0
    assert (int(m.group(2)) * 60 + int(m.group(1))) + 600 < 1440  # 10h scheduler-delay budget


def test_dispatch_has_a_categories_input() -> None:
    dispatch = _doc()["on"]["workflow_dispatch"]
    assert "categories" in dispatch["inputs"]


def test_permissions_are_contents_write_only() -> None:
    assert _doc()["permissions"] == {"contents": "write"}


def test_concurrency_never_cancels() -> None:
    c = _doc()["concurrency"]
    assert c["group"] == "attention-refresh"
    assert c["cancel-in-progress"] is False


def test_actions_pinned_like_the_snapshot_workflow() -> None:
    ref = yaml.safe_load((WORKFLOWS / "narrative-snapshot.yml").read_text(encoding="utf-8"))
    want = {s["uses"] for s in next(iter(ref["jobs"].values()))["steps"] if "uses" in s}
    got = {s["uses"] for s in _all_steps() if "uses" in s}
    assert got == want, (got, want)


def test_no_secret_is_echoed_or_printed() -> None:
    for line in _text().splitlines():
        code = line.split("#", 1)[0]
        if re.search(r"\b(echo|printf|print|cat)\b", code):
            assert not re.search(r"X_BEARER_TOKEN|secrets\.|\$\{\{\s*secrets", code), line
    assert "set -x" not in _text() and "env |" not in _text() and "printenv" not in _text()
    for step in _all_steps():
        secret_vars = [k for k, v in step.get("env", {}).items() if "secrets." in str(v)]
        for line in step.get("run", "").splitlines():
            if re.search(r"\b(echo|printf|print|cat)\b", line):
                assert not any(k in line for k in secret_vars), line


def test_secret_only_in_the_optional_x_gate_and_x_step() -> None:
    doc = _doc()
    assert "secrets." not in str(doc.get("env", ""))
    for job in doc["jobs"].values():
        assert "secrets." not in str(job.get("env", ""))
    x = [s for s in _steps() if "xsearch" in s.get("run", "")]
    assert len(x) == 1
    gate = [s for s in _steps() if s.get("id") == "xgate"]
    assert len(gate) == 1
    assert "ATTENTION_X_LIVE" in str(gate[0]["env"]) and "X_BEARER_TOKEN" in str(gate[0]["env"])
    assert "steps.xgate.outputs.enabled == 'true'" in str(x[0]["if"])
    rgate = [s for s in _steps("refresh-extra") if s.get("id") == "redditgate"]
    reddit = [s for s in _steps("refresh-extra") if "--sources reddit" in s.get("run", "")]
    assert len(rgate) == 1 and len(reddit) == 1
    for s in _all_steps():
        if s not in (gate[0], x[0], rgate[0], reddit[0]):
            assert "secrets." not in str(s)
    assert x[0].get("continue-on-error") is True


def test_runs_default_sources_then_categories_and_never_x_by_default() -> None:
    runs = [s.get("run", "") for s in _steps()]
    joined = "\n".join(runs)
    assert "refresh_attention.py" in joined
    assert "--sources categories" in joined
    assert joined.index("refresh_attention.py") < joined.index("--sources categories")
    probe = [s for s in _steps() if "record_probe" in s.get("run", "")]
    assert len(probe) == 1
    assert "--state" not in probe[0]["run"]  # only observed state, never hand-set
    assert joined.index("attention_freshness") < joined.index("record_probe")
    assert "attention-ok.txt" in probe[0]["run"]  # only sources the verifier passed


EXTRA = ("exchange_volume", "hyperliquid_volume", "trends", "reddit")


def test_extra_job_runs_after_core_even_when_it_is_red() -> None:
    job = _doc()["jobs"]["refresh-extra"]
    assert job["needs"] == "refresh"
    assert job["if"] == "${{ !cancelled() }}"
    assert job["timeout-minutes"] == 40
    assert "needs" not in _doc()["jobs"]["refresh"]
    assert job["steps"][0]["with"]["ref"] == "${{ github.ref_name }}"  # latest main, with the core push


def test_core_job_is_unchanged_in_shape() -> None:
    core = _steps("refresh")
    assert [s.get("name") for s in core][:3] == [None, None, "Install api/ dependencies"]
    assert "--sources exchange_volume" not in str(core) and "reddit" not in str(core).lower()


def test_each_extra_source_has_its_own_continue_on_error_step() -> None:
    for src in EXTRA:
        steps = [s for s in _steps("refresh-extra") if f"--sources {src} " in s.get("run", "")]
        assert len(steps) == 1, src
        assert steps[0]["continue-on-error"] is True
        assert "pipefail" in steps[0]["run"] and f"extra-{src}.log" in steps[0]["run"]
        assert steps[0]["timeout-minutes"] <= 8


def test_reddit_step_is_gated_and_gets_secrets_only_there() -> None:
    reddit = [s for s in _steps("refresh-extra") if "--sources reddit" in s.get("run", "")][0]
    assert "steps.redditgate.outputs.enabled == 'true'" in reddit["if"]
    assert set(reddit["env"]) == {"REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"}
    gate = [s for s in _steps("refresh-extra") if s.get("id") == "redditgate"][0]
    assert "not-probed no credentials" in gate["run"]


def test_extra_verify_fails_on_code_errors_and_probe_lists_only_ok_sources() -> None:
    steps = _steps("refresh-extra")
    verify = [s for s in steps if "attention_extra.py" in s.get("run", "")]
    assert len(verify) == 1 and "continue-on-error" not in verify[0]
    probe = [s for s in steps if "record_probe" in s.get("run", "")]
    assert len(probe) == 1 and "attention-extra-ok.txt" in probe[0]["run"]
    assert "--state" not in probe[0]["run"] and "--sources \"$ok\"" in probe[0]["run"]
    assert "|| true" not in _text()
    commit = [s for s in steps if "git commit" in s.get("run", "")]
    assert len(commit) == 1 and "git push" in commit[0]["run"] and "git pull --rebase" in commit[0]["run"]


def test_failure_propagates() -> None:
    text = _text()
    assert "|| true" not in text
    refresh = [s for s in _steps() if "refresh_attention.py" in s.get("run", "") and "xsearch" not in s["run"]]
    assert refresh
    for s in refresh:
        assert "pipefail" in s["run"] and "set +e" not in s["run"]
        assert "continue-on-error" not in s
    verify = [s for s in _steps() if "attention_freshness" in s.get("run", "")]
    assert len(verify) == 1 and "sys.exit(1)" in verify[0]["run"]
    assert "<= before" not in verify[0]["run"]
    commit = [s for s in _steps() if "git commit" in s.get("run", "")]
    assert commit and "cancelled()" in str(commit[0]["if"])


def test_commit_stages_only_the_attention_store_and_probe_records() -> None:
    adds = re.findall(r"^\s*git add\b.*$", _text(), re.M)
    assert [a.strip() for a in adds] == ["git add -f api/data/cache/attention/",
                                         "git add -f api/data/attention/probe_records.json"] * 2


def test_git_diff_over_github_is_only_the_new_file() -> None:
    try:
        out = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", ".github"],
                             cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("origin/main not available")
    changed = {ln for ln in out.splitlines() if ln}
    assert changed <= {".github/workflows/" + NAME}, changed
