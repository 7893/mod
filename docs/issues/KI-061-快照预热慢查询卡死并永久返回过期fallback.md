# KI-061 · 快照预热慢查询卡死并永久返回过期 fallback

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-08
- 适用范围：大盘快照日期锚点查询、SWR 预热与刷新状态机、fallback 结构契约、API 健康探针及生产发布验收
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-059 全场景秒级响应 SLA 保障](KI-059-全场景秒级响应SLA保障与台账筛选分页死锁治理.md)、[KI-046 数据库依赖与健康探针治理](KI-046-数据库依赖双重yield与发布健康探针掩盖故障.md)、[测试规范](../development/TESTING-STANDARD.md)

---

## 结论

生产 API 的大盘快照后台预热被日期锚点 SQL 长时间卡住，SWR 状态机因此无法把启动时预装的旧
fallback 替换为实时快照。旧 fallback 又未包含后来新增的趋势与双轨明细字段，直接造成 C3、D3、D6
等面板显示空态。数据库连接与 HeatWave 装载探针仍返回健康，`refresh-meta` 也把旧 fallback 误报为
`live`，导致发布和运行监控未能发现故障。

该问题不是前端图表布局或 ECharts 渲染缺陷，不得通过硬编码数据、隐藏空态或放宽字段要求掩盖。

## 生产现象与只读证据

2026-09-08 只读核查确认：

1. 实际服务 `mod-api.service` 正常监听 `127.0.0.1:8100`，数据库连接与 HeatWave 9 张目标表装载状态均为健康。
2. `/api/dashboard/snapshot` 持续返回生成于 2026-09-04 的旧结构快照：
   - 顶层缺少 `rolloutTrend`，C3 进入“暂无批次历史快照”空态；
   - 顶层缺少 `operationsTrend`，D3 进入“暂无连续日吞吐数据”空态；
   - `operations` 缺少 `dualRunConsistent` 与 `dualRunInconsistent`，D6 进入“当前快照未提供双轨明细”空态。
3. MySQL `SHOW FULL PROCESSLIST` 同时发现 4 个只读快照刷新会话卡在同一条 SQL，最长已执行约 66 分钟：

   ```sql
   SELECT MAX(DATE(submit_time)) AS docs_as_of_date
   FROM business_document
   WHERE submit_time < :anchor_date;
   ```

4. `business_document.submit_time` 已有独立索引，但原 SQL 的执行计划为在 HeatWave RAPID 次级引擎中扫描
   约 587 万行，再对 `DATE(submit_time)` 做聚合；计划成本约 3.3 亿。
5. 语义等价的索引友好表达 `DATE(MAX(submit_time))` 的只读 `EXPLAIN` 显示
   `Rows fetched before execution`，无需扫描全表。该结果只证明优化方向，实施时仍须验证边界日期语义。
6. 服务重启后预热线程只记录“已触发”，不再记录“刷新就绪”或异常；停止服务连续发生 5 秒超时并被
   systemd 强制终止。每次重启会再产生一个同类长查询，形成资源堆积。

## 根因

### 1. 日期锚点 SQL 破坏最大值索引优化

`MAX(DATE(submit_time))` 先对每行时间执行 `DATE()`，再求最大值，优化器无法直接从
`idx_doc_submit_time` 取得满足上界条件的最后一个值。查询被路由到 RAPID 后仍是全表扫描；免费层单核
在当前约 587 万行规模下无法满足快照预热时限。

### 2. SWR 对“永久不返回”的构建缺少时限和熔断

`_background_refresh_snapshot()` 只有在构建返回或抛出异常后才会清除 `_snapshot_refreshing`。数据库调用
无限期处于 `executing` 时，状态永久停留在“刷新中”，后续请求只能持续读取旧缓存，也不会触发新的有效刷新。
当前连接仅配置连接超时，没有为查询执行设置明确上限。

### 3. fallback 未跟随快照字段契约演进

后端与前端 bundled fallback 均缺少 `rolloutTrend`、`operationsTrend`、`dualRunConsistent` 和
`dualRunInconsistent`。SWR 失效后，旧快照仍能维持多数老面板，却使依赖新增字段的面板集中空白，形成
“接口 200、部分页面失效”的隐蔽故障。

### 4. 健康与元数据探针没有检查快照新鲜度和来源

`/api/health` 只验证数据库连接与 HeatWave 装载，不验证快照刷新是否在限定时间内完成；
`refresh-meta` 仅根据请求依赖能否取得数据库连接判定 `live/frozen`，没有读取当前缓存的真实来源、生成时间和
刷新状态。因此旧 fallback 被错误标记为实时数据，发布健康门禁无法阻止缺字段版本上线。

## 影响范围

- 用户可见：C3、D3、D6 当前无数据；未来任何只依赖新增可选快照字段的面板都可能同样失效。
- 数据库：服务每次重启可能遗留新的全表扫描，持续占用免费 HeatWave 单核资源并拖慢其他分析查询。
- 服务生命周期：后台线程与数据库调用无法及时退出，`mod-api.service` 停止超时并被 SIGKILL。
- 可观测性：HTTP 200、健康探针 `ok` 与 `data_version=live` 均不能证明大盘快照可用。
- 发布：现有发布验收只验证服务与数据库连接，不能发现字段契约缺失和快照陈旧。

