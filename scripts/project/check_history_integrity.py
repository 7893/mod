#!/usr/bin/env python3
"""Verify frozen history against its tracked content-integrity manifest."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / "docs" / "history"
MANIFEST = HISTORY / "MANIFEST.sha256"


def load_manifest(path: Path = MANIFEST) -> dict[str, str]:
    entries: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        digest, separator, rel_path = line.partition("  ")
        if not separator or len(digest) != 64 or rel_path in entries:
            raise ValueError(f"invalid manifest entry at line {number}")
        entries[rel_path] = digest
    return entries


def validate(require_all: bool | None = None) -> list[str]:
    if not MANIFEST.exists():
        return ["history integrity manifest is missing"]
    try:
        entries = load_manifest()
    except ValueError as exc:
        return [str(exc)]
    if require_all is None:
        require_all = os.getenv("MOD_REQUIRE_LOCAL_HISTORY") == "1" or (ROOT / ".env.systemd").exists()
    errors: list[str] = []
    actual = {
        path.relative_to(ROOT).as_posix()
        for path in HISTORY.iterdir()
        if path.is_file() and path != MANIFEST
    }
    for rel_path, expected in entries.items():
        path = ROOT / rel_path
        if not path.exists():
            if require_all:
                errors.append(f"frozen history missing: {rel_path}")
            continue
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_digest != expected:
            errors.append(f"frozen history changed: {rel_path}")
    for unlisted in sorted(actual - set(entries)):
        errors.append(f"history file is not protected by manifest: {unlisted}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"  HISTORY INTEGRITY  {error}")
        return 1
    print("[history-integrity] OK: frozen history matches the tracked manifest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
