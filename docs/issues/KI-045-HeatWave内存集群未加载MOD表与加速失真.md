# KI-045 · HeatWave 内存集群未加载 MOD 表与加速失真

- 状态：RESOLVED
- 优先级：P1
- 更新日期：2026-09-08
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[HEATWAVE使用与边界](../development/HEATWAVE-USAGE-AND-BOUNDARIES.md)

## 结论

文档宣称生产大屏由 Oracle HeatWave 内存集群加速，但实际只读核验发现：
1. 生产 HeatWave 节点（16GB RAM）处于在线状态，当前已加载的 11 张表全属于另一数据库 `modo_db`。
2. `mod` 数据库的所有大表虽在 DDL 中声明了 `SECONDARY_ENGINE="RAPID"`，但实际均未执行 `SECONDARY_LOAD`（状态显示为 0）。
3. 数据库慢查询与诊断已累计记录 2253 次“表未加载导致不能下推 RAPID”；所有大屏聚合查询全部退化回普通 InnoDB 引擎执行。
4. 16GB 的 HeatWave 内存能力未得到有效利用，文档描述与生产实际失真。

## 修复目标与实施

1. **容量核算与全量核心表载入**：
   - 评估 MOD 数据库各表结构与容量，经实测 9 张核心报表大表在 RAPID 列式压缩内存中仅占用约 752 MB，远低于 16GB 节点上限（空闲 11.82 GB）；
   - 对 9 张核心大表全量执行 `SECONDARY_ENGINE = RAPID` 与 `SECONDARY_LOAD`：
     - `business_document_line`：4,622,428 行，168 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `accounting_voucher_line`：2,957,692 行，148 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `business_document`：2,325,895 行，236 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `accounting_voucher`：1,478,846 行，116 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `integration_result`：1,391,678 行，64 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `rollout_status_snapshot`：144,872 行，4 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `construction_task`：63,182 行，8 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `dual_run_result`：31,306 行，4 MB，状态 `AVAIL_RPDGSTABSTATE`
     - `org_unit`：2,002 行，4 MB，状态 `AVAIL_RPDGSTABSTATE`
2. **定位并消除执行引擎优化器阻断（HW_ER_1142）**：
   - 排查发现后端 SQLAlchemy 默认以隐式事务 `autocommit=0` 发起查询，触发 HeatWave 优化器硬限制导致无法下推；
   - 在 `backend/app/db.py` 的 `create_engine` 中配置 `execution_options={"isolation_level": "AUTOCOMMIT"}`，并在连接建立时显式注入 `SET use_secondary_engine = ON`，彻底打通 API 到 RAPID 的下推管道。
3. **运维工具与执行计划验证闭环**：
   - 实现运维工具 [`scripts/project/heatwave_manager.py`](../../scripts/project/heatwave_manager.py)，提供 `status`、`load`、`verify` 三大指令；
   - 使用 `verify` 模块强制校验（`use_secondary_engine = FORCED`），7 项核心业务聚合查询 100% 出现 `Using secondary engine RAPID`，消除了虚假加速与降级损耗；
   - 增加单元测试 [`backend/tests/test_heatwave_manager.py`](../../backend/tests/test_heatwave_manager.py) 并通过全量校验。

## 进度

- 2026-09-07：现场核验并立项。
- 2026-09-08：完成全量 9 张核心表载入 HeatWave 内存集群，排查并修复后端 SQLAlchemy AUTOCOMMIT 阻断，实现管理工具与执行计划 100% RAPID 验证，问题关闭。

