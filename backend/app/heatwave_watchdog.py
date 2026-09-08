from __future__ import annotations

import logging
from typing import Any, Sequence
from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger("heatwave_watchdog")

# 9 张需要加载入 HeatWave 内存列存集群的 MOD 核心业务与核算大表
TARGET_MOD_TABLES: list[str] = [
    "business_document_line",
    "accounting_voucher_line",
    "business_document",
    "accounting_voucher",
    "integration_result",
    "rollout_status_snapshot",
    "construction_task",
    "dual_run_result",
    "org_unit",
]


def get_heatwave_status(conn: Connection) -> dict[str, Any]:
    """
    只读探测 HeatWave 内存集群中 MOD 核心表的就绪状态。
    查询 performance_schema.rpd_tables 与 rpd_table_id，开销 ~1ms。
    """
    try:
        stmt = text("""
            SELECT i.TABLE_NAME, t.LOAD_STATUS
            FROM performance_schema.rpd_tables t
            JOIN performance_schema.rpd_table_id i ON t.ID = i.ID
            WHERE i.SCHEMA_NAME = 'mod' AND t.LOAD_STATUS = 'AVAIL_RPDGSTABSTATE'
        """)
        result = conn.execute(stmt)
        loaded: set[str] = set()
        for row in result.fetchall():
            if isinstance(row, (tuple, list)):
                loaded.add(str(row[0]))
            elif hasattr(row, "TABLE_NAME"):
                loaded.add(str(row.TABLE_NAME))
            elif isinstance(row, dict):
                loaded.add(str(row.get("TABLE_NAME", "")))
            else:
                try:
                    loaded.add(str(row[0]))
                except Exception:
                    pass

        missing = [t for t in TARGET_MOD_TABLES if t not in loaded]
        is_healthy = len(missing) == 0

        return {
            "status": "HEALTHY" if is_healthy else "DEGRADED",
            "loaded_count": len(loaded),
            "total_target": len(TARGET_MOD_TABLES),
            "loaded_tables": sorted(list(loaded)),
            "missing_tables": missing,
        }
    except Exception as e:
        logger.warning("HeatWave 状态探测失败或在模拟环境中跳过: %s", e)
        return {
            "status": "UNKNOWN",
            "loaded_count": 0,
            "total_target": len(TARGET_MOD_TABLES),
            "loaded_tables": [],
            "missing_tables": TARGET_MOD_TABLES,
            "notice": "HeatWave performance_schema unreadable or mocked",
        }


def heal_heatwave_tables(conn: Connection, missing_tables: Sequence[str]) -> dict[str, Any]:
    """
    针对未加载或状态脱落的核心表发起 SECONDARY_LOAD 自动补偿自愈。
    """
    if not missing_tables:
        return {"healed": [], "failed": []}

    healed: list[str] = []
    failed: list[dict[str, str]] = []

    for table in missing_tables:
        if table not in TARGET_MOD_TABLES:
            continue
        logger.info("HeatWave 看门狗触发自愈，开始重载表: mod.%s", table)
        try:
            # 1. 确保 SECONDARY_ENGINE = RAPID
            try:
                conn.execute(text(f"ALTER TABLE `mod`.`{table}` SECONDARY_ENGINE = RAPID"))
            except Exception:
                pass
            # 2. 执行 SECONDARY_LOAD
            conn.execute(text(f"ALTER TABLE `mod`.`{table}` SECONDARY_LOAD"))
            healed.append(table)
            logger.info("HeatWave 看门狗自愈成功: mod.%s 已加载", table)
        except Exception as e:
            logger.error("HeatWave 看门狗自愈失败: mod.%s: %s", table, e)
            failed.append({"table": table, "error": str(e)})

    return {"healed": healed, "failed": failed}


def check_and_heal(conn: Connection) -> dict[str, Any]:
    """
    检查并在表缺失时自动执行自愈闭环。
    """
    status_before = get_heatwave_status(conn)
    if status_before.get("status") == "HEALTHY":
        return status_before

    missing = status_before.get("missing_tables", [])
    heal_result = heal_heatwave_tables(conn, missing)

    status_after = get_heatwave_status(conn)
    status_after["heal_actions"] = heal_result
    return status_after
