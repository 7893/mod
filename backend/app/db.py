from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from .config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


@lru_cache
def get_v2_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url_v2,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_args={"connect_timeout": 3},
    )


def connection() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        conn.execute(text("SET time_zone = '+00:00'"))
        conn.commit()
        yield conn


def v2_connection() -> Iterator[Connection | None]:
    try:
        with get_v2_engine().connect() as conn:
            # V2 会话固定 +08:00：该库的业务时间戳按 UTC+8 落库，与展示时区偏移一致。
            # 这是相对"后端一律 UTC"契约的已知偏差，改动会移动 NOW()/CURDATE() 的日界，
            # 属于数据语义变更，需单独授权与只读核验后处理。
            conn.execute(text("SET time_zone = '+08:00'"))
            conn.commit()
            yield conn
    except Exception:
        yield None
