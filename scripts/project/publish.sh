#!/usr/bin/env bash
# publish.sh — 前后端统一原子发布脚本（软链切换模式）
#
# 用法：bash scripts/project/publish.sh
#
# 执行步骤：
#   1. 构建前端到 frontend/releases/<ts>/
#   2. 复制后端 app/ 到 backend/releases/<ts>/
#   3. 运行 make check（全绿才继续）
#   4. 原子切换前后端软链
#   5. reload Nginx + restart mod-api
#   6. 验证线上 HTTP 200 + /api/health
#   7. 失败时自动回滚到上一版本
#   8. 清理旧 release（保留最近 5 个）
#
# 回滚命令：
#   后端：ln -sfn /home/ubuntu/mod/backend/releases/<prev_ts> backend/current && sudo systemctl restart mod-api
#   前端：ln -sfn /home/ubuntu/mod/frontend/releases/<prev_ts> frontend/current && sudo systemctl reload nginx
#
# 本脚本必须由主控（主控 agent）在获得明确授权后运行。
# agy 等执行 agent 不得直接调用本脚本。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"

BE_RELEASES="$REPO_ROOT/backend/releases"
BE_CURRENT="$REPO_ROOT/backend/current"
BE_RELEASE_DIR="$BE_RELEASES/$TS"

FE_RELEASES="$REPO_ROOT/frontend/releases"
FE_CURRENT="$REPO_ROOT/frontend/current"
FE_RELEASE_DIR="$FE_RELEASES/$TS"

HEALTH_URL="https://mod.fuming.name/api/health"

echo "=========================================="
echo "  统一发布  $TS"
echo "=========================================="

# 1. 构建前端
echo "[1/8] 构建前端..."
cd "$REPO_ROOT/frontend"
pnpm build 2>&1 | tail -3
mkdir -p "$FE_RELEASE_DIR"
cp -r "$REPO_ROOT/frontend/dist/." "$FE_RELEASE_DIR/"
echo "  前端 release: $FE_RELEASE_DIR"

# 2. 复制后端 app/
echo "[2/8] 复制后端 app/..."
mkdir -p "$BE_RELEASE_DIR"
cp -r "$REPO_ROOT/backend/app/." "$BE_RELEASE_DIR/"
echo "  后端 release: $BE_RELEASE_DIR"

# 3. make check
echo "[3/8] 运行 make check..."
cd "$REPO_ROOT"
make check

# 4. 原子切换软链
echo "[4/8] 切换软链..."
PREV_FE=$(readlink "$FE_CURRENT" 2>/dev/null || echo "")
PREV_BE=$(readlink "$BE_CURRENT" 2>/dev/null || echo "")
ln -sfn "$FE_RELEASE_DIR" "$FE_CURRENT"
ln -sfn "$BE_RELEASE_DIR" "$BE_CURRENT"
echo "  前端: $FE_CURRENT -> $FE_RELEASE_DIR"
echo "  后端: $BE_CURRENT -> $BE_RELEASE_DIR"

# 5. reload Nginx + restart mod-api
echo "[5/8] reload Nginx + restart mod-api..."
sudo systemctl reload nginx
sudo systemctl restart mod-api
sleep 4

# 6. 验证
echo "[6/8] 验证线上健康..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")
if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: 线上返回 $HTTP_CODE，自动回滚..."
    [ -n "$PREV_FE" ] && ln -sfn "$PREV_FE" "$FE_CURRENT"
    [ -n "$PREV_BE" ] && ln -sfn "$PREV_BE" "$BE_CURRENT"
    sudo systemctl reload nginx
    sudo systemctl restart mod-api
    echo "已回滚到: 前端=$PREV_FE  后端=$PREV_BE"
    exit 1
fi
echo "  线上 OK（HTTP $HTTP_CODE）"
curl -s "$HEALTH_URL" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  DB: {d[\"database\"]}  时间: {d[\"now_cst\"]}')" 2>/dev/null || true

# 7. 清理旧 release（保留最近 5 个）
echo "[7/8] 清理旧 release（保留最近 5 个）..."
for dir in "$FE_RELEASES" "$BE_RELEASES"; do
    ls -1t "$dir" | tail -n +6 | while read -r old; do
        echo "  删除旧 release: $dir/$old"
        rm -rf "${dir:?}/$old"
    done
done

echo "[8/8] 完成"
echo "=========================================="
echo "  发布成功: $TS"
echo "  回滚命令（前端）: ln -sfn $FE_RELEASES/<prev_ts> $FE_CURRENT && sudo systemctl reload nginx"
echo "  回滚命令（后端）: ln -sfn $BE_RELEASES/<prev_ts> $BE_CURRENT && sudo systemctl restart mod-api"
echo "=========================================="
