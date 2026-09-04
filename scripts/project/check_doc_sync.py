#!/usr/bin/env python3
"""
Check whether core codebase changes are accompanied by docs/CURRENT-STATE.md updates.

Enforces semi-mechanism for KI-025 and ENFORCEMENT.md Gate C:
- If changes touch backend/app/, deploy/, or schema without modifying docs/CURRENT-STATE.md,
  emits a GitHub Actions warning annotation.
- Non-blocking: always exits with code 0 so as not to block builds or PRs.
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
        command.append("--cached")

    try:
        res = subprocess.run(command, capture_output=True, text=True, check=True)
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
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
    """Check if file is in backend/app/, deploy/, or relates to schema."""
    p = path.lower()
    if path.startswith("backend/app/"):
        return True
    if path.startswith("deploy/"):
        return True
    if "schema" in p:
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
            "Changes detected in core backend/schema/deploy files without modifying docs/CURRENT-STATE.md. "
            "Please verify whether architectural, data scale, or operational facts need to be synced (see ENFORCEMENT.md Gate C)."
        )
        print(f"::warning title=CURRENT-STATE Sync Notice::{msg}")
        print(f"[notice] {msg}", file=sys.stderr)
    else:
        print("[notice] CURRENT-STATE sync check passed (no unsynced core changes).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
