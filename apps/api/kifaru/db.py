"""Database engine/session factory.

PostgreSQL uses three schemas: core, pii, ts. SQLite (tests, quick dev) has no schemas, so the schema
names are translated to the default namespace via `schema_translate_map`.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        s = get_settings()
        kwargs: dict = {"echo": s.db_echo, "future": True}
        if s.is_sqlite:
            kwargs["connect_args"] = {"check_same_thread": False}
            _engine = create_engine(s.database_url, **kwargs).execution_options(
                schema_translate_map={"core": None, "pii": None, "ts": None}
            )

            @event.listens_for(_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        else:
            kwargs["pool_pre_ping"] = True
            kwargs["pool_size"] = 10
            kwargs["pool_recycle"] = 300
            connect_args: dict = {}
            url = s.database_url
            if "supabase.co" in url or "supabase.com" in url or s.db_require_ssl:
                connect_args["sslmode"] = "require"
            if "pooler.supabase.com" in url or s.db_pooler_transaction_mode:
                # Supavisor / PgBouncer transaction mode cannot track server-side prepared statements: psycopg 3 would
                # otherwise start preparing after 5 executions of the same statement and fail with "prepared statement
                # does not exist". Session mode (port 5432 on the pooler) tolerates them but disabling is harmless there too.
                connect_args["prepare_threshold"] = None
                kwargs["pool_size"] = 5
            if "supabase" in url:
                # A remote database costs 300-600 ms per round trip from Kenya. pool_pre_ping would add one such trip to
                # every request; instead recycle connections before the pooler's idle timeout and keep them alive.
                kwargs["pool_pre_ping"] = False
                kwargs["pool_recycle"] = 240
                connect_args.update({"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3})
            if connect_args:
                kwargs["connect_args"] = connect_args
            _engine = create_engine(url, **kwargs)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


def reset_engine() -> None:
    """Used by tests to point at a fresh database."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def ensure_schemas(engine: Engine) -> None:
    """Create the core/pii/ts schemas on PostgreSQL (no-op on SQLite, where they are translated away)."""
    if engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        for schema in ("core", "pii", "ts"):
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
