"""The one end-to-end acceptance: `python -m api.tests.cycle.acceptance [--regression] [--ui] [--report PATH]`.

Runs the synthetic daily cycle (C1-C14) in a temporary root over loopback TLS, the spawned fake browser and the
fake gql/feed origin, writes `cycle_report.json` (scenario -> observed result, no secrets) and exits 0 only if every
scenario passed with zero skips. C15 (the consolidated regression) is a separate gate: `--regression` prints its
command and its recorded result and never derives it from this run. `--ui` (S-E2E-UI) then serves this cycle's
cache through the real FastAPI app and the real web app on isolated ports (fresh `E2E_CACHE_ROOT`) and runs
`web/e2e/collector-status.spec.ts` in Playwright's bundled Chromium at 375/768/1280; a busy port or short memory
fails explicitly (exit 2), never skipped and never reported as passed.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CANNOT_PROVE = (
    "This acceptance proves logic and wiring on synthetic loopback services only. It does NOT prove real X or "
    "Reddit behaviour, real Chrome/Edge behaviour (only the spawned fake browser runs), route quality, Windows "
    "deployment ACLs or Task Scheduler, ban avoidance, that real Reddit responses fit the grammar, or the real "
    "transaction-ID parser (substituted; the real bootstrap request path runs). Native (non-Python) sockets are "
    "not observed (BP13). Probe records are synthetic recordings, not owner-approved live runs.")
SCENARIOS = tuple(f"C{i}" for i in range(1, 15))
REGRESSION_COMMAND = "UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/ -q -rs"
BUDGET_S, BUDGET_BYTES = 180.0, 1 << 30
UI_PORTS = (18181, 18182)  # isolated API / web ports, never the dev defaults
UI_MIN_FREE_BYTES = 1 << 30  # free physical memory for two dev servers plus one Chromium
UI_TIMEOUT_S = 900
WEB = Path(__file__).resolve().parents[3] / "web"


def peak_memory() -> int | None:
    if os.name != "nt":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    c = Counters()
    c.cb = ctypes.sizeof(c)
    kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    ok = psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return int(c.PeakWorkingSetSize) if ok else None


class _Logs(logging.Handler):
    def __init__(self, sink):
        super().__init__(logging.DEBUG)
        self.sink = sink

    def emit(self, record):
        self.sink.append(record.getMessage())


def run_cycle(root: Path, patch, *, nested: bool) -> dict:
    """Run C1-C14; returns {scenario: {state, observed|error}}. The first failure stops the cycle (later steps
    depend on its state) and every later scenario is reported `not_run`, never passed."""
    from loguru import logger as loguru_logger

    from api.tests.cycle import closing
    from api.tests.cycle.world import CycleWorld
    logs: list[str] = []
    handler = _Logs(logs)
    logging.getLogger().addHandler(handler)
    sink = None
    world = CycleWorld(root, patch)
    try:
        with world:
            # after the reader start (which reconfigures the library's loguru handlers)
            sink = loguru_logger.add(lambda message: logs.append(str(message)), level="DEBUG")
            try:
                world.run(nested=nested, logs=logs)
            except Exception as exc:  # noqa: BLE001 - reported per scenario; the marker values are scrubbed
                text = f"{type(exc).__name__}: {exc}"[:600]
                for value in closing.markers().values():
                    text = text.replace(value, "<marker>")
                world.results[world.current] = {"state": "failed", "error": text}
    finally:
        try:
            if sink is not None:
                loguru_logger.remove(sink)
        except ValueError:
            logs.append("loguru sink removed by the library during the run")
        logging.getLogger().removeHandler(handler)
    return {s: world.results.get(s, {"state": "not_run"}) for s in SCENARIOS}


def regression(record_path: Path | None) -> dict:
    if record_path is None or not record_path.exists():
        return {"state": "not_recorded", "command": REGRESSION_COMMAND,
                "note": "separate gate (G-FINAL); never derived from the targeted cycle tests"}
    record = json.loads(record_path.read_text(encoding="utf-8"))
    state = "passed" if record.get("result") == "passed" else "failed"
    return {"state": state, "command": REGRESSION_COMMAND, "recorded": record}


def available_memory() -> int | None:
    if os.name != "nt":
        try:
            return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        except (ValueError, OSError):
            return None

    class Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    s = Status()
    s.dwLength = ctypes.sizeof(s)
    if not ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(s)):
        return None
    # Node fails with "Committing semi space failed" when the commit limit, not physical memory, runs out.
    return int(min(s.ullAvailPhys, s.ullAvailPageFile))


def ui_preflight(api_port: int, web_port: int) -> str | None:
    """The reason `--ui` cannot run here, or None. Unknown memory is not assumed sufficient."""
    free = available_memory()
    if free is None or free < UI_MIN_FREE_BYTES:
        return f"memory short: {free} bytes available, {UI_MIN_FREE_BYTES} required"
    import socket
    for port in (api_port, web_port):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return f"port {port} in use"
    return None


def ui_command(cycle_root: Path, e2e_root: Path, out: Path, api_port: int, web_port: int) -> tuple[list, dict]:
    from api.tests.collector_status_e2e import CYCLE_ENV
    env = {k: v for k, v in os.environ.items() if k not in ("D18_E2E", "PLAYWRIGHT_CHROMIUM_PATH")}
    env.update(B2_E2E="1", E2E_API_PORT=str(api_port), E2E_WEB_PORT=str(web_port), E2E_CACHE_ROOT=str(e2e_root))
    env[CYCLE_ENV] = str(cycle_root)
    argv = ["pnpm", "exec", "playwright", "test", "e2e/collector-status.spec.ts", "--reporter=list",
            f"--output={out}"]
    return argv, env


def run_ui(cycle_root: Path, api_port: int, web_port: int) -> dict:
    """Playwright over the finished cycle; screenshots stay in `out` for inspection."""
    from api.tests.cycle import closing
    planted = closing.markers()
    (cycle_root / "ui-markers.json").write_text(json.dumps(sorted(planted.values())), encoding="utf-8")
    e2e_root = Path(tempfile.mkdtemp(prefix="cycle-ui-e2e-"))
    out = Path(tempfile.mkdtemp(prefix="cycle-ui-results-"))
    argv, env = ui_command(cycle_root, e2e_root, out, api_port, web_port)
    exe = shutil.which(argv[0])
    if exe is None:
        return {"state": "failed", "error": "pnpm not found"}
    try:
        proc = subprocess.run([exe, *argv[1:]], cwd=WEB, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=UI_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"state": "failed", "error": f"playwright exceeded {UI_TIMEOUT_S}s", "results": str(out)}
    shots = sorted(str(p) for p in out.rglob("cycle-*.png"))
    passed = proc.returncode == 0 and len(shots) == 3
    row = {"state": "passed" if passed else "failed", "exit": proc.returncode, "screenshots": shots,
           "results": str(out), "e2e_cache_root": str(e2e_root)}
    if not passed:
        tail = (proc.stdout + proc.stderr)[-4000:]
        for value in planted.values():
            tail = tail.replace(value, "<marker>")
        row["error"] = tail
    return row


def main(argv=None) -> int:
    import pytest

    parser = argparse.ArgumentParser(prog="python -m api.tests.cycle.acceptance")
    nested = os.environ.get("MYSITE_CYCLE_NESTED") == "1"
    default = "cycle_report_selftest.json" if nested else "cycle_report.json"
    parser.add_argument("--report", type=Path, default=Path(tempfile.gettempdir()) / default)
    parser.add_argument("--regression", action="store_true", help="report C15: the consolidated command and result")
    parser.add_argument("--regression-record", type=Path, help="recorded C15 result (json: {result, date, ...})")
    parser.add_argument("--ui", action="store_true", help="UI acceptance (S-E2E-UI) over this cycle's cache")
    parser.add_argument("--ui-ports", type=int, nargs=2, default=UI_PORTS, metavar=("API", "WEB"))
    args = parser.parse_args(argv)
    if args.ui:
        reason = ui_preflight(*args.ui_ports)
        if reason:
            print(f"--ui: {reason}; failing explicitly, nothing skipped")
            return 2
    started = time.monotonic()
    ui = None
    with tempfile.TemporaryDirectory(prefix="cycle_", ignore_cleanup_errors=True) as tmp, \
            pytest.MonkeyPatch.context() as patch:
        results = run_cycle(Path(tmp), patch, nested=nested)
        elapsed, peak = round(time.monotonic() - started, 1), peak_memory()
        passed = all(r["state"] == "passed" for r in results.values())
        if args.ui:
            ui = run_ui(Path(tmp), *args.ui_ports) if passed else {"state": "not_run", "error": "cycle failed"}
    budget = {"seconds": elapsed, "limit_s": BUDGET_S, "peak_bytes": peak, "limit_bytes": BUDGET_BYTES,
              "within": elapsed <= BUDGET_S and (peak is None or peak <= BUDGET_BYTES),
              "note": "includes the nested self-test child started by the real doctor runner" if not nested else
              "nested self-test child"}
    report = {"scenarios": results, "budget": budget, "cannot_prove": CANNOT_PROVE, "skips": 0,
              "passed": passed and budget["within"] and (ui is None or ui["state"] == "passed")}
    if ui is not None:
        report["ui"] = ui
    if args.regression:
        report["C15"] = regression(args.regression_record)
    args.report.write_text(json.dumps(report, indent=1, sort_keys=True, default=str), encoding="utf-8")
    for name, row in results.items():
        detail = row.get("error") or ""
        print(f"{name:<4} {row['state']:<8} {detail}")
    if args.regression:
        print(f"C15  {report['C15']['state']:<8} {REGRESSION_COMMAND}")
    if ui is not None:
        print(f"UI   {ui['state']:<8} {ui.get('error') or ''}")
        for shot in ui.get("screenshots", []):
            print(f"     screenshot {shot}")
    print(f"budget: {elapsed}s, peak {peak} bytes, within={budget['within']}")
    print(CANNOT_PROVE)
    print(f"report: {args.report}")
    ok = report["passed"] and (not args.regression or report["C15"]["state"] == "passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
