"""
Tests for MOD Automated Disaster Recovery Backup Pipeline (KI-042).
"""

from __future__ import annotations

import datetime
import gzip
import os
import sys
from pathlib import Path

import pytest

# Import functions from scripts.ops
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ops"))

from backup_pipeline import (  # noqa: E402
    calculate_sha256,
    check_disk_space,
    encrypt_backup,
    load_environment_config,
    prune_local_backups,
)
from verify_and_restore import (  # noqa: E402
    decrypt_archive,
    scan_sql_contents,
    verify_gzip_integrity,
)


def test_check_disk_space_pass(tmp_path):
    """Sufficient disk capacity passes check."""
    check_disk_space(tmp_path, min_free_mb=1)


def test_check_disk_space_insufficient(tmp_path):
    """Insufficient disk capacity raises RuntimeError fail-closed."""
    with pytest.raises(RuntimeError, match="Insufficient disk space"):
        check_disk_space(tmp_path, min_free_mb=100_000_000)


def test_calculate_sha256(tmp_path):
    """SHA-256 calculation matches known digest."""
    test_file = tmp_path / "sample.txt"
    test_file.write_bytes(b"mod disaster recovery test")
    # sha256 of "mod disaster recovery test"
    import hashlib
    expected = hashlib.sha256(b"mod disaster recovery test").hexdigest()
    assert calculate_sha256(test_file) == expected


def test_encryption_decryption_roundtrip(tmp_path):
    """Ensures encrypt_backup and decrypt_archive achieve 100% data fidelity."""
    original_data = b"-- MySQL dump\nCREATE TABLE org_unit (id INT);\nINSERT INTO org_unit VALUES (1);\n" * 100
    
    # 1. Create gzipped input
    gz_file = tmp_path / "backup.sql.gz"
    with gzip.open(gz_file, "wb") as f:
        f.write(original_data)

    enc_file = tmp_path / "backup.sql.gz.enc"
    dec_file = tmp_path / "decrypted.sql.gz"
    enc_key = "secure-random-test-key-321"

    # 2. Encrypt
    enc_size = encrypt_backup(gz_file, enc_file, enc_key)
    assert enc_file.exists()
    assert enc_size > 0
    assert not gz_file.exists()  # Original plaintext must be purged immediately

    # 3. Decrypt
    decrypt_archive(enc_file, dec_file, enc_key)
    assert dec_file.exists()

    # 4. Verify gzip integrity
    verify_gzip_integrity(dec_file)

    # 5. Verify uncompressed data matches original byte-for-byte
    with gzip.open(dec_file, "rb") as f:
        restored = f.read()
    assert restored == original_data


def test_scan_sql_contents(tmp_path):
    """Validates SQL content parser extracts tables and databases."""
    sql_text = """
    -- Current Database: `mod`
    CREATE TABLE `org_unit` (id INT);
    CREATE TABLE `business_document` (id INT);
    CREATE TABLE `sys_user` (id INT);
    CREATE TABLE `accounting_voucher` (id INT);
    CREATE TABLE `accounting_voucher_line` (id INT);
    CREATE TABLE `business_document_line` (id INT);
    CREATE TABLE `integration_result` (id INT);
    -- Current Database: `ML_SCHEMA_admin`
    CREATE TABLE `MODEL_CATALOG` (id INT);
    """
    gz_file = tmp_path / "test.sql.gz"
    with gzip.open(gz_file, "wt", encoding="utf-8") as f:
        f.write(sql_text)

    inspection = scan_sql_contents(gz_file)
    assert "mod" in inspection["databases"]
    assert "ML_SCHEMA_admin" in inspection["databases"]
    assert "org_unit" in inspection["tables"]
    assert "MODEL_CATALOG" in inspection["tables"]
    assert inspection["missing_core_tables"] == []
    assert inspection["health"] == "healthy"


