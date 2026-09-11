---
name: mod-governance
description: Index for document lifecycle, CURRENT-STATE sync, and release governance.
---
> **Authoritative Standard**: This skill is a condensed navigation index. For full governance rules, see [DOCUMENTATION-STANDARD.md](../../../docs/development/DOCUMENTATION-STANDARD.md) and [DOCUMENTATION-LIFECYCLE.md](../../../docs/development/DOCUMENTATION-LIFECYCLE.md).

# MOD Governance Index

This skill serves as a navigation index. **Do not guess rules; read the referenced documents on-demand.**

## What to Read When...

- **Changing any core code**: Read `docs/development/DOCUMENTATION-STANDARD.md`. You MUST update `docs/CURRENT-STATE.md` in the same commit.
- **Managing Known Issues (KIs)**: Read `docs/development/DOCUMENTATION-LIFECYCLE.md`.
- **Modifying history docs**: STOP. History docs under `docs/history/` are immutable and protected by `MANIFEST.sha256`.
- **Publishing/Deploying**: Read `docs/development/DOCUMENTATION-STANDARD.md` and use `scripts/project/publish.sh` AFTER running `make sim-status`.

## Validation
Governance is strictly enforced by `make check` (Gate C doc sync, history integrity, links).
