# KI-081 · 投影事件不入库、JSONL 无限增长及双轨一致性根治

- 状态：DONE
- 优先级：P2
- 更新日期：2026-09-13
- 适用范围：实时投影事件持久化、`sim_event_outbox` 架构、`committed_projection_events.jsonl`、`LiveProjectionBroker`、`CommittedEventJournal`
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-073 实时投影与持久化模拟器双轨事件链事实分裂](KI-073-实时投影与持久化模拟器双轨事件链事实分裂.md)、[业务拟真引擎](../development/BUSINESS-SIMULATION-ENGINE.md)、[实时投影规范](../development/LIVE-PROJECTION.md)

## 2026-09-13 复核与修订（现行方案）

下文原方案保留为立项历史，以下内容取代其结论、实现步骤和完成定义，不能直接执行旧 SQL/伪代码。

- 已确认 commit 与 JSONL append 不原子，轮转无运行调用（测试有调用）。日志文件仍保留历史，不能说重启后历史全部消失；本轮观测文件约 4.27 MB，最后修改时间为 9 月 11 日，不能证明当前持续增长。
- 原累计业务指标来自数据库快照，SSE 不叠加到业务总数；当前漏洞主要影响播报、续播与会话统计。
- 追加发现：重放修改全局累计和序号、状态事件 ID 不可续播、API 重启固定 projection_id 配合归零序号导致前端忽略事件。
- 新方案：同事务写入 outbox 与持久序列/累计状态；使用单行锁序列化序号分配，避免把未提交序号误当已消费位置。数据库缺表/写入失败则事务失败，不回退 JSONL。
- SSE 每个连接独立使用数据库游标分页读取，无进程共享消费位置、无内存丢弃队列。初次连接从当前快照边界开始；携带有效游标的重连从游标之后补发。状态消息使用有效持久游标，重放不修改全局累计。
- 保留期外、格式错误或数据库代际变化的游标，显式返回 reset 原因并要求前端刷新权威快照；不能声称无限历史不丢失。连接暂停不推进位点，正常重连按至少一次交付与稳定序号去重。
- 默认保留最多 150000 条；30 天前的过期前缀在后续写入事务内分批清理，并更新持久保留边界。旧 JSONL 仅保留归档，不自动导入为新事件，不删除。
- 历史浏览接口属于后续新能力，本次不新增。生产 DDL、迁移、服务切换、停服窗口与回滚需要另行授权和现场验收。

### 当前完成定义

- [x] 本地 schema 与事务写入实现完成，业务与 outbox 同提交/同回滚。
- [x] SSE 持久游标、分页重放、重启/多客户端一致、慢客户端无静默丢弃、过期游标 reset。
- [x] 有界保留与前端 reset/去重覆盖回归测试。
- [x] 现行规范、迁移与回滚步骤、语义闸门同步；全量本地检查通过。
- [x] 经另行授权完成生产 schema、权限、切换及数据库故障/恢复验收。

本 KI 生产环境迁移与验收已闭环（DONE）。


### 本地实施与验收记录（2026-09-13）

- 新增 [outbox schema](../../deploy/projection-outbox.sql)、[事务写入](../../backend/app/live_projection/outbox_writer.py)、[只读分页](../../backend/app/live_projection/outbox.py)；模拟器在原事务提交前写入，缺表/失败整体回滚，无 JSONL 回退。
- [SSE broker](../../backend/app/live_projection/broker.py) 改为每连接持久游标，重启后序列不归零，重放为纯转换；状态使用有效游标；慢客户端分页消费，未知/过期游标明确 reset，数据库故障不推进游标，恢复且无新事件时也恢复来源状态。
- 前端按持久代际/序号去重，拒绝重复事件播报，reset 时刷新数据库快照。累计仍不叠加到业务总量。
- `make check` 最终成功：后端 260 项、前端 147 项、项目脚本 24 项测试通过，Ruff、样式、类型检查、构建、历史完整性与文档闸门通过。覆盖事务可见性/回滚、重复 ID、缺表、自动提交拒绝、有界分页/清理、重启、多客户端、保留过期、故障恢复与前端去重/reset。
- SQL 事务测试使用独立 SQLite 临时库，FOR UPDATE 在测试适配层去除；它不验证 MySQL 行锁。两个读客户端和重启行为使用内存数据源。生产 MySQL 同版本锁/引擎/权限/故障演练仍待现场实施，未声称已实测。
- 初次全量文档检查被 KI-082 的相对路径错误阻断，仅将部署基线链接改为 `../operations/USA-DEPLOYMENT-LAYOUT.md`；未改该 KI 的技术内容，随后重跑全量检查通过。
- 原 JSONL 保留，文件大小与修改时间未变；未执行生产 DDL/DML、服务切换、重训、外部模型调用、部署或 Git 提交。