def test_prune_local_backups(tmp_path):
    """Expired backups are pruned while recent backups are retained."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Recent backup (1 day old)
    recent_enc = tmp_path / "mod_backup_20260907_120000.sql.gz.enc"
    recent_sha = tmp_path / "mod_backup_20260907_120000.sha256"
    recent_enc.write_bytes(b"recent")
    recent_sha.write_bytes(b"sha")

    # Old backup (10 days old)
    old_enc = tmp_path / "mod_backup_20260825_120000.sql.gz.enc"
    old_sha = tmp_path / "mod_backup_20260825_120000.sha256"
    old_enc.write_bytes(b"old")
    old_sha.write_bytes(b"sha")

    old_time = (now - datetime.timedelta(days=10)).timestamp()
    os.utime(old_enc, (old_time, old_time))
    os.utime(old_sha, (old_time, old_time))

    pruned = prune_local_backups(tmp_path, retention_days=7)
    assert old_enc.name in pruned
    assert not old_enc.exists()
    assert not old_sha.exists()
    assert recent_enc.exists()
    assert recent_sha.exists()


def test_load_environment_config(tmp_path, monkeypatch):
    """Config loading priority respects CLI/files/defaults."""
    monkeypatch.delenv("MOD_DB_HOST", raising=False)
    monkeypatch.delenv("MOD_BACKUP_ENCRYPTION_KEY", raising=False)

    env_file = tmp_path / "custom.env"
    env_file.write_text("MOD_DB_HOST=10.0.0.99\nMOD_BACKUP_ENCRYPTION_KEY=testkey123\n", encoding="utf-8")

    cfg = load_environment_config(str(env_file))
    assert cfg.get("MOD_DB_HOST") == "10.0.0.99"
    assert cfg.get("MOD_BACKUP_ENCRYPTION_KEY") == "testkey123"  # secret-scan: allow


def test_load_environment_config_r2(monkeypatch):
    """Ensure R2 and CF prefixed environment variables are retained."""
    monkeypatch.setenv("MOD_BACKUP_STORAGE", "r2")
    monkeypatch.setenv("MOD_BACKUP_S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("MOD_BACKUP_S3_PROFILE", "r2")

    cfg = load_environment_config()
    assert cfg.get("MOD_BACKUP_STORAGE") == "r2"
    assert cfg.get("MOD_BACKUP_S3_ENDPOINT") == "https://example.r2.cloudflarestorage.com"
    assert cfg.get("MOD_BACKUP_S3_PROFILE") == "r2"


def test_get_aws_cli_bin():
    """get_aws_cli_bin should return a resolvable binary path or command."""
    from backup_pipeline import get_aws_cli_bin

    bin_path = get_aws_cli_bin()
    assert bin_path is not None
    assert "aws" in bin_path


def test_upload_to_s3_command_args(tmp_path, monkeypatch):
    """upload_to_s3 should include --endpoint-url and --profile when provided."""
    from backup_pipeline import upload_to_s3
    import subprocess

    dummy_file = tmp_path / "test.enc"
    dummy_file.write_bytes(b"enc data")

    executed_cmds = []

    def mock_run(cmd, *args, **kwargs):
        executed_cmds.append(cmd)
        class Res:
            returncode = 0
            stdout = "2026-09-08 00:00:00 test.enc"
            stderr = ""
        return Res()

    monkeypatch.setattr(subprocess, "run", mock_run)

    dest = upload_to_s3(
        file_path=dummy_file,
        s3_bucket="mod-backup",
        s3_prefix="backups",
        s3_region="auto",
        endpoint_url="https://r2.example.com",
        profile="r2",
    )

    assert dest == "s3://mod-backup/backups/test.enc"
    assert len(executed_cmds) == 2  # cp and ls
    cp_cmd = executed_cmds[0]
    assert "--endpoint-url" in cp_cmd
    assert "https://r2.example.com" in cp_cmd
    assert "--profile" in cp_cmd
    assert "r2" in cp_cmd
    assert "--region" in cp_cmd
    assert "auto" in cp_cmd


def test_fetch_from_s3_command_args(tmp_path, monkeypatch):
    """fetch_from_s3 should include --endpoint-url and --profile when provided."""
    from verify_and_restore import fetch_from_s3
    import subprocess

    executed_cmds = []

    def mock_run(cmd, *args, **kwargs):
        executed_cmds.append(cmd)
        target = Path(cmd[4])
        target.write_bytes(b"downloaded content")
        class Res:
            returncode = 0
            stdout = ""
            stderr = ""
        return Res()

    monkeypatch.setattr(subprocess, "run", mock_run)

    out = fetch_from_s3(
        s3_uri="s3://mod-backup/backups/test.enc",
        target_dir=tmp_path,
        s3_region="auto",
        endpoint_url="https://r2.example.com",
        profile="r2",
    )

    assert out.name == "test.enc"
    assert len(executed_cmds) == 1
    cmd = executed_cmds[0]
    assert "--endpoint-url" in cmd
    assert "https://r2.example.com" in cmd
    assert "--profile" in cmd
    assert "r2" in cmd
    assert "--region" in cmd
    assert "auto" in cmd
