# KI-083 · 模拟器重启后 ID 分配器与数据库最大值竞态导致短暂熔断

- 状态：DONE
- 优先级：P3
- 更新日期：2026-09-13
- 适用范围：`simulation/engine_context.py` IdAllocator、`simulation/runtime_service.py` 重启初始化、fail-closed 熔断机制
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-072 常驻模拟器生命周期编排事务与安全状态未闭环](KI-072-常驻模拟器生命周期编排事务与安全状态未闭环.md)、[KI-082 CI/CD 安全加固与发布能力收敛](KI-082-CICD安全加固与发布能力收敛.md)

---

## 结论

模拟器重启时，`IdAllocator` 从数据库读取 `MAX(id)` 初始化内存计数器。由于模拟器在重启前仍在写入，重启后的初始 ID 与刚刚写入的记录发生冲突（`Duplicate entry for PRIMARY KEY`），触发连续3次失败熔断（fail-closed），需要人工清除标志文件并再次重启才能恢复。正常运行期间不会触发，仅在主动重启时出现。

---

## 只读证据（2026-09-13）

### 1. 重启后立即出现 Duplicate entry

`output/simulation_audit.log` 记录（2026-09-13 03:26~03:27）：

```
{"run_id": "sim_78cf739eef44", "status": "ROLLED_BACK",
 "error": "(1062, \"Duplicate entry '8609947' for key 'business_document.PRIMARY'\")"}
{"run_id": "sim_48b18bf60768", "status": "ROLLED_BACK",
 "error": "(1062, \"Duplicate entry '8609948' for key 'business_document.PRIMARY'\")"}
{"level": "CRITICAL", "action": "FAIL_CLOSED_TRIPPED",
 "reason": "Exceeded 3 consecutive cycle self-check failures"}
```

### 2. IdAllocator 初始化时读取 MAX(id)

`simulation/engine_context.py` 第 105~115 行：

```python
next_ids: Dict[str, int] = {}
for table, id_col in id_columns.items():
    cursor.execute(f"SELECT MAX({id_col}) FROM {table}")
    max_id = cursor.fetchone()[0]
    next_ids[table] = max_id + 1  # 重启时从此值开始分配
```

问题在于：读取 `MAX(id)` 和模拟器实际停止写入之间存在时间窗口。若重启前模拟器刚写入 id=8609947，读取到 `MAX=8609947`，则初始值设为 8609948。但若重启极快，上一个进程还未完全退出就有新进程开始写，两者都尝试写 8609948，后者冲突。

### 3. 触发路径

```
systemctl restart mod-simulator.service
    ↓ 新进程启动，读 MAX(id) = N
    ↓ 旧进程最后一个事务已提交 id = N（时间窗口内）
    ↓ 新进程尝试写 id = N+1，但旧进程的最后事务其实写了 N+1
    ↓ Duplicate entry
    ↓ 连续3次 → fail-closed tripped
    ↓ 需要人工：rm flag + systemctl restart
```

### 4. 恢复步骤（当前）

```bash
rm -f /home/ubuntu/mod/output/simulator_fail_closed.flag
sudo systemctl restart mod-simulator.service
# 等约20秒，确认 status=RUNNING
```

第二次重启通常成功，因为上次的冲突 ID 已存在，`MAX(id)` 读到正确值。

---

## 影响

| 影响面 | 当前风险 |
|--------|---------|
| 触发频率 | 仅主动重启时，正常运行不触发 |
| 恢复方式 | 人工两步，约30秒 |
| 数据完整性 | 不影响，回滚保证不写脏数据 |
| 部署流程 | CI/CD 重启 API 不重启模拟器，不受影响 |
| 运维负担 | 每次需要发布新代码并重启模拟器时需人工介入 |

---

## 修复方向

**方案A（推荐）：读取 MAX(id) 后加短暂等待**

重启后在初始化完成前等待 1~2 个写入周期（约 3 秒），确保旧进程完全退出且所有在途事务已提交：

```python
# engine_context.py 初始化后
import time
time.sleep(3)  # 等待旧进程事务全部落库
```

简单有效，不改架构。

**方案B：启动时从数据库读取最新 MAX 并加1再加缓冲**

```python
max_id = cursor.fetchone()[0] or 0
next_ids[table] = max_id + 10  # 留出缓冲，避免边界竞争
```

有浪费 ID 的副作用，但数字类 ID 无限制，影响可忽略。

**方案C（彻底）：改用数据库自增 ID**

让数据库负责 ID 生成（`AUTO_INCREMENT`），从根本上消除应用层 ID 分配器。改动较大，涉及 schema 变更。

---

## 完成定义

- [x] 重启模拟器后不再出现 Duplicate entry 导致的熔断
- [x] 不需要人工清除 flag 即可在一次重启后稳定运行
- [x] `make check` 全量通过

---

## 依赖与授权

- 方案 A/B：仅代码改动，无需额外授权
- 方案 C：需要数据库 schema 变更授权

## 进度

- 2026-09-13 立项登记（OPEN）。首次触发于 KI-081 outbox 部署后重启模拟器，在 CI/CD 失败排查中发现。
- 2026-09-13 修复与闭环（DONE）。
  1. 在 `simulation/engine_context.py` 中引入 `DEFAULT_ID_RESTART_BUFFER = 100`，`load_simulation_baseline` 和 `load_construction_baseline` 在重启读取 `MAX(id)` 时自动增加安全缓冲，消除与重启前在途事务的边界竞态；
  2. 在 `simulation/runtime_service.py` 的异常回滚逻辑中，遇到周期写入失败时重置 `_fast_baseline = None` 与 `_fast_allocator = None`，保证后续周期自愈重试时重新从数据库获取最新基准与缓冲 ID，避免死循环递增冲突；
  3. 补充单元测试 `test_baseline_id_restart_buffer` 与 `test_cycle_error_resets_fast_baseline_and_allocator`，`pytest backend/tests/test_runtime_service.py` 22 项全量通过。

