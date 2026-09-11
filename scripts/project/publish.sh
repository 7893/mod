#!/usr/bin/env bash
# publish.sh — 前后端统一原子发布脚本（JPA 开发机 -> USA 生产机远程软链发布模式）
#
# 用法：bash scripts/project/publish.sh [--local]
#
# 执行步骤：
#   1. 构建前端到 frontend/releases/<ts>/
#   2. 复制后端 app/ 到 backend/releases/<ts>/
#   3. 运行 make check（全绿才继续）
#   4. 推送打包产物至 USA 生产机（或本地切换，若指定 --local）
#   5. 原子切换前后端软链
#   6. reload Nginx + restart mod-api + restart mod-simulator
#   7. 验证线上 HTTP 200 + 核心健康探针（/api/health, /api/simulator/status, /api/dashboard/snapshot）
#   8. 失败时自动回滚到上一版本
#   9. 清理旧 release（保留最近 5 个）
#
# 回滚命令（USA 生产机）：
#   后端：ssh usa "ln -sfn /home/ubuntu/mod/backend/releases/<prev_ts> /home/ubuntu/mod/backend/current && sudo systemctl restart mod-api mod-simulator"
#   前端：ssh usa "ln -sfn /home/ubuntu/mod/frontend/releases/<prev_ts> /home/ubuntu/mod/frontend/current && sudo systemctl reload nginx"
#
# 本脚本必须由项目 Owner（用户）或主控 Agent 运行，或在其明确授权下由被授权的 Agent（如执行 Agent）调用。
# 未获得项目 Owner 或主控 Agent 显式授权时，任何 Agent 严禁擅自调用本脚本。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"

LOCAL_MODE=false
if [[ "${1:-}" == "--local" ]]; then
    LOCAL_MODE=true
fi

REMOTE_HOST="usa"
REMOTE_ROOT="/home/ubuntu/mod"

BE_RELEASES="$REPO_ROOT/backend/releases"
BE_CURRENT="$REPO_ROOT/backend/current"
BE_RELEASE_DIR="$BE_RELEASES/$TS"

FE_RELEASES="$REPO_ROOT/frontend/releases"
FE_CURRENT="$REPO_ROOT/frontend/current"
FE_RELEASE_DIR="$FE_RELEASES/$TS"

