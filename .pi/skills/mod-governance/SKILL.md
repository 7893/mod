---
name: mod-governance
description: Document lifecycle, CURRENT-STATE.md synchronization, atomic release, and CI check governance.
---
> **Authoritative Standard**: This skill is a condensed execution reference. For full governance rules, see [DOCUMENTATION-STANDARD.md](../../../docs/development/DOCUMENTATION-STANDARD.md) and [DOCUMENTATION-LIFECYCLE.md](../../../docs/development/DOCUMENTATION-LIFECYCLE.md).


# MOD Governance & Release Skill

## 1. 状态同步铁律 (CURRENT-STATE Sync Rule)
- Whenever any core file (`backend/app/*`, `frontend/src/*`, `simulation/*`, `deploy/*`) is modified:
  - **`docs/CURRENT-STATE.md` MUST be updated in the same change/commit.**
  - Failure to update `docs/CURRENT-STATE.md` will immediately fail `make check` via `check_doc_sync.py` (ENFORCEMENT.md Gate C).

## 2. 历史档案只读与不可变 (Immutable History)
- Files under `docs/history/` are protected by `MANIFEST.sha256`.
- Never modify or delete existing frozen history documents.
- Any attempt to alter historical documents will fail `check_history_integrity.py`.

## 3. 发布与部署验证 (Publish Workflow)
- Use `scripts/project/publish.sh` for atomic production deployment.
- Deployment steps:
  1. Frontend build
  2. Backend & simulator release packaging
  3. `make check` (all tests, linters, and governance scripts must pass)
  4. Symlink atomic switch (`current -> releases/<timestamp>`)
  5. Reload Nginx and restart systemd services (`mod-api`, `mod-simulator`)
  6. Dual health probes (`/api/health`, `/api/simulator/status`, `/api/dashboard/snapshot`)
  7. Automatic rollback if any probe fails.
