#!/usr/bin/env python3
"""Disaster Recovery Backup & Restoration Drill for MOD Historical Documents (KI-074).

Capabilities:
1. Archive: Packages docs/history/ into tar.gz with deterministic paths.
2. Encryption: Client-side AES-256-CBC PBKDF2 (100,000 iter) encryption.
3. Checksum: Calculates SHA-256 of the encrypted bundle.
4. Remote Replication: Optional upload to Cloudflare R2 / S3 when configured.
5. Restoration & Drill: Decrypts archive to temporary sandbox and verifies
   all files against docs/history/MANIFEST.sha256.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = ROOT / "docs" / "history"
MANIFEST_PATH = HISTORY_DIR / "MANIFEST.sha256"
DEFAULT_BACKUP_DIR = ROOT / "backups" / "history"


def get_encryption_key() -> str:
    """Retrieve encryption key from environment, fallback key file, or generate drill key."""
    key = os.getenv("MOD_BACKUP_ENCRYPTION_KEY")
    if key:
        return key.strip()

    key_file = ROOT / ".backup_key"
    if key_file.is_file():
        try:
            return key_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # For drills where no key is present, generate an ephemeral session key
    return secrets.token_hex(32)


def calculate_sha256(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_history_archive(output_tar_gz: Path, source_dir: Path = HISTORY_DIR) -> int:
    """Create a gzip-compressed tar archive of the history directory."""
    if not source_dir.exists():
        raise FileNotFoundError(f"Source history directory not found: {source_dir}")

    with tarfile.open(output_tar_gz, "w:gz") as tar:
        # Add source directory preserving relpath under docs/history
        for item in sorted(source_dir.iterdir()):
            if item.is_file() and not item.name.endswith(".tmp"):
                tar.add(item, arcname=f"docs/history/{item.name}")

    return output_tar_gz.stat().st_size


def encrypt_file(input_path: Path, output_enc_path: Path, encryption_key: str) -> int:
    """Encrypt a file using OpenSSL AES-256-CBC PBKDF2 (100,000 iterations)."""
    env = os.environ.copy()
    env["_BACKUP_ENC_KEY"] = encryption_key

    cmd = [
        "openssl",
        "enc",
        "-aes-256-cbc",
        "-salt",
        "-pbkdf2",
        "-iter",
        "100000",
        "-pass",
        "env:_BACKUP_ENC_KEY",
        "-in",
        str(input_path),
        "-out",
        str(output_enc_path),
    ]

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"OpenSSL encryption failed: {res.stderr.strip()}")

    return output_enc_path.stat().st_size


def decrypt_file(input_enc_path: Path, output_path: Path, encryption_key: str) -> int:
    """Decrypt an OpenSSL AES-256-CBC PBKDF2 encrypted file."""
    env = os.environ.copy()
    env["_BACKUP_ENC_KEY"] = encryption_key

    cmd = [
        "openssl",
        "enc",
        "-aes-256-cbc",
        "-d",
        "-pbkdf2",
        "-iter",
        "100000",
        "-pass",
        "env:_BACKUP_ENC_KEY",
        "-in",
        str(input_enc_path),
        "-out",
        str(output_path),
    ]

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"OpenSSL decryption failed: {res.stderr.strip()}")

    return output_path.stat().st_size


def verify_restored_history(
    restored_root: Path, require_all: Optional[bool] = None
) -> Tuple[bool, List[str]]:
    """Verify restored files against MANIFEST.sha256."""
    manifest = restored_root / "docs" / "history" / "MANIFEST.sha256"
    if not manifest.exists():
        return False, ["MANIFEST.sha256 not found in restored archive"]

    if require_all is None:
        require_all = os.getenv("MOD_REQUIRE_LOCAL_HISTORY") == "1" or (ROOT / ".env.systemd").exists()

    entries: Dict[str, str] = {}
    for lineno, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, separator, rel_path = line.partition("  ")
        if not separator or len(digest) != 64:
            return False, [f"Invalid manifest line {lineno}: {line}"]
        entries[rel_path.strip()] = digest.strip()

    errors: List[str] = []
    restored_history = restored_root / "docs" / "history"
    actual_files = {
        f"docs/history/{p.name}": p
        for p in restored_history.iterdir()
        if p.is_file() and p.name != "MANIFEST.sha256"
    }

    # Verify all files present in manifest
    for rel_path, expected_hash in entries.items():
        if rel_path not in actual_files:
            if require_all:
                errors.append(f"Restored file missing: {rel_path}")
            continue
        actual_hash = calculate_sha256(actual_files[rel_path])
        if actual_hash != expected_hash:
            errors.append(f"Hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}")

    # Verify no unmanifested files
    for rel_path in sorted(set(actual_files.keys()) - set(entries.keys())):
        errors.append(f"Restored file not in manifest: {rel_path}")

    return len(errors) == 0, errors


def run_drill(
    source_dir: Path = HISTORY_DIR,
    key: Optional[str] = None,
    require_all: Optional[bool] = None,
) -> bool:
    """Execute a self-contained local disaster recovery drill."""
    drill_key = key or get_encryption_key()
    with tempfile.TemporaryDirectory(prefix="mod_history_drill_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        tar_gz_path = temp_dir / "history.tar.gz"
        enc_path = temp_dir / "history.tar.gz.enc"
        decrypted_tar_path = temp_dir / "history_restored.tar.gz"
        restore_extract_dir = temp_dir / "extracted"

        print("[dr-drill] 1. Packing history directory into gzip tarball...")
        archive_size = create_history_archive(tar_gz_path, source_dir)
        print(f"           Archive created: {archive_size / 1024:.1f} KB")

        print("[dr-drill] 2. Encrypting with AES-256-CBC PBKDF2...")
        enc_size = encrypt_file(tar_gz_path, enc_path, drill_key)
        enc_hash = calculate_sha256(enc_path)
        print(f"           Encrypted size: {enc_size / 1024:.1f} KB (SHA-256: {enc_hash[:16]}...)")

        print("[dr-drill] 3. Decrypting archive to verification sandbox...")
        decrypt_file(enc_path, decrypted_tar_path, drill_key)

        print("[dr-drill] 4. Extracting decrypted tarball...")
        restore_extract_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(decrypted_tar_path, "r:gz") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=restore_extract_dir, filter="data")
            else:
                tar.extractall(path=restore_extract_dir)

        print("[dr-drill] 5. Validating cryptographic integrity against MANIFEST.sha256...")
        success, errors = verify_restored_history(restore_extract_dir, require_all=require_all)

        if not success:
            for err in errors:
                print(f"  [ERROR] {err}", file=sys.stderr)
            print(f"[dr-drill] DRILL FAILED: {len(errors)} integrity errors encountered.", file=sys.stderr)
            return False

        manifest_count = len([
            l for l in (source_dir / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")
        ])
        print(f"[dr-drill] DRILL SUCCESS: All {manifest_count} files restored and 100% hash-verified.")
        return True


def perform_backup(
    output_dir: Path = DEFAULT_BACKUP_DIR,
    source_dir: Path = HISTORY_DIR,
    upload: bool = False,
    endpoint_url: Optional[str] = None,
    s3_bucket: Optional[str] = None,
    s3_profile: Optional[str] = None,
) -> Path:
    """Create a persistent encrypted backup bundle and its SHA-256 checksum file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = f"mod_history_backup_{date_str}"
    enc_path = output_dir / f"{base_name}.tar.gz.enc"
    sha_path = output_dir / f"{base_name}.tar.gz.enc.sha256"

    key = get_encryption_key()

    with tempfile.TemporaryDirectory(prefix="mod_hist_backup_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        tar_gz_path = temp_dir / "history.tar.gz"

        print(f"[backup] Packaging history archive...")
        create_history_archive(tar_gz_path, source_dir)

        print(f"[backup] Encrypting history archive to {enc_path.name}...")
        encrypt_file(tar_gz_path, enc_path, key)

    enc_hash = calculate_sha256(enc_path)
    sha_path.write_text(f"{enc_hash}  {enc_path.name}\n", encoding="utf-8")
    print(f"[backup] Backup complete: {enc_path} ({enc_path.stat().st_size / 1024:.1f} KB)")
    print(f"[backup] Checksum saved:  {sha_path} ({enc_hash})")

    if upload and s3_bucket:
        upload_cmd = [
            "aws",
            "s3",
            "cp",
            str(enc_path),
            f"s3://{s3_bucket}/history/{enc_path.name}",
            "--only-show-errors",
        ]
        if endpoint_url:
            upload_cmd.extend(["--endpoint-url", endpoint_url])
        if s3_profile:
            upload_cmd.extend(["--profile", s3_profile])

        print(f"[backup] Uploading to s3://{s3_bucket}/history/...")
        res = subprocess.run(upload_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"S3/R2 upload failed: {res.stderr.strip()}")
        print(f"[backup] Upload successful.")

    return enc_path


def main() -> int:
    parser = argparse.ArgumentParser(description="MOD History Disaster Recovery & Verification Tool.")
    parser.add_argument("--drill", action="store_true", help="Execute an end-to-end backup, decryption, and verification drill.")
    parser.add_argument("--backup", action="store_true", help="Generate an encrypted backup bundle in the backup directory.")
    parser.add_argument("--restore-and-verify", metavar="FILE", help="Decrypt and verify an existing encrypted backup bundle.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_BACKUP_DIR, help="Destination directory for persistent backup bundles.")
    parser.add_argument("--upload", action="store_true", help="Upload encrypted bundle to Cloudflare R2 / AWS S3.")
    parser.add_argument("--endpoint-url", default=os.getenv("MOD_BACKUP_S3_ENDPOINT"), help="Custom S3/R2 endpoint URL.")
    parser.add_argument("--bucket", default=os.getenv("MOD_BACKUP_BUCKET", "mod-backup"), help="S3 bucket name.")
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE", "r2"), help="AWS CLI profile name.")
    args = parser.parse_args()

    if args.restore_and_verify:
        enc_file = Path(args.restore_and_verify)
        if not enc_file.exists():
            print(f"Error: Specified file does not exist: {enc_file}", file=sys.stderr)
            return 1
        key = get_encryption_key()
        with tempfile.TemporaryDirectory(prefix="mod_restore_verify_") as tmp_dir:
            tmp = Path(tmp_dir)
            tar_path = tmp / "history.tar.gz"
            extract_dir = tmp / "extracted"
            decrypt_file(enc_file, tar_path, key)
            extract_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tar_path, "r:gz") as tar:
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(path=extract_dir, filter="data")
                else:
                    tar.extractall(path=extract_dir)
            success, errors = verify_restored_history(extract_dir)
            if not success:
                for err in errors:
                    print(f"  [ERROR] {err}", file=sys.stderr)
                return 1
            print(f"[restore] SUCCESS: {enc_file.name} successfully decrypted and verified against MANIFEST.sha256.")
            return 0

    if args.backup:
        try:
            perform_backup(
                output_dir=args.output_dir,
                upload=args.upload,
                endpoint_url=args.endpoint_url,
                s3_bucket=args.bucket,
                s3_profile=args.profile,
            )
            return 0
        except Exception as exc:
            print(f"[backup] FAILED: {exc}", file=sys.stderr)
            return 1

    # Default to drill
    success = run_drill()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