ORIGIN_SECRET="${CLOUDFRONT_ORIGIN_SECRET:-$(grep -m 1 -oP 'http_x_origin_secret != "\K[^"]+' /etc/nginx/sites-available/mod.fuming.name 2>/dev/null || echo '')}"  # secret-scan: allow

echo "=========================================="
if [ "$LOCAL_MODE" = true ]; then
    echo "  统一发布（本地模式）  $TS"
else
    echo "  统一发布（JPA 开发机 -> USA 生产机）  $TS"
fi
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

if [ "$LOCAL_MODE" = true ]; then
    # 本地切换软链
    echo "[4/8] 切换本地软链..."
    PREV_FE=$(readlink "$FE_CURRENT" 2>/dev/null || echo "")
    PREV_BE=$(readlink "$BE_CURRENT" 2>/dev/null || echo "")
    ln -sfn "$FE_RELEASE_DIR" "$FE_CURRENT"
    ln -sfn "$BE_RELEASE_DIR" "$BE_CURRENT"
    echo "  前端: $FE_CURRENT -> $FE_RELEASE_DIR"
    echo "  后端: $BE_CURRENT -> $BE_RELEASE_DIR"

    echo "[5/8] reload Nginx + restart mod-api + restart mod-simulator..."
    sudo systemctl reload nginx
    sudo systemctl restart mod-api
    sudo systemctl restart mod-simulator
    sleep 4
else
    # 远程同步与发布至 USA
    echo "[4/8] 同步产物至 USA 生产机..."
    ssh "$REMOTE_HOST" "mkdir -p $REMOTE_ROOT/backend/releases/$TS $REMOTE_ROOT/frontend/releases/$TS $REMOTE_ROOT/deploy"
    rsync -az "$BE_RELEASE_DIR/" "$REMOTE_HOST:$REMOTE_ROOT/backend/releases/$TS/"
    rsync -az "$FE_RELEASE_DIR/" "$REMOTE_HOST:$REMOTE_ROOT/frontend/releases/$TS/"
    rsync -az "$REPO_ROOT/deploy/" "$REMOTE_HOST:$REMOTE_ROOT/deploy/"

    echo "  切换 USA 远程软链..."
    PREV_FE=$(ssh "$REMOTE_HOST" "readlink $REMOTE_ROOT/frontend/current 2>/dev/null || echo ''")
    PREV_BE=$(ssh "$REMOTE_HOST" "readlink $REMOTE_ROOT/backend/current 2>/dev/null || echo ''")
    ssh "$REMOTE_HOST" "ln -sfn $REMOTE_ROOT/frontend/releases/$TS $REMOTE_ROOT/frontend/current && ln -sfn $REMOTE_ROOT/backend/releases/$TS $REMOTE_ROOT/backend/current"

    # 同时更新本地软链保持开发机工作区与最新 release 对齐
    ln -sfn "$FE_RELEASE_DIR" "$FE_CURRENT"
    ln -sfn "$BE_RELEASE_DIR" "$BE_CURRENT"

    echo "[5/8] 远程 reload Nginx + restart mod-api + restart mod-simulator on USA..."
    ssh "$REMOTE_HOST" "sudo systemctl reload nginx && sudo systemctl restart mod-api && sudo systemctl restart mod-simulator"
    sleep 4
fi

# 6. 验证
echo "[6/8] 验证线上服务与接口健康探针..."

fetch_probe() {
    local endpoint="$1"
    if [ "$LOCAL_MODE" = true ]; then
        curl -s -k -H "Host: mod.fuming.name" -H "X-Origin-Secret: $ORIGIN_SECRET" "https://127.0.0.1$endpoint"  # secret-scan: allow
    else
        ssh "$REMOTE_HOST" "curl -s -k -H 'Host: mod.fuming.name' -H 'X-Origin-Secret: $ORIGIN_SECRET' 'https://127.0.0.1$endpoint'"  # secret-scan: allow
    fi
}

rollback() {
    echo "ERROR: 探针验证失败，自动回滚..."
    if [ "$LOCAL_MODE" = true ]; then
        [ -n "$PREV_FE" ] && ln -sfn "$PREV_FE" "$FE_CURRENT"
        [ -n "$PREV_BE" ] && ln -sfn "$PREV_BE" "$BE_CURRENT"
        sudo systemctl reload nginx
        sudo systemctl restart mod-api mod-simulator
    else
        ssh "$REMOTE_HOST" "
            [ -n '$PREV_FE' ] && ln -sfn '$PREV_FE' '$REMOTE_ROOT/frontend/current'
            [ -n '$PREV_BE' ] && ln -sfn '$PREV_BE' '$REMOTE_ROOT/backend/current'
            sudo systemctl reload nginx
            sudo systemctl restart mod-api mod-simulator
        "
    fi
    echo "已回滚到: 前端=$PREV_FE  后端=$PREV_BE"
    exit 1
}

# 探针 1: KI-046 验证 /api/health (HTTP 200 + DB 连接健康)
HEALTH_BODY=$(fetch_probe "/api/health" || echo "")
if ! echo "$HEALTH_BODY" | python3 -c '
import sys, json
raw = sys.stdin.read()
if not raw.strip():
    sys.exit(1)
data = json.loads(raw)
if data.get("status") != "ok":
    sys.exit(1)
db = data.get("database")
tz = data.get("session_timezone")
now = data.get("now_cst")
hw = data.get("heatwave", {}).get("status")
if not db or not now:
    sys.exit(1)
print(f"  Health probe OK: DB={db} tz={tz} now={now} HeatWave={hw}")
'; then
    echo "ERROR: /api/health 数据库探针返回异常或非健康状态，触发回滚..."
    rollback
fi

# 探针 2: KI-039 验证 /api/simulator/status
STATUS_BODY=$(fetch_probe "/api/simulator/status" || echo "")
if ! echo "$STATUS_BODY" | python3 -c '
import sys, json
raw = sys.stdin.read()
if not raw.strip():
    sys.exit(1)
data = json.loads(raw)
required = ["service", "status", "fresh", "enabled", "last_cycle_status", "fail_closed_tripped"]
if not all(k in data for k in required):
    sys.exit(1)
if "Internal Server Error" in json.dumps(data):
    sys.exit(1)
svc = data.get("service")
st = data.get("status")
fr = data.get("fresh")
print(f"  Simulator probe OK: service={svc} status={st} fresh={fr}")
if not (
    svc == "mod-simulator"
    and st == "RUNNING"
    and fr is True
    and data.get("enabled") is True
    and data.get("last_cycle_status") == "SUCCESS"
    and data.get("fail_closed_tripped") is False
):
    sys.exit(1)
'; then
    echo "ERROR: 模拟器非新鲜可写 SUCCESS 状态（含 dry-run/限流/熔断），触发回滚..."
    rollback
fi

# 探针 3: KI-061 验证 /api/dashboard/snapshot 字段契约 (C3/D3/D6 字段完整)
SNAPSHOT_BODY=$(fetch_probe "/api/dashboard/snapshot" || echo "")
if ! echo "$SNAPSHOT_BODY" | python3 -c '
import sys, json
raw = sys.stdin.read()
if not raw.strip():
    sys.exit(1)
data = json.loads(raw)
if not data.get("rolloutTrend"):
    sys.exit(1)
if not data.get("operationsTrend"):
    sys.exit(1)
ops = data.get("operations", {})
if "dualRunConsistent" not in ops or "dualRunInconsistent" not in ops:
    sys.exit(1)
print("  Snapshot contract OK: rolloutTrend=%d opsTrend=%d" % (len(data["rolloutTrend"]), len(data["operationsTrend"])))
'; then
    echo "ERROR: /api/dashboard/snapshot 契约缺失 (C3/D3/D6 缺失)，触发回滚..."
    rollback
fi

# 7. 清理旧 release（保留最近 5 个）
echo "[7/8] 清理旧 release（保留最近 5 个）..."
for dir in "$FE_RELEASES" "$BE_RELEASES"; do
    ls -1t "$dir" | tail -n +6 | while read -r old; do
        echo "  删除本地旧 release: $dir/$old"
        rm -rf "${dir:?}/$old"
    done
done

if [ "$LOCAL_MODE" = false ]; then
    ssh "$REMOTE_HOST" "
        for dir in '$REMOTE_ROOT/frontend/releases' '$REMOTE_ROOT/backend/releases'; do
            ls -1t \"\$dir\" | tail -n +6 | while read -r old; do
                echo \"  删除 USA 旧 release: \$dir/\$old\"
                rm -rf \"\${dir:?}/\$old\"
            done
        done
    "
fi

echo "[8/8] 完成"
echo "=========================================="
echo "  发布成功: $TS"
if [ "$LOCAL_MODE" = true ]; then
    echo "  回滚命令（前端）: ln -sfn $FE_RELEASES/<prev_ts> $FE_CURRENT && sudo systemctl reload nginx"
    echo "  回滚命令（后端及常驻）: ln -sfn $BE_RELEASES/<prev_ts> $BE_CURRENT && sudo systemctl restart mod-api mod-simulator"
else
    echo "  回滚命令（前端）: ssh usa 'ln -sfn $REMOTE_ROOT/frontend/releases/<prev_ts> $REMOTE_ROOT/frontend/current && sudo systemctl reload nginx'"
    echo "  回滚命令（后端及常驻）: ssh usa 'ln -sfn $REMOTE_ROOT/backend/releases/<prev_ts> $REMOTE_ROOT/backend/current && sudo systemctl restart mod-api mod-simulator'"
fi
echo "=========================================="
