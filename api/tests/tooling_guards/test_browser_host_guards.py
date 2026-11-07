"""A5/A8/A16/A17 browser host guards; later CDP/relay slices extend this chain."""
import ast
from pathlib import Path

from api.data.attention import browser_host as host

ATTENTION = Path(host.__file__).parent
BANNED = ("--remote-debugging-port", "--remote-allow-origins", "DevToolsActivePort", "--no-sandbox",
          "--enable-logging", "--log-net-log", "Page.captureScreenshot", "Tracing.start", "HeapProfiler.",
          "Input.dispatch", "Network.setCookie", "Fetch.enable", "Target.sendMessageToTarget")


def problems(source):
    tree = ast.parse(source)
    # The rejection vocabulary is allowed only in the one constant, never a call/argv.
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REJECT_FLAGS" for t in node.targets):
            assert all(isinstance(c, ast.Constant) and isinstance(c.value, str) for c in node.value.elts)
            node.value = ast.Tuple(elts=[], ctx=ast.Load())
    text = ast.unparse(tree)
    result = [item for item in BANNED if item in text]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                result.append("print")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"debug", "info", "warning", "error", "exception"}:
                result.append("logging")
    return result


def test_host_and_profile_have_no_debug_endpoint_secret_capture_or_logging():
    for name in ("browser_host.py", "browser_profile.py"):
        assert not problems((ATTENTION / name).read_text(encoding="utf-8"))


def test_guard_detects_planted_unsafe_launch_and_logging():
    for value in BANNED:
        assert problems("argv = [" + repr(value) + "]")
    assert problems("print(frame)")
    assert problems("logger.debug(argv)")


def test_one_merged_feature_list_and_corrected_probe_flags():
    flags = host.FIXED_FLAGS
    assert [f for f in flags if f.startswith("--disable-features=")] == ["--disable-features=" + host.FEATURES]
    assert "--proxy-bypass-list=<-loopback>" in flags
    assert "--webrtc-ip-handling-policy=disable_non_proxied_udp" in flags
    assert "--media-router=0" in flags
    assert all(f in host.FEATURES.split(",") for f in ("MediaRouter", "DialMediaRouteProvider", "CastMediaRouteProvider"))


def test_only_host_constructs_native_process_and_no_production_fixture_import():
    for name in ("browser_host.py", "browser_profile.py"):
        source = (ATTENTION / name).read_text(encoding="utf-8")
        assert "api.tests" not in source and "fake-script" not in source and "browser_fake_main" not in source
    source = (ATTENTION / "browser_host.py").read_text(encoding="utf-8")
    assert "0x20002" in source  # explicit PROC_THREAD_ATTRIBUTE_HANDLE_LIST
    assert "k.AssignProcessToJobObject(self.handle, self.process)" in source
    assert source.index("k.AssignProcessToJobObject(self.handle, self.process)") < source.index("k.ResumeThread(info.thread)")


# S-BrowserCDP (A1/A2/A4/A16/A17): single serialization chokepoint and the no-input property, statically.
CDP_SOURCE = ATTENTION / "browser_cdp.py"
ENDPOINT_STRINGS = ("--remote-debugging-port", "DevToolsActivePort", "ws://", "wss://", "/devtools/browser",
                    "/json/version", "webSocketDebuggerUrl", "--remote-allow-origins")


