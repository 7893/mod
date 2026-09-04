#!/usr/bin/env python3
"""
Lint frontend Vue files for forbidden Tailwind arbitrary values.

Enforces Contract 3 of docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md (KI-018):
- Strictly forbidden: text-[..], bg-[..], border-[..], p-[..], m-[..], gap-[..], rounded-[..]
- Allowed layout guardrails: min-h-[..], max-h-[..]
- Inline exemption: add `<!-- lint: allow -->` on the same line to exempt.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Match forbidden arbitrary value patterns with optional variant prefixes (e.g., hover:text-[10px])
FORBIDDEN_PATTERN = re.compile(
    r'(?:^|[\s"\'`:(])'
    r'((?:[a-z0-9_-]+:)*'
    r'(?:text|bg|border|rounded|ring|fill|stroke|gap|gap-x|gap-y|p|px|py|pt|pb|pl|pr|ps|pe|m|mx|my|mt|mb|ml|mr|ms|me)'
    r'-\[[^\]]+\])'
)

EXEMPTION_MARKER = "lint: allow"


def scan_vue_file(file_path: Path) -> list[tuple[int, str, str]]:
    """
    Scan a .vue file for forbidden arbitrary values within <template> sections.
    Returns a list of (line_number, line_content, matched_token).
    """
    violations: list[tuple[int, str, str]] = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return violations

    lines = content.splitlines()
    template_depth = 0

    for idx, line in enumerate(lines, start=1):
        open_tags = len(re.findall(r"<template\b", line))
        close_tags = len(re.findall(r"</template>", line))

        in_template_before = template_depth > 0
        template_depth += open_tags - close_tags

        if not in_template_before and template_depth <= 0 and open_tags == 0:
            continue

        # Check for exemption comment
        if EXEMPTION_MARKER in line:
            continue

        match = FORBIDDEN_PATTERN.search(line)
        if match:
            matched_token = match.group(1)
            violations.append((idx, line.strip(), matched_token))

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint Vue files for forbidden Tailwind arbitrary values.")
    parser.add_argument("files", nargs="*", help="Optional specific .vue files to scan")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    frontend_src = repo_root / "frontend" / "src"

    if args.files:
        vue_files = [Path(f).resolve() for f in args.files]
    else:
        if not frontend_src.exists():
            print(f"Frontend directory not found at {frontend_src}", file=sys.stderr)
            return 1
        vue_files = sorted(frontend_src.glob("**/*.vue"))

    total_violations = 0

    for vue_file in vue_files:
        violations = scan_vue_file(vue_file)
        if violations:
            try:
                rel_path = vue_file.relative_to(repo_root)
            except ValueError:
                rel_path = vue_file
            for line_no, line_content, token in violations:
                print(f"{rel_path}:{line_no}: forbidden arbitrary value '{token}' found in template")
                print(f"    Line {line_no}: {line_content}")
            total_violations += len(violations)

    if total_violations > 0:
        print(
            f"\n[lint] Failed: {total_violations} forbidden Tailwind arbitrary value(s) detected.\n"
            "       See docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md (Contract 3).\n"
            "       Use defined Design Tokens in theme.css or add '<!-- lint: allow -->' for approved exceptions.",
            file=sys.stderr,
        )
        return 1

    print(f"[lint] Passed: checked {len(vue_files)} Vue files, 0 forbidden arbitrary values found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
