"""S-E2E-UI wiring: `acceptance --ui` preflight and command, and the cycle-mode seeding of the status server."""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from api.data import cache
from api.tests import collector_status_e2e as e2e
from api.tests.cycle import acceptance


def test_ui_refuses_a_busy_port_explicitly(monkeypatch):
    monkeypatch.setattr(acceptance, "available_memory", lambda: acceptance.UI_MIN_FREE_BYTES)
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        reason = acceptance.ui_preflight(port, port + 1 if port < 65535 else port - 1)
    assert reason is not None and f"port {port} in use" in reason


def test_ui_refuses_short_memory(monkeypatch):
    monkeypatch.setattr(acceptance, "available_memory", lambda: acceptance.UI_MIN_FREE_BYTES - 1)
    assert "memory" in acceptance.ui_preflight(*free_ports())


def test_ui_command_is_isolated(tmp_path):
    argv, env = acceptance.ui_command(tmp_path / "cycle", tmp_path / "e2e", tmp_path / "out", 18181, 18182)
    assert argv[:3] == ["pnpm", "exec", "playwright"] and "e2e/collector-status.spec.ts" in argv
    assert env["B2_E2E"] == "1" and env["E2E_API_PORT"] == "18181" and env["E2E_WEB_PORT"] == "18182"
    assert env["E2E_CACHE_ROOT"] == str(tmp_path / "e2e") and env[e2e.CYCLE_ENV] == str(tmp_path / "cycle")
    assert Path(env["E2E_CACHE_ROOT"]).resolve() != cache.DEFAULT_CACHE_ROOT.resolve()
    assert "D18_E2E" not in env


def test_cycle_seed_requires_a_finished_cycle(tmp_path, monkeypatch):
    monkeypatch.setenv("SCREENER_CACHE_ROOT", str(tmp_path / "e2e"))
    monkeypatch.setenv(e2e.CYCLE_ENV, str(tmp_path / "missing"))
    with pytest.raises(SystemExit, match="cycle"):
        e2e.seed()


def test_sizing_shortfall_is_the_real_capacity_arithmetic():
    values = e2e.shortfall_sizing(global_room=800, remaining_caps=240, coins=14, per_unit=20)
    assert values == {"capacity_reads": 240, "need_reads": 280, "shortfall_reads": 40, "backlog_reads": 0}
    with pytest.raises(AssertionError):
        e2e.shortfall_sizing(global_room=800, remaining_caps=240, coins=2, per_unit=20)


def free_ports():
    ports = []
    for _ in range(2):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            ports.append(s.getsockname()[1])
    return ports