## 修复要求

### A. 消除锚点全表扫描

1. 将日期锚点查询改为可使用 `idx_doc_submit_time` 最大值优化的等价表达，例如先求
   `MAX(submit_time)` 再在结果上转换日期。
2. 以 `EXPLAIN` 和只读计时同时验收，确认不再出现 RAPID 全表扫描，且 `< :anchor_date` 的边界语义、
   空表行为与展示时区保持不变。
3. 不新增重复索引；现有 `idx_doc_submit_time` 已能覆盖正确写法。

### B. 给 SWR 建立有界失败状态

1. 为快照构建设置明确的查询执行超时或可取消边界；超时必须记录结构化错误并释放连接。
2. 刷新失败或超时后必须可靠清除“刷新中”状态，并采用有上限的退避重试，禁止每个请求或每次重启堆积查询。
3. 服务停止时不得因快照线程无限等待超过 systemd 停止时限；不得以延长 `TimeoutStopSec` 掩盖查询不可取消。
4. 保持前台请求快速返回，但必须显式暴露当前返回的是实时缓存、陈旧缓存还是 fallback。

### C. 补齐 fallback 结构契约

1. 后端与前端 fallback 必须包含当前快照 Schema 的全部面板依赖字段。
2. fallback 数据只能来自可追溯、已核验的冻结快照；不得为填满面板编造趋势或一致率。
3. 缺乏可验证数据时允许返回空数组或 `null`，但状态和接口元数据必须明确标记为 fallback/degraded，不能冒充 live。

### D. 收紧健康探针与发布门禁

1. 健康输出至少包含快照来源、最近一次成功刷新时间、刷新耗时/状态和失败原因分类，不暴露 SQL 或凭据。
2. `refresh-meta` 必须根据实际缓存来源判断 `data_version`，不得仅凭数据库连接存在就声明 `live`。
3. 发布验收必须检查 C3/D3/D6 所需字段结构、快照新鲜度及最近刷新成功状态；连接健康但快照陈旧时不得判定发布成功。
4. 为快照刷新长期运行、连续失败和陈旧 fallback 建立日志或监控告警。

### E. 处置现有遗留查询

修复部署并验证新查询计划后，重新只读解析当时仍存活的精确会话；终止遗留查询属于生产数据库控制操作，
必须单独获得授权。不得把本次诊断时观察到的会话编号写死到脚本或操作手册中。

## 禁止性做法

- 不得在前端为 C3、D3、D6 填写硬编码趋势、成功率或一致/差异数量。
- 不得只更新 fallback 而保留会永久卡死的 SQL 与 SWR 状态机。
- 不得仅延长 HTTP、数据库或 systemd 超时时间掩盖全表扫描。
- 不得通过隐藏空态、始终返回 HTTP 200 或继续把 fallback 标记为 live 制造“恢复”。
- 不得在未经授权和重新核验目标的情况下执行 `KILL`、重启服务或修改生产数据库。

## 自动化回归要求

1. 后端单测覆盖日期锚点查询的边界语义，并以结构断言防止重新写成 `MAX(DATE(indexed_column))`。
2. API 测试模拟快照构建成功、抛错和超时，验证刷新状态可恢复、旧缓存来源被准确标记且不会并发重复构建。
3. fallback 契约测试断言 C3/D3/D6 所需字段存在且类型兼容。
4. 健康与 `refresh-meta` 测试覆盖 live、stale、fallback、refreshing、failed 状态，禁止数据库连接健康时误报缓存来源。
5. 发布脚本测试或静态契约检查必须证明缺字段、过期快照或刷新失败能够触发发布失败/回滚。

## 验收标准

- [x] 原日期锚点 SQL 已改为索引友好写法，`EXPLAIN` 不再扫描约 587 万行的 `business_document`。
- [x] 快照构建在约定时限内成功；超时/异常时连接、线程和 `_snapshot_refreshing` 均能可靠恢复。
- [x] 连续刷新与服务重启不会新增长期 `executing` 的同类查询，服务可在停止时限内退出。
- [x] 实时 `/api/dashboard/snapshot` 返回非空、结构正确的 `rolloutTrend`、`operationsTrend`、
      `dualRunConsistent` 与 `dualRunInconsistent`，C3、D3、D6 恢复真实数据展示。
- [x] fallback 与当前快照字段契约一致，且其来源和新鲜度不会被误报为 live。
- [x] `/api/health`、`refresh-meta` 与发布门禁能识别快照陈旧、刷新超时和字段缺失。
- [x] 新增自动化回归测试，后端测试、前端契约测试及 `make check` 全量通过。
- [x] 生产只读验收确认数据库无本问题遗留的长期扫描，API 延迟与 HeatWave 资源恢复正常。

## 实施授权边界

本 KI 仅登记已确认的生产缺陷和修复验收边界，不授权数据库写入/会话终止、服务启停、Nginx 变更、
生产发布或云资源操作。实施阶段应先完成代码与自动化测试；涉及生产控制时须重新只读核验并取得明确授权。
