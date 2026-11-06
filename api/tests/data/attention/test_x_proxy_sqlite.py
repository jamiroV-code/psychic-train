"""Locked-xreader real SQLite lifecycle with injected synthetic ACL inspection."""
import asyncio
import contextvars
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("twscrape", reason="optional xreader; required B2 acceptance uses import preflight")

from api.data.attention import x_proxy as p
from api.data.attention.x_proxy_sqlite import DatabaseGuard


def make_guard(tmp_path):
    path = tmp_path / "private" / "alpha.db"
    path.parent.mkdir()
    policy = SimpleNamespace(private_root=path.parent)
    config = SimpleNamespace(x_accounts_db_path=str(path.parent), x_accounts=("alpha",))
    runtime = SimpleNamespace(snapshot=SimpleNamespace(policy=policy, config=config), repo_root=tmp_path / "repo")
    inspections = []
    def inspect(item, policy, repo, *, create=False):
        assert item.parent == policy.private_root and repo == runtime.repo_root
        if not item.exists():
            p.require(create, "proxy_private")
            with item.open("xb"):
                pass
        info = item.stat()
        inspections.append((item.name, create))
        return info.st_dev, info.st_ino
    guard = DatabaseGuard(runtime, p.ProxyFailure, contextvars.ContextVar("label", default="alpha"), file_guard=inspect)
    return path, guard, inspections


def test_real_migrate_commit_reopen_rollback_keeps_journal_identity(tmp_path):
    path, guard, inspections = make_guard(tmp_path)
    async def run():
        async with guard.module.DB(str(path)) as connection:
            await connection.execute("CREATE TABLE b2_fixture (value TEXT NOT NULL)")
            await connection.execute("INSERT INTO b2_fixture VALUES ('original')")
            await connection.commit()
        identity = guard.identities[path]
        with pytest.raises(RuntimeError, match="rollback fixture"):
            async with guard.module.DB(str(path)) as connection:
                await connection.execute("UPDATE b2_fixture SET value='uncommitted'")
                raise RuntimeError("rollback fixture")
        async with guard.module.DB(str(path)) as connection:
            async with connection.execute("SELECT value FROM b2_fixture") as cursor:
                assert (await cursor.fetchone())[0] == "original"
            async with connection.execute("PRAGMA journal_mode") as cursor:
                assert (await cursor.fetchone())[0] == "persist"
            async with connection.execute("PRAGMA temp_store") as cursor:
                assert (await cursor.fetchone())[0] == 2
        assert guard.identities[path] == identity
    try:
        asyncio.run(run())
        assert {item.name for item in path.parent.iterdir()} == {path.name, path.name + "-journal"}
        assert inspections.count((path.name + "-journal", False)) >= 3
    finally:
        guard.close()


@pytest.mark.parametrize("sidecar", ["-wal", "-shm", "-unknown"])
def test_unsafe_sidecar_refused_before_sqlite_open(tmp_path, sidecar):
    path, guard, inspections = make_guard(tmp_path)
    Path(str(path) + sidecar).write_bytes(b"sensitive synthetic remnant")
    async def run():
        with pytest.raises(p.ProxyFailure, match="proxy_private"):
            async with guard.module.DB(str(path)):
                pytest.fail("unsafe sidecar reached open")
    try:
        asyncio.run(run())
        assert inspections == []
        assert not path.exists()
    finally:
        guard.close()


def test_missing_persistent_journal_never_silently_recreated(tmp_path):
    path, guard, _ = make_guard(tmp_path)
    async def run():
        async with guard.module.DB(str(path)):
            pass
        Path(str(path) + "-journal").unlink()
        with pytest.raises(p.ProxyFailure, match="proxy_private"):
            async with guard.module.DB(str(path)):
                pytest.fail("removed journal reopened")
        assert not Path(str(path) + "-journal").exists()
    try:
        asyncio.run(run())
    finally:
        guard.close()


