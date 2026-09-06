#!/usr/bin/env python3
"""
Check that all relative Markdown links inside docs/ and root *.md files
point to files that actually exist.

Exits 0 when no dead links are found.
Exits 1 when dead links are detected, printing each offending file/line.

Skips:
- External links (http/https/mailto/ftp)
- Anchor-only links (#section)
- Links inside archive/ and .git/
- Code fences (lines inside ``` blocks)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Markdown link pattern: [text](target)  or  [text]: target
_INLINE = re.compile(r'\[(?:[^\]]*)\]\(([^)#][^)]*)\)')
_REF = re.compile(r'^\s*\[[^\]]+\]:\s*(\S+)', re.MULTILINE)

_SKIP_DIRS = {"archive", ".git", "node_modules", ".venv", "__pycache__"}


def should_skip(path: Path) -> bool:
    return any(part in _SKIP_DIRS for part in path.parts)


def collect_md_files() -> list[Path]:
    files: list[Path] = []
    # root-level *.md
    for f in ROOT.glob("*.md"):
        files.append(f)
    # docs/**/*.md
    for f in (ROOT / "docs").rglob("*.md"):
        if not should_skip(f.relative_to(ROOT)):
            files.append(f)
    return files


def check_file(md_path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, target) for dead links."""
    dead: list[tuple[int, str]] = []
    lines = md_path.read_text(encoding="utf-8").splitlines()

    in_fence = False
    for lineno, line in enumerate(lines, 1):
        # Track code fences to avoid scanning code blocks
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        if in_fence:
            continue

        targets: list[str] = []
        for m in _INLINE.finditer(line):
            targets.append(m.group(1))
        for m in _REF.finditer(line):
            targets.append(m.group(1))

        for target in targets:
            # Skip external and anchor-only
            if target.startswith(("http://", "https://", "mailto:", "ftp://", "#")):
                continue
            # Strip inline anchor
            target_path = target.split("#")[0].strip()
            if not target_path:
                continue
            # Resolve relative to the md file's directory
            resolved = (md_path.parent / target_path).resolve()
            if not resolved.exists():
                dead.append((lineno, target))
    return dead


def main() -> int:
    md_files = collect_md_files()
    total_dead = 0
    for md_path in sorted(md_files):
        dead = check_file(md_path)
        if dead:
            rel = md_path.relative_to(ROOT)
            for lineno, target in dead:
                print(f"  DEAD LINK  {rel}:{lineno}  →  {target}")
                total_dead += 1

    if total_dead:
        print(f"\n[check_doc_links] {total_dead} dead link(s) found.", file=sys.stderr)
        return 1

    checked = len(md_files)
    print(f"[doc-links] OK: checked {checked} Markdown files, 0 dead links found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
