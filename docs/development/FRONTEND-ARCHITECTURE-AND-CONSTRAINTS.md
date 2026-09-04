# 前端整体规划与约束规范

更新日期：2026-09-03
状态：现行
适用范围：`frontend/` 下所有页面、组件、样式与状态；约束人类与 AI 的前端改动

## 本文定位

本文是前端的“宪法”，分两部分：

- **第一部分 · 规划**：六屏应有的整体形态、信息架构与视觉基调（目标形态）。
- **第二部分 · 约束**：骨架、物料、Token 三层契约与 AI 填内容的边界（不许越过的线）。

规划回答“做成什么样”，约束回答“不许怎么做”。两者合为一体：先按规划定骨架，
再由约束保证任何人和 AI 只能在骨架内填内容，不能重新发明布局与样式。

### 与既有文档的关系

- 六屏架构与 Zone 编号体系沿用 `docs/23-V2六屏驾驶舱页面区域与布局规范.md` 的**结构定义**，
  但**不沿用其中的具体数据数值与旧 CSS 标记规则**：
  - `docs/23` 内写死的行数、单位数、指标数值均为早期封版快照，已过时，以数据库只读结果为准。
  - `docs/23` 第四节的 `class="panel"`、`zone-badge`、`#00d2ff 青色发光`等旧 CSS 标记规则**已废除**，
    由本文第二部分的 `CockpitPanel` + Tailwind 契约取代。
- 目录归属与文件规模沿用 `DEVELOPMENT-STANDARD.md` 前端章节与 `PROJECT-ORGANIZATION.md`，本文不重复。
- 执行强制方式以 `ENFORCEMENT.md` 为准；本文是内容规范，不自带闸门。

---

# 第一部分 · 规划

## 1. 六屏架构

沿用六屏与稳定 Zone 编号（结构定义见 `docs/23`），路由与职责概览：

| 屏 | 路由 | 名称 | 职责 |
|---|---|---|---|
| A | `/dashboard` | 全周期总览 | 驾驶舱首屏，全网态势与下钻入口 |
| B | `/construction` | 建设进度 | 建设完成度与阶段任务 |
| C | `/rollout` | 推广上线 | 批次推进、省域上线、单位台账 |
| D | `/operations` | 业务与凭证运营 | 单据凭证全链路与质量 |
| E | `/issues` | 问题与风险 | 未解决事项、风险分级 |
| F | `/insights` | 智能研判与预测 | AutoML/AI 状态与预测契约 |

Zone 编号（A1–F5）是稳定的产品坐标，用于沟通定位，不得替代业务标题；
编号本身不绑定任何一套具体 CSS 实现。

## 2. 信息架构原则

- 每屏是“若干块（Panel）”的组合，不是自由画布。先确定分区，再填内容。
- 首屏（A）承担态势总览与下钻入口；B–F 各自聚焦一个业务域，互不重复堆叠指标。
- 缺失数据显示为 `—` 或明确的“未提供”，不得用冻结基线数值或伪造结果填充。
- 一切金额、剧情、比对文案若来自模拟投影，必须与数据库真实数值解耦并标注为演示动态。

## 3. 视觉基调

- 基调：深色仪表盘（obsidian slate），克制、硬朗、低噪点。
- 只有具备信号灯价值处（风险、异常、成功率）才使用高饱和亮色；其余以中性灰阶承载。
- 禁止无业务信息量的装饰性效果（如伪雷达同心圆、仿金属铆钉、多向异色描边、成串魔法阴影）。
  科技感来自对齐与秩序，不是来自堆叠特效。

---

# 第二部分 · 约束（三层契约）

前端腐化的根因是“逐元素堆叠、无整体约束”。三层契约把 AI 的自由度收敛到“在格子里填内容”，
从结构上消除“重新发明布局与样式”的空间。

## 契约一 · 骨架契约（Layout）

- 每屏的分区骨架（几列几行、比例、命名区域）是**受保护结构**，集中定义、显式标注、禁止随意改动。
- 骨架比例不得散落在各处魔法数字中；应以具名方式集中定义（如 `tailwind.config` 的具名
  `gridTemplateColumns`/`gridTemplateRows`），模板只引用名字。
- 大屏适配采用固定设计基准 + 整体缩放思路，避免以逐屏断点补丁维持对齐。
- 修改骨架属于结构变更，需在改动说明中明确指出，不得在填内容时顺手调整分区比例。

## 契约二 · 物料契约（Component）

- 所有面板必须使用统一窗体物料 `frontend/src/components/CockpitPanel.vue` 包裹（存量旧物料 `components/Panel.vue` 已彻底废弃并物理删除，全站包括 `/data` 台账页均完全统一），不得在页面里另起一套私有面板样式。
- 物料的可选形态由其 props 有限枚举承载（如 `tone` 仅 `default`/`risk`），不得在外部叠加样式覆盖。
- 复用组件放 `components/`，页面放 `views/`，复用逻辑放 `composables/`，共享状态放 `stores/`；
  不新建 `misc`、`utils` 型散装模块。

## 契约三 · Token 契约（Style）

- 颜色、间距、字号、圆角、阴影必须来自集中定义的 Token（`frontend/src/styles/theme.css` 的
  Tailwind 4 `@theme` 块，与 `foundation.css` 的变量层），不得在模板中散写任意值。