def test_native_protected_sqlite_live_writer_inspection_and_immutable_input_sharing(tmp_path, monkeypatch):
    """Native root/files/handle proof; synthetic ancestors are NOT host approval."""
    import os
    from api.data.attention import x_proxy_private as private
    from api.data.attention.x_proxy_sqlite import secure_database_file
    root = tmp_path / "native-private"
    sid = private.actual_service_sid() if os.name == "nt" else "S-1-5-21-1-2-3-1001"
    if os.name == "nt":
        private._windows_create(root, sid, directory=True)
    else:
        root.mkdir(mode=0o700)
    original_verify = private.verify_private
    if os.name == "nt":
        native_inspector = private.inspect_windows_acl
        def fixture_inspector(item):
            if item == root or root in item.parents:
                return native_inspector(item)
            return private.Acl(private.SYSTEM, False, (
                private.Ace(sid, private.READ_EXECUTE), private.Ace(private.SYSTEM, private.MODIFY)))
        def verify(path, root, **kwargs):
            return original_verify(path, root, inspector=fixture_inspector, **kwargs)
    else:
        def verify(path, root, **kwargs):
            def fixture_stat(item):
                info = item.lstat()
                if item != root and root not in item.parents:
                    return SimpleNamespace(st_mode=info.st_mode & ~0o022, st_uid=info.st_uid)
                return info
            return original_verify(path, root, stat_inspector=fixture_stat, **kwargs)
    monkeypatch.setattr(private, "verify_private", verify)
    policy = SimpleNamespace(private_root=root, service_sid=sid)
    config = SimpleNamespace(x_accounts_db_path=str(root), x_accounts=("alpha",))
    runtime = SimpleNamespace(snapshot=SimpleNamespace(policy=policy, config=config), repo_root=tmp_path / "repo")
    guard = DatabaseGuard(runtime, p.ProxyFailure, contextvars.ContextVar("native_label", default="alpha"))
    path = root / "alpha.db"
    async def run():
        async with guard.module.DB(str(path)) as connection:
            await connection.execute("CREATE TABLE native_fixture(value INTEGER)")
            await connection.execute("INSERT INTO native_fixture VALUES (1)")
            await connection.commit()
            # This is the real native sharing/ACL/file identity route, not file_guard injection.
            assert secure_database_file(path, policy, runtime.repo_root) == guard.identities[path][0]
            if os.name == "nt":
                with pytest.raises(p.ProxyFailure, match="proxy_private"):
                    with private.verified_open(path, root, repo_root=runtime.repo_root, service_sid=sid):
                        pytest.fail("immutable input unexpectedly shared SQLite writer")
        async with guard.module.DB(str(path)) as connection:
            async with connection.execute("SELECT value FROM native_fixture") as cursor:
                assert (await cursor.fetchone())[0] == 1
    try:
        asyncio.run(run())
        from datetime import UTC, datetime
        from api.data.attention import twscrape_reader as tr, web_queries as wq, x_proxy_snapshot
        configuration = wq.validate_config({**wq.DEFAULTS, "x_accounts": ["alpha"],
            "x_accounts_db_path": str(root), "x_proxy_required": True,
            "x_proxy_list_path": str(root / "list"), "x_proxy_assignments_path": str(root / "assignments"),
            "x_proxy_policy_path": str(root / "policy")})
        verified = SimpleNamespace(config=configuration, policy=policy, assignments={})
        monkeypatch.setattr(x_proxy_snapshot, "load_snapshot", lambda *args, **kwargs: verified)
        environment = {**tr.REQUIRED_ENV, "TWS_HTTP_BACKEND": "httpx"}
        tr.refresh_cookies("alpha", "auth_token=SYNTHETIC_COOKIE; ct0=SYNTHETIC_CSRF",
            config=configuration, config_path=root / "queries", env=environment,
            now=datetime.now(UTC), repo_root=runtime.repo_root)
        async def check_cookie():
            async with guard.module.DB(str(path)) as connection:
                async with connection.execute("SELECT cookies FROM accounts WHERE username='alpha'") as cursor:
                    assert "SYNTHETIC_COOKIE" in (await cursor.fetchone())[0]
        asyncio.run(check_cookie())
        guard.after(path, policy)
        if os.name == "nt":
            private.validate_acl(private.inspect_windows_acl(path), sid, directory=False)
            private.validate_acl(private.inspect_windows_acl(Path(str(path) + "-journal")), sid, directory=False)
    finally:
        guard.close()


def test_real_crash_recovery_preserves_rollback_value_and_guarded_journal(tmp_path):
    import subprocess
    import sys
    path, guard, _ = make_guard(tmp_path)
    async def initialize():
        async with guard.module.DB(str(path)) as connection:
            await connection.execute("CREATE TABLE crash_fixture(value TEXT)")
            await connection.executemany("INSERT INTO crash_fixture VALUES (?)", [("original" * 1000,)] * 10)
            await connection.commit()
    script = (
        "import sqlite3,sys,os; "
        "c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA journal_mode=PERSIST'); "
        "c.execute('PRAGMA cache_size=1'); c.execute('BEGIN IMMEDIATE'); "
        "c.execute(\"UPDATE crash_fixture SET value='uncommitted' || value\"); os._exit(17)"
    )
    async def reopen():
        async with guard.module.DB(str(path)) as connection:
            async with connection.execute("SELECT count(*) FROM crash_fixture WHERE value LIKE 'original%'") as cursor:
                assert (await cursor.fetchone())[0] == 10
    try:
        asyncio.run(initialize())
        identity = guard.identities[path]
        result = subprocess.run([sys.executable, "-c", script, str(path)], capture_output=True, timeout=10)
        assert result.returncode == 17
        asyncio.run(reopen())
        assert guard.identities[path] == identity
        guard.after(path, guard.runtime.snapshot.policy)
    finally:
        guard.close()


def test_exclusive_guarded_connections_serialize_and_release_after_close(tmp_path):
    path, guard, _ = make_guard(tmp_path)
    async def run():
        entered = asyncio.Event()
        async def second():
            async with guard.module.DB(str(path)) as connection:
                entered.set()
                async with connection.execute("SELECT count(*) FROM accounts") as cursor:
                    assert (await cursor.fetchone())[0] == 0
        async with guard.module.DB(str(path)) as connection:
            await connection.execute("INSERT INTO accounts(username,password,email,email_password,user_agent,active,cookies) "
                                     "VALUES ('rollback','_','_','_','fixture',1,'{}')")
            await connection.rollback()
            task = asyncio.create_task(second())
            await asyncio.sleep(0.1)
            assert not entered.is_set() and not task.done()
        async with asyncio.timeout(5):
            await task
        assert entered.is_set()
    try:
        asyncio.run(run())
    finally:
        guard.close()
