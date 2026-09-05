# KI-008 · 前端全六屏旧 CSS 全部清零，全面契约化完成

- 状态：DONE（2026-09-04）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：A–F 全六屏已全量完成 Tailwind + CockpitPanel + 集中 Token 迁移；各屏专属旧 CSS 全部物理清零。
- 依据：`docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 迁移现状章节。
- 处理进展：
  - 2026-09-04 完成 C 屏（推广上线 RolloutView.vue）迁移，物理删除 `rollout.css`（404 行），
    中部三栏沉淀 Token `--grid-template-columns-rollout-mid`，通过 `make check` 与 1920x1080 视觉验收（Commit `eb8212a`）。
  - 2026-09-04 完成 D 屏（业务运营 OperationsView.vue）迁移，物理删除 `operations.css`（295 行），
    网格沉淀 Token `--grid-template-columns-operations` / `--grid-template-rows-operations`，通过 `make check` 与 1920x1080 视觉验收（Commit `c88e66b`）。
  - 2026-09-04 完成 E 屏（问题清单 IssuesView.vue）迁移，物理删除 `issues.css`（97 行），
    顶部栏沉淀 Token `--grid-template-columns-issues-top`，通过 `make check` 与 1920x1080 视觉验收；同步修复 KI-018 中 RolloutView 残留的 `text-[10px]`（Commit `3640b27`）。
  - 2026-09-04 完成 F 屏（智能研判 InsightsView.vue）迁移，物理删除 `insights.css`（380 行），
    网格沉淀 Token `--grid-template-columns-insights` / `--grid-template-rows-insights`，重构 `ModelContractCard.vue` 契约化，通过 `make check` 与 1920x1080 视觉验收。全站存量专属旧 CSS 正式清零归零。
- 处理结论：六屏旧 CSS 清理与 CockpitPanel 迁移全面闭环。
