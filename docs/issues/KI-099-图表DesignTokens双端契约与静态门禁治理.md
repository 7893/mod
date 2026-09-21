# KI-099 · 图表 Design Tokens 双端契约与静态门禁治理

编写日期：2026-09-17
- 更新日期：2026-09-21
- 状态：DONE
- 优先级：P2
适用范围：前端设计系统、ECharts 主题配置、样式治理脚本、CI/CD 质量门禁

## 问题与证据

- **渲染层物理断层**：Tailwind 4 `@theme` 仅作用于 DOM 样式树，底层 Canvas/ECharts 无法直接消费 CSS 变量或类名，造成 Design System 在图表层断层。
- **散落硬编码与魔鬼数字**：在 2026-09-17 字号体系调整中，发现大量图表配置（如 A1 顶栏、双轨趋势图、模型契约卡等）由于缺乏图表层 Token 规范，直接硬编码 `fontSize: 9`、`10` 等魔鬼数字，改动全局 CSS 无法联动生效。
- **机器守卫缺位**：现行 `lint_frontend_arbitrary_values.py` 仅约束 Vue 模板的 Tailwind 任意值，未对 `.vue` 与 `charts/*.ts` 中的图表字号、边距等数值建立静态 AST 或正则守卫，导致破窗效应不断蔓延。

## 目标与方案

1. **建立图表专用 Design Tokens 契约**：
   在 `frontend/src/charts/tokens.ts` 中建立类型安全的只读字号 Token（micro/axis/caption/body/tooltip/subMetric/metric/kpi），与 `theme.css` 的 DOM 字号语义对齐。栅格、柱宽、线宽和圆角只有在多个图表中形成稳定语义后再提升为 Token；单图特有几何仍属于 option，避免制造与裸数字一一对应的伪抽象。
2. **新增图表静态治理门禁**：
   扩展既有 `scripts/project/lint_frontend_styles.py`，静态扫描所有前端代码，严禁出现裸数字字号（如 `fontSize: \d+`），强制引用 `CHART_FONT`。复用现有检查器可避免新增重复 CLI、CI 步骤和维护入口。
3. **纳入门禁流水线**：
   既有样式检查器已经接入 `Makefile`、Git `pre-commit` 与 GitHub Actions，规则随同生效。

## 修复范围与验收

- [x] 新建 `frontend/src/charts/tokens.ts`，导出标准语义字号 Token。
- [x] 重构 `frontend/src/charts/*.ts` 与既有内嵌图表，全量替换裸数字字号为 Token 引用。
- [x] 扩展既有 `lint_frontend_styles.py` 并补充自动化单元测试，不新增重复检查器。
- [x] 复用 `make check`、pre-commit 与 CI 中已有的样式检查步骤阻断非法硬编码。
- [x] 更新 `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md`，固化图表 Token 契约。
- [x] `make check` 与远端质量门通过。
- [x] 完成固定场景人工视觉回归后再关闭本 KI。

## 2026-09-20 实施校正

原方案要求一次性把所有图表几何数字都 Token 化，会形成大量仅被引用一次、与原数字一一对应的常量，
反而增加跳转和命名成本。本次按“稳定重复才抽象”的原则缩小 Token 边界，并把门禁并入既有检查器；
这项校正不降低字号治理强度，同时减少了脚本、流水线配置和长期维护面。

## 2026-09-21 验证与部署进度

最新提交 `bfa02e9` 的 GitHub Actions 质量门与 Deploy 作业均已成功，Token 与静态门禁已经随前端部署。
2026-09-21 用户确认现行布局，随后在隔离夹具下更新两档截图基线；22 项浏览器回归全部通过，
包含六屏、组件展例、失败降级、治理抽屉、窗口变化与全屏导航。本 KI 关闭。

## 边界

- 本任务仅规范前端图表配置代码与静态门禁，不变更后端 API 与数据库。
- 保持现有 1920×980 整体缩放基准不变，不破坏已验收的视觉排版。

## 关联

- [问题看板](../KNOWN-ISSUES.md)
- [前端规范](../development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md)
- [当前状态](../CURRENT-STATE.md)
- [KI-076 · 前端展示事实、组合布局与视觉回归缺口](KI-076-FRONTEND-PRESENTATION-CONTRACT.md)
