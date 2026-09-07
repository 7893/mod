# MySQL HeatWave 集群使用指南与能力边界手册

更新日期：2026-09-07  
状态：现行参考手册  
适用范围：Oracle MySQL HeatWave（RAPID 引擎）在本项目中的使用方法、OLAP 加速机制、数据生命周期管理、系统表巡检与硬限制边界  
维护角色：agy 维护，主控（kiro）审阅  

---

## 本文定位

本文是 **MySQL HeatWave 集群与底层分析引擎（RAPID）的权威使用与边界手册**，系统解答“HeatWave 是如何加速的、怎么加载与卸载数据、SQL 是如何下推执行的、有哪些核心限制与踩坑点”。

- **与 [`HEATWAVE-AUTOML-CAPABILITIES.md`](./HEATWAVE-AUTOML-CAPABILITIES.md) 的分工与互补**：
  - 那份手册专讲 **库内机器学习（AutoML）** 的任务类型、模型训练、SHAP 归因与机器学习边界。
  - 本文系统讲解 **HeatWave 分布式内存列式分析引擎（RAPID）本身**：数据加载、CDC 实时同步、OLAP 聚合加速、优化器调度、性能 Schema 监控、DDL/SQL 语法限制与 Always Free 规格边界。
- **与本项目（MOD 大屏）架构的关系**：
  - 本系统库内沉淀了千万级业务单据与财务凭证（15M+ 行）。日常 OLTP 事务写操作由常驻模拟器（`mod-simulator`）持续写入 InnoDB；
  - 面向领导驾驶舱的大规模多维聚合、复杂穿透与统计查询，则交由 HeatWave 内存集群并行加速，实现“秒级出数、前后端无感知解耦”。

---

## 一、HeatWave 核心架构与加速原理

### 1.1 双引擎混合架构（InnoDB + RAPID）

MySQL HeatWave 绝非传统的“外挂独立数仓（ClickHouse/Greenplum/Doris）”，而是**直接深度内嵌于 MySQL 内核的原生双引擎架构**：

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MySQL Server 客户端连接                           │
│              (FastAPI / Python pymysql / MySQL CLI / DBeaver)                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ SQL 请求
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MySQL Server 查询层 (内核)                         │
│   ├── SQL 解析器 & 权限认证                                                 │
│   └── 基于代价的查询优化器 (Cost-Based Optimizer)                            │
│         ├── 代价 < 门槛 (100,000) 或含不支持语法 ──► 路由给 InnoDB 引擎       │
│         └── 代价 ≥ 门槛 且符合下推条件          ──► 卸载给 HeatWave (RAPID)   │
└──────────────────────┬───────────────────────────────────────┬──────────────┘
                       │                                       │
        [主存储引擎: 行式 OLTP]                  [次级引擎: 分布式内存列式 OLAP]
                       ▼                                       ▼
┌──────────────────────────────────────────┐    ┌─────────────────────────────┐
│          InnoDB 存储引擎 (磁盘/BufferPool)│    │   HeatWave 内存集群 (RAPID)  │
│  - 负责事务 ACID、主键索引、行级锁        │───►│  - 分布式 Shared-Nothing 架构│
│  - 真实业务数据源 (Single Source of Truth)│ CDC│  - 混合列式内存表 (In-Memory)│
│  - 承担日常 INSERT / UPDATE / DELETE 事务│同步│  - 向量化执行 (SIMD) 加速计算│
└──────────────────────────────────────────┘    └─────────────────────────────┘
```

1. **主引擎（Primary Engine - InnoDB）**：负责 OLTP 事务、行级锁、崩溃恢复与磁盘持久化，保证强一致性（ACID）。
2. **次级引擎（Secondary Engine - RAPID）**：即 HeatWave 内存集群。数据以列式压缩形态保存在集群内存中，按分区哈希打散到各节点，专跑高并发、大规模 OLAP 分析查询。
3. **内置 CDC 自动增量同步**：表被加载到 HeatWave 后，InnoDB 发生的任何变更（INSERT / UPDATE / DELETE）均由内部后台复制线程自动捕获并毫秒级推送到 HeatWave 内存，**零外部 ETL 工具、零人工同步管道**。

### 1.2 为什么 HeatWave 能快几十倍？
* **内存列式存储与字典压缩**：分析查询往往只读取其中少数几列，列式存储天然避免无用 I/O；字典编码大幅削减内存占用并使比较运算矢量化。
* **极度纯粹的 Shared-Nothing 分布式并发**：每个节点独立计算其内存切片，无中心锁竞争。
* **芯片级向量化计算（SIMD）**：充分利用现代 CPU 向量指令集，单时钟周期并行处理多条数据过滤。

---

## 二、数据生命周期管理（加载、同步与卸载）

### 2.1 数据加载标准四步法

在 MySQL HeatWave 中，数据表不会自动载入内存集群，必须显式声明并执行加载。标准工作流如下：

```sql
-- 【第一步】声明次级引擎为 RAPID（此时尚未载入内存，仅打上标记）
ALTER TABLE mod.business_document SECONDARY_ENGINE = RAPID;

