#!/usr/bin/env python3
"""Validate MOD commit subjects for local hooks and CI.

Input: a commit message file, or a Git range supplied with --base/--head.
Output: diagnostics on stderr and a non-zero exit code for invalid subjects.
This script is read-only and does not access the network, database, or credentials.
"""

from __future__ import annotations

import re
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

ALLOWED_TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "style",
    "test",
)
SUBJECT_PATTERN = re.compile(
    rf"^(?:{'|'.join(ALLOWED_TYPES)})(?:\([a-z0-9-]+\))?: [a-z0-9][a-z0-9 ._/-]*$"
)
MAX_WORDS = 7


def validate_subject(subject: str) -> list[str]:
    errors: list[str] = []
    if not subject:
        return ["subject is empty"]
    if not subject.isascii():
        errors.append("subject must contain ASCII English characters only")
    if subject != subject.lower():
        errors.append("subject must be lowercase")
    if not SUBJECT_PATTERN.fullmatch(subject):
        errors.append(f"subject must use an allowed type prefix: {', '.join(ALLOWED_TYPES)}")
    if len(subject.split()) > MAX_WORDS:
        errors.append(f"subject must contain no more than {MAX_WORDS} words")
    return errors


def _subjects_from_range(base: str, head: str) -> list[tuple[str, str]]:
    if set(base) == {"0"}:
        command = ["git", "show", "-s", "--format=%H%x00%s", head]
    else:
        revision = f"{base}..{head}"
        command = ["git", "log", "--format=%H%x00%s", "--no-merges", revision]
    output = subprocess.run(command, capture_output=True, text=True, check=True).stdout
    subjects: list[tuple[str, str]] = []
    for line in output.splitlines():
        commit, separator, subject = line.partition("\0")
        if separator:
            subjects.append((commit, subject))
    return subjects


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Validate MOD commit message subjects.")
    parser.add_argument("message_file", nargs="?", type=Path)
    parser.add_argument("--base", help="Validate commits after this base commit.")
    parser.add_argument("--head", default="HEAD", help="Range head used with --base (default: HEAD).")
    args = parser.parse_args(argv)

    if (args.message_file is not None) == (args.base is not None):
        parser.error("provide exactly one message_file or --base")

    if args.message_file:
        raw = args.message_file.read_text(encoding="utf-8")
        non_comments = [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]
        subject = non_comments[0] if non_comments else ""
        subjects = [("pending", subject)]
    else:
        base = args.base if args.base else "HEAD~1"
        subjects = _subjects_from_range(base, args.head)

    failures: list[tuple[str, str, list[str]]] = []
    for commit, subject in subjects:
        errors = validate_subject(subject)
        if errors:
            failures.append((commit, subject, errors))

    if not failures:
        return 0

    print("Commit message validation failed.", file=sys.stderr)
    for commit, subject, errors in failures:
        print(f"  {commit[:12]} {subject!r}", file=sys.stderr)
        for error in errors:
            print(f"    - {error}", file=sys.stderr)
    print("Example: fix: derive regional document additions", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
