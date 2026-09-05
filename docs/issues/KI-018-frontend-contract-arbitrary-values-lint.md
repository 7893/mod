# KI-018 · 前端契约缺自动校验（Tailwind 任意值漏网）

- 状态：DONE（2026-09-04）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 契约三禁止脱离 Token 的任意值
  （如 `text-[10px]`、`bg-[#xxxxxx]`），但此前闸门（`make check` 的 typecheck/build）无法识别这类违规——
  语法合法、可正常构建，因此靠人工 review 才能发现。
- 实例：`eb8212a`（rollout 迁移）残留 1 处 `text-[10px]`，应为 `text-cockpit-xs`。
- 影响：前端契约停留在“须知 + 人工 review”，未成“闸门”；迁移过程中易漏网，长期累积会重新滋生散写样式。
- 处理结果：
  1. [已修复 2026-09-04] `RolloutView.vue` 残留的 `text-[10px]` → `text-cockpit-xs`。
  2. [已修复 2026-09-04] 在 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 契约三与 KI-022 中界定清晰边界（禁止字号/颜色/间距等任意值，受控允许图表 min-h/max-h guardrails）。
  3. [已落地 2026-09-04] 实现项目级校验脚本 `scripts/project/lint_frontend_arbitrary_values.py`，精准拦截字号/颜色/间距/边框等禁止模式，放行受控 guardrails，并支持 `<!-- lint: allow -->` 行内显式豁免。
  4. [已接入 2026-09-04] 接入 `Makefile`（`frontend-check` 目标）及 GitHub Actions CI（`.github/workflows/quality.yml`），违规直接阻断提交与构建。
- 关联：`KI-008`（B–F 屏迁移）、`KI-022`（收尾清理）。
