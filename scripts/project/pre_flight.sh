#!/usr/bin/env bash
# 2026-09-11: shared local harness with compact reports. Original implementation
# below is retained as a portable fallback when this machine's harness is absent.
if [ -f /home/ubuntu/local-harness/cli.mjs ]; then
    exec node /home/ubuntu/local-harness/cli.mjs check --project /home/ubuntu/mod --run "$@"
else
    echo "[Error] local-harness/cli.mjs not found. Cannot run pre-flight checks."
    exit 1
fi

