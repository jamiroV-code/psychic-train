"""Camoufox local lifecycle/feasibility probe (camoufox-probe, 02-11-26).

Run ONLY with the throwaway venv at C:/Users/jamir/camoufox-probe/venv:

    C:/Users/jamir/camoufox-probe/venv/Scripts/python.exe camoufox_probe.py <step>

Every browser runs headless against a loopback origin this script serves on
127.0.0.1:18765. The browser's HTTP/HTTPS proxy prefs point at a loopback SINK
on 127.0.0.1:18766 that never forwards anything: it records the host each
background request was aimed at and answers 403. A connection watcher records
any non-loopback socket the browser tree opens. Cookie values are synthetic
(FAKE) and are never printed or written to the evidence JSON; only names,
counts and booleans are.

Each step writes evidence/<step>.json beside this script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import StreamRequestHandler, ThreadingTCPServer

import psutil

PROBE_ROOT = Path("C:/Users/jamir/camoufox-probe")
PROFILES = PROBE_ROOT / "profiles"
PRIVATE = PROBE_ROOT / "private"
EVIDENCE = Path(__file__).resolve().parent / "evidence"
ORIGIN_PORT = 18765
SINK_PORT = 18766
ORIGIN = f"http://127.0.0.1:{ORIGIN_PORT}"
RAM_GUARD_MB = 600
# An extra browser while one is already open needs the floor PLUS its own
# footprint (peak private bytes measured in `lifecycle`: ~800 MB).
EXTRA_BROWSER_NEED_MB = RAM_GUARD_MB + 800
LOOPBACK = {"127.0.0.1", "::1", "0.0.0.0", "::"}

# All background traffic goes to the loopback sink; nothing leaves the host.
SINK_PREFS = {
    "network.proxy.type": 1,
    "network.proxy.http": "127.0.0.1",
    "network.proxy.http_port": SINK_PORT,
    "network.proxy.ssl": "127.0.0.1",
    "network.proxy.ssl_port": SINK_PORT,
    "network.proxy.share_proxy_settings": True,
    "network.proxy.no_proxies_on": "127.0.0.1,localhost",
    "network.proxy.failover_direct": False,
    "network.trr.mode": 5,
}

IDENTITY_JS = r"""
async () => {
  const c = document.createElement('canvas'); c.width = 280; c.height = 60;
  const x = c.getContext('2d'); x.textBaseline = 'top'; x.font = '16px Arial';
  x.fillStyle = '#f60'; x.fillRect(100, 1, 62, 20); x.fillStyle = '#069';
  x.fillText('Camoufox probe \u263a', 2, 15); x.fillStyle = 'rgba(102,204,0,0.7)';
  x.fillText('Camoufox probe', 4, 17);
  let gl = null;
  try {
    const g = document.createElement('canvas').getContext('webgl');
    const d = g.getExtension('WEBGL_debug_renderer_info');
    gl = {vendor: g.getParameter(d ? d.UNMASKED_VENDOR_WEBGL : g.VENDOR),
          renderer: g.getParameter(d ? d.UNMASKED_RENDERER_WEBGL : g.RENDERER)};
  } catch (e) { gl = {error: String(e)}; }
  let voices = null;
  try { voices = speechSynthesis.getVoices().length; } catch (e) { voices = String(e); }
  const fontProbe = ['Segoe UI', 'Calibri', 'Helvetica Neue', 'Ubuntu', 'DejaVu Sans', 'Arial']
    .map(f => [f, document.fonts.check('12px "' + f + '"')]);
  return {
    userAgent: navigator.userAgent, platform: navigator.platform, oscpu: navigator.oscpu,
    hardwareConcurrency: navigator.hardwareConcurrency, languages: navigator.languages,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    screen: {width: screen.width, height: screen.height, availWidth: screen.availWidth,
             availHeight: screen.availHeight, colorDepth: screen.colorDepth},
    outer: [outerWidth, outerHeight], inner: [innerWidth, innerHeight], dpr: devicePixelRatio,
    webgl: gl, canvasDataUrl: c.toDataURL(), voices: voices, fonts: fontProbe,
  };
}
"""

STORAGE_JS = r"""
() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return o; }
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def sha256(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


# --------------------------------------------------------------------------- loopback origin
class OriginHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def _send(self, body: bytes, ctype: str, cookies=()):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for c in cookies:
            self.send_header("Set-Cookie", c)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        from urllib.parse import parse_qs, urlparse
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/set":
            acct = q.get("acct", ["x"])[0]
            cookies = [
                "auth_token=FAKE; Max-Age=86400; Path=/; HttpOnly; SameSite=Lax",
                "ct0=FAKE; Max-Age=86400; Path=/; SameSite=Lax",
                f"acct={acct}; Max-Age=86400; Path=/; SameSite=Lax",
                "sess_marker=FAKE-SESSION; Path=/; SameSite=Lax",  # session cookie
            ]
            self._send(b"<html><body>set</body></html>", "text/html", cookies)
        elif u.path == "/mark":
            name = q.get("name", ["marker"])[0]
            self._send(b"<html><body>mark</body></html>", "text/html",
                       [f"{name}=1; Max-Age=86400; Path=/; SameSite=Lax"])
        elif u.path == "/echo":
            # Names only, plus the non-secret acct value: never echo FAKE values.
            jar = {}
            for part in (self.headers.get("Cookie") or "").split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    jar[k] = v
            out = {"cookie_names": sorted(jar), "acct": jar.get("acct"),
                   "auth_token_is_FAKE": jar.get("auth_token") == "FAKE",
                   "ct0_is_FAKE": jar.get("ct0") == "FAKE"}
            self._send(json.dumps(out).encode(), "application/json")
        else:
            self._send(b"<!doctype html><html><head><title>probe</title></head><body>loopback probe origin</body></html>",
                       "text/html")


# --------------------------------------------------------------------------- loopback sink
SINK_LOG: list = []


class SinkHandler(StreamRequestHandler):
    def handle(self):
        try:
            head = b""
            while b"\r\n\r\n" not in head and len(head) < 65536:
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                head += chunk
            line = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            parts = line.split(" ")
            method, target = (parts[0], parts[1]) if len(parts) >= 2 else (line, "")
            if method == "CONNECT":
                host = target.rsplit(":", 1)[0]
                path_hint = ""
            else:
                from urllib.parse import urlparse
                pu = urlparse(target)
                host = pu.hostname or target
                path_hint = (pu.path or "")[:60]
            SINK_LOG.append({"t": now(), "method": method, "host": host, "path_hint": path_hint})
            self.request.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        except Exception as e:  # noqa: BLE001
            SINK_LOG.append({"t": now(), "error": repr(e)})


def start_servers():
    ThreadingHTTPServer.allow_reuse_address = False
    origin = ThreadingHTTPServer(("127.0.0.1", ORIGIN_PORT), OriginHandler)
    origin.daemon_threads = True
    threading.Thread(target=origin.serve_forever, daemon=True).start()
    ThreadingTCPServer.allow_reuse_address = False
    ThreadingTCPServer.daemon_threads = True
    sink = ThreadingTCPServer(("127.0.0.1", SINK_PORT), SinkHandler)
    threading.Thread(target=sink.serve_forever, daemon=True).start()
    return origin, sink


# --------------------------------------------------------------------------- process-tree measurement
class TreeMonitor:
    """Samples every descendant of this Python process (driver + browser)."""

    def __init__(self, interval: float = 0.25):
        self.me = psutil.Process()
        self.interval = interval
        self.samples: list = []
        self.seen: dict = {}  # pid -> {name, create_time, cpu, exe}
        self.external: list = []
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t.start()
        return self

    def stop(self):
        self._stop.set()
        self._t.join(timeout=5)

    def procs(self):
        try:
            return self.me.children(recursive=True)
        except psutil.Error:
            return []

    def snapshot(self):
        rss = priv = 0
        n = 0
        for p in self.procs():
            try:
                with p.oneshot():
                    mi = p.memory_info()
                    ct = p.cpu_times()
                    info = self.seen.setdefault(p.pid, {"name": p.name(), "create_time": p.create_time()})
                    info["cpu"] = ct.user + ct.system
                    info["peak_wset_mb"] = round(getattr(mi, "peak_wset", 0) / 2**20, 1)
                rss += mi.rss
                priv += getattr(mi, "private", mi.vms)
                n += 1
            except psutil.Error:
                continue
        return {"t": time.monotonic(), "procs": n, "rss_mb": rss / 2**20, "private_mb": priv / 2**20}

    def _net(self):
        pids = {p.pid for p in self.procs()}
        try:
            conns = psutil.net_connections(kind="inet")
        except psutil.Error:
            return
        for c in conns:
            if c.pid in pids and c.raddr and c.raddr.ip not in LOOPBACK:
                rec = {"t": now(), "pid": c.pid, "raddr": f"{c.raddr.ip}:{c.raddr.port}", "status": c.status}
                if rec["raddr"] not in {e["raddr"] for e in self.external}:
                    self.external.append(rec)

    def _run(self):
        k = 0
        while not self._stop.is_set():
            self.samples.append(self.snapshot())
            if k % 4 == 0:
                self._net()
            k += 1
            self._stop.wait(self.interval)

    def window(self, t0: float, t1: float):
        xs = [s for s in self.samples if t0 <= s["t"] <= t1 and s["procs"]]
        if not xs:
            return None
        return {
            "n": len(xs),
            "rss_mb_mean": round(sum(s["rss_mb"] for s in xs) / len(xs), 1),
            "private_mb_mean": round(sum(s["private_mb"] for s in xs) / len(xs), 1),
            "rss_mb_max": round(max(s["rss_mb"] for s in xs), 1),
            "private_mb_max": round(max(s["private_mb"] for s in xs), 1),
            "procs_max": max(s["procs"] for s in xs),
        }

    def peak(self):
        xs = [s for s in self.samples if s["procs"]]
        if not xs:
            return None
        return {"rss_mb": round(max(s["rss_mb"] for s in xs), 1),
                "private_mb": round(max(s["private_mb"] for s in xs), 1),
                "procs": max(s["procs"] for s in xs)}

    def cpu_total(self):
        return round(sum(v.get("cpu", 0) for v in self.seen.values()), 2)

    def survivors(self):
        alive = []
        for pid, info in self.seen.items():
            try:
                p = psutil.Process(pid)
                if abs(p.create_time() - info["create_time"]) < 1e-3 and p.is_running():
                    alive.append({"pid": pid, "name": info["name"]})
            except psutil.Error:
                continue
        return alive

    def wait_exit(self, timeout: float = 30.0):
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if not self.survivors():
                return round(time.monotonic() - t0, 2)
            time.sleep(0.05)
        return None

    def browser_pids(self):
        out = []
        for p in self.procs():
            try:
                if p.name().lower() == "camoufox.exe":
                    out.append(p)
            except psutil.Error:
                pass
        return out


# --------------------------------------------------------------------------- helpers
def free_ram_mb() -> int:
    return int(psutil.virtual_memory().available / 2**20)


def guard_ram(result: dict, label: str, need_mb: int = RAM_GUARD_MB) -> bool:
    mb = free_ram_mb()
    result.setdefault("ram_checks", []).append({"t": now(), "before": label, "available_mb": mb, "need_mb": need_mb})
    if mb < need_mb:
        result["aborted"] = f"available RAM {mb} MB < {need_mb} MB before {label}"
        return False
    return True


def dir_size_mb(path: Path) -> float:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 2**20, 2)


