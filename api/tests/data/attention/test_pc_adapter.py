"""W8b AC11/AC12/AC19/AC27: adapter Protocol, error classes, fake adapter, wrapper refusals, cost meter, log scrub.

Pure; no network. API Anything is never installed or run here; only the Protocol and a fake exist.
"""
from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.data.attention import pc_adapter as pa

REPO = Path(__file__).resolve().parents[4]
# Fake values only; the bearer one is split so the repo secret scan does not match a test fixture.
PLANTED = ("cookie=sessid-PLANTED-c00k1e", "Bear" + "er PLANTED-t0ken-value", "q=PLANTED-query-term",
           "PLANTED-message-xyz")


@pytest.fixture(autouse=True)
def _isolated(attention_cache):
    """Every test here writes state or evidence: keep it out of the real cache root."""
    return attention_cache



class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


# --- AC27 wrapper rules ---------------------------------------------------------------------------------------

def test_pinned_sha_constant_is_20cb677039fcfe92d3d9c777aa9362e30ff1fdb8():
    assert pa.PINNED_COMMIT == "20cb677039fcfe92d3d9c777aa9362e30ff1fdb8"


def test_install_command_uses_npm_ci_ignore_scripts():
    assert pa.INSTALL_COMMAND == "npm ci --ignore-scripts"


def test_adapter_refuses_registry_and_publish_calls():
    safe = pa.SafeAdapter(pa.FakeAdapter(pages=[]))
    for name in ("registry_pull", "pull_registry", "publish", "publish_recipe", "import_cookies", "cookie_import",
                 "registry", "importCookies", "pullFromRegistry"):
        with pytest.raises(pa.RefusedFeature):
            getattr(safe, name)


def test_wrapper_refuses_inner_adapter_with_refused_features():
    class Bad(pa.FakeAdapter):
        def publish(self):  # pragma: no cover - never called
            raise AssertionError

    with pytest.raises(pa.RefusedFeature):
        pa.SafeAdapter(Bad(pages=[]))


def test_protocol_and_fake_expose_no_refused_feature():
    for obj in (pa.XAdapter, pa.FakeAdapter, pa.SafeAdapter):
        public = [n for n in dir(obj) if not n.startswith("_")]
        assert not [n for n in public if pa.is_refused_name(n)], obj


def test_safe_adapter_forwards_search_only():
    page = pa.SearchPage([], has_more=False)
    inner = pa.FakeAdapter(pages=[page], page_size=25)
    safe = pa.SafeAdapter(inner)
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    assert safe.search_page("q", now, now, 0) is page and safe.page_size == 25 and inner.calls == 1
    with pytest.raises(pa.RefusedFeature):
        safe.anything_else  # noqa: B018


def test_shipped_x_recipe_never_loaded(tmp_path):
    for p in (Path("C:/vet/apianything/sites/x.json"), Path("/opt/api-anything/sites/x.md"), Path("sites/x.yaml")):
        with pytest.raises(pa.RefusedFeature):
            pa.check_recipe_path(p)
    learned = tmp_path / "learned" / "x-recipe.json"
    assert pa.check_recipe_path(learned) == learned


# --- error classes and log scrub (AC11) -------------------------------------------------------------------------

def test_error_classes_carry_reason_and_status_only():
    cases = {pa.RateLimited: ("rate_limited", True), pa.LoginRequired: ("x_login_required", True),
             pa.AccountSuspended: ("x_account_suspended", True), pa.RedditBlocked: ("reddit_blocked", True),
             pa.EmptyResults: ("empty_results", True), pa.LayoutChanged: ("layout_changed", False),
             pa.Offline: ("offline", False)}
    for cls, (reason, warning) in cases.items():
        exc = cls(418)
        assert exc.reason == reason and exc.warning is warning and exc.status == 418
        assert str(exc) == cls.__name__ and exc.args == ()
    assert {c().reason for c in cases if c().warning} == set(pa.WARNING_REASONS)
    assert set(pa.OWNER_ACTION_REASONS) == {"x_account_suspended", "x_login_required"}


def test_status_must_be_an_int():
    with pytest.raises(TypeError):
        pa.RateLimited("429 " + PLANTED[0])


