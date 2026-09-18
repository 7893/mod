#!/usr/bin/env bash
# 2026-09-11: shared local harness with compact reports. Original implementation
# below is retained as a portable fallback when this machine's harness is absent.
if command -v harness >/dev/null 2>&1; then
    exec harness check --project /home/ubuntu/mod --run "$@"
elif [ -f "$HOME/.local/share/harness/cli.mjs" ]; then
    exec node "$HOME/.local/share/harness/cli.mjs" check --project /home/ubuntu/mod --run "$@"
else
    echo "[Error] harness CLI not found. Cannot run pre-flight checks."
    exit 1
fi

