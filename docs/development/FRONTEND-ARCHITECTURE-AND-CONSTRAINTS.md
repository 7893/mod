# 前端整体规划与约束规范

更新日期：2026-09-09
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
| E | `/issues` | 问题与风险 | 未解决事项、风险分级、实时广播走字流（`LiveActivityTicker`）、整改抽屉（`ComplianceInspectDrawer`）与展厅巡航（`KioskSpotlightTour`） |
| F | `/insights` | 智能研判与预测 | AutoML/AI 状态、决策简报、Cloudflare AI 每日安全额度胶囊（`AiQuotaCapsule`，$0.00 零费用硬防护） |

Zone 编号（A1–F5）是稳定的产品坐标，用于沟通定位，不得替代业务标题；
编号本身不绑定任何一套具体 CSS 实现。

## 2. 信息架构原则

- 每屏是“若干块（Panel）”的组合，不是自由画布。先确定分区，再填内容。
- 首屏（A）承担态势总览与下钻入口；B–F 各自聚焦一个业务域，互不重复堆叠指标。
- 缺失数据显示为 `—` 或明确的“未提供”，不得用冻结基线数值或伪造结果填充。
- 一切金额、剧情、比对文案若来自模拟投影，必须与数据库真实数值解耦并标注为演示动态。

### 面板信息密度平衡

- 一排出现 6 个及以上同构小卡、且主要用于比较时，优先改为柱图、堆叠图或折线图；卡片只保留需要独立强调的核心 KPI。
- 大面板不得靠重复标签、说明文字或硬编码数字填空；应选择能表达构成、趋势、排序或差异的图表。
- 图表必须回答明确问题，同一面板不重复展示完全相同的信息；tooltip 承载明细，画布保留主比较关系。
- 连续类别若数值与状态完全相同、且阅读重点是异常或在推项，应合并为汇总类别，把明细留给 tooltip 或台账，避免重复线条挤压有效画布。
- 缺失数据不画满格、不回填 100% 或 0 异常，统一显示 `—` 或明确空态。

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
- 浏览器全屏时顶部导航必须常驻；缩放引擎始终以导航下方 `command-main` 的实际内容盒为准，
  不得用 `window.screen` 尺寸绕过真实布局，也不得通过隐藏导航换取画布高度。
- 修改骨架属于结构变更，需在改动说明中明确指出，不得在填内容时顺手调整分区比例。

## 契约二 · 物料契约（Component）

- 所有面板必须使用统一窗体物料 `frontend/src/components/CockpitPanel.vue` 包裹（存量旧物料 `components/Panel.vue` 已彻底废弃并物理删除，全站包括 `/data` 台账页均完全统一），不得在页面里另起一套私有面板样式。
- 物料的可选形态由其 props 有限枚举承载（如 `tone` 仅 `default`/`risk`），不得在外部叠加样式覆盖。
- 复用组件放 `components/`，页面放 `views/`，复用逻辑放 `composables/`，共享状态放 `stores/`，
  无副作用的纯函数放 `utils/`（必须配套单测）；不新建 `misc` 型散装模块。
- 积木库 `components/blocks/` 现有：`MetricGrid`（`flat`/`fill`/`size xs–lg`）、`StatList`（`flat`/`dense`/`ranked`）、`StatusList`（`wrap`/`scroll`/`chevron`）、`ChartBlock`、`CommandBand`、`OverviewBand`、`CompositionBar`、`NoteBanner`、`EmptyNote`。新增展示结构前先检查能否由现有积木 + 数据映射表达；新增积木需同时补 `blocks.css` 原型与本表。
- 台账/清单类面板必须复用 `components/ledger/` 物料（`SearchInput`、`FilterSelect`、`LedgerPager`、
  `EntityEditDrawer`）与 `composables/usePagedList.ts`（分页状态机）、`composables/useEntityEditor.ts`
  （调态抽屉）、`utils/entityOptions.ts`（省份/批次/状态顺序表、带计数选项、关键字匹配），
  不得在组件内重写筛选、分页、计数或抽屉逻辑。

## 契约三 · Token 契约（Style）

