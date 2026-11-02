"""The attention collector as its own process (standalone-collector, 02-11-26).

    SCREENER_ATTENTION_PC_WORKER=1 python -m api.data.attention_collector

Runs the same PC worker as the API lifespan (`attention_pc_refresh.start_from_env`, mode `standalone`): X and Reddit
on their two threads, the same pacing, budgets, evidence and lazy X library import, the same rotating log file
(`<cache>/attention/_logs/attention_pc.log`) and the shared heartbeat (`collector_heartbeat`). Restarting the API no
longer interrupts collection once the API's launch environment drops the flag.

- Refuses to start (exit code `EXIT_FLAG_OFF`) unless `SCREENER_ATTENTION_PC_WORKER` is exactly `1`, and
  (`EXIT_REFUSED`) while another live collector, standalone or inside the API, holds a fresh heartbeat.
- Blocks until CTRL+C, CTRL+BREAK, SIGTERM or (Windows) the console window closing, a logoff or a shutdown; then
  stops the worker, joins its threads, marks the heartbeat stopped and removes the log handler. A hard kill (Task
  Scheduler "End", TerminateProcess) leaves a heartbeat whose process is gone: the status reads it as stopped.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time as _time
from collections.abc import Callable

from api.data import attention_pc_refresh as apr

log = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FLAG_OFF = 2
EXIT_REFUSED = 3
EXIT_START_FAILED = 4
POLL_SECONDS = 1.0  # the main thread wakes this often, so a signal is handled within a second on every platform
CONSOLE_CLOSE_WAIT_SECONDS = 4.5  # Windows ends the process about 5 s after a close, logoff or shutdown event
# Windows console control events (wincon.h).
CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT = 0, 1, 2, 5, 6
_console_handler = None  # the registered ctypes callback, kept alive while it is installed


def console_event(ctrl_type: int, stop: threading.Event, done: threading.Event, timeout: float) -> bool:
    """A Windows console control event: request the stop. CTRL+C and CTRL+BREAK return False so Python's own handler
    still raises SIGINT / SIGBREAK; close, logoff and shutdown wait (bounded) for the cleanup and return True, since
    Windows ends the process as soon as the handler returns."""
    stop.set()
    if ctrl_type in (CTRL_C_EVENT, CTRL_BREAK_EVENT):
        return False
    done.wait(timeout)
    return True


def _install_console_handler(stop: threading.Event, done: threading.Event) -> Callable[[], None]:
    global _console_handler
    import ctypes
    from ctypes import wintypes

    routine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetConsoleCtrlHandler.argtypes = (routine, wintypes.BOOL)
    handler = routine(lambda ctrl_type: console_event(ctrl_type, stop, done, CONSOLE_CLOSE_WAIT_SECONDS))
    if not kernel32.SetConsoleCtrlHandler(handler, True):
        log.warning("attention collector console close handler not installed: error=%s", ctypes.get_last_error())
        return lambda: None
    _console_handler = handler

    def remove() -> None:
        global _console_handler
        kernel32.SetConsoleCtrlHandler(handler, False)
        _console_handler = None

    return remove


def _install_signal_handlers(stop: threading.Event, done: threading.Event) -> Callable[[], None]:
    """SIGINT, SIGTERM and (Windows) SIGBREAK set `stop`; the previous handlers come back on the returned call."""
    def on_signal(signum, _frame) -> None:
        log.info("attention collector stopping: signal=%s", signal.Signals(signum).name)
        stop.set()

    previous = {}
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            sig = getattr(signal, name)
            previous[sig] = signal.signal(sig, on_signal)
    remove_console = _install_console_handler(stop, done) if sys.platform == "win32" else (lambda: None)

    def restore() -> None:
        remove_console()
        for sig, handler in previous.items():
            signal.signal(sig, handler)

    return restore


def run(env=None, *, stop: threading.Event | None = None, install_signals: bool = True,
        poll_seconds: float = POLL_SECONDS, **worker_kwargs) -> int:
    """Start the worker in this process and block until `stop` is set (by a signal or the caller); the exit code."""
    env = os.environ if env is None else env
    if not apr.enabled(env):
        log.error("attention collector not started: %s must be exactly 1 in this process's environment",
                  apr.FLAG_ENV)
        return EXIT_FLAG_OFF
    stop = stop or threading.Event()
    done = threading.Event()
    restore = _install_signal_handlers(stop, done) if install_signals else (lambda: None)
    try:
        worker = apr.start_from_env(env, mode="standalone", **worker_kwargs)
        if worker is None:
            reason = apr.disabled_reason()
            log.error("attention collector not started: %s", reason)
            return EXIT_REFUSED if reason == "another-instance" else EXIT_START_FAILED
        log.info("attention collector running: pid=%s sources=%s", os.getpid(), ",".join(worker.streams) or "none")
        while not stop.wait(poll_seconds):
            pass
        log.info("attention collector stopping")
        return EXIT_OK
    finally:
        apr.stop_worker()
        done.set()
        restore()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s",
                        datefmt="%Y-%m-%dT%H:%M:%S")
    logging.Formatter.converter = _time.gmtime
    return run()


if __name__ == "__main__":
    sys.exit(main())
