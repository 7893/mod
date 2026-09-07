"""
backend/tests/test_heatwave_manager.py
======================================
Tests for HeatWave cluster management, engine configuration, and RAPID execution verification (KI-045).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops import heatwave_manager  # noqa: E402


def test_heatwave_target_tables_list():
    """KI-045: 验证目标加载表包含全部 9 张核心报表大表。"""
    required_tables = [
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
    for table in required_tables:
        assert table in heatwave_manager.TARGET_MOD_TABLES


def test_heatwave_verify_success():
    """KI-045: 当所有 EXPLAIN 结果均包含 secondary engine RAPID 时，verify 成功返回 0。"""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # 模拟所有测试查询的 EXPLAIN 均包含 secondary engine RAPID
    mock_cur.fetchall.return_value = [
        {"EXPLAIN": "-> Table scan on table in secondary engine RAPID (cost=0..0)"}
    ]

    with patch.object(heatwave_manager, "get_db_connection", return_value=mock_conn):
        ret = heatwave_manager.cmd_verify()
        assert ret == 0


def test_heatwave_verify_failure_when_not_in_rapid():
    """KI-045: 若任何查询未走 secondary engine RAPID，verify 返回 1 告警。"""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # 模拟退化为普通 InnoDB 扫描
    mock_cur.fetchall.return_value = [
        {"EXPLAIN": "-> Table scan on table in storage engine InnoDB"}
    ]

    with patch.object(heatwave_manager, "get_db_connection", return_value=mock_conn):
        ret = heatwave_manager.cmd_verify()
        assert ret == 1


def test_engine_configured_with_autocommit():
    """KI-045: 验证 backend/app/db.py 中的 get_engine 配置了 AUTOCOMMIT 隔离级别。"""
    from app.db import get_engine

    engine = get_engine()
    assert engine.get_execution_options().get("isolation_level") == "AUTOCOMMIT"