-- 【第二步】列级裁剪优化（强烈推荐，节约珍贵内存）
-- 将不参与大屏分析的超长文本、备注列标记为 NOT SECONDARY
ALTER TABLE mod.business_document MODIFY audit_remark TEXT NOT SECONDARY;

-- 【第三步】执行加载：将数据转换为列式并推入 HeatWave 内存集群
ALTER TABLE mod.business_document SECONDARY_LOAD;

-- 【第四步】验证加载状态（确保为 AVAIL_RPDGSTABSTATE）
SELECT 
    t.NAME AS table_name,
    t.LOAD_STATUS,
    t.NROWS AS row_count
FROM performance_schema.rpd_tables t
JOIN performance_schema.rpd_table_id i ON t.ID = i.ID
WHERE i.NAME = 'mod/business_document';
```

### 2.2 卸载与清退指令

当需要释放集群内存或对表进行 DDL 重构时，执行卸载：

```sql
-- 仅从内存集群中清退数据，保留次级引擎标记
ALTER TABLE mod.business_document SECONDARY_UNLOAD;

-- 彻底解除与 HeatWave 引擎的绑定（完全退出 HeatWave）
ALTER TABLE mod.business_document SECONDARY_ENGINE = NULL;
```

### 2.3 核心铁律：加载状态下的 DDL 限制

> [!WARNING]
> **已加载表的 DDL 阻断铁律**  
> 一旦数据表处于 `SECONDARY_LOAD` 激活状态，**MySQL 严禁对其直接执行大部分结构修改类 DDL 操作**（如 `ALTER TABLE ADD/DROP COLUMN`、`RENAME TABLE`、`TRUNCATE TABLE` 等），否则会抛出错误并阻断执行。

**标准 DDL 维护流水线（三步走）**：
1. **先卸载**：`ALTER TABLE <table_name> SECONDARY_UNLOAD;`
2. **执行结构变更**：`ALTER TABLE <table_name> ADD COLUMN new_col INT ...;`
3. **重新加载**：`ALTER TABLE <table_name> SECONDARY_LOAD;`

---

## 三、查询加速与优化器调度机制

### 3.1 优化器如何决定是否走 HeatWave？

客户端发送任何一条 SQL 到 MySQL 端口时，完全使用标准 MySQL 协议与语法，应用层无需修改驱动。MySQL 查询优化器通过以下判定树自动决策：

1. **会话开关检查**：系统变量 `use_secondary_engine` 是否开启（默认为 `ON`）。
2. **事务自动提交检查**：当前会话必须是 `autocommit = ON`。在未提交的手工事务块中，为保障未决事务隔离，默认不卸载至次级引擎。
3. **语法与算子兼容性检查**：SQL 中涉及的所有数据类型、内置函数、子查询语法是否在 HeatWave 支持清单内。
4. **代价阈值评估（Cost Threshold）**：
   - 优化器评估该查询在 InnoDB 上的执行成本（Cost）。
   - 如果估算成本 $\ge$ `heatwave_min_query_cost`（默认值为 **100,000**），优化器判定下推带来的收益大于跨网络序列化开销，**自动下推给 RAPID 执行**；
   - 如果估算成本低于该阈值（如简单的 `SELECT * FROM tbl WHERE id = 1` 主键单点查询），优化器**坚决留在 InnoDB 本地执行**，避免大炮打蚊子。

### 3.2 关键会话参数与调试控制

| 参数 / 语法 | 可选值 | 行为与用途 |
|---|---|---|
| `use_secondary_engine` | `ON`（默认） | **自动智能路由**。符合条件则走 HeatWave；若语法不支持或成本不足，**静默降级回退到 InnoDB 执行**，业务完全不报错。 |
| `use_secondary_engine` | `OFF` | **强制禁用次级引擎**。所有查询一律走本地 InnoDB。用于性能压测比对（对比有无 HeatWave 的性能差距）。 |
| `use_secondary_engine` | `FORCED` | **强制走 HeatWave**。如果该查询由于语法、类型或成本原因无法下推，**直接报错抛出具体根因**（如 `ERROR 3889 (HY000)`）。排查“为什么我的慢 SQL 没走 HeatWave”的利器。 |

**针对单条 SQL 的 Optimizer Hint 注入（推荐开发调试使用）**：
```sql
-- 强制此条查询必须走 HeatWave，否则报错返回原因
SELECT /*+ SET_VAR(use_secondary_engine = FORCED) */ 
    province, 
    COUNT(*), 
    SUM(total_amount) 