def launch_kwargs(profile: Path, **extra):
    kw = dict(headless=True, persistent_context=True, user_data_dir=str(profile),
              firefox_user_prefs=dict(SINK_PREFS))
    kw.update(extra)
    return kw


def identity(page) -> dict:
    raw = page.evaluate(IDENTITY_JS)
    raw["canvas_sha256"] = sha256(raw.pop("canvasDataUrl"))
    return raw


def cookie_summary(ctx) -> dict:
    cs = ctx.cookies([ORIGIN])
    return {
        "names": sorted(c["name"] for c in cs),
        "acct": next((c["value"] for c in cs if c["name"] == "acct"), None),
        "auth_token_is_FAKE": any(c["name"] == "auth_token" and c["value"] == "FAKE" for c in cs),
        "session_cookie_present": any(c["name"] == "sess_marker" for c in cs),
    }


def storage(page) -> dict:
    return page.evaluate(STORAGE_JS)


def write_evidence(step: str, result: dict):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    result["sink_requests"] = SINK_LOG
    result["sink_hosts"] = sorted({r.get("host") for r in SINK_LOG if r.get("host")})
    path = EVIDENCE / f"{step}.json"
    path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"wrote {path}")


def open_profile(profile: Path, result: dict, label: str, mon: TreeMonitor, **extra):
    """Launch; returns (cm, ctx, page, timings)."""
    from camoufox.sync_api import Camoufox
    t0 = time.monotonic()
    cm = Camoufox(**launch_kwargs(profile, **extra))
    ctx = cm.__enter__()
    t1 = time.monotonic()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(ORIGIN + "/")
    t2 = time.monotonic()
    result.setdefault("launches", []).append({
        "label": label, "t": now(), "launch_s": round(t1 - t0, 2), "first_page_s": round(t2 - t1, 2)})
    return cm, ctx, page, (t0, t1, t2)


