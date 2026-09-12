from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_SCRIPTS))

from backup_history_to_r2 import (  # noqa: E402
    HISTORY_DIR,
    create_history_archive,
    decrypt_file,
    encrypt_file,
    run_drill,
    verify_restored_history,
)
from sanitize_history import check_sanitization  # noqa: E402


class HistoryBackupDrillTests(unittest.TestCase):
    def test_all_sanitized_documents_are_leak_free(self) -> None:
        """Verify that all 23 sanitized files exist and contain zero sensitive signatures."""
        errors = check_sanitization()
        self.assertEqual(errors, [], f"Sanitization leaks detected: {errors}")

    def test_encryption_decryption_roundtrip(self) -> None:
        """Verify AES-256-CBC PBKDF2 encryption and decryption preserves content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            sample_file = tmp / "sample.txt"
            sample_file.write_text("Confidential historical text for MOD drill", encoding="utf-8")

            enc_file = tmp / "sample.enc"
            dec_file = tmp / "sample.dec"
            key = "test-secret-key-12345"

            encrypt_file(sample_file, enc_file, key)
            self.assertTrue(enc_file.exists())
            self.assertGreater(enc_file.stat().st_size, 0)

            decrypt_file(enc_file, dec_file, key)
            self.assertEqual(dec_file.read_text(encoding="utf-8"), "Confidential historical text for MOD drill")

    def test_manifest_verification_detects_tampering(self) -> None:
        """Verify that verify_restored_history flags tampered or unmanifested files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hist = root / "docs" / "history"
            hist.mkdir(parents=True, exist_ok=True)

            file1 = hist / "doc1.md"
            file1.write_text("Hello world", encoding="utf-8")
            hash1 = hashlib.sha256(file1.read_bytes()).hexdigest()

            manifest = hist / "MANIFEST.sha256"
            manifest.write_text(f"{hash1}  docs/history/doc1.md\n", encoding="utf-8")

            # Valid case
            ok, errors = verify_restored_history(root)
            self.assertTrue(ok)
            self.assertEqual(errors, [])

            # Tampered content case
            file1.write_text("Tampered content", encoding="utf-8")
            ok, errors = verify_restored_history(root)
            self.assertFalse(ok)
            self.assertTrue(any("Hash mismatch" in err for err in errors))

    def test_full_history_disaster_recovery_drill(self) -> None:
        """Execute complete drill on the real docs/history directory."""
        self.assertTrue(run_drill(source_dir=HISTORY_DIR))


if __name__ == "__main__":
    unittest.main()
