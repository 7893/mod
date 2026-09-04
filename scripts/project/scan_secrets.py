#!/usr/bin/env python3
"""Staged-diff secret scanner for the MOD pre-commit gate.

只读扫描本次暂存区的新增内容，命中明文凭据特征即以非零退出码阻断提交。
设计依据：docs/development/SECRET-SCAN-HOOK-DESIGN.md 与 ENFORCEMENT.md 闸门 A。

范围：仅扫描 `git diff --cached` 的新增行，不扫描全库（历史泄露另行处理）。
取向：宁可偶尔误报，不可漏报。误报可用行内标记 `# secret-scan: allow` 放行。
本脚本只读，不修改任何文件，不访问网络，不连接数据库。
"""

from __future__ import annotations

import re
import subprocess
import sys
from argparse import ArgumentParser

# 行内豁免标记：对该行显式放行，需提交者对该行负责。无“整仓关闭”开关。
ALLOW_MARKER = "secret-scan: allow"

# 路径前缀豁免：归档区（回收站）保留历史残留，不作为活跃代码扫描。
EXCLUDED_PREFIXES = ("archive/",)

# 安全占位符：命中这些视为示例，不阻断。
PLACEHOLDERS = (
    "changeme", "your-password", "your_password", "placeholder", "example",
    "xxxx", "****", "<password>", "<secret>", "<token>", "redacted", "dummy",
    "fake", "localhost", "随机密码", "脱敏", "__", "your_",
)

# 值为代码表达式（从环境读取、函数调用、变量、f-string 占位）视为非明文，不阻断。
_CODE_VALUE = re.compile(
    r"^(?:os\.(?:getenv|environ)|getenv|environ|quote_plus|[A-Za-z_][\w.]*\s*\(|"
    r"self\.|\{|None|True|False|\"\"|''|number$|str$|int$)",
)

# 检测规则：(规则名, 已编译正则)。命中任意一条即判定为疑似凭据。
_RULES: list[tuple[str, re.Pattern[str]]] = [
    # 键值式明文口令：变量名以 pass/pwd/secret/token/apikey 等结尾（后不接字母，
    # 避免 totalPassed 误伤），后接 =/: 与非占位符值。
    ("kv-secret", re.compile(
        r"(?i)(?<![a-z])(password|passwd|pass|pwd|secret|token|api[_-]?key|access[_-]?key)"
        r"(?![a-z])\s*[=:]\s*['\"]?([^\s'\"]{6,})",
    )),
    # 数据库连接串内嵌口令：scheme://user:pass@host（排除变量占位与假值在 _scan_line 处理）  # secret-scan: allow
    ("db-url-credential", re.compile(
        r"(?i)[a-z0-9+.\-]+://[^\s:/@]+:[^\s:/@{}]+@[^\s/]+",
    )),
    # PEM/OpenSSH 私钥块头
    ("private-key", re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
    )),
    # AWS Access Key ID 典型格式
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
]


def _added_lines(base: str | None = None, head: str = "HEAD") -> list[tuple[str, int, str]]:
    """Return added diff lines as (path, line number, content)."""
    command = ["git", "diff", "--unified=0", "--no-color"]
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
        diff = subprocess.run(
            command,
            capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        print(error.stderr.strip() or "Unable to read Git diff.", file=sys.stderr)
        raise

    results: list[tuple[str, int, str]] = []
    current_file = ""
    new_lineno = 0
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
            continue
        if raw.startswith("+++ ") or raw.startswith("--- "):
            continue
        m = hunk_re.match(raw)
        if m:
            new_lineno = int(m.group(1))
            continue
        if raw.startswith("+"):
            results.append((current_file, new_lineno, raw[1:]))
            new_lineno += 1
        elif not raw.startswith("-"):
            new_lineno += 1
    return results


def _is_placeholder(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in PLACEHOLDERS)


def _scan_line(line: str) -> list[str]:
    """返回该行命中的规则名列表；空列表表示无命中。"""
    if ALLOW_MARKER in line:
        return []
    hits: list[str] = []
    for name, pattern in _RULES:
        m = pattern.search(line)
        if not m:
            continue
        if name == "kv-secret":
            value = m.group(2)
            # 占位符、或值本身是代码表达式（从环境读取/函数/变量/占位）→ 非明文，放行
            if _is_placeholder(value) or _CODE_VALUE.match(value):
                continue
        if name == "db-url-credential":
            matched = m.group(0)
            # 变量占位 {..}、或明确的假值标记 → 非真实连接串，放行（不使用宽泛占位符表）
            if "{" in matched or any(k in matched.lower() for k in ("fake", "localhost", "脱敏", "your_", "__")):
                continue
        hits.append(name)
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description="Scan added Git diff lines for credentials.")
    parser.add_argument("--base", help="Scan changes from this commit to --head instead of the staged diff.")
    parser.add_argument("--head", default="HEAD", help="Range head used with --base (default: HEAD).")
    args = parser.parse_args(argv)

    findings: list[tuple[str, int, str, str]] = []
    for path, lineno, line in _added_lines(args.base, args.head):
        if path.startswith(EXCLUDED_PREFIXES):
            continue
        # .env.example 一律按占位符文件对待，仍扫描但占位符会被放行
        for rule in _scan_line(line):
            findings.append((path, lineno, rule, line.strip()[:120]))

    if not findings:
        return 0

    print("提交被阻断：暂存改动中检测到疑似明文凭据。", file=sys.stderr)
    print("依据 ENFORCEMENT.md 闸门 A：凭据不得进入源码、命令、日志或 Git 历史。", file=sys.stderr)
    print("", file=sys.stderr)
    for path, lineno, rule, snippet in findings:
        print(f"  [{rule}] {path}:{lineno}", file=sys.stderr)
        print(f"      {snippet}", file=sys.stderr)
    print("", file=sys.stderr)
    print("修复：改用环境变量或受控密钥机制读取，源码中不保留可用默认值。", file=sys.stderr)
    print(f"确属误报可在该行末尾追加  # {ALLOW_MARKER}  并对该行负责。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
