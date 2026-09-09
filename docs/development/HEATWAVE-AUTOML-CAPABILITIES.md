# HeatWave AutoML 能力与边界手册

更新日期：2026-09-06
状态：现行
适用范围：Oracle MySQL HeatWave（永久免费层）库内 AutoML 在本项目中的能力清单、使用方式与边界
维护角色：agy 维护，主控（kiro）审阅

## 本文定位

本文是 **HeatWave AutoML 的能力参考手册**，回答“它能做什么、不能做什么、怎么调、有哪些坑”，供后续任何要在本项目里使用库内机器学习的人查阅。

- 与 [`ML-AI-DATA-BOUNDARY.md`](./ML-AI-DATA-BOUNDARY.md) 的区别：那份讲**数据边界与授权红线**（该不该用、哪些数据能进），本文讲**技术能力与用法**（能力清单、算法、函数、限制、最佳实践）。两者互补，不重复。
- 与项目 AI 策略的关系：本项目是**大屏展示项目**，AI 遵循“后台算、前台展示、零交互、诚实标注”。HeatWave AutoML 承担**结构化数据预测重活**（免费、零边际成本、数据不出库），大模型（LLM）承担**宏观指标自然语言表达**。详见待建的 AI 策略 ADR。

> 本项目关键背景：我们**没有本地 GPU、不做本地训练**。HeatWave AutoML 是我们唯一的“真训练”能力，且永久免费、算力由 Oracle 云提供、数据全程不出库——这是它相对在线大模型 API 与自建 GPU 管线的独特核心价值。

---

## 一、HeatWave AutoML 是什么

### 1.1 一句话定义
**MySQL HeatWave AutoML** 是集成在 Oracle MySQL HeatWave 数据库内核与分布式内存加速集群中的自动化机器学习引擎。开发者只需通过标准 SQL 存储过程与函数调用，即可全自动完成数据清洗、特征预处理、算法选择、超参数调优（Auto-tuning）、模型训练、评估解释以及批量/在线推理，**全程无需将数据导出到外部 Python 环境，亦无需搭建外部机器学习平台**。

### 1.2 与“在线大模型 API”的本质区别
| 维度 | HeatWave AutoML | 在线大模型 API（如 OpenAI / Claude / Workers AI） |
|---|---|---|
| **核心任务** | 结构化表格数据的精准预测（回归、分类、时序、异常检测） | 非结构化自然语言理解、归纳总结与生成式内容表达 |
| **底层原理** | 参数化统计机器学习模型（XGBoost, LightGBM, Random Forest, 线性/逻辑回归等） | 深度自回归大型语言模型（Transformer 架构） |
| **计费模式** | 库内集群运行，在 Always Free 额度内**完全免费（零边际成本）** | 按输入/输出 Token 数量或 API 调用频次严格计费 |
| **确定性与指标** | 数学指标严谨客观（$R^2$、MAE、RMSE、Accuracy、F1、AUC），支持独立测试集切分验证 | 存在生成随机性与“幻觉”风险，难以用数值函数量化泛化误差 |
| **数据隐私** | 原始数据始终保留在数据库内部，物理不出库 | 需通过网络将提示词与上下文明细发送至远端模型供应商 |

### 1.3 与传统自建 ML 管线（Python + GPU）的区别
1. **数据不出库（Data In-Place）**：传统 Python 管线需要通过 ETL 脚本将几万至上百万行明细拉取到本地或训练服务器，极易产生网络延迟、跨端凭据泄露以及数据版本不一致；HeatWave AutoML 在数据库内存集群内就地计算，零传输损耗。
2. **免维护分布式算力池**：无需配置 CUDA 驱动、PyTorch/TensorFlow 运行环境或管理 GPU 实例租用；底层集群由 Oracle 云全托管。
3. **全流程原生自动化**：传统管线需要手写复杂的特征归一化、One-Hot 编码、网格搜索与交叉验证；HeatWave AutoML 在 `ML_TRAIN` 内部自动完成自适应特征工程与并行算法寻优。

### 1.4 本项目运行规格基准（OCI Always Free 永久免费层）
根据我们在 OCI 美国区域运行环境的实测与配置，当前项目所依托的免费层规格如下：
- **MySQL DB 系统 Shape**：`MySQL.Free`（配置 2 ECPU，8 GiB 内存，50 GiB 数据与日志存储，网络带宽 1 Gbps）。
- **HeatWave 集群 Shape**：`HeatWave.Free`（固定 1 个计算节点，16 GB 内存集群容量，10 GiB Lakehouse 对象存储支持）。
- **高可用限制**：Always Free 不支持高可用（HA）集群与只读副本。

