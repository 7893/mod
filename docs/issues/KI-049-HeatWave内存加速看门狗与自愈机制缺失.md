# KI-049 · HeatWave 内存加速看门狗与自愈机制缺失

- 状态：DONE
- 优先级：P2
- 更新日期：2026-09-08
- 适用范围：HeatWave RAPID 内存集群加速状态观测、后端健康探针增强与应用级自愈机制
- 关联：[KI-045 HeatWave 内存集群未加载 MOD 表与加速失真](KI-045-HeatWave内存集群未加载MOD表与加速失真.md)、[HEATWAVE使用与边界](../development/HEATWAVE-USAGE-AND-BOUNDARIES.md)、[已知问题看板](../KNOWN-ISSUES.md)

---

## 结论与背景

在 KI-045 中，系统完成了对 9 张核心报表大表加载入 Oracle HeatWave（RAPID）内存集群的操作，并验证了全量聚合查询命中 `Using secondary engine RAPID`。然而在进一步的系统鲁棒性审计中发现：

1. **宿主机重启与维护后的静默降级（Silent Degradation）风险**：
   - HeatWave 是内存列存引擎，当 MySQL DB System 宿主机发生重启、云端维护、或长连接重连时，根据 Oracle 官方文档（*MySQL HeatWave Cluster Data Recovery*），在包含字典编码列、未打检查点或 Binlog 截断等场景下，对象存储自动恢复可能中断；
   - 因 OCI 托管云权限策略限制，普通租户管理员无权执行 `SET PERSIST rapid_reload_on_restart = ON`；
   - 后端会话当前配置为 `SET use_secondary_engine = ON`（智能成本路由），一旦表在内存中脱落，MySQL 优化器**不会抛出任何报错，而是默默回退到磁盘 InnoDB 行存全表扫描**，导致查询延迟由数十毫秒突增至数秒，运维与业务人员难以在第一时间察觉。
2. **缺乏应用层状态观测与主动自愈（Watchdog & Self-Healing）**：
   - 后端 `/api/health` 探针仅校验 `SELECT 1` 与时区，对 HeatWave 加速状态完全盲区；
   - 后端启动生命周期（`lifespan`）缺少对 9 张核心加速表的就绪性自检，无法在开机或故障恢复后主动拉起补偿加载。

---

## 修复实施

1. **应用内置轻量看门狗模块 ([`backend/app/heatwave_watchdog.py`](../../backend/app/heatwave_watchdog.py))**：
   - `get_heatwave_status`：以 ~1ms 开销查询 `performance_schema.rpd_tables` 与 `rpd_table_id`，只读获取 9 张核心表就绪状态（`AVAIL_RPDGSTABSTATE`）；
   - `heal_heatwave_tables`：针对缺失表自动补发 `ALTER TABLE mod.<table_name> SECONDARY_LOAD` 完成闭环自愈；
   - `check_and_heal`：整合巡检与自愈，就绪时零动作，缺失时自动补偿。
2. **启动生命周期接入 ([`backend/app/main.py`](../../backend/app/main.py))**：
   - 在 FastAPI `lifespan` 启动钩子中执行 `check_and_heal` 开机自检与自愈，保障首批请求到达前 100% 就绪。
3. **健康探针透出 HeatWave 状态 ([`backend/app/api.py`](../../backend/app/api.py))**：
   - `/api/health` 响应中新增 `heatwave` 对象（`status: HEALTHY | DEGRADED`、`loaded_count`、`total_target`、`loaded_tables`、`missing_tables`），彻底消除加速可观测性盲区。
4. **运维 CLI 看门狗命令扩展 ([`scripts/project/heatwave_manager.py`](../../scripts/project/heatwave_manager.py))**：
   - 增加 `watchdog` 子命令（`python3 scripts/project/heatwave_manager.py watchdog`），可用于运维排障或 Systemd Timer / Crontab 周期巡检。
5. **单元测试与回归防线 ([`backend/tests/test_heatwave_watchdog.py`](../../backend/tests/test_heatwave_watchdog.py))**：
   - 覆盖健康、降级、异常容灾、自愈调用与 `/api/health` 端到端断言，测试全绿通过。

---

## 进度与验收

- 2026-09-08：完成问题分析与官方机理求证，正式立项建档；完成代码开发、单元测试与全工程 `make check` 验证，准备验收交付。
