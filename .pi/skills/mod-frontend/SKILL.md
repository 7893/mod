---
name: mod-frontend
description: Frontend guidelines, constraints, and architecture for the MOD cockpit project (Vue 3, Tailwind 4, CockpitPanel, Design Tokens).
---
> **Authoritative Standard**: This skill is a condensed execution reference. For full frontend rules, see [FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md](../../../docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md).


# MOD Frontend Development Skill

When working on any file in `frontend/`, adhere strictly to the following three-layer contract:

## 1. 骨架契约 (Layout Contract)
- Do not invent arbitrary layout ratios. Use named Tailwind grid templates (`grid-cols-cockpit`, `grid-cols-construction`, etc.).
- The screen base is obsidian slate dark dashboard.
- Responsive scaling is anchored to `command-main`, never hide top navigation.

## 2. 物料契约 (Component Contract)
- Every panel MUST be wrapped in `CockpitPanel.vue` (`components/CockpitPanel.vue`). Do not write private panel CSS wrappers.
- Reusable UI blocks live in `components/blocks/` (`MetricGrid`, `StatList`, `CompositionBar`, `EmptyNote`, `ChartBlock`, etc.). Check existing blocks before creating new ones.
- Reusable drawers must use `DrawerShell.vue` with standard slide animations and backdrop masks.
- Table / ledger components must use `components/ledger/` and composables (`usePagedList`, `useEntityEditor`).

## 3. Token 契约 (Style & Token Contract)
- **STRICTLY FORBIDDEN**: Tailwind arbitrary values like `w-[120px]`, `text-[13px]`, `p-[7px]`, `#00d2ff`. All arbitrary values will fail `make check` (`lint_frontend_arbitrary_values.py`).
- Use designated tokens defined in `frontend/src/styles/theme.css`:
  - Backgrounds: `bg-surface-base`, `bg-surface-panel`, `border-surface-hairline`, `bg-surface-veil-06`.
  - Font sizes: `text-cockpit-xs` (10px), `text-cockpit-sm` (11px), `text-cockpit-md` (13px), `text-cockpit-metric` (18px), `text-cockpit-kpi` (24px).
  - Semantic lights: `sky-400` (highlight), `emerald-400` (success), `amber-400` (warn), `rose-500` (risk).
- ECharts colors must come from `charts/theme.ts`. Never hardcode hex colors in chart options.

## 4. 验证要求
- Always run `pnpm test` (vitest) and `pnpm run typecheck` (vue-tsc) after changing Vue/TS code.
- Pure functions in `utils/` must have 100% test coverage.
