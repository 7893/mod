#!/usr/bin/env python3
"""Guard high-risk facts that must stay aligned across code and living docs.

This is intentionally a small set of explicit contracts, not a claim that prose can
be fully verified by a linter. Add a contract when a cross-layer invariant has caused
or could cause a user-visible fact split.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def validate_contracts(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    lifecycle = _read(root, "backend/app/business_rules.py")
    for expected in (
        "DUAL_RUN_CONSISTENCY_RATE_MIN = 98.0",
        "CONSTRUCTION_LAG_RATE = 88.0",
        "OPENING_DATA_LAG_RATE = 88.0",
        "LAST_ACTIVE_BATCH_ID = 7",
    ):
        if expected not in lifecycle:
            errors.append(f"lifecycle policy drift: missing `{expected}`")

    for relative in (
        "frontend/src/views/OperationsView.vue",
        "frontend/src/views/IssuesView.vue",
        "frontend/src/views/InsightsView.vue",
    ):
        if "snapshot.businessRules" not in _read(root, relative):
            errors.append(f"dashboard rule source drift: {relative} bypasses businessRules")

    theme = _read(root, "frontend/src/styles/theme.css")
    scale = _read(root, "frontend/src/composables/useScaleScreen.ts")
    app = _read(root, "frontend/src/App.vue")
    if "--spacing-canvas-h: 980px" not in theme:
        errors.append("canvas contract drift: theme height is not 980px")
    if "baseHeight = 980" not in scale or "baseHeight: 980" not in app:
        errors.append("canvas contract drift: scale implementation is not 1920x980")

    broker = _read(root, "backend/app/live_projection/broker.py")
    live_doc = _read(root, "docs/development/LIVE-PROJECTION.md")
    if "OutboxReader" not in broker or "CommittedEventJournal" in broker:
        errors.append("live projection drift: broker must consume the transactional outbox only")
    for forbidden in ("RealisticSimulationEngine", "_load_units_pool"):
        if forbidden in broker:
            errors.append(f"live projection drift: broker contains `{forbidden}`")
    if "sim_event_outbox" not in live_doc:
        errors.append("live projection documentation drift: transactional outbox is not documented")

    runtime = _read(root, "simulation/runtime_service.py")
    for expected in (
        "EvolutionCoordinator",
        "auto_commit=False",
        "self.projection_writer(conn,",
    ):
        if expected not in runtime:
            errors.append(f"simulator orchestration drift: missing `{expected}`")

    writer = _read(root, "backend/app/live_projection/outbox_writer.py")
    for expected in ("FOR UPDATE", "pruned_through", "get_autocommit", "MAX_RETAINED_EVENTS"):
        if expected not in writer:
            errors.append(f"transactional outbox safety drift: missing `{expected}`")
    if "projection_journal.append" in runtime or "conn.commit(" in writer:
        errors.append("outbox transaction drift: independent journal write or writer-owned commit")

    heatwave = _read(root, "backend/app/integrations/heatwave_ml.py")
    risk_table = _read(root, "frontend/src/components/AtRiskUnitTable.vue")
    for source in ("HEATWAVE_SHAP", "RULE_BASED", "UNAVAILABLE"):
        if source not in heatwave or source not in risk_table:
            errors.append(f"model explanation provenance drift: `{source}` is not end-to-end")

    quota_capsule = _read(root, "frontend/src/components/AiQuotaCapsule.vue")
    compliance_drawer = _read(root, "frontend/src/components/ComplianceInspectDrawer.vue")
    for relative, content in (
        ("frontend/src/components/AiQuotaCapsule.vue", quota_capsule),
        ("frontend/src/components/ComplianceInspectDrawer.vue", compliance_drawer),
    ):
        for forbidden in ("$0.00", "零费用", "免费日配额"):
            if forbidden in content:
                errors.append(f"AI quota billing boundary drift: {relative} contains `{forbidden}`")
    if "不代表 Cloudflare 账户账单" not in quota_capsule:
        errors.append("AI quota scope drift: quota capsule lacks the account-billing disclaimer")
    for forbidden in ("handleDispatch", "handleEnrich", "/dispatch", "/enrich"):
        if forbidden in compliance_drawer:
            errors.append(f"read-only governance drawer drift: found online write marker `{forbidden}`")

    api = _read(root, "backend/app/api.py")
    for forbidden in (
        '@router.patch("/organizations/{org_id}")',
        '@router.post("/governance/issues/{issue_id}/dispatch")',
        '@router.post("/governance/issues/{issue_id}/enrich")',
    ):
        if forbidden in api:
            errors.append(f"read-only display API drift: found write route `{forbidden}`")

    # Deployment topology and recovery boundaries are repeated across several living
    # documents. Keep the small set of dangerous, previously observed contradictions
    # mechanically aligned with the implementation.
    workflow = _read(root, ".github/workflows/quality.yml")
    current_state = _read(root, "docs/CURRENT-STATE.md")
    enforcement = _read(root, "ENFORCEMENT.md")
    contributing = _read(root, "CONTRIBUTING.md")
    secrets = _read(root, "docs/development/SECRETS-AND-CONFIG.md")
    cli_policy = _read(root, "docs/development/CLI-SCRIPT-POLICY.md")
    ml_boundary = _read(root, "docs/development/ML-AI-DATA-BOUNDARY.md")
    collaboration = _read(root, "docs/development/GOVERNANCE-AND-COLLABORATION.md")
    project_layout = _read(root, "PROJECT-LAYOUT.md")
    data_security = _read(root, "docs/development/DATA-AND-SECURITY-STANDARD.md")
    project_organization = _read(root, "docs/development/PROJECT-ORGANIZATION.md")
    browser_rendering = _read(root, "docs/development/CLOUDFLARE-BROWSER-RENDERING.md")
    testing_standard = _read(root, "docs/development/TESTING-STANDARD.md")
    refresh_doc = _read(root, "docs/development/DASHBOARD-REFRESH-MECHANISM.md")
    simulation_doc = _read(root, "docs/development/BUSINESS-SIMULATION-ENGINE.md")
    disaster_recovery = _read(root, "docs/runbooks/DISASTER-RECOVERY-RUNBOOK.md")
    deployment_layout = _read(root, "docs/operations/USA-DEPLOYMENT-LAYOUT.md")

    if "  deploy:" not in workflow or "needs: check" not in workflow:
        errors.append("CI/CD drift: quality workflow must deploy only after checks")
    if "不包含部署或生产访问" in current_state:
        errors.append("CI/CD documentation drift: CURRENT-STATE denies the deploy job")
    if "生产与工作区分离" not in enforcement:
        errors.append("deployment topology drift: ENFORCEMENT lacks JPA/USA separation")

    stale_topology_phrases = {
        "docs/development/SECRETS-AND-CONFIG.md": (secrets, "无跨主机自动部署"),
        "docs/development/CLI-SCRIPT-POLICY.md": (cli_policy, "无独立部署主机"),
        "docs/development/GOVERNANCE-AND-COLLABORATION.md": (collaboration, "同机生产"),
        "PROJECT-LAYOUT.md": (project_layout, "同一主机同时承载生产"),
        "docs/development/DATA-AND-SECURITY-STANDARD.md": (data_security, "ADR-0006"),
        "docs/development/PROJECT-ORGANIZATION.md": (project_organization, "ADR-0006"),
        "docs/development/CLOUDFLARE-BROWSER-RENDERING.md": (browser_rendering, "ADR-0006"),
        "CONTRIBUTING.md": (contributing, "同机承载生产"),
        "docs/development/TESTING-STANDARD.md": (testing_standard, "系统级 `mod-api`"),
    }
    for relative, (text, forbidden) in stale_topology_phrases.items():
        if forbidden in text:
            errors.append(f"deployment topology documentation drift: {relative} contains `{forbidden}`")

    for forbidden in ("只读 `/api/v2`", "本机持久日志", "逻辑见 `simulation/models.py`", "backend/app/simulation/"):
        if forbidden in current_state:
            errors.append(f"CURRENT-STATE implementation drift: contains `{forbidden}`")
    if "sim_event_outbox" not in current_state:
        errors.append("CURRENT-STATE implementation drift: transactional outbox is not documented")
    for expected in ("2026-09-17 修正", "现行业务库名为 `mod`", "现行生产位于 USA"):
        if expected not in ml_boundary:
            errors.append(f"ML/AI boundary documentation drift: missing `{expected}`")
    for forbidden in ("backend/app/simulation/", "mod_s_v2", "独立 systemd 服务"):
        if forbidden in simulation_doc:
            errors.append(f"simulation documentation drift: contains `{forbidden}`")

    if "/api/v2/" in refresh_doc or "fixKeys" in refresh_doc:
        errors.append("dashboard refresh documentation drift: legacy API prefix or key converter restored")
    for expected in ("/api/dashboard/snapshot", "/api/dashboard/refresh-meta", "meta.source"):
        if expected not in refresh_doc:
            errors.append(f"dashboard refresh documentation drift: missing `{expected}`")

    expected_timers = {
        "mod-daily-briefing.timer",
        "mod-heatwave-watchdog.timer",
        "mod-ml-retrain.timer",
    }
    actual_timers = {path.name for path in (root / "deploy").glob("mod-*.timer")}
    if actual_timers != expected_timers:
        errors.append(
            "deployment timer drift: expected "
            f"{sorted(expected_timers)}, found {sorted(actual_timers)}"
        )
    for retired in ("mod-api.service", "mod-simulator.service", "mod-backup.service", "mod-backup.timer"):
        if (root / "deploy" / retired).exists():
            errors.append(f"retired deployment unit restored: deploy/{retired}")
    for expected in ("mod.service", *sorted(expected_timers), "/api/health"):
        if expected not in deployment_layout:
            errors.append(f"deployment layout drift: missing `{expected}`")

    for expected in ("保留 1 天", "PITR 关闭", "没有第二套数据库副本"):
        if expected not in disaster_recovery:
            errors.append(f"recovery boundary drift: runbook missing `{expected}`")

    return errors


def main() -> int:
    errors = validate_contracts()
    if errors:
        for error in errors:
            print(f"  SEMANTIC CONTRACT  {error}")
        return 1
    print("[semantic-contracts] OK: high-risk cross-layer facts remain aligned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
