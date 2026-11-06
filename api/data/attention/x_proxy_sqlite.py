"""Lazy configured-route SQLite guard for cookie-bearing DB/journal files.

No unrelated database is changed. A protected persistent rollback journal and
memory-only temporary storage are selected before migrations or writes. A changed
journal identity fails closed for this adapter; it is never silently recreated.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

from api.data.attention import x_proxy as p
from api.data.attention.x_proxy_private import (
    _windows_create, secure_directory, verified_database_open,
)


def secure_database_file(path, policy, repo_root, *, create=False):
    p.require(path.is_absolute() and policy.private_root in path.parents, "proxy_private")
    secure_directory(path.parent, service_sid=policy.service_sid)
    if not path.exists():
        p.require(create, "proxy_private")
        fd = (_windows_create(path, policy.service_sid, directory=False) if os.name == "nt" else
              os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        with os.fdopen(fd, "wb") as stream:
            stream.flush()
            os.fsync(stream.fileno())
    with verified_database_open(path, policy.private_root, repo_root=repo_root, service_sid=policy.service_sid) as stream:
        info = os.fstat(stream.fileno())
        p.require(info.st_ino != 0, "proxy_private")
        header = stream.read(100) if path.suffix == ".db" else b""
        if path.suffix == ".db" and info.st_size:
            p.require(len(header) == 100 and header[:16] == b"SQLite format 3\x00"
                      and header[18:20] == b"\x01\x01", "proxy_private")
        return (info.st_dev, info.st_ino)


class DatabaseGuard:
    def __init__(self, runtime, abort, label_context, *, file_guard=secure_database_file):
        from twscrape import db as module
        p.require(tuple(inspect.signature(module.DB.__init__).parameters) == ("self", "db_path")
                  and tuple(inspect.signature(module.DB.__aenter__).parameters) == ("self",)
                  and tuple(inspect.signature(module.DB.__aexit__).parameters) == ("self", "exc_type", "exc_val", "exc_tb"), "proxy_policy")
        self.module, self.original = module, module.DB
        self.runtime, self.abort, self.context, self.file_guard = runtime, abort, label_context, file_guard
        self.bindings, self.identities, self.broken = {}, {}, set()
        guard = self
        original = self.original

        class PrivateDB(original):
            async def __aenter__(self):
                binding = guard.safe_binding(self.db_path)
                if binding is None:
                    return await super().__aenter__()
                path, policy = binding
                connection = None
                reason = None
                try:
                    guard.before(path, policy)
                    import aiosqlite
                    await module.check_version()
                    connection = await aiosqlite.connect(str(path))
                    connection.row_factory = aiosqlite.Row
                    # Set connection-local locking before the first database
                    # read: hot-journal recovery must retain the verified file,
                    # not recover in SQLite's initial DELETE mode.
                    async with connection.execute("PRAGMA main.locking_mode=EXCLUSIVE") as cursor:
                        row = await cursor.fetchone()
                        p.require(row is not None and str(row[0]).lower() == "exclusive", "proxy_private")
                    async with connection.execute("PRAGMA journal_mode=PERSIST") as cursor:
                        row = await cursor.fetchone()
                        p.require(row is not None and str(row[0]).lower() == "persist", "proxy_private")
                    await connection.execute("PRAGMA temp_store=MEMORY")
                    async with connection.execute("PRAGMA temp_store") as cursor:
                        row = await cursor.fetchone()
                        p.require(row is not None and row[0] == 2, "proxy_private")
                    # Scope transaction verification to this connection, including
                    # commits inside upstream migrations/cookie helpers.
                    for operation in ("commit", "rollback"):
                        original_operation = getattr(connection, operation)
                        async def checked_transaction(operation=original_operation):
                            failure = None
                            try:
                                guard.after(path, policy)
                                result = await operation()
                                guard.after(path, policy)
                                return result
                            except Exception as error:
                                failure = error.reason if isinstance(error, p.ProxyFailure) else "proxy_private"
                            guard.broken.add(path)
                            raise guard.abort(failure)
                        setattr(connection, operation, checked_transaction)
                    guard.after(path, policy)
                    if not self._init_once[self.db_path]:
                        await module.migrate(connection)
                        self._init_once[self.db_path] = True
                    self.conn = connection
                    return connection
                except Exception as error:
                    reason = error.reason if isinstance(error, p.ProxyFailure) else "proxy_private"
                if connection is not None:
                    try:
                        await connection.close()
                    except Exception:
                        pass
                guard.broken.add(path)
                raise guard.abort(reason)

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                binding = guard.safe_binding(self.db_path)
                if binding is None:
                    return await super().__aexit__(exc_type, exc_val, exc_tb)
                path, policy = binding
                reason = None
                try:
                    if self.conn is not None:
                        if exc_type is None:
                            await self.conn.commit()
                        else:
                            await self.conn.rollback()
                except Exception as error:
                    reason = error.reason if isinstance(error, p.ProxyFailure) else "proxy_private"
                finally:
                    if self.conn is not None:
                        try:
                            await self.conn.close()
                        except Exception:
                            reason = "proxy_private"
                        finally:
                            self.conn = None
                try:
                    guard.after(path, policy)
                except p.ProxyFailure as error:
                    reason = error.reason
                if reason is not None:
                    guard.broken.add(path)
                    raise guard.abort(reason)

        self.replacement = PrivateDB
        module.DB = PrivateDB

    def safe_binding(self, raw):
        reason = None
        try:
            return self.binding(raw)
        except p.ProxyFailure as error:
            reason = error.reason
        raise self.abort(reason)

    def binding(self, raw):
        if raw == ":memory:":
            return None
        path = Path(raw)
        snapshot = self.runtime.snapshot
        if path in self.bindings:
            # An already private DB remains guarded after direct/off cutover.
            # A new private revision must revalidate against its current policy.
            policy = snapshot.policy or self.bindings[path]
            self.bindings[path] = policy
            return path, policy
        if snapshot.policy is None:
            return None
        directory = Path(snapshot.config.x_accounts_db_path)
        labels = {directory / f"{label}.db": label for label in snapshot.config.x_accounts}
        if path not in labels:
            return None  # scoped: unrelated twscrape DB users retain their original behavior
        p.require(self.context.get() in (None, labels[path]), "proxy_revision")
        p.require(path.is_absolute() and snapshot.policy.private_root in path.parents, "proxy_private")
        self.bindings[path] = snapshot.policy
        return path, snapshot.policy

    def sidecars(self, path):
        try:
            with os.scandir(path.parent) as entries:
                for entry in entries:
                    p.require(not entry.name.startswith(path.name + "-") or entry.name == path.name + "-journal", "proxy_private")
        except OSError:
            raise p.ProxyFailure("proxy_private") from None

    def before(self, path, policy):
        p.require(path not in self.broken, "proxy_private")
        self.sidecars(path)
        first = path not in self.identities
        db_identity = self.file_guard(path, policy, self.runtime.repo_root, create=first)
        journal = Path(str(path) + "-journal")
        journal_identity = self.file_guard(journal, policy, self.runtime.repo_root, create=first)
        if first:
            self.identities[path] = (db_identity, journal_identity)
        p.require(self.identities[path] == (db_identity, journal_identity), "proxy_private")

    def after(self, path, policy):
        self.sidecars(path)
        expected = self.identities.get(path)
        p.require(expected is not None, "proxy_private")
        actual = (self.file_guard(path, policy, self.runtime.repo_root, create=False),
                  self.file_guard(Path(str(path) + "-journal"), policy, self.runtime.repo_root, create=False))
        p.require(expected == actual, "proxy_private")

    def close(self):
        p.require(self.module.DB is self.replacement, "proxy_policy")
        self.module.DB = self.original
