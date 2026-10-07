#!/usr/bin/env bash
# Explicit portable release publisher. Owner: project.
# Input: MOD_DEPLOY_ROOT, MOD_DEPLOY_USER, MOD_DEPLOY_HOST (remote), target env file.
# Default: no changes. --apply authorizes deployment; --local selects this host.
# GitHub CI never calls this script. Review rendered configuration before publishing.
# Failed health probes restore the prior current symlink; no releases are deleted.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_MODE=false
APPLY=false
for arg in "$@"; do
    case "$arg" in
        --local) LOCAL_MODE=true ;;
        --apply) APPLY=true ;;
        --help) echo 'Usage: publish.sh [--local] --apply; set MOD_DEPLOY_ROOT/USER/HOST and MOD_DEPLOY_ENV_FILE'; exit 0 ;;
        *) echo '[Error] Unknown option'; exit 2 ;;
    esac
done
ORIGIN_SECRET="${CLOUDFRONT_ORIGIN_SECRET:-}"
ORIGIN_HOST="${MOD_ORIGIN_HOST:-${MOD_PUBLIC_HOST:-}}"
if [ -n "$ORIGIN_SECRET" ] && [ -z "$ORIGIN_HOST" ]; then
    echo '[Error] CLOUDFRONT_ORIGIN_SECRET requires MOD_ORIGIN_HOST (or MOD_PUBLIC_HOST).'
    exit 1
fi
if [ -n "$ORIGIN_HOST" ] && [[ ! "$ORIGIN_HOST" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo '[Error] Invalid origin host'; exit 1
fi
if [ "$APPLY" = false ]; then
    echo 'No deployment performed. Supply --apply and explicit deployment parameters.'
    exit 2
fi
TARGET_ROOT="${MOD_DEPLOY_ROOT:?Set MOD_DEPLOY_ROOT explicitly}"
TARGET_USER="${MOD_DEPLOY_USER:?Set MOD_DEPLOY_USER explicitly}"
TARGET_ENV="${MOD_DEPLOY_ENV_FILE:?Set MOD_DEPLOY_ENV_FILE explicitly}"
TARGET_HOST="${MOD_DEPLOY_HOST:-}"
for path in "$TARGET_ROOT" "$TARGET_ENV"; do
    if [[ ! "$path" =~ ^/[A-Za-z0-9_./-]+$ ]] || [[ "$path" == / ]] || [[ "/$path/" == *'/../'* ]]; then
        echo '[Error] Target paths must be absolute without parent traversal or shell syntax'; exit 2
    fi
done
if [[ ! "$TARGET_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]; then echo '[Error] Invalid target user'; exit 2; fi
if [ "$LOCAL_MODE" = false ]; then
    if [[ ! "$TARGET_HOST" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]; then echo '[Error] Set a valid MOD_DEPLOY_HOST explicitly'; exit 2; fi
fi
TARGET_ROOT="${TARGET_ROOT%/}"
TS="$(date +%Y%m%d-%H%M%S)"
RELEASE="$TARGET_ROOT/releases/$TS"
DESTINATION="$TARGET_USER@$TARGET_HOST"
run_target() {
    if [ "$LOCAL_MODE" = true ]; then bash -c "$1"; else ssh -o StrictHostKeyChecking=yes "$DESTINATION" "$1"; fi
}
# Existing target configuration and tools are required; nothing fetches old credentials.
run_target "test -f '$TARGET_ENV' && command -v uv >/dev/null && test ! -e '$RELEASE'"
(cd "$REPO_ROOT" && make check)
(cd "$REPO_ROOT/frontend" && pnpm build)
STAGING="$(mktemp -d)"
trap 'rm -rf -- "$STAGING"' EXIT
mkdir -p "$STAGING/backend" "$STAGING/frontend" "$STAGING/scripts"
cp -R "$REPO_ROOT/backend/app" "$STAGING/backend/"
cp "$REPO_ROOT/backend/pyproject.toml" "$REPO_ROOT/backend/uv.lock" "$STAGING/backend/"
cp -R "$REPO_ROOT/frontend/dist" "$STAGING/frontend/"
cp -R "$REPO_ROOT/simulation" "$REPO_ROOT/demo-data" "$STAGING/"
for owner in project agy kiro; do cp -R "$REPO_ROOT/scripts/$owner" "$STAGING/scripts/"; done
python3 "$REPO_ROOT/scripts/project/render_deploy_config.py" \
    --root "$TARGET_ROOT/current" --user "$TARGET_USER" --env-file "$TARGET_ENV" \
    --python "$TARGET_ROOT/current/backend/.venv/bin/python" --output "$STAGING/deploy"
run_target "mkdir -p '$RELEASE'"
if [ "$LOCAL_MODE" = true ]; then
    rsync -a --exclude='__pycache__/' --exclude='output/' --exclude='tmp/' --exclude='.env*' "$STAGING/" "$RELEASE/"
else
    rsync -az -e 'ssh -o StrictHostKeyChecking=yes' --exclude='__pycache__/' --exclude='output/' --exclude='tmp/' --exclude='.env*' "$STAGING/" "$DESTINATION:$RELEASE/"
fi
run_target "uv sync --project '$RELEASE/backend' --frozen --no-dev"
PREVIOUS="$(run_target "readlink '$TARGET_ROOT/current' || true")"
if [ -n "$PREVIOUS" ] && [[ ! "$PREVIOUS" =~ ^/[A-Za-z0-9_./-]+$ ]]; then
    echo '[Error] Existing current symlink target is unsafe'; exit 2
fi
run_target "ln -sfn '$RELEASE' '$TARGET_ROOT/current' && sudo install -m 0644 '$RELEASE/deploy/mod.service' /etc/systemd/system/mod.service && sudo systemctl daemon-reload && sudo systemctl restart mod.service"
fetch_probe() {
    # Credential headers travel via stdin, never as process command arguments.
    python3 -c 'import json,os,sys
endpoint=sys.argv[1]
secret=os.getenv("CLOUDFRONT_ORIGIN_SECRET", "")
host=os.getenv("MOD_ORIGIN_HOST") or os.getenv("MOD_PUBLIC_HOST", "")
print("silent\nshow-error\nfail\nmax-time = 30")
print("url = " + json.dumps(("https://127.0.0.1" if secret else "http://127.0.0.1:8100") + endpoint))
if secret:
    print("insecure")
    print("header = " + json.dumps("Host: " + host))
    print("header = " + json.dumps("X-Origin-Secret: " + secret))' "$1" |
        run_target 'curl --config -'
}
rollback() {
    if [ -n "$PREVIOUS" ]; then
        run_target "ln -sfn '$PREVIOUS' '$TARGET_ROOT/current' && sudo systemctl restart mod.service"
    fi
    echo '[Error] Release verification failed; prior symlink restored when available.'
    exit 1
}
# Allow background cache refresh to complete; require the restored demo DB, not fallback.
READY=false
for attempt in $(seq 1 12); do
    if fetch_probe /api/health | python3 -c 'import json,sys;d=json.load(sys.stdin);sys.exit(0 if d.get("status")=="ok" else 1)' && \
        fetch_probe /api/dashboard/snapshot | python3 -c 'import json,sys;d=json.load(sys.stdin);m=d.get("meta",{});sys.exit(0 if m.get("demo") and m.get("source")=="live" and d.get("entities") else 1)'; then
        READY=true; break
    fi
    sleep 5
done
if [ "$READY" = false ]; then rollback; fi
echo 'Release verified. No timers enabled and no previous releases removed.'
