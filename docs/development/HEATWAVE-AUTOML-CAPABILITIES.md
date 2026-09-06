# HeatWave AutoML 能力与边界手册

更新日期：2026-09-06
状态：草稿（骨架待填充）
适用范围：Oracle MySQL HeatWave（永久免费层）库内 AutoML 在本项目中的能力清单、使用方式与边界
维护角色：待填充由 agy 负责，主控（kiro）审阅

## 本文定位

本文是 **HeatWave AutoML 的能力参考手册**，回答“它能做什么、不能做什么、怎么调、有哪些坑”，
供后续任何要在本项目里使用库内机器学习的人查阅。

- 与 [`ML-AI-DATA-BOUNDARY.md`](./ML-AI-DATA-BOUNDARY.md) 的区别：那份讲**数据边界与授权红线**（该不该用、
  哪些数据能进），本文讲**技术能力与用法**（能力清单、算法、函数、限制、最佳实践）。两者互补，不重复。
- 与项目 AI 策略的关系：本项目是**大屏展示项目**，AI 遵循“后台算、前台展示、零交互、诚实标注”。
  HeatWave AutoML 承担**预测重活**（免费、零边际成本、数据不出库），LLM 承担表达。详见待建的 AI 策略 ADR。

> 本项目关键背景：我们**没有本地 GPU、不做本地训练**。HeatWave AutoML 是我们唯一的“真训练”能力，
> 且永久免费、算力由 Oracle 提供、数据全程不出库——这是它相对在线大模型 API 的独特价值。

---

## 一、HeatWave AutoML 是什么（待填充）

<!-- agy 填充要点：
- 一句话定义：MySQL HeatWave 内置的库内 AutoML，SQL 调用即可完成训练/预测，无需导出数据、无需外部 ML 平台。
- 与“在线大模型 API”的本质区别：结构化预测（回归/分类/异常检测/预测/推荐）vs 自然语言生成。
- 与传统自建 ML 管线（Python + GPU）的区别：数据不出库、算力 Oracle 提供、SQL 原生、永久免费层可用。
- 我们能用的版本/规格：永久免费层的 HeatWave 具体规格、内存、节点限制。
-->

## 二、支持的机器学习任务类型（待填充）

<!-- agy 填充要点：逐项列出 HeatWave AutoML 支持的 task 类型，并标注本项目是否用得上：
- classification（分类）—— 本项目用途：单位延期风险分类（高危/正常）
- regression（回归）—— 本项目用途：单据日增量预测
- forecasting（时序预测）—— 本项目用途：单据量/上线趋势时序预测
- anomaly_detection（异常检测）—— 本项目用途：实时流水异常发现
- recommendation（推荐）—— 本项目大概率用不上，说明原因
每类补充：适用场景、输入要求、输出形态。以官方文档为准，不要凭记忆写。
-->

## 三、核心 SQL 接口与调用方式（待填充）

<!-- agy 填充要点：把项目实际用到的 HeatWave ML 例程整理成速查表，标注读/写属性：
- ML_TRAIN(table, target, options)        —— 训练（写操作，需授权）
- ML_MODEL_METADATA / sys 视图             —— 查询模型状态（只读）
- ML_PREDICT_ROW(features, model)          —— 单行预测（只读）
- ML_PREDICT_TABLE(model, src, dst)        —— 批量评分写结果表（写操作，需授权）
- ML_EXPLAIN / ML_SCORE 等                 —— 解释与评估
每个补充：签名、参数、返回、读写属性、示例。
交叉引用项目内已有实现：backend/app/integrations/heatwave_ml.py、heatwave_sql.py。
-->

## 四、本项目已定义的模型（待填充 / 需按实际现状核对）

<!-- agy 填充要点：核对代码与库内实际状态，如实记录，不虚构：
- 模型一：单据日增量回归（MOD_REGRESSION_MODEL）
    target / features / 算法 / 当前质量分（R²）/ 当前状态
- 模型二：单位延期风险分类（MOD_RISK_CLASSIFIER）
    target / features / 算法 / 当前质量分 / 当前状态
当前已知：两个模型均 VALIDATION_FAILED（回归 R²≈-0.013、分类退化），
根因是模拟数据缺乏可学习的真实因果关系（不是算力或算法问题）。如实记录，标注为待修复。
-->

## 五、能力边界与硬限制（本文重点 · 待 agy 逐项查证官方文档后填写）

> 本章是全文重点。以下每一项都必须**以 Oracle 官方文档为唯一依据**去查证填写，
> 严禁凭记忆或推测。查到的每条限制请附上官方文档来源链接与查证日期。
> 查不到确切数字的，明确标注“官方未明确/待进一步核实”，不要编一个数字。

### 5.1 是否免费 · 计费边界（待查证）

<!-- agy 必须查清并填写：
- Oracle Cloud「Always Free」永久免费层是否包含 HeatWave？包含到什么程度？
- 免费层的 HeatWave 具体规格：内存大小、节点数、可用形状（shape）。
- AutoML 训练/预测在免费层是否额外收费？还是包含在免费额度内？
- 超出免费层之后如何计费（按什么计价单位：OCPU 时？内存 GB 时？）。
- 免费层是否有「用不满会被回收/停止」之类的策略。
官方来源：Oracle Cloud Always Free 文档 + HeatWave 定价文档，附链接与查证日期。
-->

