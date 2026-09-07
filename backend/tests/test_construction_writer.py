"""Unit tests for safe transactional construction writer (Phase E)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from simulation.construction_models import (
    DualRunCheckEventFootprint,
    DualRunResultRecordFootprint,
    ConstructionTaskFootprint,
)
from simulation.construction_writer import ConstructionWriter, is_construction_writer_enabled


def test_construction_writer_safety_switch_blocked(monkeypatch):
    monkeypatch.delenv("MOD_SIMULATION_ENGINE_ENABLED", raising=False)
    assert not is_construction_writer_enabled()

    writer = ConstructionWriter()
    res = writer.write_construction_events([], execute=True)
    assert not res.success
    assert "BLOCKED" in (res.error or "")


def test_construction_writer_execute_false_blocked(monkeypatch):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    assert is_construction_writer_enabled()

    writer = ConstructionWriter()
    res = writer.write_construction_events([], execute=False)
    assert not res.success
    assert "BLOCKED" in (res.error or "")


def test_construction_writer_atomic_rollback_on_error(monkeypatch, tmp_path):
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate error on execute
    mock_cursor.execute.side_effect = RuntimeError("Simulated DB connection error")

    writer = ConstructionWriter(
        conn=mock_conn,
        audit_log_path=str(tmp_path / "audit.log"),
        backup_dir=str(tmp_path / "backups"),
    )
    # Mock backup to avoid real DB queries
    writer.backup_affected_tables = MagicMock(return_value="mock_backup.json")

    event = DualRunCheckEventFootprint(
        org_id=10,
        batch_id=1,
        event_date=date(2026, 9, 5),
        dual_run=DualRunResultRecordFootprint(
            id=101,
            org_id=10,
            check_type="业务单据金额核对",
            v1_amount=Decimal("1000.00"),
            v2_amount=Decimal("1000.00"),
            diff_amount=Decimal("0.00"),
            result="一致",
            check_date=date(2026, 9, 5),
        ),
        associated_task=ConstructionTaskFootprint(
            id=201,
            org_id=10,
            name="双轨核对任务",
            type="双轨验证",
            owner="张三",
            plan_time=date(2026, 9, 5),
            actual_time=date(2026, 9, 5),
            status="已完成",
            progress=100,
            update_time=date(2026, 9, 5),
        ),
    )

    res = writer.write_construction_events([event], execute=True)
    assert not res.success
    assert "Rolled back" in (res.error or "")
    mock_conn.rollback.assert_called_once()



def test_backup_whitelist_includes_sys_user(tmp_path):
    """KI-035 回归：入池会写 sys_user / daily_stats 等表，备份白名单必须覆盖所有写入表，
    否则备份被拒、入池失败。锁死"写入白名单 ⊆ 备份白名单"。"""
    rows = [{"id": 1, "name": "测试单位", "status": "未启动"}]
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    writer = ConstructionWriter(
        conn=mock_conn,
        audit_log_path=str(tmp_path / "audit.log"),
        backup_dir=str(tmp_path / "backups"),
    )
    # 所有可能被写入的表都必须允许备份，不得抛 Unauthorized
    all_written_tables = [
        "org_unit", "sys_user", "construction_task", "rollout_batch",
        "rollout_status_snapshot", "data_readiness", "training",
        "dual_run_result", "daily_stats",
    ]
    path = writer.backup_affected_tables(all_written_tables)
    assert path  # 全部允许、返回备份路径即通过（未抛异常）


def test_write_construction_events_empty_short_circuit(monkeypatch, tmp_path):
    """KI-038: 空事件列表必须立即短路，零备份、零DB游标、成功返回。"""
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")
    mock_conn = MagicMock()
    writer = ConstructionWriter(
        conn=mock_conn,
        audit_log_path=str(tmp_path / "audit.log"),
        backup_dir=str(tmp_path / "backups"),
    )
    writer.backup_affected_tables = MagicMock()

    res = writer.write_construction_events([], execute=True, create_backup=True)
    assert res.success
    assert res.event_count == 0
    writer.backup_affected_tables.assert_not_called()
    mock_conn.cursor.assert_not_called()


def test_backup_affected_tables_disk_guard(tmp_path):
    """KI-038: 磁盘可用空间不足时 fail-closed 抛出 RuntimeError。"""
    from unittest.mock import patch
    import pytest

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"id": 1}]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    writer = ConstructionWriter(
        conn=mock_conn,
        audit_log_path=str(tmp_path / "audit.log"),
        backup_dir=str(tmp_path / "backups"),
    )

    with patch("shutil.disk_usage") as mock_du:
        # total, used, free (10MB free < 1GB min_free_bytes)
        mock_du.return_value = type("Usage", (), {"total": 100 * 1024**3, "used": 99 * 1024**3, "free": 10 * 1024**2})()
        with pytest.raises(RuntimeError, match="Insufficient disk space for backup"):
            writer.backup_affected_tables(["org_unit"], min_free_bytes=1024**3)


def test_backup_affected_tables_compression_and_rotation(tmp_path):
    """KI-038: 默认 gzip 压缩并轮转保留不超过 max_backups 份文件。"""
    import gzip
    import json

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"id": 1, "name": "unit_1"}]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    backup_dir = tmp_path / "backups"
    writer = ConstructionWriter(
        conn=mock_conn,
        audit_log_path=str(tmp_path / "audit.log"),
        backup_dir=str(backup_dir),
    )

    from datetime import datetime, timedelta
    from unittest.mock import patch

    created_paths = []
    base_time = datetime(2026, 9, 7, 10, 0, 0)
    for i in range(5):
        simulated_now = base_time + timedelta(seconds=i * 10)
        with patch("simulation.construction_writer.datetime") as mock_dt:
            mock_dt.now.return_value = simulated_now
            path = writer.backup_affected_tables(["org_unit"], max_backups=3, compress=True)
            created_paths.append(path)

    # 验证最新文件是 gzip 压缩且能解压
    latest_path = created_paths[-1]
    assert latest_path.endswith(".json.gz")
    with gzip.open(latest_path, "rt", encoding="utf-8") as f:
        data = json.load(f)
        assert "org_unit" in data
        assert data["org_unit"] == [{"id": "1", "name": "unit_1"}]

    # 验证轮转：目录中仅保留 3 份 construction_backup_* 文件
    remaining = list(backup_dir.glob("construction_backup_*"))
    assert len(remaining) == 3


def test_construction_writer_multi_batch_failure_zero_commits_and_single_rollback(monkeypatch, tmp_path):
    """KI-040: 多 batch 写入场景下，前批成功后批故障，最终零 commit 且执行一次 rollback，库中零残留。"""
    monkeypatch.setenv("MOD_SIMULATION_ENGINE_ENABLED", "true")

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    audit_file = tmp_path / "audit.log"
    writer = ConstructionWriter(
        conn=mock_conn,
        audit_log_path=str(audit_file),
        backup_dir=str(tmp_path / "backups"),
    )
    writer.backup_affected_tables = MagicMock(return_value="mock_backup.json")

    event1 = DualRunCheckEventFootprint(
        org_id=10,
        batch_id=1,
        event_date=date(2026, 9, 5),
        dual_run=DualRunResultRecordFootprint(
            id=101,
            org_id=10,
            check_type="业务单据金额核对",
            v1_amount=Decimal("1000.00"),
            v2_amount=Decimal("1000.00"),
            diff_amount=Decimal("0.00"),
            result="一致",
            check_date=date(2026, 9, 5),
        ),
        associated_task=ConstructionTaskFootprint(
            id=201,
            org_id=10,
            name="双轨核对任务1",
            type="双轨验证",
            owner="张三",
            plan_time=date(2026, 9, 5),
            actual_time=date(2026, 9, 5),
            status="已完成",
            progress=100,
            update_time=date(2026, 9, 5),
        ),
    )
    event2 = DualRunCheckEventFootprint(
        org_id=10,
        batch_id=1,
        event_date=date(2026, 9, 5),
        dual_run=DualRunResultRecordFootprint(
            id=102,
            org_id=10,
            check_type="业务单据金额核对",
            v1_amount=Decimal("2000.00"),
            v2_amount=Decimal("2000.00"),
            diff_amount=Decimal("0.00"),
            result="一致",
            check_date=date(2026, 9, 5),
        ),
        associated_task=ConstructionTaskFootprint(
            id=202,
            org_id=10,
            name="双轨核对任务2",
            type="双轨验证",
            owner="李四",
            plan_time=date(2026, 9, 5),
            actual_time=date(2026, 9, 5),
            status="已完成",
            progress=100,
            update_time=date(2026, 9, 5),
        ),
    )

    call_count = 0

    def mock_write_event(cur, ev, rows):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            rows["construction_task"] += 1
            rows["dual_run_result"] += 1
        else:
            raise RuntimeError("Injected batch 2 database connection reset")

    writer._write_single_event = mock_write_event

    # 2 events with batch_size=1: 2 batches. Batch 1 succeeds, Batch 2 fails!
    res = writer.write_construction_events([event1, event2], batch_size=1, execute=True)

    assert not res.success
    assert "Rolled back" in (res.error or "")
    # Single-transaction atomicity guarantees:
    mock_conn.commit.assert_not_called()
    mock_conn.rollback.assert_called_once()
    assert sum(res.rows_written.values()) == 0

    # Audit log entry must record FAILED and 0 rows written
    import json
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    audit_data = json.loads(lines[0])
    assert audit_data["status"] == "FAILED"
    assert sum(audit_data["rows_written"].values()) == 0


def test_backup_retention_days_and_total_bytes_bounds(tmp_path):
    """KI-040: 备份轮转同时受控于保留天数与总容量上限，且绝不删除唯一有效副本。"""
    import os
    import time

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    writer = ConstructionWriter(conn=MagicMock(), backup_dir=str(backup_dir))

    now = time.time()
    # 4 files: 3 are 10 days old, 1 is 1 day old
    file1 = backup_dir / "construction_backup_20260825_100000.json.gz"
    file2 = backup_dir / "construction_backup_20260826_100000.json.gz"
    file3 = backup_dir / "construction_backup_20260827_100000.json.gz"
    file4 = backup_dir / "construction_backup_20260906_100000.json.gz"

    for f, age_days in [(file1, 13), (file2, 12), (file3, 11), (file4, 1)]:
        f.write_bytes(b"x" * 1024)
        mtime = now - (age_days * 86400)
        os.utime(f, (mtime, mtime))

    # Retention limit: 7 days. Files 1, 2, 3 must be purged. File 4 kept.
    writer._rotate_backups(max_backups=5, retention_days=7, max_total_bytes=100 * 1024)
    remaining = [p.name for p in backup_dir.glob("construction_backup_*")]
    assert len(remaining) == 1
    assert remaining[0] == file4.name

    # Now add 2 more files within retention days, each 2000 bytes
    file5 = backup_dir / "construction_backup_20260907_100000.json.gz"
    file6 = backup_dir / "construction_backup_20260907_120000.json.gz"
    file5.write_bytes(b"y" * 2000)
    file6.write_bytes(b"z" * 2000)
    os.utime(file5, (now - 3600, now - 3600))
    os.utime(file6, (now, now))

    # Total size now is 1024 + 2000 + 2000 = 5024 bytes
    # Limit max_total_bytes to 4500 bytes. File 4 (oldest, 1024 bytes) must be pruned to bring total under 4500 (2000+2000=4000).
    writer._rotate_backups(max_backups=5, retention_days=7, max_total_bytes=4500)
    remaining_paths = sorted(backup_dir.glob("construction_backup_*"), key=lambda p: p.stat().st_mtime)
    total_bytes = sum(p.stat().st_size for p in remaining_paths)
    assert total_bytes <= 4500
    assert not file4.exists()
    assert file5.exists()
    assert file6.exists()


def test_backup_rotation_fail_closed(tmp_path, monkeypatch):
    """KI-040: 备份删除失败或超限无法恢复时 fail-closed 抛出 RuntimeError。"""
    import pytest
    from pathlib import Path

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    writer = ConstructionWriter(conn=MagicMock(), backup_dir=str(backup_dir))

    f1 = backup_dir / "construction_backup_20260901_100000.json.gz"
    f2 = backup_dir / "construction_backup_20260902_100000.json.gz"
    f1.write_bytes(b"123")
    f2.write_bytes(b"456")

    # Simulate unlink error
    def mock_unlink(self):
        raise PermissionError("Unlink denied by file lock")

    monkeypatch.setattr(Path, "unlink", mock_unlink)

    with pytest.raises(RuntimeError, match="Failed to delete"):
        writer._rotate_backups(max_backups=1)

