#!/usr/bin/env python3
"""Enforce MOD documentation lifecycle and preservation rules.

Owner: project governance tooling.
Input: repository files and an optional Git base/head range.
Output: diagnostics only; this script is read-only.
Risk: none. It never changes files, Git state, services, or external systems.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALID_KI_STATUSES = {"DRAFT", "OPEN", "IN-PROGRESS", "DONE"}
FROZEN_PREFIXES = (
    "archive/",
    "docs/history/",
    "docs/evidence/",
    "docs/decisions/",
)
INDEXED_DIRECTORIES = (
    ROOT / "docs" / "development",
    ROOT / "docs" / "operations",
    ROOT / "docs" / "runbooks",
    ROOT / "docs" / "evidence",
)
STATUS_RE = re.compile(r"^\s*-\s*状态：([A-Z-]+)", re.MULTILINE)
BOARD_RE = re.compile(
    r"^\|\s*(KI-\d{3}(?:-\d+)?)\s*\|.*?\|\s*([A-Z-]+)\s*\|.*?"
    r"\[详情\]\((issues/[^)]+\.md)\)\s*\|$",
    re.MULTILINE,
)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)")
MUTABLE_METADATA_RE = re.compile(
    r"^\s*-?\s*(?:状态|更新日期|日期|适用范围|取代|被取代|原始位置)[：:]"
)


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def parse_board(text: str) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for identifier, status, link in BOARD_RE.findall(text):
        if identifier in entries:
            raise ValueError(f"看板存在重复编号：{identifier}")
        entries[identifier] = (status, link)
    return entries


def parse_detail_status(text: str) -> str | None:
    match = STATUS_RE.search("\n".join(text.splitlines()[:15]))
    return match.group(1) if match else None


def missing_metadata(text: str) -> list[str]:
    head = "\n".join(text.splitlines()[:15])
    missing: list[str] = []
    if not text.startswith("# "):
        missing.append("标题")
    if not re.search(r"(?:更新日期|编写日期)[：:]\s*\d{4}-\d{2}-\d{2}", head):
        missing.append("更新日期")
    if not re.search(r"状态[：:]", head):
        missing.append("状态")
    if not re.search(r"适用范围[：:]", head):
        missing.append("适用范围")
    return missing


def preserves_frozen_body(old: str, new: str) -> bool:
    """Return True when every immutable old line remains in order.

    Lifecycle metadata may change so an ADR or historical record can be marked as
    superseded. Body text may only be retained or appended to.
    """

    def immutable_lines(text: str) -> list[str]:
        return [line for line in text.splitlines() if not MUTABLE_METADATA_RE.match(line)]

    old_lines = immutable_lines(old)
    new_iter = iter(immutable_lines(new))
    return all(any(candidate == line for candidate in new_iter) for line in old_lines)


def is_document_path(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix == ".md" or (
        suffix == ".txt" and path.startswith(("docs/", "archive/"))
    )


def changed_entries(base: str | None, head: str) -> list[tuple[str, str, str | None]]:
    args = ["diff", "--name-status", "-M"]
    if base:
        args.extend([base, head])
    else:
        args.append("HEAD")
    entries: list[tuple[str, str, str | None]] = []
    for line in run_git(*args).splitlines():
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            if is_document_path(parts[1]) or is_document_path(parts[2]):
                entries.append(("R", parts[2], parts[1]))
        elif is_document_path(parts[1]):
            entries.append((status[0], parts[1], None))
    if not base:
        tracked = {path for _, path, _ in entries}
        for path in run_git("ls-files", "--others", "--exclude-standard").splitlines():
            if is_document_path(path) and path not in tracked:
                entries.append(("A", path, None))
    return entries


def read_revision(path: str, revision: str | None) -> str:
    if revision is None:
        return (ROOT / path).read_text(encoding="utf-8")
    return run_git("show", f"{revision}:{path}")


def check_ki_registry(errors: list[str]) -> None:
    board_path = ROOT / "docs" / "KNOWN-ISSUES.md"
    try:
        board = parse_board(board_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        errors.append(str(exc))
        return

    details: dict[str, Path] = {}
    for path in (ROOT / "docs" / "issues").glob("KI-*.md"):
        match = re.match(r"(KI-\d{3}(?:-\d+)?)-", path.name)
        if not match:
            errors.append(f"KI 文件名不符合编号规则：{path.relative_to(ROOT)}")
            continue
        identifier = match.group(1)
        if identifier in details:
            errors.append(f"KI 详情存在重复编号：{identifier}")
        details[identifier] = path

    for identifier, (board_status, link) in board.items():
        detail_path = ROOT / "docs" / link
        if not detail_path.exists():
            errors.append(f"{identifier} 看板链接不存在：docs/{link}")
            continue
        detail_status = parse_detail_status(detail_path.read_text(encoding="utf-8"))
        if board_status not in VALID_KI_STATUSES:
            errors.append(f"{identifier} 看板状态非法：{board_status}")
        if detail_status not in VALID_KI_STATUSES:
            errors.append(f"{identifier} 详情状态非法：{detail_status or '缺失'}")
        if detail_status != board_status:
            errors.append(
                f"{identifier} 状态不一致：看板={board_status}，详情={detail_status}"
            )

    for identifier, path in details.items():
        if identifier not in board:
            errors.append(f"{identifier} 详情未登记到看板：{path.relative_to(ROOT)}")


def check_index(errors: list[str]) -> None:
    index_path = ROOT / "docs" / "INDEX.md"
    text = index_path.read_text(encoding="utf-8")
    linked: set[Path] = set()
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        linked.add((index_path.parent / target.strip()).resolve())

    for directory in INDEXED_DIRECTORIES:
        for path in directory.glob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
                if path.resolve() not in linked:
                    errors.append(f"现行文档未以 Markdown 链接纳入 INDEX：{path.relative_to(ROOT)}")


def check_changes(
    errors: list[str], entries: list[tuple[str, str, str | None]], base: str | None, head: str
) -> None:
    old_revision = base or "HEAD"
    new_revision = head if base else None
    for status, path, old_path in entries:
        if status == "D":
            errors.append(f"禁止删除已跟踪文档，请标记或使用 Git 重命名迁移：{path}")
            continue
        if not path.endswith(".md"):
            continue
        if (
            status in {"A", "M", "R"}
            and path.startswith("docs/")
            and not path.startswith(FROZEN_PREFIXES)
        ):
            missing = missing_metadata(read_revision(path, new_revision))
            if missing:
                errors.append(f"{path} 缺少必需元数据：{'、'.join(missing)}")
        compare_path = old_path or path
        touches_frozen = path.startswith(FROZEN_PREFIXES) or bool(
            old_path and old_path.startswith(FROZEN_PREFIXES)
        )
        if status in {"M", "R"} and touches_frozen:
            old = read_revision(compare_path, old_revision)
            new = read_revision(path, new_revision)
            if not preserves_frozen_body(old, new):
                errors.append(f"冻结文档正文被删减或改写，只允许追加标记/勘误：{path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查文档生命周期与历史保全规则。")
    parser.add_argument("--base", help="CI 比较基线 Git revision")
    parser.add_argument("--head", default="HEAD", help="CI 比较目标 Git revision")
    args = parser.parse_args()

    errors: list[str] = []
    check_ki_registry(errors)
    check_index(errors)
    try:
        check_changes(errors, changed_entries(args.base, args.head), args.base, args.head)
    except subprocess.CalledProcessError as exc:
        errors.append(f"无法读取 Git 文档差异：{exc}")

    if errors:
        for error in errors:
            print(f"  DOCUMENT GOVERNANCE  {error}")
        print(f"\n[document-governance] {len(errors)} 个问题。", file=sys.stderr)
        return 1

    print("[document-governance] OK: preservation, metadata, index and KI state checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
