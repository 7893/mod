"""
模拟器配置模块

职责：
- 集中读取并验证模拟器相关环境变量。
- 提供严格的布尔白名单解析，防止任意非空字符串误启用模拟器。
- 在显式启用但缺少写库 URL 时 fail-closed，并给出不含凭据的明确错误。
- 本模块不包含任何硬编码凭据、主机地址或密码。

环境变量：
  MOD_SIMULATOR_ENABLED  - 仅接受 "true" / "1" / "yes" 为启用（大小写不敏感）
                            其他所有值（包括空字符串）均视为禁用
  MOD_DB_WRITE_URL       - SQLAlchemy 数据库 URL（不得含明文凭据提示）
                            仅在 MOD_SIMULATOR_ENABLED=true 时读取
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# 明确白名单：只有这些值被认为是 "true"
_TRUE_VALUES = frozenset({"true", "1", "yes"})


class SimulatorConfigError(ValueError):
    """模拟器配置错误（不含凭据信息）"""


def parse_bool_env(env_name: str) -> bool:
    """
    严格解析布尔型环境变量。

    仅当变量值（去空格后，大小写不敏感）属于 {"true", "1", "yes"} 时返回 True。
    变量未设置或为其他任何值时返回 False。
    """
    raw = os.environ.get(env_name, "")
    return raw.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class SimulatorConfig:
    """已验证的模拟器配置（不可变）"""
    enabled: bool
    db_write_url: str  # 仅 enabled=True 时非空


def load_simulator_config() -> SimulatorConfig:
    """
    加载并验证模拟器配置。

    规则：
    1. MOD_SIMULATOR_ENABLED 未设置或不在白名单 → 返回 enabled=False，不读取写库 URL。
    2. MOD_SIMULATOR_ENABLED 在白名单，但 MOD_DB_WRITE_URL 未设置或为空 → 抛出
       SimulatorConfigError（错误信息不含凭据，仅说明缺少哪个变量）。
    3. 两项均满足 → 返回 enabled=True 及写库 URL。

    不抛出时保证：
    - 返回 enabled=False 时 db_write_url 为空字符串。
    - 返回 enabled=True 时 db_write_url 为非空字符串，但本模块不校验格式。
    """
    enabled = parse_bool_env("MOD_SIMULATOR_ENABLED")

    if not enabled:
        return SimulatorConfig(enabled=False, db_write_url="")

    # 显式启用：必须提供写库 URL
    db_write_url = os.environ.get("MOD_DB_WRITE_URL", "").strip()
    if not db_write_url:
        raise SimulatorConfigError(
            "模拟器已通过 MOD_SIMULATOR_ENABLED 显式启用，"
            "但未提供 MOD_DB_WRITE_URL。"
            "请设置 MOD_DB_WRITE_URL 环境变量后再启动。"
            "（提示：不要将连接字符串写入代码，应通过环境变量或密钥管理服务注入。）"
        )

    return SimulatorConfig(enabled=True, db_write_url=db_write_url)