- 颜色、间距、字号、圆角、阴影必须来自集中定义的 Token（`frontend/src/styles/theme.css` 的
  Tailwind 4 `@theme` 块，这是**唯一** Token 来源，不再有 `:root` 变量层），不得在模板中散写任意值。
- 语义色不另造名字：文字用 `slate-50/400/500/600`（主/次/弱/暗），信号灯用 `sky-400`（强调）、
  `emerald-400`（成功）、`amber-400`（警告）、`rose-500`（风险）；表面色用 `surface-*` Token。
  手写 CSS 中引用形式为 `var(--color-sky-400)`，透明度用 `color-mix(in srgb, var(--color-…) N%, transparent)`。
- 间距用 Tailwind 刻度（模板 `gap-3`，手写 CSS `--spacing(3)`），圆角用 `var(--radius-sm|md|lg)`，
  动效用 `var(--ease-out)` 与 `var(--default-transition-duration)`；不得再定义 `--space-*`、`--radius-*`、`--duration-*`。
- 图表（ECharts option）内的颜色只能取自 `charts/theme.ts` 的 `chartPalette`/`chartInk`/`mapRamp`，
  不得在组件内写色值字面量。
- SFC 内如需手写引用 Token 的 `<style>`，块首必须 `@reference "../styles.css";`。
- 已定义的 Token（模板直接引用其工具类，禁止再写等价任意值）：
  - 骨架：`grid-cols-cockpit`（三栏 390px/1fr/370px）、`grid-rows-cockpit-side`（1.15fr/1fr）、
    `grid-cols-construction`（B 屏 12 列）与 `grid-rows-construction`（上下 0.95fr/1.05fr）。
  - 表面色：`bg-surface-base`（大屏底色）、`bg-surface-panel`、`border-surface-hairline`、
    `bg-surface-veil-06`、`bg-surface-veil-03`。
  - 字号：`text-cockpit-xs`(10)、`text-cockpit-sm`(11)、`text-cockpit-md`(13)、`text-cockpit-metric`(18)、
    `text-cockpit-kpi`(24，仅用于单面板唯一主指标)。
  - 信号灯语义色沿用 Tailwind 内置 sky/rose/amber/emerald，仅在有信号价值处使用。
- 优先使用 Tailwind 原子类表达布局与样式；不得为可用 Token 表达的样式手写新的一次性 CSS 规则。
- 手写 CSS 仅保留 Token 定义、第三方组件必要覆盖、以及无法用原子类表达的少量复杂选择器；
  发现与契约重复或已失效的 CSS 应删除，而非叠加。
- 严禁新增 `bg-[#xxxxxx]`、`text-[13px]` 这类脱离 Token 的任意值；确需新值，先在 `theme.css`
  沉淀为 Token 再引用。
- **Arbitrary Value 允许与禁止边界（[KI-018](../issues/KI-018-前端契约任意值lint.md) / [KI-022](../issues/KI-022-前端迁移收尾小修.md) 闭环）**：
  - **严格禁止（Strictly Forbidden）**：禁止在字号（如 `text-[10px]`）、颜色（如 `bg-[#...]`、`border-[...]`）、基础内外边距（如 `p-[12px]`）等已有系统化 Token 维度使用 arbitrary value。
  - **受控允许（Layout Guardrails）**：在大屏图表（ECharts/SVG）、折线走势或复杂弹性栅格中，为防止极端缩放下图表塌陷而设立的物理高度上下界（如 `min-h-[220px]`、`max-h-[350px]`），作为 Layout Guardrails 受控允许；通用宽度或网格列宽能沉淀为 Token（如 `--grid-template-columns-ops-volume`、`min-w-44`）的应优先沉淀。

## AI 填内容的边界

- AI 只能在既定骨架的区域内、用 `CockpitPanel` 物料、以 Token 与原子类填充内容。
- AI 不得：新增或修改骨架比例、绕过 `CockpitPanel` 自造面板、引入脱离 Token 的任意值、
  为追求视觉效果添加无业务信息量的装饰。
- 需要突破契约（新分区、新物料形态、新 Token）时，先提出并获确认，再落地为契约的一部分，
  不得先斩后奏地在局部实现。

## 全局样式文件契约

