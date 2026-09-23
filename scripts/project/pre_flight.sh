#!/usr/bin/env bash
# 维护者辅助预检脚本（Harness 驱动）。
# 公共、可复现的标准质量门禁请直接使用 `make check`。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if command -v harness >/dev/null 2>&1; then
    exec harness check --project "$REPO_ROOT" --run "$@"
elif [ -f "$HOME/.local/share/harness/cli.mjs" ]; then
    exec node "$HOME/.local/share/harness/cli.mjs" check --project "$REPO_ROOT" --run "$@"
else
    echo "[Info] 本地环境未检测到私有 harness 工具。"
    echo "       `make pre-flight` 为核心维护者/Harness 专属辅助入口；"
    echo "       外部开源贡献者或标准工作流请执行项目统一质量门禁: make check"
    exit 0
fi
