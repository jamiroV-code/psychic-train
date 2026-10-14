"""AC-15: tooling tests that can reach the network must be marked or use the fixture server."""
from __future__ import annotations

import ast

from api.tests.tooling_guards._common import TOOL_DIR
from api.tests.tooling_guards.test_import_boundary import imported_modules, is_network

MARKERS = {"browser", "antibot", "integration"}


def _is_risky(mods: set[str]) -> bool:
    return any(is_network(m) or m.startswith("data_integration.fetch_tier") for m in mods)


def _marker_names(node: ast.AST) -> set[str]:
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Attribute) and sub.value.attr == "mark":
            out.add(sub.attr)
    return out


def _pytestmark_names(body: list[ast.stmt]) -> set[str]:
    out: set[str] = set()
    for node in body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "pytestmark" for t in node.targets):
            out |= _marker_names(node)
    return out


def _walk_tests(body: list[ast.stmt], inherited: set[str]):
    """Yield (name, markers, node) for test functions, incl. async ones and methods of (nested) classes."""
    scope = inherited | _pytestmark_names(body)
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            marks = set(scope)
            for d in node.decorator_list:
                marks |= _marker_names(d)
            yield node.name, marks, node
        elif isinstance(node, ast.ClassDef):
            cls_marks = set(scope)
            for d in node.decorator_list:
                cls_marks |= _marker_names(d)
            yield from _walk_tests(node.body, cls_marks)


def unmarked_tests(source: str) -> list[str]:
    tree = ast.parse(source)
    if not _is_risky(imported_modules(source)):
        return []
    bad = []
    for name, marks, node in _walk_tests(tree.body, set()):
        args = node.args.args + node.args.kwonlyargs
        uses_fixture = any(a.arg == "fixture_server" for a in args)
        if not (marks & MARKERS or uses_fixture):
            bad.append(name)
    return bad


def test_audit_flags_unmarked_network_test():
    src = "import socket\n\ndef test_a():\n    pass\n"
    assert unmarked_tests(src) == ["test_a"]


def test_audit_accepts_marked_or_fixture_tests():
    src = (
        "import pytest\nimport httpx\n\n"
        "@pytest.mark.browser\ndef test_a():\n    pass\n\n"
        "def test_b(fixture_server):\n    pass\n"
    )
    assert unmarked_tests(src) == []
    assert unmarked_tests("import pytest\npytestmark = pytest.mark.antibot\nimport scrapling\n\ndef test_c():\n    pass\n") == []


def test_audit_ignores_pure_tests():
    assert unmarked_tests("import json\n\ndef test_a():\n    pass\n") == []


def test_tooling_tests_are_marked():
    tests = TOOL_DIR / "tests"
    assert tests.is_dir()
    offenders = {}
    for path in sorted(tests.glob("test_*.py")):
        bad = unmarked_tests(path.read_text(encoding="utf-8"))
        if bad:
            offenders[path.name] = bad
    assert offenders == {}


def test_audit_flags_unmarked_class_method_and_async_tests():
    src = (
        "import socket\n\n"
        "class TestA:\n    def test_m(self):\n        pass\n\n"
        "    class TestInner:\n        def test_n(self):\n            pass\n\n"
        "async def test_async():\n    pass\n"
    )
    assert unmarked_tests(src) == ["test_m", "test_n", "test_async"]


def test_audit_accepts_marked_class_method_and_async_tests():
    src = (
        "import pytest\nimport httpx\n\n"
        "@pytest.mark.integration\nclass TestA:\n    def test_m(self):\n        pass\n\n"
        "class TestB:\n    @pytest.mark.antibot\n    async def test_n(self):\n        pass\n\n"
        "    def test_o(self, fixture_server):\n        pass\n\n"
        "@pytest.mark.browser\nasync def test_async():\n    pass\n"
    )
    assert unmarked_tests(src) == []