`frontend/src/styles.css` 只做导入；`frontend/src/styles/` 固定四层，不得新增文件：

| 文件 | 职责 | 允许内容 |
|---|---|---|
| `theme.css` | Token 唯一来源 | 仅 `@theme` 块 |
| `base.css` | 文档重置 | 元素选择器级全局规则 |
| `shell.css` | 外壳与顶栏（缩放画布之外） | `.command-*`/`.header-*`/`.nav-*` 等外壳类；**全站唯一允许媒体查询与 `clamp()` 的地方** |
| `blocks.css` | 积木原型 | `MetricGrid`/`StatList`/`ChartBlock`/`StatusList` 的 BEM 规则 |

组件私有样式写在其 SFC `<style>` 内（ECharts tooltip 这类渲染在组件根之外的 HTML 用非 scoped 块）。
任何全局 CSS 类若在 `.vue`/`.ts` 中无引用即为死代码，必须删除。

以上文件集、色值字面量位置、旧变量、媒体查询位置、选择器引用与 `@reference` 要求由
`scripts/project/lint_frontend_styles.py` 在 `make check` 与 CI 中机器校验；模板任意值由
`lint_frontend_arbitrary_values.py` 校验。两者失败均阻断提交。

## 迁移现状与推进

- 六屏均已使用 `CockpitPanel` 外壳与具名 Grid Token。2026-09-09 完成 C/D/E/F 屏积木化：首行指挥带统一为 `blocks/CommandBand`（左主图 + 右事实栏），面板内事实栏/对账明细/TOP 列表统一为 `MetricGrid`/`StatList` 的 `flat` 平铺形态，规则告警统一为 `StatusList`，提示条统一为 `NoteBanner`，空态统一为 `EmptyNote`；D7 金标准核验四卡收敛为 `MetricGrid` 数据映射。
- 风险判定单一来源：E 屏合规监督与 F 屏困难户共用 `utils/riskRules.ts`（`evaluateRiskFlags`/`deriveComplianceUnits`/`deriveAtRiskUnits`），阈值只读 `businessRules`，视图与模板中不得再出现门禁数字字面量。
- 2026-09-09 完成全局样式收口：删除 `foundation/components/utilities/page-hierarchy/dashboard-topbar/responsive-breakpoints` 六个文件及约 120 条无引用规则，全局 CSS 由 1897 行降至约 880 行；删除 `:root` 旧变量层，Token 唯一来源为 `theme.css`。
- 2026-09-09 完成台账层去重：`ConstructionLedger`/`RolloutLedgerTable`/`AtRiskUnitTable` 的筛选、分页、计数、调态抽屉收敛到 `components/ledger/` 与 `usePagedList`/`useEntityEditor`/`entityOptions`，三组件合计由 1234 行降至约 790 行；`AtRiskUnitTable` 顺带补齐总页数收缩时的最小页钳位。
- 数字与日期时间展示统一走 `formatters/metrics.ts`（`formatCount`/`formatPercent`/`formatDateTime`）：视图、组件、图表 tooltip 与 store 中不得再直接调用 `toLocaleString`/`Intl.*`，空值一律显示 `—`。
- A1、B1、C1、D1、E1、F1、A2、A3、B2、B4、B5、C2、C5、D4、D6、D7、E4、F3、F4、F5 已完成面板密度图表化：拥挤的横排卡收敛为比较图，空旷数字面板补充构成、进度或质量图，长篇简报转为分组摘要卡，重复信息由图表交互或悬停提示承载。
- 六屏主面板采用统一的“领域主图 + 少量精确事实”语言，但不强制同构：A1 为双进度环、运营规模谱和风险闭环，B2 为阶段状态矩阵与八轴轮廓，C1 为上线仪表与推进漏斗，D1 为业务规模谱与结构效率，E1 为合规仪表与监督梯队，F1 为风险比较条与模型质量门禁。面板区号、标题和小说明保持单行；主面板内容以分隔线组织，不再套同级边框框体。图表派生数据集中在 `charts/`，视觉统一复用 `charts/theme.ts`。
- 同屏去重契约已扩展到 A8/B4/C3/D3/D7：A8 只做聚合运营异常、联系人只留 C5；B4 只做上线门禁与培训转化；C3 只做批次历史爬坡、C2 只做当前构成；D3 只做日吞吐趋势、D1/D2 分别保留累计规模与链路阶段；D7 在全量合规时比较真实核验覆盖规模，不再用四根相同 100% 柱填充空间。时间序列或异常字段缺失时必须显示明确空态。
- 信息密度必须驱动具名骨架比例：A 屏左栏由 `dashboard-left` / `dashboard-stack` 固定 A2、A3、A4 的面积分工，B 屏上排 B2/B3 大于下排 B4/B5；C3 作为主分析画布占左侧 8 列并跨两行，C4/C5 作为辅助区在右侧 4 列上下叠放。比例只允许在 `theme.css` 的具名 Token 中维护。异步简报等首屏内容必须预留稳定槽位，数据到达不得推动主体布局；单行简报内容整体居中。
- 笛卡尔图表的分类图例统一放入 `CockpitPanel` 标题行的 `actions` 插槽，不得侵占绘图区顶部或从右侧切割坐标系；窄面板使用 `PanelLegend compact` 只显示颜色块，原生悬停提示与无障碍文本提供完整含义。只有 B5 等环图适合保持“图形在左、图例或精确读数在右”的横向组织。
- E/F 屏合规治理与 AI 算力护栏闭环（GI-003/GI-004）：E 屏顶端集成 `LiveActivityTicker.vue`，毫秒级轮播专班一线处置流水，赋予大屏环境生命体征；E 屏台账支持下钻唤起 `ComplianceInspectDrawer.vue`（六态 Stepper、专班责任人、一键督办上帝之手与 AI 深度研判）；空闲 45 秒由 `KioskSpotlightTour.vue` 自动唤醒展厅聚光灯巡航 HUD 浮窗，交互瞬时淡出；F 屏操作区嵌入 `AiQuotaCapsule.vue`，透视 Cloudflare AI 每日 3,000 Neurons 安全额度与熔断状态，坚守 $0.00 零费用硬防护。详见 [GOVERNANCE-SIMULATION-SYNTHESIS.md](GOVERNANCE-SIMULATION-SYNTHESIS.md)。


