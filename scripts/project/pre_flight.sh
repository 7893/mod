#!/usr/bin/env bash
# 2026-09-11: shared local harness with compact reports. Original implementation
# below is retained as a portable fallback when this machine's harness is absent.
if [ -f /home/ubuntu/local-harness/cli.mjs ]; then
    exec node /home/ubuntu/local-harness/cli.mjs check --project /home/ubuntu/mod --run "$@"
fi
set -e

echo "=== MOD Targeted Pre-Flight Checks ==="
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || true)
UNTRACKED_FILES=$(git ls-files --others --exclude-standard 2>/dev/null || true)
ALL_FILES="$CHANGED_FILES"$'\n'"$UNTRACKED_FILES"

HAS_BACKEND=false
HAS_FRONTEND=false

if echo "$ALL_FILES" | grep -qE '^(backend/|simulation/)'; then
    HAS_BACKEND=true
fi

if echo "$ALL_FILES" | grep -qE '^frontend/'; then
    HAS_FRONTEND=true
fi

if [ "$HAS_BACKEND" = true ]; then
    echo "[Pre-flight] Checking Backend (ruff + pytest)..."
    (cd backend && .venv/bin/ruff check app tests ../simulation)
    (cd backend && .venv/bin/python -m pytest -p no:cacheprovider -q)
    echo "✓ Backend checks passed!"
else
    echo "[Pre-flight] No backend changes detected. Skipping backend tests."
fi

if [ "$HAS_FRONTEND" = true ]; then
    echo "[Pre-flight] Checking Frontend (vitest + typecheck)..."
    python3 scripts/project/lint_frontend_arbitrary_values.py
    python3 scripts/project/lint_frontend_styles.py
    (cd frontend && pnpm run typecheck)
    (cd frontend && pnpm test)
    echo "✓ Frontend checks passed!"
else
    echo "[Pre-flight] No frontend changes detected. Skipping frontend tests."
fi

echo "[Pre-flight] Checking document sync (Gate C)..."
python3 scripts/project/check_doc_sync.py
echo "=== Pre-Flight Verification PASSED ==="
