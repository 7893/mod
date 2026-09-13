from __future__ import annotations

from contextlib import suppress

from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.pool import ConnectionPoolEntry

from .config import get_settings


def _on_connect(dbapi_conn: object, connection_record: ConnectionPoolEntry) -> None:
    """Initialize session variables once per physical connection, not per checkout.

    KI-086 #3: This eliminates 2 redundant network round-trips per HTTP request
    by moving SET statements from checkout to physical connection establishment.
    """
    cursor = dbapi_conn.cursor()  # type: ignore[union-attr]
    try:
        # 会话固定 +08:00：业务时间戳按 UTC+8 落库，与展示时区偏移一致。
        cursor.execute("SET time_zone = '+08:00'")
        # 显式激活次级引擎（HeatWave RAPID）智能路由
        cursor.execute("SET use_secondary_engine = ON")
    finally:
        cursor.close()


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        execution_options={"isolation_level": "AUTOCOMMIT"},
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_args={"connect_timeout": 3},
    )
    event.listen(engine, "connect", _on_connect)
    return engine



def connection() -> Iterator[Connection | None]:
    conn: Connection | None = None
    try:
        conn = get_engine().connect()
        # KI-086 #3: Session variables now set via connect event hook, not here.
    except Exception:

        if conn is not None:
            with suppress(Exception):
                conn.close()
        yield None
        return

    try:
        yield conn
    finally:
        with suppress(Exception):
            conn.close()