FROM mod.business_document 
GROUP BY province;
```

### 3.3 如何验证查询是否真正命中了 HeatWave？

执行 `EXPLAIN` 查看执行计划，若在最外层或步骤中看到 **`Using secondary engine RAPID`**，即证明成功下推并由 HeatWave 内存集群执行：

```sql
EXPLAIN SELECT province, COUNT(*) FROM mod.business_document GROUP BY province;
```
*典型输出*：
```text
+----+-------------+-------------------+------------+------+---------------+------+---------+------+------+----------+------------------------------+
| id | select_type | table             | partitions | type | possible_keys | key  | key_len | ref  | rows | filtered | Extra                        |
+----+-------------+-------------------+------------+------+---------------+------+---------+------+------+----------+------------------------------+
|  1 | SIMPLE      | business_document | NULL       | ALL  | NULL          | NULL | NULL    | NULL | 2304 |   100.00 | Using secondary engine RAPID |
+----+-------------+-------------------+------------+------+---------------+------+---------+------+------+----------+------------------------------+
```

---

## 四、系统表巡检与监控运维

HeatWave 将其集群状态、表加载详情与查询统计暴露在 MySQL 的 `performance_schema` 专属表中。以下为运维巡检核心 SQL 库：

### 4.1 查看集群中所有表的加载状态与行数
```sql
SELECT 
    i.NAME AS schema_table,
    t.LOAD_STATUS,
    t.LOAD_PROGRESS,
    t.NROWS AS in_memory_rows,
    t.AUTO_UNLOAD
FROM performance_schema.rpd_tables t
JOIN performance_schema.rpd_table_id i ON t.ID = i.ID
ORDER BY t.NROWS DESC;
```
*状态值说明*：
* `AVAIL_RPDGSTABSTATE`：**已完全加载且就绪（正常可用）**。
* `LOADING_RPDGSTABSTATE`：数据正在加载转换中。
* `UNAVAIL_RPDGSTABSTATE`：不可用或已卸载。

### 4.2 查看节点拓扑与节点健康度
```sql
SELECT 
    NODE_ID,
    STATE,
    IP_ADDRESS,
    PORT,
    LAST_HEARTBEAT
