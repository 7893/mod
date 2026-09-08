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
SIMULATOR_STATUS_URL="https://mod.fuming.name/api/simulator/status"

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

# 2. 复制后端及后台服务
echo "[2/8] 打包后端及后台常驻写服务 release..."
mkdir -p "$BE_RELEASE_DIR"
cp -r "$REPO_ROOT/backend/app/." "$BE_RELEASE_DIR/"
ln -s . "$BE_RELEASE_DIR/app"
cp -r "$REPO_ROOT/simulation" "$BE_RELEASE_DIR/"
cp -r "$REPO_ROOT/scripts" "$BE_RELEASE_DIR/"
echo "  后端与后台写服务 release: $BE_RELEASE_DIR"

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

# 5. reload Nginx + restart mod-api + restart mod-simulator
echo "[5/8] reload Nginx + restart mod-api + restart mod-simulator..."
sudo systemctl reload nginx
sudo systemctl restart mod-api
sudo systemctl restart mod-simulator
sleep 4

# 6. 验证
echo "[6/8] 验证线上服务与接口健康探针..."
# 探针 1: KI-046 验证 /api/health (HTTP 200 + DB 连接健康)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")
if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: /api/health 线上返回 $HTTP_CODE，自动回滚..."
    [ -n "$PREV_FE" ] && ln -sfn "$PREV_FE" "$FE_CURRENT"
    [ -n "$PREV_BE" ] && ln -sfn "$PREV_BE" "$BE_CURRENT"
    sudo systemctl reload nginx
    sudo systemctl restart mod-api
    sudo systemctl restart mod-simulator
    echo "已回滚到: 前端=$PREV_FE  后端=$PREV_BE"
    exit 1
fi

HEALTH_BODY=$(curl -s "$HEALTH_URL")
if ! echo "$HEALTH_BODY" | python3 -c '
import sys, json
data = json.load(sys.stdin)
if data.get("status") != "ok":
    sys.exit(1)
db = data.get("database")
tz = data.get("session_timezone")
now = data.get("now_cst")
if not db or not now:
    sys.exit(1)
print(f"  Health probe OK: DB={db} tz={tz} now={now}")
'; then
    echo "ERROR: /api/health 数据库探针返回异常或非健康状态，自动回滚..."
    [ -n "$PREV_FE" ] && ln -sfn "$PREV_FE" "$FE_CURRENT"
    [ -n "$PREV_BE" ] && ln -sfn "$PREV_BE" "$BE_CURRENT"
    sudo systemctl reload nginx
    sudo systemctl restart mod-api
    sudo systemctl restart mod-simulator
    echo "已回滚到: 前端=$PREV_FE  后端=$PREV_BE"
    exit 1
fi


# 探针 2: KI-039 验证 /api/simulator/status
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SIMULATOR_STATUS_URL")
if [ "$STATUS_CODE" != "200" ]; then
    echo "ERROR: /api/simulator/status 线上返回 $STATUS_CODE，自动回滚..."
    [ -n "$PREV_FE" ] && ln -sfn "$PREV_FE" "$FE_CURRENT"
    [ -n "$PREV_BE" ] && ln -sfn "$PREV_BE" "$BE_CURRENT"
    sudo systemctl reload nginx
    sudo systemctl restart mod-api
    sudo systemctl restart mod-simulator
    echo "已回滚到: 前端=$PREV_FE  后端=$PREV_BE"
    exit 1
fi

STATUS_BODY=$(curl -s "$SIMULATOR_STATUS_URL")
if ! echo "$STATUS_BODY" | python3 -c '
import sys, json
data = json.load(sys.stdin)
required = ["service", "status", "fresh"]
if not all(k in data for k in required):
    sys.exit(1)
if "Internal Server Error" in json.dumps(data):
    sys.exit(1)
svc = data.get("service")
st = data.get("status")
fr = data.get("fresh")
print(f"  Simulator probe OK: service={svc} status={st} fresh={fr}")
'; then
    echo "ERROR: /api/simulator/status 响应契约异常，自动回滚..."
    [ -n "$PREV_FE" ] && ln -sfn "$PREV_FE" "$FE_CURRENT"
    [ -n "$PREV_BE" ] && ln -sfn "$PREV_BE" "$BE_CURRENT"
    sudo systemctl reload nginx
    sudo systemctl restart mod-api
    sudo systemctl restart mod-simulator
    echo "已回滚到: 前端=$PREV_FE  后端=$PREV_BE"
    exit 1
fi

# 探针 3: KI-061 验证 /api/dashboard/snapshot 字段契约 (C3/D3/D6 字段完整)
SNAPSHOT_URL="https://mod.fuming.name/api/dashboard/snapshot"
SNAPSHOT_BODY=$(curl -s "$SNAPSHOT_URL")
if ! echo "$SNAPSHOT_BODY" | python3 -c '
import sys, json
data = json.load(sys.stdin)
if not data.get("rolloutTrend"):
    sys.exit(1)
if not data.get("operationsTrend"):
    sys.exit(1)
ops = data.get("operations", {})
if "dualRunConsistent" not in ops or "dualRunInconsistent" not in ops:
    sys.exit(1)
print(f"  Snapshot contract OK: rolloutTrend={len(data[\"rolloutTrend\"])} opsTrend={len(data[\"operationsTrend\"])}")
'; then
    echo "ERROR: /api/dashboard/snapshot 契约缺失 (C3/D3/D6 缺失)，自动回滚..."
    [ -n "$PREV_FE" ] && ln -sfn "$PREV_FE" "$FE_CURRENT"
    [ -n "$PREV_BE" ] && ln -sfn "$PREV_BE" "$BE_CURRENT"
    sudo systemctl reload nginx
    sudo systemctl restart mod-api
    sudo systemctl restart mod-simulator
    echo "已回滚到: 前端=$PREV_FE  后端=$PREV_BE"
    exit 1
fi

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
echo "  回滚命令（后端及常驻）: ln -sfn $BE_RELEASES/<prev_ts> $BE_CURRENT && sudo systemctl restart mod-api mod-simulator"
echo "=========================================="