## 重构执行顺序（后续 AI 必须按此顺序，不得跳步）

1. **先读标杆**：以 `DashboardView.vue` + `CockpitPanel.vue` + `theme.css` 为唯一参照，
   不自造布局与样式体系。
2. **确认 Token 齐备**：目标屏需要的骨架/颜色/字号若已有 Token 就直接用；缺失则**先在
   `theme.css` 沉淀新 Token**（并说明理由），再在模板引用——不得先写任意值事后再补。
3. **定骨架**：为该屏定义分区 Grid（列/行/比例），比例集中具名，不散写魔法数字。
   外壳以 **1920×1080** 为目标屏幕，常驻导航下的内容画布以 **1920×980**
   为唯一设计基准；靠整体等比缩放适配，不加逐屏断点补丁，也不得用最小缩放值造成横向裁切。
4. **填内容**：所有面板用 `CockpitPanel` 包裹，格内只用 Token 与原子类填充。
5. **删旧 CSS**：迁移完成后删除该屏对应的旧 `xxx.css`，并从 `styles.css` 移除其 `@import`。
6. **验证**：`pnpm run typecheck`、`pnpm run build`、`make check` 全绿；**由人工做实际页面视觉验收**
   （AI 无法自行验收视觉），确认无错位、溢出、对齐问题后再提交。
7. **一屏一提交**：每屏独立提交，信息说明迁移了哪屏、删了哪个旧 CSS。

- 顺序原则：不为重构而一次性全改；优先迁移业务数据已稳定的屏，
  依赖 [已知问题看板](../KNOWN-ISSUES.md) 中未修数据（如 KI-001/002/003）的屏往后放，避免布局与逻辑两次返工。

## 完成定义

前端变更须与 `TESTING-STANDARD.md` 一致：`pnpm run typecheck`、`pnpm run build` 与
全量 `make check` 通过；涉及视觉行为时补充实际页面验收。契约变更须同步本文。
