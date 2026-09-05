# KI-015 · risk_flag 分类模型在训练集上自评分，准确率不可信

- 状态：IN-PROGRESS（2026-09-05 启动真训练方案，派 agy 执行，主控验收）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`ml_score_risk` 全部 2000 行预测与真实 `risk_flag` 完全一致（match 100%），
  `ml_results` 概率非 0 即 1（如 `{"probabilities":{"0":0.0,"1":1.0}}`），无正常概率分布。
- 只读核查（2026-09-04）：
  - `ml_score_risk` 与 `ml_feat_risk` 是同一批 2000 个 org（overlap=2000）——即在训练集上评分。
  - 非单特征硬泄漏：无任一特征与标签完全共线；risk_flag=1 组的 `unresolved_issues`(4.8 vs 2.0)、
    `high_risk_issues`(1.43 vs 0.51) 明显高于 =0 组，其余特征两组接近。
  - 数据高度可分 + 训练集自评分共同导致 100% 假象；真实泛化准确率未知。
- 影响：该风险模型当前无泛化验证，100% 准确率是假象，不得作为“AI 预测能力”对外展示或用于决策。
- 对比：回归模型 `ml_score_doc_delta` 表现正常（MAE≈2.22，均值≈6.06，预测为有误差的连续值），可信度较高。
- 待处理：对 risk_flag 做 train/test split（或交叉验证）后重新训练与评估，得到真实准确率；
  在展示层区分“模型已训练”与“模型已验证”，未经独立验证的指标不得展示为真实预测结果
  （呼应 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 的“不得把未生成/未验证预测展示为真实结果”）。
- 依据约束：HeatWave AutoML 免费、无调用次数限制、单节点串行、目标列非 TEXT、文本特征仅英文、
  训练账号名不得含点号（`.`）；重训练须在这些边界内、以离线批处理方式进行。


## 真训练方案（2026-09-05 主控与用户敲定，派 agy 执行）
- 前置已探明：HeatWave 分析集群可用、`sys.ML_TRAIN`/`ML_SCORE` 存在、账号 `admin@%` 合规、特征表就绪。走 HeatWave AutoML 原生。
- 两模型区别对待：
  - 风险分类（`ml_feat_risk`→`risk_flag`）：特征均为单位状态量，**排除时间序列量防学歪**；按单位随机 train/test split。
  - 单据量回归（`ml_feat_doc_delta`→`daily_doc_delta`）：时间序列预测，**必须按时间切分**（早期训练/后期预测），注意 `doc_count_prev30` 等前瞻窗口不泄漏。
- 用测试集（模型未见过）评估拿真实指标（分类 accuracy/precision/recall；回归 R²/MAE），真实质量分落元数据供展示（闭环 KI-023）。
- 每日重训：香港时区每天 00:00（业务低谷、不抢 HeatWave 资源），systemd timer 托管、开机自启；用截至当日全量历史重新 split→训练→测试集评估→更新真实分→对最新数据重新打分。
- 关于周期性顾虑：训练用全量历史（跨所有周期），训练时机不受"当天是否周末"影响；真正处理点在特征设计与 split 方式（上述）。
- 库名 `mod` 为 MySQL 保留字，SQL 引用须反引号 `` `mod` ``。
- 分阶段：一 手动真训练拿基线 → 二 展示层对接真实结果 → 三 每日 00:00 自动重训。派工单 `scripts/kiro/tmp/mod-task-dispatch.html`。
