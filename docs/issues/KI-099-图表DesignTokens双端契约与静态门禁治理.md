# KI-099 · 图表 Design Tokens 双端契约与静态门禁治理

编写日期：2026-09-17
- 状态：OPEN
- 优先级：P2
适用范围：前端设计系统、ECharts 主题配置、样式治理脚本、CI/CD 质量门禁

## 问题与证据

- **渲染层物理断层**：Tailwind 4 `@theme` 仅作用于 DOM 样式树，底层 Canvas/ECharts 无法直接消费 CSS 变量或类名，造成 Design System 在图表层断层。
- **散落硬编码与魔鬼数字**：在 2026-09-17 字号体系调整中，发现大量图表配置（如 A1 顶栏、双轨趋势图、模型契约卡等）由于缺乏图表层 Token 规范，直接硬编码 `fontSize: 9`、`10` 等魔鬼数字，改动全局 CSS 无法联动生效。
- **机器守卫缺位**：现行 `lint_frontend_arbitrary_values.py` 仅约束 Vue 模板的 Tailwind 任意值，未对 `.vue` 与 `charts/*.ts` 中的图表字号、边距等数值建立静态 AST 或正则守卫，导致破窗效应不断蔓延。

## 目标与方案

1. **建立图表专用 Design Tokens 契约**：
   在 `frontend/src/charts/tokens.ts` 中建立类型安全的只读 Token 常量系统，涵盖字号阶梯（micro/caption/body/axis/subMetric/kpi）、栅格间距（grid margins）、柱宽线宽（barWidth/lineWidth）以及圆角半径，与 `theme.css` 实现语义对齐。
2. **新增图表静态治理门禁**：
   新增 `scripts/project/lint_chart_tokens.py`，静态扫描所有前端代码，严禁出现裸数字字号（如 `fontSize: \d+`），强制引用 `CHART_FONT` 等 Token 常量。
3. **纳入门禁流水线**：
   将图表 Token 检查器接入 `Makefile`（`make check`）、Git `pre-commit` 钩子及 GitHub Actions CI 流程。

## 修复范围与验收

- [ ] 新建 `frontend/src/charts/tokens.ts`，导出标准字号、内边距与几何尺寸 Token。
- [ ] 重构 `frontend/src/charts/*.ts` 与既有内嵌图表，全量替换裸数字字面量为 Token 引用。
- [ ] 编写 `scripts/project/lint_chart_tokens.py` 并配套自动化单元测试。
- [ ] 在 `make check` 与 pre-commit 增加该检查项，确保零误报且阻断非法硬编码提交。
- [ ] 更新 `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md`，固化图表 Token 契约。

## 边界

- 本任务仅规范前端图表配置代码与静态门禁，不变更后端 API 与数据库。
- 保持现有 1920×980 整体缩放基准不变，不破坏已验收的视觉排版。

## 关联

- [问题看板](../KNOWN-ISSUES.md)
- [前端规范](../development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md)
- [当前状态](../CURRENT-STATE.md)
- [KI-076 · 前端展示事实、组合布局与视觉回归缺口](KI-076-FRONTEND-PRESENTATION-CONTRACT.md)