- 已定义的 Token（模板直接引用其工具类，禁止再写等价任意值）：
  - 骨架：`grid-cols-cockpit`（三栏 390px/1fr/370px）、`grid-rows-cockpit-side`（1.15fr/1fr）。
  - 表面色：`bg-surface-base`（大屏底色）、`bg-surface-panel`、`border-surface-hairline`、
    `bg-surface-veil-06`、`bg-surface-veil-03`。
  - 字号：`text-cockpit-xs`(10)、`text-cockpit-sm`(11)、`text-cockpit-md`(13)、`text-cockpit-metric`(18)。
  - 信号灯语义色沿用 Tailwind 内置 sky/rose/amber/emerald，仅在有信号价值处使用。
- 优先使用 Tailwind 原子类表达布局与样式；不得为可用 Token 表达的样式手写新的一次性 CSS 规则。
- 手写 CSS 仅保留 Token 定义、第三方组件必要覆盖、以及无法用原子类表达的少量复杂选择器；
  发现与契约重复或已失效的 CSS 应删除，而非叠加。
- 严禁新增 `bg-[#xxxxxx]`、`text-[13px]` 这类脱离 Token 的任意值；确需新值，先在 `theme.css`
  沉淀为 Token 再引用。
- **Arbitrary Value 允许与禁止边界（KI-018 / KI-022 闭环）**：
  - **严格禁止（Strictly Forbidden）**：禁止在字号（如 `text-[10px]`）、颜色（如 `bg-[#...]`、`border-[...]`）、基础内外边距（如 `p-[12px]`）等已有系统化 Token 维度使用 arbitrary value。
  - **受控允许（Layout Guardrails）**：在大屏图表（ECharts/SVG）、折线走势或复杂弹性栅格中，为防止极端缩放下图表塌陷而设立的物理高度上下界（如 `min-h-[220px]`、`max-h-[350px]`），作为 Layout Guardrails 受控允许；通用宽度或网格列宽能沉淀为 Token（如 `--grid-template-columns-ops-volume`、`min-w-44`）的应优先沉淀。

## AI 填内容的边界

- AI 只能在既定骨架的区域内、用 `CockpitPanel` 物料、以 Token 与原子类填充内容。
- AI 不得：新增或修改骨架比例、绕过 `CockpitPanel` 自造面板、引入脱离 Token 的任意值、
  为追求视觉效果添加无业务信息量的装饰。
- 需要突破契约（新分区、新物料形态、新 Token）时，先提出并获确认，再落地为契约的一部分，
  不得先斩后奏地在局部实现。

## 迁移现状与推进

- Token 基座（`frontend/src/styles/theme.css`）已建立，`DashboardView`（A 屏）作为范式标杆；
  `ConstructionView`（B 屏）、`RolloutView`（C 屏）、`OperationsView`（D 屏）、`IssuesView`（E 屏）与 `InsightsView`（F 屏）已按同一契约全量迁移到 `CockpitPanel`、具名 Grid 与集中 Token。
- 全站存量专属旧 CSS（`rollout.css`、`operations.css`、`issues.css`、`insights.css`）已全部物理清零，旧物料 `components/Panel.vue` 已彻底物理删除；`DataView`（数据台账页）已统一为 `CockpitPanel` + Tailwind 范式，`styles.css` 仅保留基座与通用物料层。
- 全站各视图整体骨架、物料与 Token 三层契约已全面闭环生效。

## 重构执行顺序（后续 AI 必须按此顺序，不得跳步）

1. **先读标杆**：以 `DashboardView.vue` + `CockpitPanel.vue` + `theme.css` 为唯一参照，
   不自造布局与样式体系。
2. **确认 Token 齐备**：目标屏需要的骨架/颜色/字号若已有 Token 就直接用；缺失则**先在
   `theme.css` 沉淀新 Token**（并说明理由），再在模板引用——不得先写任意值事后再补。
3. **定骨架**：为该屏定义分区 Grid（列/行/比例），比例集中具名，不散写魔法数字。
   大屏以固定基准 **1920×1080** 设计，靠整体缩放适配，不加逐屏断点补丁。
4. **填内容**：所有面板用 `CockpitPanel` 包裹，格内只用 Token 与原子类填充。
5. **删旧 CSS**：迁移完成后删除该屏对应的旧 `xxx.css`，并从 `styles.css` 移除其 `@import`。
6. **验证**：`pnpm run typecheck`、`pnpm run build`、`make check` 全绿；**由人工做实际页面视觉验收**
   （AI 无法自行验收视觉），确认无错位、溢出、对齐问题后再提交。
7. **一屏一提交**：每屏独立提交，信息说明迁移了哪屏、删了哪个旧 CSS。

- 顺序原则：不为重构而一次性全改；优先迁移业务数据已稳定的屏，
  依赖 `docs/KNOWN-ISSUES.md` 中未修数据（如 KI-001/002/003）的屏往后放，避免布局与逻辑两次返工。

## 完成定义

前端变更须与 `TESTING-STANDARD.md` 一致：`pnpm run typecheck`、`pnpm run build` 与
全量 `make check` 通过；涉及视觉行为时补充实际页面验收。契约变更须同步本文。
