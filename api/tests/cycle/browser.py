"""Spawned fake browser (A13) through the REAL BrowserHost (job object), REAL relay and REAL CdpClient.

Only the spawn command (the S-Fixtures launcher seam), the memory reader, the TCP-table enumerator of the real
`browser_selftest` and the fake's script are substituted; the host, relay, CDP client, self-test, session helper and
route providers run unmodified. Never launches an installed browser. The fake's own state (script, profile jar)
lives outside the collector cache, so the cache secret scan never has to exempt it.
"""
from __future__ import annotations

import json
import os

from api.data import cache
from api.data.attention import browser_host as h
from api.data.attention import browser_profile as p
from api.data.attention import browser_selftest as selftest
from api.data.attention import browser_session as bs
from api.data.attention import twscrape_reader as tr
from api.tests.data.attention import test_browser_selftest as tst
from api.tests.data.attention import test_browser_session as tbs
from api.tests.data.attention.fixture_seams import spawn_launcher

WINDOWS = os.name == "nt"
BINARY = tbs.BINARY
NEW_CSRF = "CycleRenewedCsrfMarker" + "D" * 32
LOGGED_OUT = {"https://x.com/home": {"final_url": "https://x.com/i/flow/login"}}


def x_jar(auth, csrf):
    return [{"name": "auth_token", "value": auth, "expires": tbs.NOW + 40 * tbs.DAY},
            {"name": "ct0", "value": csrf, "expires": tbs.NOW + 3 * tbs.DAY}]


class FakeBrowser:
    """One spawned-fake host whose admission lives in the collector cache (written by the real self-test)."""

    def __init__(self, root, *, cookies=(), pages=None, extra=None):
        root.mkdir(parents=True, exist_ok=True)
        self.root, self.script, self.launches = root, root / "script.json", []
        self.write(cookies=cookies, pages=pages, extra=extra)

        def spawn(argv):
            self.launches.append(1)
            return spawn_launcher(tbs.FAKE, *argv[1:], f"--fake-script={self.script}")

        self.host = h.BrowserHost(BINARY, root / "profiles", cache_root=cache.CACHE_ROOT,
                                  policy=p.ProfilePolicy(True, True), spawn=spawn, memory=lambda: 9999)

    def write(self, *, cookies=(), pages=None, extra=None):
        self.script.write_text(json.dumps({"pages": pages or {}, "cookies": list(cookies), **(extra or {})}))

    def jar(self, label):
        return self.root / "profiles" / label / "fake_cookies.json"


def admit_by_selftest():
    """The REAL A19 self-test over the spawned fake writes the binary's admission record (empty TCP table)."""
    probe = FakeBrowser(cache.CACHE_ROOT.parent / "selftest_browser")
    result = selftest.run(probe.host, cache_root=cache.CACHE_ROOT, enumerator=tst.Enumerator(cache.CACHE_ROOT),
                          firewall=lambda binary: False, window=.3, interval=.05)
    assert result["outcome"] == "tested_clean", result
    assert h.read_admission(cache.CACHE_ROOT, BINARY, h.executable_version(BINARY))["outcome"] == "tested_clean"
    return result["outcome"]


def x_check(runtime, pool, browsers, launches):
    """The real `check_session` for site x, with the account's real `XRouteProvider` route and the pool as the
    real day guard. `browsers[label]` is the fake browser for that account's profile."""
    routes = tr.XRouteProvider(runtime)

    def check(label, mode):
        launches.append(label)
        return bs.check_session("x", label, host=browsers[label].host, profile_name=label, day_guard=pool,
                                routes=routes, mode=mode, timeout=30)
    return check