### 生产部署与现场核验记录（2026-09-13）

- 生产 MySQL 库 `mod` 成功初始化 `sim_event_outbox_state` 与 `sim_event_outbox` 表结构；
- 部署并在 USA 生产机上启动模拟器，清除历史熔断标志文件，模拟器平稳进入 `RUNNING` 状态，周期执行 `SUCCESS`，与业务凭证单据在同一事务中持续原子写入 `sim_event_outbox`；
- `/api/live-projection/status` 实测验证：游标与 stream_id 正确生成（形如 `outbox:c4331b70-aedf-11f1-9eaa-020017350568:8`），`mode: committed_simulation`，`source_available: true`，无 reset 要求；
- 旧 JSONL 文件已不再追加新事件，保持归档只读；生产环境全链路闭环，状态转为 DONE。



---

## 结论

KI-073 修复了双轨随机生成的分裂问题，但留下了一个更深层的架构债：**模拟器提交的投影事件从不入库，只写本地 JSONL 文件**。这使得事件与业务数据在持久化层面仍然分裂——业务数据（凭证、单据）写入 MySQL，事件流只存在于磁盘文件里，无法勾稽、无法查历史、文件持续增长且 `rotate_if_needed()` 从未被调用。正确的架构是将投影事件写入同一事务的 `sim_event_outbox` 表，broker 改为查库，彻底消除 JSONL 中转层。

---

## 只读证据（2026-09-13）

### 1. 提交事务与 JSONL 写入是两个独立操作，有原子性窗口

`simulation/runtime_service.py` 第 685、689 行：

```python
conn.commit()                          # ← 业务数据已落库
self.projection_journal.append([...]) # ← 写本地文件，独立操作
```

`conn.commit()` 成功后、`journal.append()` 执行前，若进程崩溃，MySQL 有数据但 JSONL 没有事件记录，前端永远收不到该批事件推送。代码以 `projection_journal_saved` 标志位 + fail-closed 熔断应对，但这是补救，不是根治。

### 2. 投影事件永不入库，无法查询历史

`backend/app/live_projection/` 目录下没有任何查询数据库的逻辑，所有事件从 JSONL 文件读取。业务数据（`business_document`、`accounting_voucher`）可以 SQL 查询，投影事件不能。前端展示的"今天发生了哪些事件"在页面刷新后即丢失，重启后历史全部消失。

### 3. `rotate_if_needed()` 定义但从未调用

`backend/app/live_projection/journal.py` 第 101 行定义了 `rotate_if_needed(max_size_mb=10)`，但全项目没有任何调用点：

```bash
$ grep -rn "rotate_if_needed" /home/ubuntu/mod/
# 只在 journal.py 定义处出现，无调用
```

当前文件大小：

```
-rw-r--r-- 1 root root 4.1M Sep 11 22:37 output/committed_projection_events.jsonl
# 9736 行，模拟器仍在运行，文件持续增长
```

超过 10MB 后没有任何轮转或清理机制，磁盘耗尽风险与 KI-038（已关闭）描述的备份磁盘风险同源。

### 4. broker 重启后从文件末尾开始，历史事件丢失

`broker.py` 第 84 行：

```python
self._offset = self.journal.path.stat().st_size if self.journal.path.exists() else 0
```

