#!/usr/bin/env python3
"""Generate a changelog with the project-pinned git-cliff contract.

Owner: project governance tooling.
Input: Git history, cliff.toml, .git-cliff-baseline, and git-cliff 2.13.1.
Output: stdout by default, or the explicit --output path.
Risk: read-only unless --output is supplied; never creates tags, commits, or releases.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSION = "2.13.1"


def resolve_binary() -> str:
    configured = os.environ.get("MOD_GIT_CLIFF_BIN")
    binary = configured or shutil.which("git-cliff")
    if not binary:
        raise RuntimeError(
            "git-cliff 2.13.1 未找到；设置 MOD_GIT_CLIFF_BIN 指向经校验的临时二进制"
        )
    version = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if EXPECTED_VERSION not in version:
        raise RuntimeError(f"需要 git-cliff {EXPECTED_VERSION}，实际为 {version}")
    return binary


def build_command(binary: str, baseline: str, revision: str, output: Path | None) -> list[str]:
    command = [
        binary,
        "--config",
        str(ROOT / "cliff.toml"),
        f"{baseline}..{revision}",
    ]
    if output is not None:
        command.extend(["--output", str(output)])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="用锁定版本 git-cliff 生成 CHANGELOG。")
    parser.add_argument("--revision", default="HEAD", help="生成终点，默认 HEAD")
    parser.add_argument("--output", type=Path, help="显式写入路径；默认只输出到 stdout")
    args = parser.parse_args()

    baseline = (ROOT / ".git-cliff-baseline").read_text(encoding="utf-8").strip()
    try:
        binary = resolve_binary()
        result = subprocess.run(
            build_command(binary, baseline, args.revision, args.output),
            cwd=ROOT,
            text=True,
            check=True,
            capture_output=args.output is None,
        )
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[generate-changelog] {exc}", file=sys.stderr)
        return 1
    if args.output is None:
        print(result.stdout, end="")
    else:
        print(f"[generate-changelog] wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
