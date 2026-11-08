"""C12 daily report, C13 status and doctor, C14 secret scan, over the cycle's cache.

The report (`daily_report.rebuild`), the real FastAPI app (`/api/narrative/sources`) and the real doctor (`main`,
with the real `default_selftest_runner`) run unmodified. The only seam is the owner query file location
(`web_queries.QUERIES_PATH`, a temporary path) so the status reader sees the cycle's configuration.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from api.analytics.attention import daily_report
from api.data import cache
from api.data.attention import web_queries as wq
from api.scripts import collector_doctor as doctor
from api.tests.cycle import browser as cb
from api.tests.cycle import services
from api.tests.data.attention import test_x_proxy_reddit as txr
from api.tests.scripts import reddit_probe_fixtures as fx

NESTED_ENV = "MYSITE_CYCLE_NESTED"  # set for the doctor's real self-test child: it never re-enters the self-test
REPO = Path(__file__).resolve().parents[3]


def markers():
    return {**{f"auth_{k}": v for k, v in services.AUTH.items()}, "csrf": services.CSRF,
            "renewed_auth": services.NEW_AUTH, "renewed_csrf": cb.NEW_CSRF, "browser_cookie": cb.tbs.MARKER,
            "reddit_text": fx.SECRET_MARK, "proxy_credential": txr.MARKER}


def check_report(report, txt):
    for key, sec in report["per_source_method"].items():
        assert sec["eligible"] == sec["stored"] + sec["missing"], (key, sec)
        assert sec["stored"] == sec["exact"] + sec["estimated"], (key, sec)
        assert sum(sec["reasons"].values()) == sec["missing"], (key, sec)
    for source in report["sources"].values():
        for method, sec in (source.get("methods") or {}).items():
            if sec.get("state") != "ok":
                continue
            assert (sec["coverage"] == "100% stored") == (sec["stored"] == sec["eligible"] > 0), (method, sec)
            for sym, reason in sec["missing_coins"].items():
                assert f"{sym} missing ({reason})" in txt, (method, sym)
    for coins in report["coins"].values():
        assert all("selected_method" in c for c in coins.values())


def c12(world):
    r = world.reddit
    rev1, rev2 = r.report_rev1, r.report_rev2
    assert rev1["revision"] == 1 and rev2["revision"] == 2, (rev1["revision"], rev2["revision"])
    assert rev2["revisions"][-1]["changed"], rev2["revisions"]
    reports = {}
    for day in (world.clock().date() - timedelta(days=n) for n in range(1, 7)):
        built = daily_report.rebuild(day, now=world.clock(), only_if_inputs=True)
        if built is None:
            continue
        js, txt = daily_report.report_paths(day)
        assert js.exists() and txt.exists()
        check_report(built, txt.read_text(encoding="utf-8"))
        reports[day.isoformat()] = sorted(built["per_source_method"])
    d1 = daily_report.read_report(r.d1)
    browser = d1["per_source_method"]["reddit/reddit_live_browser"]
    selected = d1["coins"]["reddit"]
    world.record("C12", reports=reports, d1_reddit_browser={k: browser[k] for k in (
        "eligible", "stored", "exact", "estimated", "missing")}, d1_missing_reasons=browser["reasons"],
                 per_coin_selected_method=len(selected), late_settle={"d2_revision": 2,
                                                                        "changed_inputs": rev2["revisions"][-1]["changed"]},
                 arithmetic="eligible = stored + missing; stored = exact + estimated; 100% only when all stored")


def owner_queries(world):
    doc = json.loads(wq.QUERIES_PATH.read_text(encoding="utf-8"))
    doc["collector"] = json.loads(json.dumps(world.config.as_dict()))
    path = world.private / "queries.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert wq.load(path).config.reddit_live_methods == world.config.reddit_live_methods
    world.patch.setattr(wq, "QUERIES_PATH", path)
    return path


def status(world):
    from fastapi.testclient import TestClient
    from api.main import app
    response = TestClient(app).get("/api/narrative/sources")
    assert response.status_code == 200
    return response.text, response.json()


def c13(world, nested):
    path = owner_queries(world)
    text, payload = status(world)
    collector = payload["collector"]
    rows = {s["id"]: s for s in collector["sources"]}
    methods = {m["method"]: m["state"] for m in rows["reddit"]["methods"] or []}
    assert {"reddit_live_browser", "reddit_live_gql"} <= set(methods), methods
    x = next(r for r in payload["sources"] if r["id"] == "xsearch")["health"]
    accounts = {a["label"]: a for a in x["accounts"]}
    assert set(accounts) == set(world.labels), accounts
    unknown = [k for a in accounts.values() for k, v in a.items() if v == "unknown"]
    assert "doctor" not in collector, collector.get("doctor")  # absent until the doctor has run: no fake state

    argv = ["--queries", str(path), "--json", "--live"] + ([] if nested else ["--selftest"])
    out = io.StringIO()
    previous = os.environ.get(NESTED_ENV)
    os.environ[NESTED_ENV] = "1"  # the real runner's child inherits it and skips its own self-test re-entry
    try:
        code = doctor.main(argv, out=out, deps=doctor.Deps(cache_root=cache.CACHE_ROOT, now=world.clock(),
                                                           queries_path=path))
    finally:
        if previous is None:
            os.environ.pop(NESTED_ENV, None)
        else:
            os.environ[NESTED_ENV] = previous
    doc = json.loads(out.getvalue())
    checks = {c["name"]: (c["state"], c["reason"]) for c in doc["checks"]}
    live = {k: v for k, v in checks.items() if k.startswith("live_")}
    recorded = {"live_PR1", "live_PR2"}  # the cycle wrote synthetic PR1/PR2 verify records (world fixture)
    pending = {k: v for k, v in live.items() if k not in recorded}
    assert pending and all(state != "PASS" for state, _ in pending.values()), live
    assert doc["state"] != "PASS" and code != 0
    assert checks["feed_methods"][0] != "PASS", checks["feed_methods"]
    selftest = checks.get("selftest")
    if not nested:
        assert selftest == ("PASS", "acceptance_passed"), selftest
    text_after, after = status(world)
    assert after["collector"]["doctor"]["state"] == doc["state"]
    world.status_texts = [text, text_after]
    report_block = after["collector"].get("daily_report")
    world.record("C13", reddit_methods=methods, x_accounts={k: [a.get("state"), a.get("endpoint_state")]
                                                            for k, a in accounts.items()},
                 unknown_fields_shown=len(unknown), doctor_state=doc["state"], doctor_exit=code,
                 live_checks={k: v[0] for k, v in live.items()},
                 live_note="pending probes are never PASS; PR1/PR2 read the cycle's synthetic recorded verify "
                           "records (the doctor cannot tell a synthetic record from an owner-approved one)", feed_methods=list(checks["feed_methods"]),
                 selftest=list(selftest) if selftest else "nested run: the parent drives the real runner",
                 status_doctor_block=after["collector"]["doctor"]["state"], status_before_doctor="no doctor block",
                 status_daily_report=bool(report_block),
                 not_exercised=["--ui screenshots at 375/768/1280 (S-E2E-UI, Stage 13)",
                                "seeded x_sizing_shortfall status-box warning text (UI text is S-E2E-UI)"])


def repo_changes():
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO, capture_output=True,
                         text=True, check=True).stdout
    return {line[3:] for line in out.splitlines()}


def c14(world, before_repo, logs):
    found = {}
    planted = markers()

    def scan(name, data: bytes):
        for label, value in planted.items():
            if value.encode() in data:
                found.setdefault(name, []).append(label)

    files = [p for p in cache.CACHE_ROOT.rglob("*") if p.is_file()]
    for p in files:
        scan(str(p.relative_to(cache.CACHE_ROOT)), p.read_bytes())
    new = sorted(repo_changes() - before_repo)
    for rel in new:
        p = REPO / rel
        if p.is_file():
            scan("repo:" + rel, p.read_bytes())
    for i, text in enumerate(world.status_texts):
        scan(f"status_json_{i}", text.encode())
    scan("logs", "\n".join(logs).encode())
    scan("pool_log", "\n".join(world.pool().log).encode())
    assert found == {}, found
    private = [p for p in world.private.rglob("*.db") if p.is_file()]
    holding = sorted(p.name for p in private if any(v.encode() in p.read_bytes() for v in planted.values()))
    world.record("C14", cache_files_scanned=len(files), repo_files_new_during_run=new, log_lines=len(logs),
                 status_json_scanned=len(world.status_texts), leaks=0,
                 authorized_private_stores_with_secrets=holding,
                 not_exercised=["no routed B2 child is spawned in the cycle (direct configuration), so child "
                                "argv/env/output are not scanned here; CDP frames are not persisted by the client "
                                "and only the persisted results were scanned"])
