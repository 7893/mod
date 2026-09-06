#!/usr/bin/env bash
# publish_frontend.sh — Atomic frontend release via symlink swap.
#
# Usage: bash scripts/project/publish_frontend.sh
#
# What it does:
#   1. Builds frontend into a timestamped releases/ directory (isolated from production)
#   2. Runs make check to verify everything is green
#   3. Atomically switches the `frontend/current` symlink to the new release
#   4. Reloads Nginx (no downtime — symlink swap is atomic at OS level)
#   5. Verifies the live site returns HTTP 200
#   6. Prunes releases older than the last 5 (keeps disk clean)
#
# Rollback: ln -sfn /home/ubuntu/mod/frontend/releases/<prev_ts> /home/ubuntu/mod/frontend/current && sudo systemctl reload nginx
#
# This script must be run by the controller (主控) after explicit authorization.
# agy and other agents must NOT call this script directly — they build to releases/ via pnpm build only.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
RELEASES_DIR="$FRONTEND_DIR/releases"
CURRENT_LINK="$FRONTEND_DIR/current"
TS="$(date +%Y%m%d-%H%M%S)"
RELEASE_DIR="$RELEASES_DIR/$TS"

echo "===== Frontend Publish: $TS ====="

# 1. Build into dist (standard), then copy to isolated release directory
echo "[1/5] Building frontend (output: dist/) ..."
cd "$FRONTEND_DIR"
pnpm build 2>&1 | tail -3

echo "  Copying dist/ -> $RELEASE_DIR"
cp -r "$FRONTEND_DIR/dist" "$RELEASE_DIR"

# 2. Run full checks (backend + frontend + doc-links)
echo "[2/5] Running make check ..."
cd "$REPO_ROOT"
make check

# 3. Atomic symlink swap (ln -sfn is atomic on Linux)
echo "[3/5] Switching symlink: current -> $RELEASE_DIR"
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
echo "  Symlink now: $(readlink "$CURRENT_LINK")"

# 4. Reload Nginx
echo "[4/5] Reloading Nginx ..."
sudo systemctl reload nginx
sleep 2

# 5. Verify live site
echo "[5/5] Verifying live site ..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://mod.fuming.name/)
if [ "$HTTP_CODE" != "200" ]; then
  echo "ERROR: Live site returned $HTTP_CODE — rolling back!"
  PREV=$(ls -1t "$RELEASES_DIR" | sed -n '2p')
  if [ -n "$PREV" ]; then
    ln -sfn "$RELEASES_DIR/$PREV" "$CURRENT_LINK"
    sudo systemctl reload nginx
    echo "Rolled back to $PREV"
  fi
  exit 1
fi
echo "  Live site OK (HTTP $HTTP_CODE)"

# 6. Prune old releases (keep last 5)
echo "[6/6] Pruning old releases (keep last 5) ..."
ls -1t "$RELEASES_DIR" | tail -n +6 | while read -r old; do
  echo "  Removing old release: $old"
  rm -rf "${RELEASES_DIR:?}/$old"
done

echo "===== Publish complete: $TS ====="
echo "  Rollback cmd: ln -sfn $RELEASES_DIR/<prev_ts> $CURRENT_LINK && sudo systemctl reload nginx"
