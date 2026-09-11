# Claude Code instructions

Read and follow `AGENTS.md`, `ENFORCEMENT.md`, `CONTRIBUTING.md`, `docs/CURRENT-STATE.md`, and the relevant
standards under `docs/development/` before changing the project.

Claude-specific temporary or diagnostic scripts must be placed under `scripts/claude/`. Do not write scripts
into the repository root, another CLI's directory, `database/`, `generator/`, or `tools/`.

For read-only database queries or rapid pre-flight checks, leverage the repository's shared `pi` harness or scripts:
- Run `make sim-status` to inspect the simulator before touching deployments.
- Use `mod_db_query` via `pi -p "Use mod_db_query ..."` or `scripts/project/safe_db_query.py` instead of raw MySQL commands.
- Run `make pre-flight` for fast incremental testing.