def test_logs_contain_class_and_status_only_with_planted_secrets(caplog):
    log = logging.getLogger("api.data.attention.pc_test")
    caplog.set_level(logging.DEBUG)
    for exc, status in ((ValueError(" ".join(PLANTED)), None), (pa.RateLimited(429), 429),
                        (RuntimeError(PLANTED[1]), 503)):
        try:
            raise exc
        except Exception as caught:  # noqa: BLE001
            pa.log_failure(log, "xsearch_web", caught, status=status)
    text = caplog.text + " ".join(r.getMessage() for r in caplog.records)
    for secret in PLANTED:
        assert secret not in text and "PLANTED" not in text
    assert "ValueError status=none" in text and "RateLimited status=429" in text and "RuntimeError status=503" in text
    assert caplog.records and all(r.exc_info is None for r in caplog.records)
    assert all(not isinstance(a, BaseException) for r in caplog.records for a in (r.args or ()))


def test_describe_error_ignores_non_int_status():
    assert pa.describe_error(ValueError("x"), status="secret") == "ValueError status=none"
    assert pa.describe_error(pa.Offline()) == "Offline status=none"


# --- AC12 profile path ----------------------------------------------------------------------------------------

def test_profile_path_is_gitignored_and_outside_repo(tmp_path, monkeypatch):
    monkeypatch.delenv(pa.PROFILE_ENV, raising=False)
    default = pa.profile_dir()
    assert REPO not in default.resolve().parents and default.resolve() != REPO
    monkeypatch.setenv(pa.PROFILE_ENV, str(tmp_path / "profile"))
    assert pa.profile_dir() == tmp_path / "profile"
    for inside in (REPO / "profile", REPO / "api" / "data" / "cache" / "attention" / "_pc_state"):
        monkeypatch.setenv(pa.PROFILE_ENV, str(inside))
        with pytest.raises(pa.RefusedFeature):
            pa.profile_dir()
    # machine state the core writes lives under the git-ignored cache root
    probe = "api/data/cache/attention/_pc_state/xsearch_web.json"
    done = subprocess.run(["git", "check-ignore", "-q", probe], cwd=REPO, check=False)
    assert done.returncode == 0


# --- AC19 self-repair cost meter ---------------------------------------------------------------------------------

def test_self_repair_refused_after_15_usd_in_month(attention_cache):
    clock = Clock(datetime(2026, 10, 3, tzinfo=timezone.utc))
    meter = pa.CostMeter(clock=clock)
    adapter = pa.FakeAdapter(pages=[], repair_cost_usd=5.0)
    for _ in range(3):
        pa.attempt_self_repair(adapter, meter)
    assert meter.spent() == 15.0 and adapter.repairs == 3
    with pytest.raises(pa.SelfRepairRefused) as info:
        pa.attempt_self_repair(adapter, meter)
    assert info.value.reason == "layout_changed" and adapter.repairs == 3
    assert pa.CostMeter(clock=clock).spent() == 15.0       # persisted


def test_cap_resets_next_month(attention_cache):
    clock = Clock(datetime(2026, 10, 31, 23, 0, tzinfo=timezone.utc))
    meter = pa.CostMeter(clock=clock)
    adapter = pa.FakeAdapter(pages=[], repair_cost_usd=15.0)
    pa.attempt_self_repair(adapter, meter)
    assert not meter.can_repair()
    clock.now = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    assert meter.can_repair() and meter.spent() == 0
    pa.attempt_self_repair(adapter, meter)
    assert adapter.repairs == 2


def test_negative_or_bad_cost_rejected(attention_cache):
    meter = pa.CostMeter(clock=Clock(datetime(2026, 10, 3, tzinfo=timezone.utc)))
    for bad in (-1.0, float("nan"), float("inf"), "3"):
        with pytest.raises(ValueError):
            meter.charge(bad)


def test_fake_adapter_scripted_pages_and_errors():
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    page = pa.SearchPage([pa.Post("a", "t", now)], has_more=False)
    fake = pa.FakeAdapter(pages=[page, pa.RateLimited(429)])
    assert fake.search_page("q", now, now, 0) is page
    with pytest.raises(pa.RateLimited):
        fake.search_page("q", now, now, 1)
    with pytest.raises(pa.LayoutChanged):
        fake.search_page("q", now, now, 2)        # script exhausted reads as a shape failure, never data
    assert fake.calls == 3
