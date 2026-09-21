# ADR-0022 · 单位台账统一投影与 HeatWave 依赖治理

- 状态：采纳
- 日期：2026-09-21

## 背景

C5 单位台账曾在全景快照已携带全量单位投影的同时，再请求 `/api/organizations`，后端重复联结
`org_unit`、`rollout_status_snapshot`、`sys_user`、`construction_task`、`data_readiness`。这使 C5 与 B/E/F
屏的单位清单形成两套读取、计算和降级路径，也使用户感知的首次载入受到二次网络请求与重复物化影响。

同时，HeatWave 应用看门狗与运维脚本各自维护目标表白名单。生产 9 表清单没有包含
`sys_user`、`data_readiness`和 `daily_stats`，而它们已是单位投影或全景快照的热依赖。

## 决策

1. `build_entities()` 产生的 dashboard snapshot `entities` 是单位台账唯一原始投影。前端统一从
   `store.entities` 读取；C5 与 B 屏完整台账共用 `useEntityLedger` 筛选/分页内核。
2. 删除 C5 专用 `useOrganizations` 列表请求和后端 `query_entities_paginated` 五表重算。
   `GET /api/organizations` 为兼容而保留，但只能对同一快照投影做内存筛选和分页，不得再执行单独 SQL。
3. HeatWave 目标表只在 `backend/app/heatwave_tables.py` 定义。目标由 9 表扩展为 12 表，新增
   `sys_user`、`data_readiness`、`daily_stats`；应用看门狗和运维脚本必须导入这一定义。
4. 代码目标变更不等于生产数据库授权。由于定时看门狗会对缺失表自动执行补载，新配置只能在
   明确的数据库变更授权下，与补载窗口、回退方案、12/12 健康检查一起发布。

## 理由

- 3,202 级别的单位投影已是全景快照的必要数据；在客户端对共享投影分页的成本远低于二次 HTTP 与五表重算。
- 一份投影使 C5、B 屏和风险/合规派生清单在状态、联系人、批次和降级语义上保持一致。
- HeatWave 下推是整条执行计划的属性；只加载大表而遗漏热点维表/聚合表，会让 join 路径退回 InnoDB。
- 单一配置可消除健康检查、自愈与手工运维对“应加载哪些表”的不同回答。

## 后果

- C5 不再拥有独立读路径，展示速度与快照的首次载入/热更新一致；少一个 composable、一个大型查询函数和相关加载/错误状态。
- 兼容分页接口的数据最多滞后一个快照 TTL，与其他驾驶舱面板一致；如未来单位数量增长到不适合全量快照，必须为所有单位台账一起迁移，不重新制造单屏特例。
- 直到生产 HeatWave 补载与健康验证完成前，KI-090 保持 `IN-PROGRESS`，且本决策相关代码不单独部署。

## 2026-09-21 实施记录

提交 `7a5193c` 已通过 GitHub Actions Quality/Deploy 并发布为生产 release `20260921-115005`。
经授权的 HeatWave 看门狗只补载了 `sys_user`、`data_readiness`、`daily_stats`，健康状态由
9/12 `DEGRADED` 恢复为 12/12 `HEALTHY`。本记录不改写上述决策时点的前置条件；KI-090 仍保持
`IN-PROGRESS`，直到后续维护窗口完成一次实际回退演练。