### 5.2 调用与资源限制（待查证）

<!-- agy 必须查清并填写 Oracle 官方对以下项的硬限制：
- 单次 AutoML 训练的数据行数上限 / 下限（官方是否规定最少多少行才能训练）。
- 特征列数量上限（一个模型最多多少个 feature 列）。
- 训练时间是否有超时限制？免费层是否更严。
- 并发训练/预测的数量限制。
- ML_PREDICT_TABLE 批量评分的行数限制。
- 单账户可创建的模型数量上限。
- HeatWave 集群内存对可训练数据规模的实际约束（数据要能装进内存）。
官方来源：HeatWave AutoML 文档的 Limitations / Prerequisites 章节，附链接与查证日期。
-->

### 5.3 对数据库与字段的要求（待查证）

<!-- agy 必须查清并填写 Oracle 官方对训练数据的结构要求：
- 训练表必须满足的条件（是否必须有主键？是否必须是 InnoDB？字符集要求？）。
- 支持的字段数据类型（哪些类型可作为 feature：INT/FLOAT/VARCHAR/DATE...？哪些不支持：TEXT/BLOB/JSON...？）。
- 目标列（target）的要求：分类任务目标列取值要求、回归任务目标列类型要求。
- 缺失值 / NULL 的处理规则：官方是自动处理还是必须预处理？
- 类别型特征的基数（cardinality）是否有上限。
- 时序预测（forecasting）对时间列的格式与连续性要求。
- 数据是否必须与模型在同一 schema / 同一 HeatWave 集群内。
官方来源：HeatWave AutoML 文档的 Data Requirements / Supported Data Types 章节，附链接与查证日期。
-->

### 5.4 本项目已踩的坑（已知事实，直接记录）

<!-- 这一节是我们自己的实测结论，不用查官方：
- 两个模型均 VALIDATION_FAILED（回归 R²≈-0.013、分类退化为 1.0）。
- 根因不是算力/算法/资源，而是模拟数据过度规律，特征与目标间无可学习的真实因果。
- 结论：HeatWave AutoML 有效性的前提是「数据本身含真实可学信号」，这不是官方限制，是数据侧责任。
-->

## 六、在本项目中的正确用法（待填充）

<!-- agy 填充要点：结合“大屏项目”定位写清楚：
- AI 全程后台运行：定时训练/评分 → 结果写入结果表 → 后端读取 → 大屏直接展示，零用户交互。
- 结果如何上屏：F 屏高危单位预测（F2）、单据趋势预测（F3）；A 屏一句话摘要（由 LLM 基于预测结果生成）。
- 诚实原则：预测未达标时前端明确标“验证未达标”，绝不摆假预测（呼应 KI-028、KI-023）。
- 训练调度：常驻服务/定时任务如何触发重训（交叉引用 scripts/agy/run_ml_retrain.py、模拟器常驻服务）。
- 授权门禁：任何写库/训练操作需显式授权、只读核查在先（交叉引用 ML-AI-DATA-BOUNDARY.md）。
-->

## 七、相关文件与交叉引用（待填充）

<!-- agy 填充要点：列出项目内所有相关实现与文档的相对链接：
- backend/app/integrations/heatwave_ml.py / heatwave_sql.py
- backend/app/ml_adapter.py
- scripts/agy/run_ml_retrain.py / train_and_evaluate_models.py / verify_ml_training_baseline.py
- docs/development/ML-AI-DATA-BOUNDARY.md（数据边界与授权）
- docs/KNOWN-ISSUES.md 中 KI-028（模型指标不可信）、KI-023（AutoML 硬编码兜底）
- 待建的 AI 策略 ADR（大屏 AI 定位）
-->

---

## 填充说明（给 agy）

- 本文当前为**骨架**，各章 `<!-- 待填充 -->` 注释给出了要点提纲，请据此补全正文后删除注释。
- **第五章「能力边界与硬限制」是全文重点**：免费与否、调用限制、数据库与字段要求，
  必须**逐条去查 Oracle 官方文档**（Always Free 文档、HeatWave 定价文档、HeatWave AutoML 的
  Limitations / Prerequisites / Data Requirements 章节）。**每条限制附官方来源链接 + 查证日期。**
- **严禁凭记忆、推测或“大概是”填写任何数字或限制条款。** 查不到确切答案的，明确写
  “官方未明确 / 待进一步核实”，绝不编造。宁可留空标注，也不要填错误的硬事实。
- **以官方文档和库内真实状态为准**，API 签名、限额、算法细节同理，不确定标“待核实”。
- 遵循 `DOCUMENTATION-STANDARD.md`：中文标题、更新日期、状态、作用域、相对链接、无任何密钥或真实敏感信息。
- 涉及事实（模型状态、质量分、数据规模）须与 `docs/CURRENT-STATE.md` 和代码一致；如有冲突以代码与库内实测为准并同步更正。
- 填充完成后把状态从“草稿（骨架待填充）”改为“现行”，并在 `docs/development/README.md` 索引中登记本文。