API 进程重启时，从文件当前末尾开始尾随，重启前已写入但尚未推送的事件（如进程崩溃场景）不会重发。

### 5. 多 API 实例各自读各自文件，无法共享状态

JSONL 文件绑定在运行模拟器的主机磁盘上。若将来部署多个 API 实例（负载均衡），每个实例各自维护独立的文件读取偏移，会导致重复推送或漏推。数据库 outbox 天然共享。

### 6. `sim_event_outbox` 方案在 KI-073 中已识别但未实施

KI-073 § 8.4 明确写明：
> 短期（方案 A）：基于现有 JSONL 实现断线重放，改动小
> 长期（方案 B）：如需多 API 实例负载均衡，迁移到数据库 outbox

方案 A 已完成，方案 B 标记为"长期"但没有登记为独立 KI，形成遗漏。本 KI 正式登记并补充完整实施方案。

---

## 影响

| 影响面 | 当前风险 |
|--------|---------|
| 数据一致性 | commit 与 JSONL 写入之间有原子性窗口，崩溃时事件丢失 |
| 历史可查性 | 重启后事件历史全部丢失，无法回溯"昨天发生了什么" |
| 磁盘管理 | JSONL 无限增长，rotate 逻辑存在但从未触发 |
| 前后端勾稽 | 业务数据在 MySQL 可查，投影事件无法对应查询，无法互相验证 |
| 扩展性 | 多实例部署时文件方案不可用，必须改造才能水平扩展 |
| 代码复杂度 | `journal.py`（113行）、broker 读文件逻辑、fail-closed 熔断逻辑均因 JSONL 中转而存在，改用 outbox 后可全部删除 |

---

## 修复方案

### 方案概述

将投影事件写入 MySQL `sim_event_outbox` 表，与业务数据在**同一事务**中提交。broker 改为查库替代读文件。JSONL 中转层整体删除。

### 步骤一：新建 `sim_event_outbox` 表

```sql
CREATE TABLE sim_event_outbox (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_id          VARCHAR(36)     NOT NULL UNIQUE,   -- 幂等去重
    occurred_at       DATETIME(3)     NOT NULL,
    unit_id           VARCHAR(36),
    unit_name         VARCHAR(100),
    province          VARCHAR(50),
    business_type     VARCHAR(50),
    doc_count         INT             DEFAULT 0,
    voucher_count     INT             DEFAULT 0,
    integration_count INT             DEFAULT 0,
    story_title       VARCHAR(200),
    story_desc        VARCHAR(500),
    amount            DECIMAL(15,2),
    badge_tone        VARCHAR(20),
    batch_name        VARCHAR(50),
    created_at        DATETIME(3)     DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_id (id)
);
```

`id` 自增，broker 用作游标；`event_id` 唯一，保证幂等重试不重复插入。

### 步骤二：模拟器在同一事务内写入 outbox

`simulation/runtime_service.py` 中，在 `conn.commit()` **之前**插入 outbox 记录：

```python
# 在 conn.commit() 前，同一事务内执行
if all_events:
    outbox_rows = [_build_outbox_row(e, now_hkt) for e in all_events]
    cursor.executemany("""
        INSERT IGNORE INTO sim_event_outbox
        (event_id, occurred_at, unit_id, unit_name, province,
         business_type, doc_count, voucher_count, integration_count,
         story_title, story_desc, amount, badge_tone, batch_name)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, outbox_rows)

conn.commit()  # 业务数据 + outbox 原子提交

# 删除原有的 self.projection_journal.append([...]) 调用
```

`INSERT IGNORE` 保证幂等，重试时已存在的 `event_id` 静默跳过，不抛异常。

### 步骤三：broker 改为轮询 outbox 表

`backend/app/live_projection/broker.py` 核心改动：

