"""The one end-to-end acceptance: `python -m api.tests.cycle.acceptance [--regression] [--ui] [--report PATH]`.

Runs the synthetic daily cycle (C1-C14) in a temporary root over loopback TLS, the spawned fake browser and the
fake gql/feed origin, writes `cycle_report.json` (scenario -> observed result, no secrets) and exits 0 only if every
scenario passed with zero skips. C15 (the consolidated regression) is a separate gate: `--regression` prints its
command and its recorded result and never derives it from this run. `--ui` belongs to S-E2E-UI and fails here.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
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


def main(argv=None) -> int:
    import pytest

    parser = argparse.ArgumentParser(prog="python -m api.tests.cycle.acceptance")
    nested = os.environ.get("MYSITE_CYCLE_NESTED") == "1"
    default = "cycle_report_selftest.json" if nested else "cycle_report.json"
    parser.add_argument("--report", type=Path, default=Path(tempfile.gettempdir()) / default)
    parser.add_argument("--regression", action="store_true", help="report C15: the consolidated command and result")
    parser.add_argument("--regression-record", type=Path, help="recorded C15 result (json: {result, date, ...})")
    parser.add_argument("--ui", action="store_true", help="UI acceptance (S-E2E-UI)")
    args = parser.parse_args(argv)
    if args.ui:
        print("--ui: not available in this slice (S-E2E-UI, Stage 13); failing explicitly, nothing skipped")
        return 2
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cycle_") as tmp, pytest.MonkeyPatch.context() as patch:
        results = run_cycle(Path(tmp), patch, nested=nested)
    elapsed, peak = round(time.monotonic() - started, 1), peak_memory()
    passed = all(r["state"] == "passed" for r in results.values())
    budget = {"seconds": elapsed, "limit_s": BUDGET_S, "peak_bytes": peak, "limit_bytes": BUDGET_BYTES,
              "within": elapsed <= BUDGET_S and (peak is None or peak <= BUDGET_BYTES),
              "note": "includes the nested self-test child started by the real doctor runner" if not nested else
              "nested self-test child"}
    report = {"scenarios": results, "budget": budget, "cannot_prove": CANNOT_PROVE, "skips": 0,
              "passed": passed and budget["within"]}
    if args.regression:
        report["C15"] = regression(args.regression_record)
    args.report.write_text(json.dumps(report, indent=1, sort_keys=True, default=str), encoding="utf-8")
    for name, row in results.items():
        detail = row.get("error") or ""
        print(f"{name:<4} {row['state']:<8} {detail}")
    if args.regression:
        print(f"C15  {report['C15']['state']:<8} {REGRESSION_COMMAND}")
    print(f"budget: {elapsed}s, peak {peak} bytes, within={budget['within']}")
    print(CANNOT_PROVE)
    print(f"report: {args.report}")
    ok = report["passed"] and (not args.regression or report["C15"]["state"] == "passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
