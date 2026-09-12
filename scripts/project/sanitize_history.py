#!/usr/bin/env python3
"""Sanitize restricted historical documents and verify sanitization completeness.

Owner: project governance tooling (KI-074).
Follows: docs/development/SANITIZATION-RULES.md
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = ROOT / "docs" / "history"

# Restricted files inventory mapped to stable IDs
RESTRICTED_FILES: List[Tuple[str, str]] = [
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

# Sensitive patterns that must NOT appear in any sanitized document
LEAK_SIGNATURES = [
    r"193\.122\.180\.196",
    r"10\.0\.10\.27",
    r"10\.0\.0\.152",
    r"8n8m\.cfd",
    r"2603:c020:",
    r"ocid1\.tenancy\.oc1",
    r"ocid1\.subnet\.oc1",
    r"instance-20210605-2242",
    r"mysqldbsystem20260822145022",
    r"mysqlbackup20260830172017",
]

# Replacement mappings in order of substitution
REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    # Domain
    (re.compile(r"https?://[a-zA-Z0-9.-]+\.8n8m\.cfd/mod/?"), "https://<production-domain>/mod/"),
    (re.compile(r"[a-zA-Z0-9.-]+\.8n8m\.cfd"), "<production-domain>"),
    # IPs
    (re.compile(r"193\.122\.180\.196"), "193.122.x.x (USA公网地址，已脱敏)"),
    (re.compile(r"10\.0\.10\.27"), "10.0.10.x (MySQL私网地址，已脱敏)"),
    (re.compile(r"10\.0\.0\.152"), "10.0.0.x (USA宿主机私网地址，已脱敏)"),
    (re.compile(r"2603:c020:400d:de00:0:5dc5:c462:fc01"), "<ipv6-address (已脱敏)>"),
    # OCI identifiers
    (re.compile(r"ocid1\.tenancy\.oc1\.\.\.[a-z0-9]+"), "<tenancy-ocid>"),
    (re.compile(r"ocid1\.subnet\.oc1\.\.\.[a-z0-9]+"), "<subnet-ocid>"),
    (re.compile(r"instance-20210605-2242"), "<usa-vm-instance-id>"),
    (re.compile(r"mysqldbsystem20260822145022"), "<mysql-instance-name>"),
    (re.compile(r"mysqlbackup20260830172017"), "<mysql-backup-id>"),
    (re.compile(r"ypNq:US-ASHBURN-AD-1"), "<us-ashburn-ad>"),
    (re.compile(r"FAULT-DOMAIN-2"), "<fault-domain>"),
]


def sanitize_text(text: str, stable_id: str, raw_filename: str, raw_hash: str) -> str:
    """Apply sanitization transformations and prepend preservation header."""
    content = text
    for pattern, replacement in REPLACEMENTS:
        content = pattern.sub(replacement, content)

    # Rewrite internal links to restricted history files to their sanitized counterparts
    for _, raw_name in RESTRICTED_FILES:
        raw_sanitized = raw_name.replace(".md", ".sanitized.md")
        content = content.replace(f"./{raw_name}", f"./{raw_sanitized}")
        content = content.replace(f"({raw_name})", f"({raw_sanitized})")

    header = (
        f"> **保全说明**：本文件为历史资料 `docs/history/{raw_filename}` 的公开脱敏副本。\n"
        f"> **稳定 ID**：{stable_id}\n"
        f"> **原件哈希 (SHA-256)**：`{raw_hash}`\n"
        f"> **脱敏规范**：遵循 [SANITIZATION-RULES.md](../development/SANITIZATION-RULES.md)，"
        f"所有真实内网/公网 IP、OCID、域名及主机标识已完成安全脱敏，技术结构与演进过程 100% 保真。\n\n"
        f"---\n\n"
    )
    return header + content


def generate_sanitized_files() -> List[Path]:
    """Generate or update all sanitized copies."""
    generated: List[Path] = []
    for stable_id, raw_name in RESTRICTED_FILES:
        raw_path = HISTORY_DIR / raw_name
        if not raw_path.exists():
            print(f"[sanitize-history] WARNING: Raw file not found: {raw_path}", file=sys.stderr)
            continue
        raw_bytes = raw_path.read_bytes()
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        raw_text = raw_bytes.decode("utf-8")

        sanitized_text = sanitize_text(raw_text, stable_id, raw_name, raw_hash)
        sanitized_filename = raw_name.replace(".md", ".sanitized.md")
        sanitized_path = HISTORY_DIR / sanitized_filename

        sanitized_path.write_text(sanitized_text, encoding="utf-8")
        generated.append(sanitized_path)
        print(f"[sanitize-history] Generated {sanitized_filename} (from {stable_id}: {raw_name})")

    return generated


def check_sanitization() -> List[str]:
    """Check that all sanitized files exist and contain zero leak signatures."""
    errors: List[str] = []
    compiled_leaks = [re.compile(sig, re.IGNORECASE) for sig in LEAK_SIGNATURES]

    for stable_id, raw_name in RESTRICTED_FILES:
        sanitized_filename = raw_name.replace(".md", ".sanitized.md")
        sanitized_path = HISTORY_DIR / sanitized_filename

        if not sanitized_path.exists():
            errors.append(f"Missing sanitized copy: {sanitized_filename} for {stable_id}")
            continue

        text = sanitized_path.read_text(encoding="utf-8")
        for sig_idx, regex in enumerate(compiled_leaks):
            matches = regex.findall(text)
            if matches:
                errors.append(
                    f"Sensitive leak in {sanitized_filename}: matched '{LEAK_SIGNATURES[sig_idx]}' ({len(matches)} occurrences)"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitize historical documents.")
    parser.add_argument("--check", action="store_true", help="Verify sanitized copies against leakage.")
    parser.add_argument("--generate", action="store_true", help="Generate/update sanitized copies.")
    args = parser.parse_args()

    if args.check:
        errors = check_sanitization()
        if errors:
            for err in errors:
                print(f"  SANITIZATION LEAK  {err}", file=sys.stderr)
            return 1
        print("[sanitize-history] OK: all 23 restricted files have leak-free sanitized copies.")
        return 0

    # Default action is generate
    generated = generate_sanitized_files()
    print(f"[sanitize-history] Successfully processed {len(generated)} sanitized historical files.")

    # Self-check after generation
    errors = check_sanitization()
    if errors:
        for err in errors:
            print(f"  SANITIZATION LEAK  {err}", file=sys.stderr)
        return 1
    print("[sanitize-history] OK: self-verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
