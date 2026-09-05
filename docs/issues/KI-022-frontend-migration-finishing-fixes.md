# KI-022 · 前端迁移收尾小修

- 状态：DONE（2026-09-04）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 背景：六屏 CockpitPanel 迁移完成并已部署验收，遗留两处小项，现已全面修复闭环。
- 处理结果：
  1. **DataView 统一迁移与旧组件清零**：`frontend/src/views/DataView.vue` 全面改用 `CockpitPanel` + `MetricGrid` + 纯 Tailwind，全站组件范式彻底统一；旧存量组件 `frontend/src/components/Panel.vue` 已彻底物理删除。
  2. **Arbitrary value 治理与边界落定**：`OperationsView.vue` 中散写的 `grid-cols-[100px_1fr_80px]` 沉淀入 `theme.css`（`--grid-template-columns-ops-volume`），`min-w-[180px]` 规范化为标准 `min-w-44`；并在 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 契约三中正式明确 arbitrary value 的允许/禁止边界（禁止用于字号、颜色、间距；受控允许图表/弹性容器的防塌陷物理上下界 guardrails）。
- 关联：KI-008（六屏迁移，已全量完成）、KI-018（前端契约自动校验）。
