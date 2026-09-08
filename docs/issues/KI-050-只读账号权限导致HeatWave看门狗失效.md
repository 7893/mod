# KI-050 · 只读账号权限导致 HeatWave 看门狗观测与自愈失效

- 状态：DONE
- 优先级：P2
- 更新日期：2026-09-08
- 适用范围：KI-041 只读账号隔离 与 KI-049 HeatWave 看门狗 的权限交互闭环
- 关联：[KI-041 API 与模拟器共用可写数据库账号及公网无认证暴露](KI-041-API与模拟器共用可写数据库账号及公网无认证暴露.md)、[KI-049 HeatWave 内存加速看门狗与自愈机制缺失](KI-049-HeatWave内存加速看门狗与自愈机制缺失.md)、[HeatWave 使用与边界](../development/HEATWAVE-USAGE-AND-BOUNDARIES.md)

---

## 结论

已彻底完成只读账号权限最小补授与架构自愈职责解耦：
1. **最小只读观测权限补齐**：为 API 生产只读账号 `mod_readonly` 补授 `performance_schema.rpd_tables` 与 `performance_schema.rpd_table_id` 的 `SELECT` 权限。不赋给任何 DML/DDL 权限，严守 KI-041 的只读安全边界。`/api/health` 探针真实反映 HeatWave 加载状态（实测 9/9 表全部处于 `HEALTHY`）。
2. **自愈职责解耦（策略 b+c）**：
   - **API 进程纯只读观测**：`FastAPI lifespan` 开机与 `/api/health` 仅调用 `get_heatwave_status()` 实施轻量只读观测（~1ms），彻底去除在只读 API 进程内尝试执行 `ALTER TABLE` 的越权动作；
   - **独立运维看门狗守护进程（Timer 托管）**：落地 `mod-heatwave-watchdog.service` 与 `mod-heatwave-watchdog.timer`，开机 1 分钟后及每 5 分钟执行一次 `heatwave_manager.py watchdog`。该服务由 systemd 运行，加载具备管理凭据的 `.env.systemd`；若检测到表脱落，自动触发 `cmd_load()` 发起 `SECONDARY_LOAD` 完成秒级自愈。
3. **物理拦截核验**：实测 `mod_readonly` 账号对业务表执行 `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` 操作 100% 继续被 MySQL 物理拦截并返回 `OperationalError 1142`。
4. **自动化回归**：`test_heatwave_watchdog.py` 增补只读账号遭遇 1142 异常时的优雅防御测试，全量 195 项后端单测、84 项前端单测全绿，`make check` 100% 通过。

## 背景

KI-041 将生产 API 切换为只读数据库账号（仅授予业务库与模型库的 `SELECT`），KI-049 新增了应用层
HeatWave 看门狗（观测 9 张核心表的列存加载状态，并在缺失时补发 `SECONDARY_LOAD` 自愈）。

两个改动单独看都正确，但**组合后产生缺陷**：看门狗运行在 API 进程内、使用只读账号，而只读账号
既无权读取 `performance_schema` 的 HeatWave 状态表，也无权执行 `ALTER TABLE ... SECONDARY_LOAD`。

## 现象（2026-09-08 实测）

- `/api/health` 已如 KI-049 设计透出 `heatwave` 对象，但内容一度退化为：
  - `status: UNKNOWN`、`loaded_count: 0`、9 张核心表全部落入 `missing_tables`
  - `notice: "HeatWave performance_schema unreadable or mocked"`
- 用高权限账号交叉核验：`performance_schema` 中共 20 张表已加载，业务库 9 张核心表**全部仍处于
  已加载状态**（列存加速实际正常）。

## 根因

1. **观测盲**：只读账号无 `performance_schema` 读取权限，看门狗查询 `rpd_tables` / `rpd_table_id`
   失败，只能报 `UNKNOWN`，无法反映真实加载状态。
2. **自愈瘫**：即便探测到表缺失，只读账号也无权执行 `ALTER TABLE ... SECONDARY_LOAD`，
   KI-049 声称的“自动补偿加载”在生产账号下无法执行。

## 修复落地细节

### 1. 最小权限授权

通过高权限管理账号执行最小权限显式授权：
```sql
GRANT SELECT ON performance_schema.rpd_tables TO 'mod_readonly'@'%';
GRANT SELECT ON performance_schema.rpd_table_id TO 'mod_readonly'@'%';
```
授权后 `mod_readonly` 完整权限表：
```text
GRANT USAGE ON *.* TO `mod_readonly`@`%`
GRANT SELECT ON `mod`.* TO `mod_readonly`@`%`
GRANT SELECT ON `ML_SCHEMA_admin`.* TO `mod_readonly`@`%`
GRANT SELECT ON `performance_schema`.`rpd_table_id` TO `mod_readonly`@`%`
GRANT SELECT ON `performance_schema`.`rpd_tables` TO `mod_readonly`@`%`
```

### 2. API 生命周期只读改造与防御

修改 `backend/app/main.py` 与 `backend/app/heatwave_watchdog.py`：
- `main.py` 的 `lifespan` 改为调用 `get_heatwave_status(conn)` 做状态探测与日志打印；
- `heal_heatwave_tables()` 增加针对 MySQL 1142（Permission Denied）的捕获与降级逻辑，在只读连接传入时记录清晰原因，避免无意义重试与错误扩散。

### 3. 运维守护进程与周期定时器

在 `deploy/` 与 `/etc/systemd/system/` 部署：
- `mod-heatwave-watchdog.service`：调用 `backend/.venv/bin/python .../heatwave_manager.py watchdog`，以独立运维环境运行；
- `mod-heatwave-watchdog.timer`：`OnBootSec=1min`, `OnUnitActiveSec=5min`，持续守护。
实测 `sudo systemctl start mod-heatwave-watchdog.service` 输出：
```text
[OK] HeatWave 内存加速正常，全部 9 张核心表已就绪 (AVAIL_RPDGSTABSTATE)。
Deactivated successfully.
```

## 验收证据

1. **接口核验**：
   `curl http://127.0.0.1:8100/api/health` 实时输出：
   ```json
   {
     "status": "ok",
     "database": "mod",
     "session_timezone": "+08:00",
     "now_cst": "2026-09-08 11:27:51",
     "heatwave": {
       "status": "HEALTHY",
       "loaded_count": 9,
       "total_target": 9,
       "loaded_tables": [
         "accounting_voucher",
         "accounting_voucher_line",
         "business_document",
         "business_document_line",
         "construction_task",
         "dual_run_result",
         "integration_result",
         "org_unit",
         "rollout_status_snapshot"
       ],
       "missing_tables": []
     }
   }
   ```
2. **只读安全性核验**：
   使用 `mod_readonly` 账号执行破坏性注入，全部被物理拦截：
   - `INSERT INTO business_document ...` -> `OperationalError 1142`
   - `UPDATE business_document ...` -> `OperationalError 1142`
   - `DROP TABLE test_doc` -> `OperationalError 1142`
   - `ALTER TABLE business_document SECONDARY_LOAD` -> `OperationalError 1142`
3. **回归验证**：
   - `pytest tests/test_heatwave_watchdog.py`: 7 passed in 0.66s.
   - `make check`: 195 项后端单测、84 项前端单测、Doc Links 125 文件全部绿灯通过。

## 进度

- 2026-09-08 立项建档（OPEN）。
- 2026-09-08 完成 `mod_readonly` 最小权限授权、API 只读观测闭环、系统看门狗 Timer 服务部署与回归验证，状态转为 DONE。
