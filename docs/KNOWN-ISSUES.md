# 已知问题登记册

更新日期：2026-09-05
状态：现行
适用范围：已发现但尚未修复的业务、数据、系统与清理类问题

本文只登记问题，不作为执行授权。修复任一条目前需按 `ENFORCEMENT.md` 与
`docs/development/DATA-AND-SECURITY-STANDARD.md` 确认范围、只读核查、备份与授权。
体制类改进（约束、规范、文档、组织、流程）不在本文，另行推进。

新需求/新功能/待办任务请在 GitHub Issues 中登记（模板位于 `.github/ISSUE_TEMPLATE/`），
已发现问题与缺陷登记于此看板。每个已知问题的详细背景、分析与处置记录见 `docs/issues/`。

条目状态取值：OPEN（待处理）、IN-PROGRESS（处理中）、DONE（已完成，保留供追溯）。

---

## 活跃问题（OPEN / IN-PROGRESS）

无（当前全量已知问题已全部闭环）。

## 已关闭问题（DONE）

| 编号 | 标题 | 状态 | 优先级 | 链接 |
|---|---|---|---|---|
| KI-015 | risk_flag 分类模型在训练集上自评分，准确率不可信（真训练评估与每日重训交付） | DONE | P1 | [详情](issues/KI-015-risk-flag-model-self-scoring.md) |
| KI-027 | 版本/模式标记深度整治（唯一正统，去 v1/v2/v3、去 s_v2） | DONE | P1 | [详情](issues/KI-027-version-mode-marker-cleanup.md) |
| KI-019 | 文档组织治理（历史归拢 + 编号 + issue 分级 + 立规） | DONE | P2 | [详情](issues/KI-019-documentation-governance.md) |
| KI-001 | 省级今日新增恒为 0，与总览不一致 | DONE | P1 | [详情](issues/KI-001-provincial-today-added-zero.md) |
| KI-002 | 单据发生日期与快照基线日期塌缩为同一天 | DONE | P2 | [详情](issues/KI-002-docs-added-asof-date-collapse.md) |
| KI-003 | fallback 快照文件由缺陷 SQL 生成，内含上述不一致 | DONE | P2 | [详情](issues/KI-003-fallback-snapshot-inconsistency.md) |
| KI-004 | 生产库行数与文档记载不符 | DONE | P2 | [详情](issues/KI-004-db-row-count-doc-drift.md) |
| KI-005 | 未上线单位历史单据已被物理删除，约 1500 万行，无恢复副本 | DONE | P1 | [详情](issues/KI-005-unlaunched-org-history-deletion.md) |
| KI-006 | USA 生产 Cloudflare AI 开关与文档口径不一致 | DONE | P3 | [详情](issues/KI-006-cloudflare-ai-switch-doc-mismatch.md) |
| KI-007 | 本地已修复内容尚未部署到 USA | DONE | P2 | [详情](issues/KI-007-local-fixes-not-deployed-to-usa.md) |
| KI-008 | 前端全六屏旧 CSS 全部清零，全面契约化完成 | DONE | P2 | [详情](issues/KI-008-frontend-legacy-css-cleared.md) |
| KI-009 | 前端构建存在超过 500kB 的 chunk 警告 | DONE | P3 | [详情](issues/KI-009-frontend-build-chunk-warning.md) |
| KI-010 | database/、generator/ 内无凭据的废弃文件待清理 | DONE | P3 | [详情](issues/KI-010-clean-obsolete-generator-scripts.md) |
| KI-011 | 历史明文凭据仍存在于 archive 内容与 Git 历史中 | DONE | P1 | [详情](issues/KI-011-legacy-credentials-in-archive-git.md) |
| KI-012 | CI 侧闸门缺失（本地 hook 可被绕过） | DONE | P1 | [详情](issues/KI-012-missing-ci-quality-gates.md) |
| KI-013 | 声明式权限仅覆盖单一 CLI（绑定停用流程部分已消除） | DONE | P2 | [详情](issues/KI-013-declarative-permission-single-cli.md) |
| KI-014 | 上 GitHub 公开仓库前的净化工程 | DONE | P1 | [详情](issues/KI-014-public-repository-sanitization.md) |
| KI-016 | 提交信息格式无机制校验 | DONE | P2 | [详情](issues/KI-016-commit-message-format-validation.md) |
| KI-017 | 存量数据清洗与主数据重整（处置三：清洗后由新引擎接管） | DONE | P1 | [详情](issues/KI-017-stock-data-governance.md) |
| KI-018 | 前端契约缺自动校验（Tailwind 任意值漏网） | DONE | P2 | [详情](issues/KI-018-frontend-contract-arbitrary-values-lint.md) |
| KI-020 | 自动生成 CHANGELOG | DONE | P3 | [详情](issues/KI-020-automated-changelog-generation.md) |
| KI-021 | 文档在线可视化发布（供离线审阅与反馈） | DONE | P3 | [详情](issues/KI-021-online-documentation-visualization.md) |
| KI-022 | 前端迁移收尾小修 | DONE | P2 | [详情](issues/KI-022-frontend-migration-finishing-fixes.md) |
| KI-023 | AutoML 就绪状态与模型质量分带有硬编码兜底，可能展示未生成的结果 | DONE | P1 | [详情](issues/KI-023-automl-hardcoded-fallback.md) |
| KI-024 | 缺少新需求/任务的正式登记入口 | DONE | P2 | [详情](issues/KI-024-formal-entry-for-new-requirements.md) |
| KI-025 | 文档与代码事实的同步无机制强制（仅靠规范与自觉） | DONE | P2 | [详情](issues/KI-025-doc-code-sync-semi-mechanism.md) |
| KI-026 | 拟真引擎第二步：建设管控主线 + B模式生命周期推进器 | DONE | P1 | [详情](issues/KI-026-simulation-mainline.md) |
| KI-026-3 | 拟真引擎第三步：常驻后台服务·持续实时增长 | DONE | P1 | [详情](issues/KI-026-3-simulation-runtime-service.md) |
