#!/usr/bin/env python3
"""Generate and verify public-safe copies of restricted historical documents.

Owner: project governance tooling (KI-074, KI-103).
Input: ignored historical originals and an optional private asset inventory.
Output: tracked ``*.sanitized.md`` copies; ``--check`` is strictly read-only.
Risk: generation rewrites only public sanitized copies, never restricted originals.
Validation: python3 scripts/project/sanitize_history.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from check_public_sanitization import load_private_assets, redact_sensitive_text, scan_text

ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = ROOT / "docs" / "history"

RESTRICTED_FILES: list[tuple[str, str]] = [
    ("H-001", "01-产品与业务设计-待确认.md"),
    ("H-002", "02-数据模型-待确认.md"),
    ("H-003", "03-技术架构与实施计划.md"),
    ("H-004", "04-阶段1精确变更清单-待批准.md"),
    ("H-005", "05-USA数据库执行清单-待批准.md"),
    ("H-006", "06-组件化实施基线.md"),
    ("H-007", "07-当前部署与运维基线.md"),
    ("H-008", "08-模拟数据V2生成与验收规范-待最终确认.md"),
    ("H-009", "09-V2模拟数据生成实施任务书.md"),
    ("H-010", "10-V2后续实施移交清单_给下一位AI的Prompt.md"),
    ("H-011", "10-V2模拟数据第一轮审阅报告.md"),
    ("H-012", "11-V2模拟数据第二轮执行与整改报告.md"),
    ("H-013", "12-V2模拟数据第三轮执行与整改报告.md"),
    ("H-014", "13-V2模拟数据第四轮执行与整改报告.md"),
    ("H-015", "14-V2模拟数据第五轮执行与整改报告.md"),
    ("H-016", "15-V2模拟数据第六轮执行与整改报告.md"),
    ("H-017", "16-V2模拟数据指标口径修正与基准最终冻结声明.md"),
    ("H-018", "17-V2独立数据库导入方案与前置检查清单.md"),
    ("H-019", "18-V2数据库导入前只读环境核查报告.md"),
    ("H-020", "19-V2数据库导入执行与验收报告.md"),
    ("H-021", "20-V2数据库独立复审与账号整改报告.md"),
    ("H-022", "21-V2数据与项目目录现状基线.md"),
    ("H-023", "22-项目目录集中整理记录.md"),
]


def sanitize_text(text: str, stable_id: str, raw_filename: str, raw_hash: str) -> str:
    """Apply the shared public sanitizer and prepend preservation metadata."""
    content = redact_sensitive_text(text, load_private_assets())
    for _, raw_name in RESTRICTED_FILES:
        sanitized_name = raw_name.replace(".md", ".sanitized.md")
        content = content.replace(f"./{raw_name}", f"./{sanitized_name}")
        content = content.replace(f"({raw_name})", f"({sanitized_name})")

    header = (
        f"> **保全说明**：本文件为历史资料 `docs/history/{raw_filename}` 的公开脱敏副本。\n"
        f"> **稳定 ID**：{stable_id}\n"
        f"> **原件哈希 (SHA-256)**：`{raw_hash}`\n"
        f"> **脱敏规范**：遵循 [SANITIZATION-RULES.md](../development/SANITIZATION-RULES.md)，"
        "真实网络、云资源与私有主机标识均由统一规则替换；技术结构与演进过程保留。\n\n"
        "---\n\n"
    )
    return header + content


def generate_sanitized_files() -> list[Path]:
    """Generate public copies without modifying ignored restricted originals."""
    generated: list[Path] = []
    for stable_id, raw_name in RESTRICTED_FILES:
        raw_path = HISTORY_DIR / raw_name
        if not raw_path.exists():
            print(f"[sanitize-history] WARNING: restricted source unavailable for {stable_id}", file=sys.stderr)
            continue
        raw_bytes = raw_path.read_bytes()
        sanitized_path = HISTORY_DIR / raw_name.replace(".md", ".sanitized.md")
        sanitized_path.write_text(
            sanitize_text(
                raw_bytes.decode("utf-8"),
                stable_id,
                raw_name,
                hashlib.sha256(raw_bytes).hexdigest(),
            ),
            encoding="utf-8",
        )
        generated.append(sanitized_path)
        print(f"[sanitize-history] Generated public copy for {stable_id}")
    return generated


def check_sanitization() -> list[str]:
    """Verify every expected public copy with the shared repository scanner."""
    errors: list[str] = []
    private_assets = load_private_assets()
    for stable_id, raw_name in RESTRICTED_FILES:
        sanitized_path = HISTORY_DIR / raw_name.replace(".md", ".sanitized.md")
        if not sanitized_path.exists():
            errors.append(f"missing public copy for {stable_id}")
            continue
        relative = sanitized_path.relative_to(ROOT).as_posix()
        findings = scan_text(relative, sanitized_path.read_text(encoding="utf-8"), private_assets)
        errors.extend(f"{item.path}:{item.line}: {item.category}" for item in findings)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify public historical copies.")
    parser.add_argument("--check", action="store_true", help="Read-only verification.")
    parser.add_argument("--generate", action="store_true", help="Generate public copies (default action).")
    args = parser.parse_args()

    if not args.check:
        generated = generate_sanitized_files()
        print(f"[sanitize-history] Generated {len(generated)} public historical copies.")

    errors = check_sanitization()
    if errors:
        for error in errors:
            print(f"  SANITIZATION LEAK  {error}", file=sys.stderr)
        return 1
    print("[sanitize-history] OK: all restricted records have public-safe copies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