def close_cm(cm, mon: TreeMonitor, result: dict, label: str):
    t0 = time.monotonic()
    err = None
    try:
        cm.__exit__(None, None, None)
    except Exception as e:  # noqa: BLE001
        err = repr(e)
    t_close = round(time.monotonic() - t0, 2)
    t_exit = mon.wait_exit(30)
    result.setdefault("closes", []).append({
        "label": label, "close_call_s": t_close, "all_children_gone_s_after_close": t_exit,
        "survivors": mon.survivors(), "error": err})


def base_result(step: str) -> dict:
    import camoufox
    import playwright
    from importlib.metadata import version
    return {"step": step, "started": now(), "python": sys.version.split()[0],
            "camoufox": version("camoufox"), "playwright": version("playwright"),
            "free_ram_mb_start": free_ram_mb(),
            "disk_free_gib_start": round(psutil.disk_usage("C:/").free / 2**30, 2)}


# --------------------------------------------------------------------------- steps
def step_lifecycle(result, mon):
    prof = PROFILES / "A"
    if not guard_ram(result, "launch A"):
        return
    result["profile_size_mb_before"] = dir_size_mb(prof) if prof.exists() else 0.0
    cm, ctx, page, (t0, t1, t2) = open_profile(prof, result, "A-first", mon)
    page.goto(ORIGIN + "/set?acct=A")
    page.goto(ORIGIN + "/")
    page.evaluate("() => { localStorage.setItem('probe_acct', 'A'); localStorage.setItem('probe_written', String(Date.now())); }")
    result["identity"] = identity(page)
    result["cookies_after_set"] = cookie_summary(ctx)
    result["storage_after_set"] = storage(page)
    t_idle0 = time.monotonic()
    time.sleep(20)
    t_idle1 = time.monotonic()
    result["memory_startup_window"] = mon.window(t0, t2 + 2)
    result["memory_steady_idle_20s"] = mon.window(t_idle0 + 5, t_idle1)
    result["memory_peak"] = mon.peak()
    result["procs_during"] = [{"pid": pid, **v} for pid, v in mon.seen.items()]
    close_cm(cm, mon, result, "A-first graceful")
    result["cpu_seconds_tree"] = mon.cpu_total()
    result["profile_size_mb_after"] = dir_size_mb(prof)