---

## 二、支持的机器学习任务类型

HeatWave AutoML 原生支持以下 5 大类机器学习任务。下表结合本项目（公共事业建设推广大屏）业务场景标明适用性：

| 任务类型 | 原生参数值 | 核心适用场景 | 官方候选算法举例 | 本项目用途与适用性分析 |
|---|---|---|---|---|
| **分类 (Classification)** | `'classification'` | 预测样本所属的离散类别标签（支持二分类与多分类） | XGBoostClassifier, LGBMClassifier, RandomForestClassifier, DecisionTreeClassifier, LogisticRegression | **采用**。用于单位上线风险分类预测（`risk_flag`: 0 正常 / 1 高风险）。 |
| **回归 (Regression)** | `'regression'` | 预测连续型数值变量的目标走势 | XGBoostRegressor, LGBMRegressor, RandomForestRegressor, LinearRegression | **采用**。用于业务单据日增量预测（`daily_doc_delta`）。 |
| **时序预测 (Forecasting)** | `'forecasting'` | 基于历史时间序列样本推演未来时间窗口 | AutoARIMA, Prophet 等内嵌时序算法 | **候选**。适合推演未来 7~30 天全网单据峰值趋势，作为 F3 单据链路的进阶预测。 |
| **异常检测 (Anomaly Detection)** | `'anomaly_detection'` / `'log_anomaly_detection'` | 无监督/半监督识别偏离正态基线的孤立离群点 | Isolation Forest, One-Class SVM 等 | **候选**。适合对全网流水中非工作时间大额操作、凭证生成断链进行离群度标记。 |
| **推荐 (Recommendation)** | `'recommendation'` | 基于用户-物品交互偏好生成个性化推荐 | TwoTower, 协同过滤等 | **不采用**。本项目是指挥大屏，面向管理团队与各单位进度监管，不存在电商或内容平台的个性化偏好推荐场景；且该任务要求字段必须为 STRING，不支持 `ML_PREDICT_ROW` 与模型导入导出。 |
| **主题建模 (Topic Modeling)** | `'topic_modeling'` | 文本语料无监督聚类并提取主题词组 | 文本特征聚类算法 | **不采用**。本项目全部为结构化台账与指标数据，暂无非结构化大篇幅英文工单语料。 |

---

## 三、核心 SQL 接口与调用方式

在 MySQL HeatWave 中，AutoML 的核心功能通过系统数据库 `sys` 下的内置存储过程（Procedure）与函数（Function）对外暴露。

### 3.1 核心例程速查表

| 接口名称 | 调用方式 | 读/写属性 | 说明与门禁要求 |
|---|---|---|---|
| `sys.ML_TRAIN` | `CALL sys.ML_TRAIN(...)` | **写操作** | 触发库内 AutoML 训练，向 `ML_SCHEMA_<user>` 写入模型对象。**需显式授权与 execute 模式**。 |
| `sys.ML_MODEL_LOAD` | `CALL sys.ML_MODEL_LOAD(...)` | **写操作** | 将指定模型从元数据表加载到 HeatWave 内存集群中以供快速推理。 |
| `sys.ML_MODEL_UNLOAD` | `CALL sys.ML_MODEL_UNLOAD(...)` | **写操作** | 将模型从 HeatWave 内存集群卸载以释放内存。 |
| `sys.ML_PREDICT_ROW` | `SELECT sys.ML_PREDICT_ROW(...)` | **只读** | 对单行 JSON 特征输入进行实时在线推理，返回预测值与置信度 JSON。 |
| `sys.ML_PREDICT_TABLE` | `CALL sys.ML_PREDICT_TABLE(...)` | **写操作** | 对整个输入表进行批量预测，并将结果写入目标结果表。**需显式授权与 execute 模式**。 |
| `sys.ML_EXPLAIN_ROW` | `SELECT sys.ML_EXPLAIN_ROW(...)` | **只读** | 单行预测解释，返回特征贡献度（SHAP Attribution）。 |
| `sys.ML_EXPLAIN_TABLE` | `CALL sys.ML_EXPLAIN_TABLE(...)` | **写操作** | 批量特征归因解释，将全表特征重要度写入输出表。 |
| `sys.ML_SCORE` | `CALL sys.ML_SCORE(...)` | **只读/计算** | 针对带真实标签的测试表计算模型泛化评分（如 $R^2$、Accuracy）。 |
| `sys.TRAIN_TEST_SPLIT` | `CALL sys.TRAIN_TEST_SPLIT(...)` | **写操作** | 库内执行训练/测试集切分（分层抽样或时序切分），写入切分表。 |

