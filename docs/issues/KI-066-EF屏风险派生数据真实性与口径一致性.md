# KI-066 · E/F 屏风险派生数据真实性与口径一致性缺口

- 状态：OPEN
- 优先级：P2
- 更新日期：2026-09-09
- 适用范围：E 屏（合规监督）与 F 屏（风险预警）的风险单位派生逻辑、总览 A1/A8 的运营指标口径、快照 `entities`/`quality`/live 投影字段
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[前端架构与约束](../development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md)、[实时投影](../development/LIVE-PROJECTION.md)、[治理仿真综合](../development/GOVERNANCE-SIMULATION-SYNTHESIS.md)、`backend/app/services/dashboard_sections.py`、`frontend/src/views/{IssuesView,InsightsView}.vue`

---

## 结论

对 A~F 六屏做逐屏只读核查后，发现 E/F 屏"风险单位/困难户"的派生链路存在若干真实性与口径一致性缺口，
使部分风险维度实际上永不触发、部分"0 异常"并非真实核验结果、以及同一屏存在两套并行数据源。均为
既有实现的技术债，不是新功能需求。

## 只读证据（2026-09-09）

### ① `entities.voucherRate` 恒为 `None`，导致票据类/双轨类风险几乎永不触发（核心）

- `backend/app/services/dashboard_sections.py::build_entities` 对每个单位固定写入 `row["voucherRate"] = None`。
- 而 E 屏 `IssuesView.vue` 与 F 屏 `InsightsView.vue` 的风险判定依赖 `voucherRate < 95`：
  - 「票据异常」：`status === '双轨运行' && voucherRate !== null && voucherRate < 95`；
  - 「双轨核对差异」：同上。
- 由于 `voucherRate` 恒 `None`，上述条件恒为 false → **E/F 屏几乎不会出现"票据异常/双轨核对差异"类风险**，
  实际风险清单主要由 `construction < 88` 与 `status === '准备中'` 驱动，风险维度不完整。

### ② `quality` 金标异常三项恒为 0（诚实性问题）

- `build_dashboard_snapshot_v2` 返回的 `quality` 中
  `voucherBalanceErrors`/`timeOrderErrors`/`orphanLinkErrors` 直接硬编码为 `0`。
- 影响 A8「运营红线哨位·金标异常」、D7「数据质量金标准核验」相关展示：恒显示 0 异常。
- 问题在于 0 与"未核验"语义不同——当前把"未实际核验"呈现为"0 异常/已通过"，与项目诚实性纪律
  （KI-023 精神：不得把未生成/未核验当作已通过结果）不一致。HeatWave 具备真实核验借贷平衡、
  时间序、孤儿链的能力。

### ③ E 屏存在两套并行数据口径

- E 屏主体图表 E1~E5（`IssuesView.vue`）的风险由 `store.entities` **前端阈值现场派生**；
- 而 E 屏下钻抽屉 `ComplianceInspectDrawer.vue` 与顶部 `LiveActivityTicker.vue` 走字广播读的是
  `governance_issue` / `/api/governance/*` **治理工单表**（GI-003/GI-004 矛与盾状态机所操作的表）。
- 同一屏两套来源描述同一件事，存在潜在不一致：广播/抽屉呈现工单处置流转，E5 表格却按当前实体阈值判定，
  两者未直接联动，观众可能困惑（"广播说在处置，表格判定没变"）。

### ④ A1「本次集成」命名与口径易误解

- `CockpitTopBar.vue` 的「本次集成」= `cumulative.integrations`，来源为 **live_projection（不写库的进程内演示投影）**
  自本次会话启动以来的累计推送数；
- 它与相邻的「今日单据」「今日凭证」（真库当日增量，来自 `daily_stats` / 区域 SQL）并排且同样带「+」前缀，
  易被理解为同口径的"今日集成"。命名与语义需澄清。

## 影响

- E/F 屏风险画面维度不完整（票据/双轨维度缺失），"矛与盾"在票据维度无法真实体现与自愈。
- A8/D7 "0 异常"可能被误读为"已核验通过"，削弱大屏的可信度与诚实性。
- E 屏两套口径并存增加维护与认知成本，动态演进时易出现表面不一致。
- A1 指标口径混用，观众难以区分"真库当日增量"与"演示会话累计"。

## 修复方向（待实施；需按 ENFORCEMENT 确认范围与授权）

1. **voucherRate 真实派生**：由后端按单位真实数据派生凭证率（如该单位单据→凭证成功入账比例，或既有
   metric 口径），替代恒 `None`，使 E/F 票据/双轨类风险能真实出现并随推进自愈。注意与 KI-059 秒级 SLA
   兼容（优先用预聚合，不引入即席大聚合裸扫）。
2. **quality 诚实化**：要么用 HeatWave 真实核验借贷平衡/时间序/孤儿链并落库派生，要么在无核验时如实标注
   "未核验/接口未提供"，不得以硬编码 0 呈现为"已通过"。
3. **E 屏口径统一或明确分工**：统一 E 屏主体与治理工单表的口径；若刻意分层，需在文案/文档明确
   "表格=当前阈值态、广播/抽屉=处置流水"的分工，避免误读。
4. **A1「本次集成」澄清**：改为更准确的标签（如"演示累计集成/实时集成脉搏"），或与"今日"口径统一，
   与真库当日增量在视觉上区分。

## 完成定义（实施时）

- [ ] E/F 屏票据类/双轨类风险可依据真实凭证率出现与自愈；不再因 `voucherRate` 恒 `None` 而永不触发。
- [ ] A8/D7 的金标异常为真实核验结果或如实标注未核验，不再以硬编码 0 冒充已通过。
- [ ] E 屏数据口径统一或分工明确，抽屉/广播与主体表格无误导性不一致。
- [ ] A1「本次集成」口径清晰、不与真库当日增量混淆。
- [ ] 相关行为变更补充/更新回归测试；`docs/CURRENT-STATE.md` 同步；`make check` 全绿。

## 备注

- 本 KI 只登记问题，不构成执行授权。涉及后端派生逻辑与前端口径调整，实施前分别确认范围与数据库授权边界。
- 各项可分期实施，其中 ①（voucherRate）为最高收益项，建议优先。

## 进度

- 2026-09-09 立项登记（OPEN）。承接 A~F 六屏逐屏只读核查，发现 E/F 屏风险派生的真实性与口径一致性缺口。