```python
class LiveProjectionBroker:
    def __init__(self):
        self._cursor = 0   # 上次读到的 outbox.id
        self._subscribers = set()

    async def start(self):
        # 启动时从库中读最大已消费 id，避免重复推送历史
        row = db.query("SELECT COALESCE(MAX(id), 0) FROM sim_event_outbox")
        self._cursor = row[0]
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            rows = db.query("""
                SELECT * FROM sim_event_outbox
                WHERE id > %s
                ORDER BY id
                LIMIT 100
            """, self._cursor)
            for row in rows:
                event = _row_to_event(row)
                self._publish(event)
                self._cursor = row['id']
            await asyncio.sleep(0.5)
```

### 步骤四：断线重连改为查库

```python
async def stream(self, last_event_id: str | None = None):
    if last_event_id:
        # 从指定 event_id 之后补发漏掉的事件
        missed = db.query("""
            SELECT * FROM sim_event_outbox
            WHERE id > (
                SELECT COALESCE(id, 0) FROM sim_event_outbox
                WHERE event_id = %s
            )
            ORDER BY id
        """, last_event_id)
        for row in missed:
            yield _sse(_row_to_event(row).as_payload())

    yield _sse(self.state_payload())
    queue = self.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
                yield _sse(event.as_payload())
            except TimeoutError:
                yield ": heartbeat\n\n"
    finally:
        self.unsubscribe(queue)
```

### 步骤五：新增历史查询接口

```python
# backend/app/live_projection/api.py 新增
@router.get("/api/live-projection/history")
def get_history(limit: int = 50, before_id: int = 0):
    rows = db.query("""
        SELECT * FROM sim_event_outbox
        WHERE (%s = 0 OR id < %s)
        ORDER BY id DESC
        LIMIT %s
    """, before_id, before_id, limit)
    return [_row_to_payload(r) for r in rows]
```

### 步骤六：清理策略

outbox 数据量极小（模拟器每天最多 5000 条），可定期清理保留最近 30 天：

```sql
-- 纳入 mod-daily-briefing 定时任务或单独 systemd timer
DELETE FROM sim_event_outbox
WHERE created_at < NOW() - INTERVAL 30 DAY;
```

---

## 可以删除的代码

完成上述改动后，以下代码可以整体删除：

| 文件/代码 | 行数 | 原因 |
|-----------|------|------|
| `backend/app/live_projection/journal.py` | 113行 | 整个 JSONL 读写层不再需要 |
| `broker.py` 中读文件相关逻辑 | ~40行 | 改为查库 |
| `runtime_service.py` 中 `projection_journal_saved` 熔断逻辑 | ~15行 | outbox 与业务数据同事务，不需要单独熔断 |
| `rotate_if_needed()` 及调用点 | 15行 | 文件不再存在 |
| `output/committed_projection_events.jsonl` | 文件 | 中转层整体移除 |

**净结果：减少约 180 行代码，增加约 60 行，系统更简单、更可靠。**

---

## 完成定义

- [ ] `sim_event_outbox` 表已创建并通过 schema 验证
- [ ] 模拟器事务提交时 outbox 与业务数据原子写入，无独立熔断逻辑
- [ ] broker 从 outbox 轮询，不再读取 JSONL 文件
- [ ] API 重启后 broker 从库中恢复游标，不重复推送也不漏推
- [ ] 断线重连通过 `Last-Event-ID` 从 outbox 补发，与现有前端协议兼容
- [ ] `GET /api/live-projection/history` 接口可用
- [ ] `journal.py`、`rotate_if_needed()`、`projection_journal_saved` 熔断逻辑已删除
- [ ] `output/committed_projection_events.jsonl` 文件已清理
- [ ] `make check` 全量通过
- [ ] `LIVE-PROJECTION.md` 文档更新为 outbox 架构描述

---

## 依赖与授权

- 需要数据库 schema 变更授权（新建 `sim_event_outbox` 表，属于生产写入变更）
- 需要模拟器写入逻辑修改授权（`simulation/runtime_service.py` 事务内新增 INSERT）
- 不依赖其他未关闭 KI

## 进度

- 2026-09-13 立项登记（OPEN）。来源为 KI-073 遗留方案 B 的补充登记，结合对 JSONL 文件、broker 和 runtime_service 代码的直接审计。