### 3.2 详细签名与典型调用示例

#### 1. 模型训练：`ML_TRAIN`
```sql
CALL sys.ML_TRAIN(
    'mod.ml_feat_risk_train',                  -- 训练集表全名（必须单表）
    'risk_flag',                               -- 目标列名（Ground Truth，不可为 NULL/TEXT）
    JSON_OBJECT(                               -- 训练配置 JSON
        'task', 'classification',              -- 任务类型
        'optimization_metric', 'accuracy',     -- 优化指标（可选）
        'exclude_column_list', JSON_ARRAY('id', 'org_id') -- 显式排除 ID 与非特征列
    ),
    @risk_model_handle                         -- 出参：返回模型唯一句柄（存入会话变量）
);
```

#### 2. 模型加载与卸载：`ML_MODEL_LOAD` / `ML_MODEL_UNLOAD`
```sql
-- 将训练完毕的模型载入 HeatWave 集群内存
CALL sys.ML_MODEL_LOAD(@risk_model_handle, NULL);

-- 推理完成后或内存吃紧时卸载
CALL sys.ML_MODEL_UNLOAD(@risk_model_handle);
```

#### 3. 单行实时推理：`ML_PREDICT_ROW`
```sql
SELECT sys.ML_PREDICT_ROW(
    JSON_OBJECT(
        'construction_pct', 78.5,
        'unresolved_issues', 3,
        'high_risk_issues', 1,
        'doc_success_pct', 98.2,
        'integration_success_pct', 96.0,
        'days_since_start', 120
    ),
    @risk_model_handle,
    NULL
) AS prediction_json;
```

#### 4. 批量全量评分：`ML_PREDICT_TABLE`
```sql
CALL sys.ML_PREDICT_TABLE(
    '`mod`.ml_feat_risk',                      -- 输入特征全表
    @risk_model_handle,                        -- 模型句柄
    '`mod`.ml_score_risk',                     -- 输出评分结果表（自动创建或覆盖）
    JSON_OBJECT('recommend_feature_importance', FALSE)
);
```

#### 5. 独立验证集评估：`ML_SCORE`
```sql
CALL sys.ML_SCORE(
    '`mod`.ml_feat_risk_test',                 -- 未参与训练的独立测试集
    'risk_flag',                               -- 真实标签
    @risk_model_handle,                        -- 待评估模型
    'accuracy',                                -- 评测指标
    @test_score,                               -- 出参：真实测试分
    NULL
);
SELECT @test_score AS generalization_accuracy;
```

### 3.3 代码实现交叉引用
- 后端安全只读适配器：[`backend/app/integrations/heatwave_ml.py`](../../backend/app/integrations/heatwave_ml.py)
- SQL 语法与表结构定义：[`backend/app/integrations/heatwave_sql.py`](../../backend/app/integrations/heatwave_sql.py)
- 离线训练与独立切分验证脚本：`archive/legacy-scripts/agy/train_and_evaluate_models.py`（本地归档，不纳入版本库）
- 只读基线核查门禁脚本：`archive/legacy-scripts/agy/verify_ml_training_baseline.py`（本地归档，不纳入版本库）

---

## 四、本项目已定义的模型（实际现状核对）

在本项目中，针对大屏实际业务定义了两个专属预测模型。根据实测与元数据表 `mod.ml_model_metadata` 的真实记录，现状核对如下：

### 4.1 模型一：单据日增量回归模型（`MOD_REGRESSION_MODEL`）
- **任务类型**：`regression`
- **训练表与切分**：`mod.ml_feat_doc_delta`。按业务发展时间线进行严格的时序切分（早期 1,600 行训练集 `ml_feat_doc_delta_train`，未来 400 行测试集 `ml_feat_doc_delta_test`，严格单调递增，绝无未来数据穿越）。
- **目标变量**：`daily_doc_delta`（FLOAT，各单位最新截面当日新增单据数）。
- **输入特征集**：`org_id`, `region`, `batch_id`, `days_since_go_live`, `launched_flag`, `doc_count_prev30`, `voucher_count_prev30`, `integration_fail_cnt`。
- **AutoML 推荐算法**：`LinearRegression`（线性回归基线）。
- **当前测试集质量分**：$R^2 \approx -0.0135$（负拟合度，预测效果不如简单均值）。
- **当前系统状态**：`VALIDATION_FAILED`（已训练，独立测试集验证未达标）。

