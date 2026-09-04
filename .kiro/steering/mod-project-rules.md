---
inclusion: always
---

# MOD project rules

Read and follow `AGENTS.md`, `ENFORCEMENT.md`, `CONTRIBUTING.md`, `docs/CURRENT-STATE.md`, and the relevant standards
under `docs/development/` before changing the project.

Kiro-specific temporary or diagnostic scripts must be placed under `scripts/kiro/`. Do not write scripts into
the repository root, another CLI's directory, `database/`, `generator/`, or `tools/`. The historical collaboration
state machine is retained but must not be run or maintained.