def step_reopen(result, mon, profile="A", label="A-reopen", **extra):
    prof = PROFILES / profile
    if not guard_ram(result, f"launch {label}"):
        return
    cm, ctx, page, (t0, t1, t2) = open_profile(prof, result, label, mon, **extra)
    result["cookies_on_reopen"] = cookie_summary(ctx)
    result["storage_on_reopen"] = storage(page)
    result["echo_on_reopen"] = json.loads(page.goto(ORIGIN + "/echo").text())
    page.goto(ORIGIN + "/")
    result["identity"] = identity(page)
    time.sleep(3)
    result["memory_peak"] = mon.peak()
    close_cm(cm, mon, result, f"{label} graceful")
    result["cpu_seconds_tree"] = mon.cpu_total()
    result["profile_size_mb_after"] = dir_size_mb(prof)


def _load_pinned(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def step_pinned(result, mon, create: bool):
    prof = PROFILES / "P"
    ident = PROFILES / "P.identity.json"
    if create:
        from camoufox.fingerprints import generate_fingerprint
        fp = generate_fingerprint(os="windows")
        ident.write_text(json.dumps(fp, indent=1, default=str), encoding="utf-8")
        result["identity_file"] = str(ident)
        result["identity_file_bytes"] = ident.stat().st_size
    fp = _load_pinned(ident)
    if not guard_ram(result, "launch P"):
        return
    cm, ctx, page, _ = open_profile(prof, result, "P-create" if create else "P-reopen", mon, fingerprint=fp)
    if create:
        page.goto(ORIGIN + "/set?acct=P")
        page.goto(ORIGIN + "/")
        page.evaluate("() => localStorage.setItem('probe_acct', 'P')")
    result["cookies"] = cookie_summary(ctx)
    result["storage"] = storage(page)
    result["identity"] = identity(page)
    result["memory_peak"] = mon.peak()
    close_cm(cm, mon, result, "P graceful")


def step_crash(result, mon):
    prof = PROFILES / "A"
    if not guard_ram(result, "launch A-crash"):
        return
    cm, ctx, page, _ = open_profile(prof, result, "A-crash", mon)
    page.goto(ORIGIN + "/mark?name=precrash_marker")
    page.goto(ORIGIN + "/")
    page.evaluate("() => localStorage.setItem('precrash_ls', String(Date.now()))")
    result["cookies_before_kill"] = cookie_summary(ctx)
    result["storage_before_kill"] = storage(page)
    time.sleep(3)
    victims = mon.browser_pids()
    result["killed"] = [{"pid": p.pid, "name": p.name()} for p in victims]
    t0 = time.monotonic()
    for p in victims:
        try:
            p.kill()  # TerminateProcess: hard kill of the browser tree only
        except psutil.Error as e:
            result.setdefault("kill_errors", []).append(repr(e))
    gone, alive = psutil.wait_procs(victims, timeout=10)
    result["browser_gone_s"] = round(time.monotonic() - t0, 2)
    result["alive_after_kill"] = [p.pid for p in alive]
    try:
        page.evaluate("() => 1")
        result["playwright_after_kill"] = "no error"
    except Exception as e:  # noqa: BLE001
        result["playwright_after_kill"] = repr(e)[:300]
    close_cm(cm, mon, result, "A-crash exit after kill")
    lock_files = [p.name for p in prof.iterdir() if p.name.lower() in ("parent.lock", "lock", ".parentlock")]
    result["lock_files_after_kill"] = lock_files


def step_after_crash(result, mon):
    step_reopen(result, mon, profile="A", label="A-after-crash")


def step_isolation_seq(result, mon):
    out = {}
    for name in ("B", "C"):
        prof = PROFILES / name
        if not guard_ram(result, f"launch {name}"):
            return
        cm, ctx, page, _ = open_profile(prof, result, f"{name}-create", mon)
        page.goto(ORIGIN + f"/set?acct={name}")
        page.goto(ORIGIN + "/")
        page.evaluate(f"() => localStorage.setItem('probe_acct', '{name}')")
        out[name] = {"cookies": cookie_summary(ctx), "storage": storage(page), "identity": identity(page)}
        close_cm(cm, mon, result, f"{name}-create graceful")
    for name in ("B", "C"):
        prof = PROFILES / name
        if not guard_ram(result, f"reopen {name}"):
            return
        cm, ctx, page, _ = open_profile(prof, result, f"{name}-reopen", mon)
        out[name]["reopen_cookies"] = cookie_summary(ctx)
        out[name]["reopen_storage"] = storage(page)
        out[name]["reopen_echo"] = json.loads(page.goto(ORIGIN + "/echo").text())
        page.goto(ORIGIN + "/")
        out[name]["reopen_identity"] = identity(page)
        close_cm(cm, mon, result, f"{name}-reopen graceful")
    result["profiles"] = out
    result["memory_peak_single"] = mon.peak()


def step_isolation_concurrent(result, mon):
    from playwright.sync_api import sync_playwright
    from camoufox.sync_api import NewBrowser
    out = {}
    with sync_playwright() as pw:
        ctxs = {}
        for name in ("B", "C"):
            if not guard_ram(result, f"concurrent launch {name}", RAM_GUARD_MB if not ctxs else EXTRA_BROWSER_NEED_MB):
                break
            t0 = time.monotonic()
            ctx = NewBrowser(pw, **launch_kwargs(PROFILES / name))
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(ORIGIN + "/echo")
            echo = json.loads(page.inner_text("body"))
            page.goto(ORIGIN + "/")
            ctxs[name] = ctx
            out[name] = {"launch_s": round(time.monotonic() - t0, 2), "cookies": cookie_summary(ctx),
                         "echo": echo, "storage": storage(page), "identity": identity(page)}
            time.sleep(5)
            out[name]["tree_after_launch"] = mon.snapshot()
        time.sleep(10)
        result["memory_both_open_10s"] = mon.window(time.monotonic() - 8, time.monotonic())
        result["memory_peak"] = mon.peak()
        # Same profile twice while B is open: Playwright/Firefox must refuse.
        if "B" in ctxs and guard_ram(result, "second launch on B", EXTRA_BROWSER_NEED_MB):
            t0 = time.monotonic()
            try:
                dup = NewBrowser(pw, **launch_kwargs(PROFILES / "B"))
                result["same_profile_twice"] = {"rejected": False}
                dup.close()
            except Exception as e:  # noqa: BLE001
                result["same_profile_twice"] = {"rejected": True, "seconds": round(time.monotonic() - t0, 2),
                                                "error": str(e)[:1500]}
        for name, ctx in ctxs.items():
            ctx.close()
    result["exit_s"] = mon.wait_exit(30)
    result["survivors"] = mon.survivors()
    result["profiles"] = out
    result["cpu_seconds_tree"] = mon.cpu_total()


def step_same_profile_twice(result, mon):
    """Sequential-API variant: a second Camoufox() on a profile that is open."""
    from camoufox.sync_api import Camoufox
    if not guard_ram(result, "launch B"):
        return
    cm, ctx, page, _ = open_profile(PROFILES / "B", result, "B-hold", mon)
    # The attempt asks for a Linux identity: a host-OS (Windows) identity makes
    # launch_options() start a whole extra probe browser to read the host GPU,
    # which would be a real second browser. A locked-profile attempt itself
    # should exit early, so it needs less headroom than a full browser.
    if guard_ram(result, "second Camoufox on B", RAM_GUARD_MB + 300):
        # A second sync Playwright cannot start in this thread; use a child process.
        code = (
            "import json,sys\n"
            "sys.path.insert(0, r'%s')\n"
            "import camoufox_probe as P\n"
            "from camoufox.sync_api import Camoufox\n"
            "try:\n"
            "    with Camoufox(**P.launch_kwargs(P.PROFILES / 'B', os='linux')) as c:\n"
            "        print(json.dumps({'rejected': False}))\n"
            "except Exception as e:\n"
            "    print(json.dumps({'rejected': True, 'error': str(e)[:1500]}))\n"
        ) % str(Path(__file__).resolve().parent)
        t0 = time.monotonic()
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
        t1 = time.monotonic()
        result["same_profile_twice_child"] = {
            "seconds": round(t1 - t0, 2), "rc": proc.returncode,
            "stdout_tail": proc.stdout[-1500:], "stderr_tail": proc.stderr[-1500:],
            "tree_memory_during_attempt": mon.window(t0, t1)}
    result["holder_still_alive"] = bool(page.evaluate("() => 1") == 1)
    close_cm(cm, mon, result, "B-hold graceful")


def _camou_config(opts: dict) -> dict:
    env = opts.get("env") or {}
    keys = sorted((k for k in env if k.startswith("CAMOU_CONFIG_")), key=lambda k: int(k.rsplit("_", 1)[1]))
    return json.loads("".join(str(env[k]) for k in keys))


def _diff_keys(a: dict, b: dict) -> list:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def step_config_determinism(result, mon):
    """No browser: build launch options twice per mode and diff the Camoufox
    config (CAMOU_CONFIG) and prefs that the browser would receive."""
    import warnings
    from camoufox.utils import launch_options
    fp = _load_pinned(PROFILES / "P.identity.json")
    modes = {
        "unpinned_default": {},
        "pinned_fingerprint": {"fingerprint": fp, "i_know_what_im_doing": True},
    }
    out = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for mode, extra in modes.items():
            runs = [launch_options(headless=True, firefox_user_prefs=dict(SINK_PREFS), **extra) for _ in range(2)]
            c1, c2 = (_camou_config(r) for r in runs)
            p1, p2 = (r.get("firefox_user_prefs", {}) for r in runs)
            out[mode] = {
                "config_keys": len(c1),
                "config_keys_that_differ": _diff_keys(c1, c2),
                "prefs_that_differ": _diff_keys(p1, p2),
                "canvas_placeholder_pref_keys": sorted(k for k in p1 if "canvas" in k.lower()),
                "sample": {k: c1.get(k) for k in ("navigator.userAgent", "screen.width", "screen.height",
                                                    "navigator.hardwareConcurrency", "webGl:renderer")},
                "fonts_count": len(c1.get("fonts") or []),
            }
    result["modes"] = out


def step_canvas_stability(result, mon):
    """Is the canvas hash stable WITHIN one session (same page twice, after a
    reload, in a second page)? Separates per-read noise from per-launch change."""
    fp = _load_pinned(PROFILES / "P.identity.json")
    if not guard_ram(result, "launch P-canvas"):
        return
    cm, ctx, page, _ = open_profile(PROFILES / "P", result, "P-canvas", mon, fingerprint=fp,
                                    i_know_what_im_doing=True)
    hashes = [identity(page)["canvas_sha256"], identity(page)["canvas_sha256"]]
    page.reload()
    hashes.append(identity(page)["canvas_sha256"])
    p2 = ctx.new_page()
    p2.goto(ORIGIN + "/")
    hashes.append(identity(p2)["canvas_sha256"])
    result["canvas_hashes_same_session"] = hashes
    result["identity"] = identity(page)
    close_cm(cm, mon, result, "P-canvas graceful")


def step_cookie_export(result, mon):
    PRIVATE.mkdir(parents=True, exist_ok=True)
    out_file = PRIVATE / "cookies-B.json"
    if not guard_ram(result, "launch B-export"):
        return
    cm, ctx, page, _ = open_profile(PROFILES / "B", result, "B-export", mon)
    cookies = ctx.cookies([ORIGIN])
    out_file.write_text(json.dumps(cookies), encoding="utf-8")
    user = os.environ.get("USERNAME", "")
    acl = subprocess.run(["icacls", str(out_file), "/inheritance:r", "/grant:r", f"{user}:F"],
                         capture_output=True, text=True)
    acl_show = subprocess.run(["icacls", str(out_file)], capture_output=True, text=True)
    result["export"] = {
        "file": str(out_file), "bytes": out_file.stat().st_size, "count": len(cookies),
        "names": sorted(c["name"] for c in cookies),
        "fields": sorted(cookies[0].keys()) if cookies else [],
        "auth_like_values_are_FAKE": all(c["value"] == "FAKE" for c in cookies if c["name"] in ("auth_token", "ct0")),
        "icacls_rc": acl.returncode, "icacls_after": acl_show.stdout.strip().splitlines()[:4],
        "httpOnly_flags": {c["name"]: c["httpOnly"] for c in cookies},
    }
    close_cm(cm, mon, result, "B-export graceful")
    # Re-import into a FRESH persistent profile D (deleted first if a prior run left it).
    prof_d = PROFILES / "D"
    if prof_d.exists():
        import shutil
        shutil.rmtree(prof_d)
    if not guard_ram(result, "launch D-import"):
        return
    cm, ctx, page, _ = open_profile(prof_d, result, "D-import", mon)
    result["D_before_import"] = cookie_summary(ctx)
    imported = json.loads(out_file.read_text(encoding="utf-8"))
    ctx.add_cookies(imported)
    result["D_after_import"] = cookie_summary(ctx)
    result["D_server_echo"] = json.loads(page.goto(ORIGIN + "/echo").text())
    close_cm(cm, mon, result, "D-import graceful")


def step_exception(result, mon):
    from camoufox.sync_api import Camoufox
    if not guard_ram(result, "launch E-exception"):
        return
    t0 = time.monotonic()
    try:
        with Camoufox(**launch_kwargs(PROFILES / "E")) as ctx:
            page = ctx.new_page()
            page.goto(ORIGIN + "/")
            time.sleep(2)
            result["procs_open"] = mon.snapshot()["procs"]
            raise RuntimeError("probe: deliberate exception inside the with-block")
    except RuntimeError as e:
        result["exception"] = str(e)
    result["with_exit_s"] = round(time.monotonic() - t0, 2)
    result["children_gone_s"] = mon.wait_exit(30)
    result["survivors"] = mon.survivors()


def step_close_twice(result, mon):
    from camoufox.sync_api import Camoufox
    if not guard_ram(result, "launch E-close-twice"):
        return
    cm = Camoufox(**launch_kwargs(PROFILES / "E"))
    ctx = cm.__enter__()
    ctx.new_page().goto(ORIGIN + "/")
    calls = []
    for i in range(2):
        t0 = time.monotonic()
        try:
            ctx.close()
            calls.append({"call": f"context.close #{i + 1}", "ok": True, "s": round(time.monotonic() - t0, 2)})
        except Exception as e:  # noqa: BLE001
            calls.append({"call": f"context.close #{i + 1}", "ok": False, "error": repr(e)[:300]})
    t0 = time.monotonic()
    try:
        cm.__exit__(None, None, None)
        calls.append({"call": "Camoufox.__exit__ after close", "ok": True, "s": round(time.monotonic() - t0, 2)})
    except Exception as e:  # noqa: BLE001
        calls.append({"call": "Camoufox.__exit__ after close", "ok": False, "error": repr(e)[:300]})
    result["calls"] = calls
    result["children_gone_s"] = mon.wait_exit(30)
    result["survivors"] = mon.survivors()


def step_kill_python(result, mon):
    """Parent (this process) launches a child probe that holds a browser, then
    hard-kills ONLY the child Python process: are driver/browser orphaned?"""
    code = (
        "import sys,time\n"
        "sys.path.insert(0, r'%s')\n"
        "import camoufox_probe as P\n"
        "from camoufox.sync_api import Camoufox\n"
        "with Camoufox(**P.launch_kwargs(P.PROFILES / 'E')) as c:\n"
        "    p = c.new_page(); p.goto(P.ORIGIN + '/')\n"
        "    print('READY', flush=True)\n"
        "    time.sleep(120)\n"
    ) % str(Path(__file__).resolve().parent)
    if not guard_ram(result, "launch child holder"):
        return
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = child.stdout.readline().strip()
    result["child_ready"] = line
    time.sleep(2)
    tree = mon.procs()
    result["tree_before_kill"] = [{"pid": p.pid, "name": p.name()} for p in tree]
    child.kill()
    child.wait(10)
    t0 = time.monotonic()
    deadline = t0 + 30
    alive = []
    while time.monotonic() < deadline:
        alive = [p for p in tree if p.pid != child.pid and p.is_running()]
        if not alive:
            break
        time.sleep(0.25)
    result["after_python_kill_alive"] = [{"pid": p.pid, "name": p.name()} for p in alive]
    result["self_exit_s"] = None if alive else round(time.monotonic() - t0, 2)
    if alive:
        # Clean up our own orphans only (PIDs recorded from our own tree above).
        for p in alive:
            try:
                p.kill()
            except psutil.Error:
                pass
        result["orphans_killed_by_probe"] = [p.pid for p in alive]


STEPS = {
    "lifecycle": step_lifecycle,
    "reopen": step_reopen,
    "pinned_create": lambda r, m: step_pinned(r, m, True),
    "pinned_reopen": lambda r, m: step_pinned(r, m, False),
    "crash": step_crash,
    "after_crash": step_after_crash,
    "isolation_seq": step_isolation_seq,
    "isolation_concurrent": step_isolation_concurrent,
    "same_profile_twice": step_same_profile_twice,
    "cookie_export": step_cookie_export,
    "exception": step_exception,
    "close_twice": step_close_twice,
    "kill_python": step_kill_python,
    "config_determinism": step_config_determinism,
    "canvas_stability": step_canvas_stability,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=sorted(STEPS))
    args = ap.parse_args()
    PROFILES.mkdir(parents=True, exist_ok=True)
    result = base_result(args.step)
    origin, sink = start_servers()
    mon = TreeMonitor().start()
    try:
        STEPS[args.step](result, mon)
    except Exception as e:  # noqa: BLE001
        result["error"] = repr(e)[:2000]
        result["traceback"] = traceback.format_exc()[-4000:]
    finally:
        time.sleep(0.5)
        mon.stop()
        result["external_connections_seen"] = mon.external
        result["free_ram_mb_end"] = free_ram_mb()
        result["finished"] = now()
        result["survivors_at_end"] = mon.survivors()
        origin.shutdown()
        sink.shutdown()
        write_evidence(args.step, result)


if __name__ == "__main__":
    main()