### 4.2 模型二：单位上线延期风险分类模型（`MOD_RISK_CLASSIFIER`）
- **任务类型**：`classification`
- **训练表与切分**：`mod.ml_feat_risk`。按单位随机分层切分（训练集 1,600 行 `ml_feat_risk_train`，测试集 400 行 `ml_feat_risk_test`，固定随机种子 seed=42）。
- **目标变量**：`risk_flag`（TINYINT，0 正常 / 1 高风险；业务口径：未解决问题 $\ge 5$ 或高风险问题 $\ge 2$ 则标注为 1）。
- **输入特征集**：`org_id`, `region`, `batch_id`, `construction_pct`, `unresolved_issues`, `high_risk_issues`, `doc_success_pct`, `integration_success_pct`, `days_since_start`（**已全面剥离时序单据波动特征**，防止时序泄露）。
- **AutoML 推荐算法**：`DecisionTreeClassifier`（决策树分类器）。
- **当前测试集质量分**：测试集 Accuracy = 1.0（100% 退化）。
- **当前系统状态**：`VALIDATION_FAILED`（已训练，独立测试集验证未达标）。

### 4.3 现状结论与待修复说明
正如已知问题看板 [`docs/KNOWN-ISSUES.md`](../KNOWN-ISSUES.md) 中 **KI-028** 与 [`docs/issues/KI-028-模型指标不可信.md`](../issues/KI-028-模型指标不可信.md) 所深度剖析：
1. **分类模型退化**：测试集准确率 100% 并不是算法优秀，而是**模拟数据生成层过于刻板**。目标 `risk_flag` 是特征集合的纯确定性布尔函数，毫无现实业务中的不确定性噪声与灰色地带，导致模型学到了死板规则而非泛化规律，对外展示 100% 准确率反显虚假。
2. **回归模型无预测力**：单据量预测呈现负 $R^2$，根因在于当前特征未包含业务单据产生的强因果周期（如周几、月末冲账、法定节假日以及历史同期波峰）。
3. **系统应对机制**：根据项目“诚实原则”，后端 [`backend/app/api.py`](../../backend/app/api.py) 设置了有效性阈值检查（$R^2 > 0$ 且分类 Accuracy $\in (0.5, 1.0)$）；未达标前，大屏明确显示“已训练，验证未达标”，坚决不展示虚假的预测数值。后续修复需由拟真引擎数据生成层（KI-026 系列）引入现实受控噪声后重训解决。

---

## 五、能力边界与硬限制

> **查证声明**：本章所有条目均以 **Oracle 官方文档（Oracle Help Center / MySQL Documentation）为唯一依据**逐条查证核实，每项均标注官方来源链接与查证日期（2026-09-06）。严禁凭空推测或编造数值。

### 5.1 是否免费 · 计费边界

