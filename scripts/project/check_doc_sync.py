#!/usr/bin/env python3
"""
Check whether core codebase changes are accompanied by docs/CURRENT-STATE.md updates.

Enforces KI-054 and ENFORCEMENT.md Gate C:
- If behavior-bearing code, deployment configuration, or schema changes without
  docs/CURRENT-STATE.md, fail the check.
- The check is read-only and runs both locally and in CI.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def get_changed_files(base: str | None = None, head: str = "HEAD") -> list[str]:
    command = ["git", "diff", "--name-only"]
    if base:
        if set(base) == {"0"}:
            base = subprocess.run(
                ["git", "hash-object", "-t", "tree", "/dev/null"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        command.extend([base, head])
    else:
        command.append("HEAD")

    try:
        res = subprocess.run(command, capture_output=True, text=True, check=True)
        files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if not base:
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
            files.extend(line.strip() for line in untracked if line.strip())
        return sorted(set(files))
    except subprocess.CalledProcessError:
        try:
            res = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1", head],
                capture_output=True,
                text=True,
                check=True,
            )
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            return []


def is_core_file(path: str) -> bool:
    """Check whether a path may change current behavior or operating facts."""
    p = path.lower()
    if path.startswith(("backend/app/", "frontend/src/", "simulation/", "deploy/")):
        return True
    if path.startswith("database/") or "schema" in p:
        return True
    return False


def check_sync(files: list[str]) -> bool:
    """Returns True if core files were modified without docs/CURRENT-STATE.md."""
    has_core = any(is_core_file(f) for f in files)
    has_current_state = any(f == "docs/CURRENT-STATE.md" for f in files)
    return has_core and not has_current_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Check CURRENT-STATE.md sync notice.")
    parser.add_argument("--base", help="Git base ref for comparison")
    parser.add_argument("--head", default="HEAD", help="Git head ref for comparison")
    args = parser.parse_args()

    changed_files = get_changed_files(base=args.base, head=args.head)

    if check_sync(changed_files):
        msg = (
            "Behavior or operating facts changed without docs/CURRENT-STATE.md. "
            "Synchronize the current snapshot in the same change (ENFORCEMENT.md Gate C)."
        )
        print(f"::error title=CURRENT-STATE Sync Required::{msg}")
        print(f"[doc-sync] {msg}", file=sys.stderr)
        return 1
    else:
        print("[notice] CURRENT-STATE sync check passed (no unsynced core changes).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