FROM performance_schema.rpd_nodes;
```

### 4.3 查看 HeatWave 实际执行的查询计数统计
```sql
SHOW GLOBAL STATUS LIKE 'Heatwave%';
```
*关注指标*：
* `Heatwave_queries_offloaded`：成功下推给 HeatWave 处理的累计查询数（数值持续增长代表大屏分析正在生效）。
* `Heatwave_queries_failed`：下推后执行失败并回退的查询数。

---

## 五、核心能力边界与硬限制清单（Gotchas）

> [!CAUTION]
> **生产红线与官方限制**  
> 以下限制均基于 Oracle 官方规范逐条核定，在编写业务 SQL 与设计表结构时必须严格遵守。

### 5.1 免费层规格与云端限制（OCI Always Free）
1. **集群硬件上限**：`HeatWave.Free` 固定分配为 **1 个计算节点、16 GB 内存**。
   - 意味着载入内存的总数据量（经压缩后）不能突破内存上限，否则触发 OOM 导致加载失败。
   - 必须通过 `NOT SECONDARY` 剔除无用宽字段，严禁把不需要统计的大文本列灌入集群。
2. **零高可用（No HA）**：
   - 免费层不支持高可用部署（HA），不支持自动故障转移与只读副本。
3. **闲置自动停止策略（7-Day Idle Policy）**：
   - 连续 7 天 95th 百分位数的 CPU/网络利用率低于 15% 时，OCI 会将实例自动休眠（Stop）。
   - **本项目防患机制**：由常驻后台守护服务 `mod-simulator.service` 与每日简报定时器持续产生低频心跳，确保实例时刻处于活跃保护期。

### 5.2 表结构与字段约束
1. **强制要求物理主键（Primary Key）**：
   - 任何准备进入 HeatWave 的表，**必须拥有主键**。无主键的表执行 `SECONDARY_LOAD` 会直接报错（`ERROR 3877`）。
2. **列数上限**：单表最多不超过 **1,017 列**。
3. **完全不支持的数据类型**：
   - `GEOMETRY`（空间地理类型）
   - `BIT`
   - 超长二进制 `BLOB`
4. **字符串与长文本限制**：
   - 支持 `VARCHAR`, `CHAR`, `TEXT`，但在 CDC 增量同步时，单个 `TEXT` 字段的内容上限为 **65,535 字节**。超出截断或报错。

### 5.3 SQL 语法与执行限制
1. **排他锁语句不可下推**：
   - 任何带有行级锁、排他锁意图的查询（如 `SELECT ... FOR UPDATE`、`SELECT ... LOCK IN SHARE MODE`）**100% 无法下推到 HeatWave**，强制由 InnoDB 执行。
2. **临时表不可下推**：
   - 用户创建的临时表（`CREATE TEMPORARY TABLE`）不支持次级引擎。
3. **特定窗口函数与递归查询（CTE）限制**：
   - 极其复杂的递归 CTE、多层不兼容窗口函数可能无法下推，自动降级回 InnoDB。
4. **与 AutoML 并发互斥**：
   - HeatWave 集群内的常规 OLAP 查询与 `sys.ML_TRAIN` / `sys.ML_EXPLAIN_TABLE` **互斥排队**。在高并发大屏演示期间，严禁在前台接口中同步触发 AutoML 大模型重训练。

---

## 六、本项目（MOD 大屏）最佳实践口径

结合本项目在托管 MySQL HeatWave 上的实测数据与生产表现，制定如下团队落地规范：

1. **大屏接口只读契约（读写绝对分离）**：
   * 所有后端只读聚合接口（如 `/api/dashboard/snapshot`、`/api/operations/summary`）一律依托 HeatWave 的 `use_secondary_engine = ON`；
   * 后端连接池一律采用 `autocommit = True`，确保每条分析 SQL 都能合法进入代价优化器的下推管道。
2. **容灾自动降级兜底**：
   * 严禁在生产代码中使用 `use_secondary_engine = FORCED`。生产代码必须使用默认的 `ON`，确保万一 HeatWave 集群出现维护、节点重启或内存紧张时，查询能透明、平滑地自动回退到本地 InnoDB 跑出结果，**大屏前端永不崩盘、永不报 500**。
3. **非核心超长字段剔除**：
   * 业务单据表 `business_document` 与凭证表 `accounting_voucher` 中，凡属于经办人备注、审核流水详情等纯文本字段，若仅用于末端详情查看、不参与大屏 GROUP BY 聚合计算，一律标注 `NOT SECONDARY`，将宝贵的 16 GB 内存全量留给数值分析与时间线维度。

---

## 七、官方权威来源与参考文档

* [Oracle MySQL HeatWave User Guide](https://dev.mysql.com/doc/heatwave/en/)
* [MySQL HeatWave Limitations & Constraints](https://dev.mysql.com/doc/heatwave/en/mys-hw-limitations.html)
* [Supported Functions and Operators in HeatWave](https://dev.mysql.com/doc/heatwave/en/mys-hw-supported-functions.html)
* [Performance Schema RAPID Tables Reference](https://dev.mysql.com/doc/heatwave/en/mys-hw-performance-schema-rpd.html)
* [Oracle Cloud Free Tier Resources Policy](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