| 关注项 | 官方明确规范与事实 | 官方来源链接与查证日期 |
|---|---|---|
| **Always Free 是否包含 HeatWave** | **包含**。商用 Realm 内每个 OCI 租户（包括免费试用与付费账户）均可在其**主区域（Home Region）**内创建 1 个 Always Free MySQL HeatWave DB 系统。 | [Creating an Always Free DB System](https://docs.oracle.com/en-us/iaas/mysql-database/doc/creating-always-free-db-system.html)<br>[Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)<br>*查证日期：2026-09-06* |
| **免费层具体硬件规格** | • **MySQL DB System Shape**：必须为 `MySQL.Free`，固定规格为 **2 ECPU、8 GiB 内存、50 GiB 数据存储**、1 Gbps 带宽。<br>• **HeatWave Cluster Shape**：必须为 `HeatWave.Free`，固定配置 **1 个计算节点、16 GB 集群内存容量**、10 GiB Lakehouse 存储。<br>• **限制**：不支持高可用（HA）、不支持只读副本（Read Replica）、不支持手动备份与时间点恢复（PITR）。 | [Features of Always Free DB Systems](https://docs.oracle.com/en-us/iaas/mysql-database/doc/features-mysql-heatwave-service.html)<br>*查证日期：2026-09-06* |
| **AutoML 训练/预测是否额外收费** | **完全免费（At No Additional Cost）**。Oracle 官方明确承诺：HeatWave AutoML 是 MySQL HeatWave 服务的内置原生能力，**不收取任何机器学习许可费、算法训练费或单次推理费**。在 Always Free 资源包内运行，边际费用为零。 | [Oracle MySQL HeatWave Pricing](https://www.oracle.com/mysql/heatwave/pricing/)<br>[MySQL HeatWave FAQ](https://www.oracle.com/mysql/heatwave/faq/)<br>*查证日期：2026-09-06* |
| **超出免费层后的计费模式** | 超出免费层（升级付费账户扩容）后，按实际消耗资源细分计费：<br>1. **ECPU 算力**：按 `ECPU / 小时` 计费；<br>2. **HeatWave 集群容量**：按 `HeatWave Capacity / 小时` 计费（基础单位通常折算为 16 GB 内存小时）；<br>3. **存储费用**：按 `GB / 月` 计费（分数据存储与备份存储）；<br>4. **网络出口流量**：超出每月免费 10 TB 额度后按 GB 计费。 | [Oracle Cloud Infrastructure Price List](https://www.oracle.com/cloud/price-list/)<br>*查证日期：2026-09-06* |
| **闲置资源回收与停止策略** | OCI 对 Always Free 计算资源设有**空闲实例回收机制（Idle Reclamation Policy）**：<br>若实例在连续 **7 天**周期内，95th 百分位数的 CPU 使用率、网络吞吐以及内存利用率持续低于 **10%~20%**，Oracle 云可能自动停止（Stop）该实例。停止后存储卷保留，用户可在云控制台手动重启（前提是所在可用区当时有空余的 Free Shape 容量）。已绑定有效信用卡的升级账户（PAYG）不受闲置回收策略影响。 | [OCI Free Tier - Idle Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)<br>*查证日期：2026-09-06* |

### 5.2 调用与资源限制

| 限制项 | 官方明确规范与参数 | 官方来源链接与查证日期 |
|---|---|---|
| **单表训练规模上限** | 用于模型训练的单表（或单视图）**最大物理体积不得超过 10 GB**，**最大行数不得超过 1 亿行（100,000,000 rows）**，**最大列数不得超过 1,017 列**。 | [MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **单次训练数据下限** | 官方未设定全局固定行数下限，但对任务有硬性分布要求：**分类任务中每个类别（Class）必须在表中出现至少 5 行以上**（即二分类至少 10 行）。若样本极少，模型无法完成分层交叉验证与调优。 | [Supported Data Types for HeatWave AutoML](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-data-requirements.html)<br>*查证日期：2026-09-06* |
| **特征解释（SHAP）列数限制** | 尽管输入表可达 1,017 列，但 `ML_EXPLAIN_TABLE` 与 `ML_EXPLAIN_ROW` 生成的特征重要度（Feature Attribution）解释**最多仅支持并返回前 100 个最相关特征**。 | [MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **训练超时与模型体积上限** | `ML_TRAIN` 内部由调度器自主管理，**未开放可由用户指定的单次训练 `timeout` 参数**。自 MySQL 9.0.0 起，单个导入/训练的模型建议内存上限为 **4 GB**（9.0.0 之前版本限制为 900 MB），若训练产物超出此上限，`ML_TRAIN` 将报错终止。在 Always Free（16 GB 集群）上，训练应尽量控制特征表在数万行至数十万行以内以防 OOM。 | [MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **并发调用互斥限制** | **HeatWave 分析查询与 AutoML 训练/查询不支持并发执行**。若同时提交，AutoML 查询会与分析查询排队互斥，通常常规分析查询拥有更高调度优先级。在生产大屏并发访问时，严禁在前台请求中同步调用 `ML_TRAIN`。 | [MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **批量评分输出限制** | `ML_PREDICT_TABLE` 输出表中，`ml_results` 列加上原始数据整行内容的总字符长度**必须小于 65,532 字符**。对于大表批量评分，官方强烈建议采用 `batch_size` 机制（推荐切分成 10~100 行的批量）进行分段推理。 | [MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **单账户模型数量上限** | **官方未规定固定的模型总个数硬上限**。模型元数据记录在 `ML_SCHEMA_<username>.MODEL_CATALOG` 中，实际模型持久化分块存放在系统表空间，数量上限取决于 50 GiB 的存储空间大小；加载到内存中的模型数量取决于 16 GB 集群内存容量。 | [MySQL HeatWave User Guide - Model Catalog](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-model-catalog.html)<br>*查证日期：2026-09-06* |
| **集群节点上限支持** | MySQL HeatWave AutoML 仅支持在 **32 个或更少节点**的 HeatWave 集群上启用；**不支持部署在高可用（HA）DB 系统上**。 | [Additional MySQL HeatWave AutoML Requirements](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-prerequisites.html)<br>*查证日期：2026-09-06* |

### 5.3 对数据库与字段的要求

| 要求类别 | 官方规则与强制约束 | 官方来源链接与查证日期 |
|---|---|---|
| **训练表基础属性** | 1. 存储引擎必须为 **InnoDB** 表（或 HeatWave Lakehouse 支持的 Object Storage 外部表）。<br>2. 必须包含在单一数据表中（暂不支持跨表直接关联训练，关联需事先建为视图或打平成宽表）。<br>3. **主键规则**：主键非强制要求，但如果表中存在业务代理主键（如 `id`），必须通过 `exclude_column_list` 选项在 `ML_TRAIN` 中显式排除，否则主键会被误当做特征参与训练造成虚假过拟合。 | [MySQL HeatWave User Guide - Preparing Data](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-preparing-data.html)<br>*查证日期：2026-09-06* |
| **字符集与语言要求** | **仅支持英文（English）语料数据集**。自然语言文本仅在英文分词与语义下受支持，中文字符串若作为文本处理可能导致不可预期的向量化异常。 | [MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **用户名与 Schema 命名红线** | **执行 `ML_TRAIN` 的 MySQL 用户名绝对不能包含句点 `.`**（例如用户名 `'mod.admin'@'%'` 严禁使用）。**原因**：AutoML 会自动以调用者用户名创建专属模型 Schema（`ML_SCHEMA_<user_name>`），而 MySQL 数据库标识符不允许包含句点。 | [MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **支持的特征字段类型** | • **数值型**：`TINYINT`, `SMALLINT`, `MEDIUMINT`, `INT`, `BIGINT`（均支持有符号/无符号），`FLOAT`, `DOUBLE`, `DECIMAL`。<br>• **日期时间型**：`DATE`, `TIME`, `DATETIME`, `TIMESTAMP`, `YEAR`。<br>• **文本字符串型**：`CHAR`, `VARCHAR`, `TINYTEXT`, `TEXT`, `MEDIUMTEXT`, `LONGTEXT`（系统通过 `TfidfVectorizer` 进行英文词频向量化）。 | [Supported Data Types for MySQL HeatWave AutoML](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-data-requirements.html)<br>*查证日期：2026-09-06* |
| **不支持的字段类型** | `BLOB`, `BINARY`, `VARBINARY`, `GEOMETRY`, `BIT`。**特别注意**：`JSON` 虽受 HeatWave 分析引擎支持且用于传递 ML 配置，但**不能作为特征列直接输入 `ML_TRAIN`**。 | [Supported Data Types for MySQL HeatWave AutoML](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-data-requirements.html)<br>*查证日期：2026-09-06* |
| **缺失值（NULL）处理规则** | 1. **NaN 处理**：MySQL 不识别 `NaN`，数据导入前必须转换处理为 SQL `NULL`。<br>2. **自动插补**：数值型特征缺失值自动以**列均值（Mean）**填充并标准化；类别型特征缺失值自动以**众数（Mode）**填充并进行 One-Hot / Ordinal 编码。<br>3. **TEXT 列限制**：**`TEXT` 类型字段严禁包含 `NULL` 值**，若 TEXT 列含 NULL，训练直接失败。<br>4. **自动剔除列**：若特征列缺失值超过 **20%**，或整列取值为同一个单一常量，AutoML 会将其判定为无效特征并自动丢弃。 | [Supported Data Types for MySQL HeatWave AutoML](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-data-requirements.html)<br>[MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **目标列（Target）强制约束** | 1. **严禁包含 NULL**：目标列一旦出现未标注行（NULL），`ML_TRAIN` 立即中断并抛出错误码 `ML001053`。<br>2. **禁止 TEXT 类型**：目标列不能是任何类型的 `TEXT`。<br>3. **回归要求**：目标列必须是连续数值型（FLOAT/DOUBLE/INT 等）。<br>4. **分类要求**：目标列必须至少有 2 个独立类别，且每个类别必须出现在 $\ge 5$ 行中。 | [Supported Data Types for MySQL HeatWave AutoML](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-data-requirements.html)<br>[MySQL HeatWave AutoML Limitations](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-limitations.html)<br>*查证日期：2026-09-06* |
| **时序预测（Forecasting）要求** | 1. 必须声明 `datetime_index`，该列必须是 `DATE`, `TIME`, `DATETIME`, `TIMESTAMP`, `YEAR` 或自增数值索引。<br>2. 内生预测变量（`endogenous_variables`）不能是 `TEXT` 类型。<br>3. 时序数据采样间隔应尽可能均匀连贯。 | [MySQL HeatWave User Guide - Forecasting](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-forecasting.html)<br>*查证日期：2026-09-06* |
| **Schema 与存放位置** | 训练特征源表和评分结果表可位于业务库（如 `mod`），但生成的模型对象永远归属于执行者对应的 `ML_SCHEMA_<username>`。跨库调用需具有对业务库与专属 ML Schema 的读写授权。 | [MySQL HeatWave User Guide - Model Catalog](https://dev.mysql.com/doc/heatwave/en/mys-hw-automl-model-catalog.html)<br>*查证日期：2026-09-06* |

### 5.4 本项目已踩的坑（已知实测事实总结）

本节记录本项目在实际落地 HeatWave AutoML 过程中踩过的真实血泪教训。这些结论完全由真实代码评测得出，供后续架构演进参考：

1. **“自评分 100%”的虚假繁荣（KI-015）**：
   - *现象*：最初执行 `sys.ML_TRAIN` 后直接查询训练集自评分，显示分类准确率达到了完美的 1.0（100%）。
   - *教训*：训练集自评分存在严重的自拟合假象。在通过 `archive/legacy-scripts/agy/train_and_evaluate_models.py`（本地归档，不纳入版本库） 建立 80%/20% 严谨的独立 Train/Test Split 评估机制后，才真正暴露出模型的泛化问题。**永远不能拿训练集自评分当模型指标对外汇报**。

2. **模拟数据“过度可分”导致模型退化（KI-028）**：
   - *现象*：即便切分了 400 行全新的独立测试集，风险分类模型的准确率仍死死钉在 1.0（100%）。
   - *根因*：模拟数据生成逻辑过于理想化。由于特征工程中直接包含了 `unresolved_issues` 与 `high_risk_issues`，而业务目标 `risk_flag` 正是由这两个指标的硬编码阈值（$\ge 5$ 或 $\ge 2$）判定而来。模型只需学出一个简单的阶跃判定树即可做到 100% 预测。这种模型在现实真实世界中不可用，对外展示反而“一眼假”。

3. **时序预测缺乏因果特征导致负拟合（$R^2 = -0.0135$）**：
   - *现象*：单据量回归模型在消除时序穿越（仅用历史预测未来）后，测试集拟合优度 $R^2$ 跌至负数。
   - *根因*：原模拟数据生成的单据日增量未注入真实的周期节律因子（例如星期几效应、周末休眠、月末做账高峰、季度结算）。输入特征仅有时序天数和前 30 天均值，信息量严重不足，模型甚至不如采用全网常量均值进行预测。

4. **核心结论**：
   > **AutoML 负责的是“在给定特征中搜索最优数学算法与超参”，它绝不负责“凭空制造客观因果关系”。**
   > AutoML 能够生效的绝对前提是：**数据本身必须包含真实、可被归纳且具有统计显著性的因果信号**。模型验证失败是数据生成层的责任，不是 Oracle HeatWave 的算力或引擎限制。

---

## 六、在本项目中的正确用法

本项目定位为**生产指挥大屏**，具有高度的政治性、严谨性与只读观摩性。在本项目中使用 HeatWave AutoML 必须严格遵循以下原则：

### 6.1 全程后台异步运作，前台零交互
- **绝不在前台 API 中执行模型训练**：`ML_TRAIN` 属于高耗能、分钟级的重型计算，且与日常查询互斥。前台大屏请求必须纯只读。
- **离线批处理架构**：
  ```mermaid
  flowchart LR
    A["定时运维调度<br>(cron / scripts)"] -->|显式授权 execute| B["sys.ML_TRAIN<br>(库内异步重训)"]
    B --> C["sys.ML_SCORE<br>(独立测试集质检)"]
    C -->|质检通过| D["sys.ML_PREDICT_TABLE<br>(全量批量评分)"]
    D --> E["业务结果表<br>(ml_score_*)"]
    E --> F["FastAPI 后端<br>(纯只读安全查询)"]
    F --> G["大屏 UI 展示<br>(F 屏 / A 屏)"]
  ```

### 6.2 结果如何上屏展示
1. **F 屏（风险预警与智能研判）**：
   - **F2 困难户与掉队单位清单**：直接读取 `ml_score_risk` 结果表，结合当前业务合规规则（挂账、越级、非工作时间操作），展现综合高风险单位排行。
   - **F3 链路规模与增量预测**：展现单据日增量的历史曲线与模型预估值。
2. **A 屏（驾驶舱总览）**：
   - **一句话宏观研判**：由 Cloudflare Workers AI 或大模型基于经过 AutoML 筛选的宏观聚合数字（如“当前发现 24 家高危单位需重点督办”）生成自然语言总结，大模型仅负责语言组织，事实数据全部来自底层真实库内计算。

### 6.3 严格践行“诚实原则”
1. **有效性阈值门禁**：
   - 后端在输出模型状态与评分前，强制校验有效性门槛：
     - 回归模型：要求测试集 $R^2 > 0$；
     - 分类模型：要求测试集 Accuracy $\in (0.5, 1.0)$（排除随机猜测与 100% 规则退化）。
2. **异常如实提示**：
   - 若未通过门禁，接口返回 `VALIDATION_FAILED`，前端大屏直接如实展示“已训练，验证未达标”，坚决不采用 mock 假数据或硬编码数字欺骗大屏观摩者。

### 6.4 训练调度与授权双重门禁
任何试图对 HeatWave 执行 DDL、特征表重建或 `ML_TRAIN` 的操作，必须同时穿透双重安全门禁：
1. **环境变量开关**：运行时环境变量 `MOD_HW_ML_ENABLED=true`（默认始终为 `false`）；
2. **代码传参显式确认**：调用适配器方法时必须显式传递 `execute=True`（默认始终为 `False` 的 plan 试跑模式）；
3. **只读核查在先**：每次训练前后必须通过只读脚本 `archive/legacy-scripts/agy/verify_ml_training_baseline.py`（本地归档，不纳入版本库） 核验数据集无时序泄露与分布异常。

---

## 七、相关文件与交叉引用

### 7.1 项目源码与实现
- [`backend/app/integrations/heatwave_ml.py`](../../backend/app/integrations/heatwave_ml.py)：HeatWave AutoML 核心适配器（封装连接池、安全降级、状态探测与 plan/execute 模式）。
- [`backend/app/integrations/heatwave_sql.py`](../../backend/app/integrations/heatwave_sql.py)：所有特征表 DDL、插入 DML、`ML_TRAIN` 与批量评分存储过程定义。
- [`backend/app/ml_adapter.py`](../../backend/app/ml_adapter.py)：大屏上层调用的统一 ML 门面，含有效性阈值拦截。
- `archive/legacy-scripts/agy/train_and_evaluate_models.py`（本地归档，不纳入版本库）：独立 Train/Test 切分训练与评估全流程工具。
- `archive/legacy-scripts/agy/verify_ml_training_baseline.py`（本地归档，不纳入版本库）：纯只读模型基线核查与防泄露验证工具。
- [`scripts/agy/run_ml_retrain.py`](../../scripts/agy/run_ml_retrain.py)：重训执行封装脚本。

### 7.2 架构与规范文档
- [`docs/development/ML-AI-DATA-BOUNDARY.md`](./ML-AI-DATA-BOUNDARY.md)：AutoML 与大语言模型的最小数据边界、授权清单与脱敏规范。
- [`docs/CURRENT-STATE.md`](../CURRENT-STATE.md)：项目数据库、运行时、质量与操作边界的唯一事实入口。
- [`docs/KNOWN-ISSUES.md`](../KNOWN-ISSUES.md)：已知问题看板（跟踪 KI-015 训练集自评分虚高、KI-023 兜底、KI-028 模型指标不可信）。
- [`docs/issues/KI-028-模型指标不可信.md`](../issues/KI-028-模型指标不可信.md)：真实评估暴露模型指标不可信的深度复盘与根因分析。
- [`docs/development/DOCUMENTATION-STANDARD.md`](./DOCUMENTATION-STANDARD.md)：项目文档书写与事实一致性标准。
