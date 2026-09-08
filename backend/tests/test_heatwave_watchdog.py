from __future__ import annotations

from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.heatwave_watchdog import (
    TARGET_MOD_TABLES,
    get_heatwave_status,
    heal_heatwave_tables,
    check_and_heal,
)
from app.main import app
from app.db import connection


def test_get_heatwave_status_healthy():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        (table, "AVAIL_RPDGSTABSTATE") for table in TARGET_MOD_TABLES
    ]

    status = get_heatwave_status(mock_conn)
    assert status["status"] == "HEALTHY"
    assert status["loaded_count"] == len(TARGET_MOD_TABLES)
    assert status["total_target"] == len(TARGET_MOD_TABLES)
    assert status["missing_tables"] == []


def test_get_heatwave_status_degraded():
    mock_conn = MagicMock()
    # 假设只有 7 张表就绪，缺 2 张
    available = TARGET_MOD_TABLES[:7]
    mock_conn.execute.return_value.fetchall.return_value = [
        (table, "AVAIL_RPDGSTABSTATE") for table in available
    ]

    status = get_heatwave_status(mock_conn)
    assert status["status"] == "DEGRADED"
    assert status["loaded_count"] == 7
    assert len(status["missing_tables"]) == 2
    assert set(status["missing_tables"]) == set(TARGET_MOD_TABLES[7:])


def test_get_heatwave_status_exception_graceful():
    mock_conn = MagicMock()
    mock_conn.execute.side_effect = RuntimeError("database query error")

    status = get_heatwave_status(mock_conn)
    assert status["status"] == "UNKNOWN"
    assert status["loaded_count"] == 0
    assert "notice" in status


def test_heal_heatwave_tables():
    mock_conn = MagicMock()
    missing = ["business_document", "accounting_voucher"]

    result = heal_heatwave_tables(mock_conn, missing)
    assert result["healed"] == missing
    assert result["failed"] == []

    # 验证执行了 ALTER TABLE 语句
    assert mock_conn.execute.call_count >= 2


def test_heal_heatwave_tables_readonly_permission_denied():
    mock_conn = MagicMock()
    missing = ["business_document"]
    # 模拟只读账号执行 ALTER TABLE 时抛出 MySQL 1142 权限拒绝异常
    mock_conn.execute.side_effect = RuntimeError("1142: ALTER command denied to user 'mod_readonly'@'%'")

    result = heal_heatwave_tables(mock_conn, missing)
    assert result["healed"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["table"] == "business_document"
    assert "只读账号无 ALTER 权限" in result["failed"][0]["error"]


def test_check_and_heal_when_healthy():
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        (table, "AVAIL_RPDGSTABSTATE") for table in TARGET_MOD_TABLES
    ]

    result = check_and_heal(mock_conn)
    assert result["status"] == "HEALTHY"
    # 健康状态下不应发起自愈 ALTER TABLE
    assert "heal_actions" not in result


def test_health_api_includes_heatwave_status():
    client = TestClient(app)

    mock_conn = MagicMock()
    mock_row = MagicMock()
    mock_row.mappings.return_value.one.return_value = {
        "db": "mod",
        "tz": "+08:00",
        "now_cst": "2026-09-08 10:00:00",
    }
    # 第一次 execute 返回时间与数据库名，第二次 execute 供 get_heatwave_status 使用
    mock_rpd_result = MagicMock()
    mock_rpd_result.fetchall.return_value = [
        (table, "AVAIL_RPDGSTABSTATE") for table in TARGET_MOD_TABLES
    ]

    mock_conn.execute.side_effect = [mock_row, mock_rpd_result]

    def mock_connection():
        yield mock_conn

    app.dependency_overrides[connection] = mock_connection
    try:
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "heatwave" in data
        hw = data["heatwave"]
        assert hw["status"] == "HEALTHY"
        assert hw["loaded_count"] == 9
        assert hw["total_target"] == 9
        assert hw["missing_tables"] == []
    finally:
        app.dependency_overrides.pop(connection, None)
