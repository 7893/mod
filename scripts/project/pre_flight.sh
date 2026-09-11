#!/usr/bin/env bash
# 2026-09-11: shared local harness with compact reports. Original implementation
# below is retained as a portable fallback when this machine's harness is absent.
if [ -f ${HOME}/local-harness/cli.mjs ]; then
    exec node ${HOME}/local-harness/cli.mjs check --project ${MOD_PROJECT_ROOT} --run "$@"
else
    echo "[Error] local-harness/cli.mjs not found. Cannot run pre-flight checks."
    exit 1
fi

