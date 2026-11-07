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
