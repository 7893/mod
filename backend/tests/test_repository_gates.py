from __future__ import annotations

import importlib.util
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str):
    path = REPOSITORY_ROOT / "scripts" / "project" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


commit_messages = load_script("validate_commit_message.py")
credential_scanner = load_script("scan_secrets.py")


def test_commit_subject_policy():
    assert commit_messages.validate_subject("fix: derive regional document additions") == []
    assert commit_messages.validate_subject("refactor(frontend): migrate construction screen") == []

    assert commit_messages.validate_subject("Fix regional snapshot consistency")
    assert commit_messages.validate_subject("fix: 修复省级汇总")
    assert commit_messages.validate_subject("fix: this subject contains far too many words now")


def test_secret_scanner_rules():
    assert credential_scanner._scan_line("MOD_DB_PASSWORD=real-secret-value")  # secret-scan: allow
    assert credential_scanner._scan_line("url = 'mysql://user:real-secret@db.example'")  # secret-scan: allow
    assert credential_scanner._scan_line("-----BEGIN PRIVATE KEY-----")  # secret-scan: allow

    assert credential_scanner._scan_line("MOD_DB_PASSWORD=<password>") == []  # secret-scan: allow
    assert credential_scanner._scan_line("token = example-token") == []  # secret-scan: allow
    assert credential_scanner._scan_line("token = real-secret-value  # secret-scan: allow") == []  # secret-scan: allow


def test_commit_message_file_handling(tmp_path: Path):
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text("# Title comment\nfeat: add commit message gate\n\nDetailed body\n# More comments")
    assert commit_messages.main([str(msg_file)]) == 0

    empty_file = tmp_path / "EMPTY_MSG"
    empty_file.write_text("# Only comments\n\n")
    assert commit_messages.main([str(empty_file)]) == 1