def chokepoint_problems(source):
    tree = ast.parse(source)
    result = []
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def calls_inside(name):
        node = functions.get(name)
        return [c for c in ast.walk(node) if isinstance(c, ast.Call)] if node else []

    def attr_calls(attr):
        return [c for c in ast.walk(tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and c.func.attr == attr]

    sends = attr_calls("send") + attr_calls("write") + attr_calls("sendall")
    if len(sends) != 1 or sends[0] not in calls_inside("_frame"):
        result.append("pipe write call sites")
    dumps = attr_calls("dumps")
    if len(dumps) != 1 or dumps[0] not in calls_inside("_frame"):
        result.append("serialization call sites")
    frame_callers = [name for name, node in functions.items() if name != "_frame" and any(
        isinstance(c.func, ast.Attribute) and c.func.attr == "_frame" for c in ast.walk(node) if isinstance(c, ast.Call))]
    if frame_callers != ["_call"]:
        result.append("chokepoint callers")
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    if any(s.startswith("Input.") or ".Input." in s for s in strings):
        result.append("input method")
    result += [s for s in ENDPOINT_STRINGS if any(s in value for value in strings)]
    evaluated = [s for s in strings if s in {"location.href"} or s.startswith("window.")]
    if not set(evaluated) <= {"location.href", "window.scrollBy(0,"}:
        result.append("evaluate constructs")
    return result + problems(source)


def test_cdp_single_chokepoint_no_input_no_endpoint_no_logging():
    assert chokepoint_problems(CDP_SOURCE.read_text(encoding="utf-8")) == []


def test_cdp_method_tables_have_no_input_or_forbidden_method():
    from api.data.attention import browser_cdp as cdp
    methods = set().union(*cdp.METHODS.values())
    assert not any(m.split(".")[0] in {"Input", "Fetch", "Storage", "Emulation", "Debugger", "DOM", "IO", "Tracing",
                                       "Log", "Security"} for m in methods)
    assert not methods & {"Target.sendMessageToTarget", "Target.exposeDevToolsProtocol", "Target.setAutoAttach",
                          "Target.setDiscoverTargets", "Target.attachToBrowserTarget", "Runtime.callFunctionOn",
                          "Runtime.compileScript", "Network.getAllCookies", "Network.setCookie"}


def test_cdp_guard_detects_planted_second_send_raw_send_and_input():
    base = "import json\nclass C:\n    def _frame(self, f):\n        self.p.send(json.dumps(f))\n    def _call(self):\n        self._frame(1)\n"
    assert chokepoint_problems(base) == []
    assert chokepoint_problems(base + "    def raw(self, b):\n        self.p.send(b)\n")
    assert chokepoint_problems(base + "    def x(self):\n        return json.dumps(1)\n")
    assert chokepoint_problems(base + "    def y(self):\n        self._frame(2)\n")
    assert chokepoint_problems(base + "M = 'Input.insertText'\n")
    assert chokepoint_problems(base + "U = 'ws://127.0.0.1/devtools/browser/x'\n")
    assert chokepoint_problems(base + "E = 'document.cookie'\nF = 'window.open(1)'\n")
    assert chokepoint_problems(base + "print(1)\n")


# S-Relay (A5/A6b/A7/A9/A19): loopback-only relay, its constructor sites, the admission-run seam.
API_ROOT = ATTENTION.parents[1]


def _production_sources():
    for path in API_ROOT.rglob("*.py"):
        if "tests" not in path.relative_to(API_ROOT).parts:
            yield path, path.read_text(encoding="utf-8")


def test_relay_and_selftest_have_no_logging_fixture_or_tls_bypass():
    for name in ("browser_relay.py", "browser_selftest.py"):
        source = (ATTENTION / name).read_text(encoding="utf-8")
        assert not problems(source)
        for banned in ("api.tests", "fixture", "CERT_NONE", "check_hostname = False", "verify=False",
                       "ignore-certificate", "set-cookie", "New-NetFirewallRule",
                       "Set-NetFirewallRule", "Remove-NetFirewallRule", "netsh"):
            assert banned not in source, (name, banned)


def test_relay_binds_loopback_literal_only():
    from api.data.attention import browser_relay as relay
    assert relay.LISTEN_HOST == "127.0.0.1"
    tree = ast.parse((ATTENTION / "browser_relay.py").read_text(encoding="utf-8"))
    servers = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "start_server"]
    assert len(servers) == 1 and isinstance(servers[0].args[1], ast.Name) and servers[0].args[1].id == "LISTEN_HOST"
    text = ast.unparse(tree)
    assert "0.0.0.0" not in text and "'::'" not in text and ".bind(" not in text


def test_relay_constructed_only_by_browser_selftest_and_no_gateway():
    constructors, admission_runs = set(), set()
    for path, source in _production_sources():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name == "Relay":
                    constructors.add(path.name)
                for kw in node.keywords:
                    if kw.arg == "admission_run" and not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                        admission_runs.add(path.name)
        assert "gateway" not in path.name
    assert constructors == {"browser_selftest.py"}
    assert admission_runs == {"browser_selftest.py"}
    from api.data.attention import web_queries
    assert not [k for k in web_queries.__dict__.get("COLLECTOR_DEFAULTS", {}) if "gateway" in k]
    assert "gateway" not in (ATTENTION / "web_queries.py").read_text(encoding="utf-8").lower()


def test_collection_launch_still_requires_matching_admission(tmp_path):
    import sys as _sys
    from api.data.attention import browser_profile as profile
    source = (ATTENTION / "browser_host.py").read_text(encoding="utf-8")
    assert "return self._launch(label, profile_name, relay_port, headless=headless, admission_run=False)" in source
    assert "if admission_run is not True:\n            read_admission(" in source
    b = host.BrowserHost(Path(_sys.executable), tmp_path / "p", cache_root=tmp_path,
                         policy=profile.ProfilePolicy(True, True), spawn=lambda argv: argv, memory=lambda: 9999)
    import pytest
    with pytest.raises(host.BrowserFailure, match="browser_unadmitted"):
        b.launch("a", "a", 12345)
