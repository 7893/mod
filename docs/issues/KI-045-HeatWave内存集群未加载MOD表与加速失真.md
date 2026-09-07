# KI-045 · HeatWave 内存集群未加载 MOD 表与加速失真

- 状态：OPEN
- 优先级：P1
- 更新日期：2026-09-07
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[HEATWAVE使用与边界](../development/HEATWAVE-USAGE-AND-BOUNDARIES.md)

## 结论

文档宣称生产大屏由 Oracle HeatWave 内存集群加速，但实际只读核验发现：
1. 生产 HeatWave 节点（16GB RAM）处于在线状态，当前已加载的 11 张表全属于另一数据库 `modo_db`。
2. `mod` 数据库的所有大表虽在 DDL 中声明了 `SECONDARY_ENGINE="RAPID"`，但实际均未执行 `SECONDARY_LOAD`（状态显示为 0）。
3. 数据库慢查询与诊断已累计记录 2253 次“表未加载导致不能下推 RAPID”；所有大屏聚合查询全部退化回普通 InnoDB 引擎执行。
4. 16GB 的 HeatWave 内存能力未得到有效利用，文档描述与生产实际失真。

## 修复目标

- 进行列裁剪分析与内存容量评估（MOD 数据库表整体估算约 1.71 GB，远低于 16GB 限制）。
- 挑选高频聚合大表执行 `SECONDARY_LOAD`，确保只加载核心报表字段。
- 使用 `EXPLAIN` 验证执行计划出现 `Using secondary engine RAPID`，消除虚假加速。

## 进度

- 2026-09-07：现场核验并立项。
