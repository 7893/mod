from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

# 展示时区的唯一事实源。后端与数据库内部一律使用 UTC，仅面向用户的取值使用本时区。
DEFAULT_DISPLAY_TIMEZONE = "Asia/Hong_Kong"


@dataclass(frozen=True)
class Settings:
    environment: str
    host: str
    port: int
    db_host: str
    db_port: int
    db_name: str
    db_name: str
    db_user: str
    db_password: str
    db_pool_size: int
    db_max_overflow: int
    display_timezone: str

    @property
    def database_url(self) -> str:
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{password}@{self.db_host}:{self.db_port}/"
            f"{self.db_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("MOD_ENV", "development"),
        host=os.getenv("MOD_HOST", "127.0.0.1"),
        port=int(os.getenv("MOD_PORT", "8100")),
        db_host=os.getenv("MOD_DB_HOST", "127.0.0.1"),
        db_port=int(os.getenv("MOD_DB_PORT", "3306")),
        db_name=os.getenv("MOD_DB_NAME", "mod"),
        db_user=os.getenv("MOD_DB_USER", ""),
        db_password=os.getenv("MOD_DB_PASSWORD", ""),
        db_pool_size=int(os.getenv("MOD_DB_POOL_SIZE", "10")),
        db_max_overflow=int(os.getenv("MOD_DB_MAX_OVERFLOW", "20")),
        display_timezone=os.getenv("MOD_DISPLAY_TIMEZONE", DEFAULT_DISPLAY_TIMEZONE),
    )


@lru_cache
def get_display_timezone() -> ZoneInfo:
    """Return the single display timezone used by every user-facing value."""
    return ZoneInfo(get_settings().display_timezone)
