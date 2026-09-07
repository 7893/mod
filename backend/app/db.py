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
        execution_options={"isolation_level": "AUTOCOMMIT"},
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_args={"connect_timeout": 3},
    )



def connection() -> Iterator[Connection | None]:
    conn: Connection | None = None
    try:
        conn = get_engine().connect()
        # 会话固定 +08:00：业务时间戳按 UTC+8 落库，与展示时区偏移一致。
        # 这是相对"后端一律 UTC"契约的已知偏差，改动会移动 NOW()/CURDATE() 的日界，
        # 属于数据语义变更，需单独授权与只读核验后处理。
        conn.execute(text("SET time_zone = '+08:00'"))
        # 显式激活次级引擎（HeatWave RAPID）智能路由
        conn.execute(text("SET use_secondary_engine = ON"))
    except Exception:

        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        yield None
        return

    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass

