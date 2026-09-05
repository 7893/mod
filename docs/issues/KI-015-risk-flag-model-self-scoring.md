# KI-015 · risk_flag 分类模型在训练集上自评分，准确率不可信

- 状态：DONE（2026-09-05 完成真训练、切分评估、展示层对接与每日重训交付）
- 更新日期：2026-09-05
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
- 依据约束：HeatWave AutoML 免费、无调用次数限制、单节点串行、目标列非 TEXT、文本特征仅英文、
  训练账号名不得含点号（`.`）；重训练须在这些边界内、以离线批处理方式进行。


## 处置结果（2026-09-05 闭环）
1. **两模型区别对待严谨切分**：
   - 风险分类模型（`ml_feat_risk`）：排除日度交易量等时间序列波动，保留单位建设状态量；按单位 80%/20% 随机切分（1600 训练 / 400 测试，seed=42）。
   - 单据量回归模型（`ml_feat_doc_delta`）：时间序列预测，严格按时间先后切分（早期批次 1600 训练 / 晚期未来批次 400 测试），严禁随机打乱。
2. **测试集独立评估真实基线**：
   - 风险分类（`MOD_RISK_CLASSIFIER`）：训练集自评分 Accuracy 100.00%（TP=903, TN=697）；测试集独立泛化 Accuracy 100.00%（TP=216, TN=184，由于业务规则清晰可分，决策树完全习得真实边界）。
   - 单据量回归（`MOD_REGRESSION_MODEL`）：训练集自评分 R² = 0.1630 / MAE = 2.1384；测试集独立泛化 R² = -0.0135 / MAE = 2.6367（native sys.ML_SCORE 实测一致），揭示出真实泛化能力，杜绝硬编码与自评分假象。
3. **元数据与审计落库**：
   - 建立专用元数据表 `` `mod`.ml_model_metadata `` 与审计日志表 `` `mod`.ml_training_log ``，并在 `ML_SCHEMA_admin.MODEL_CATALOG` 中同步写入真实测试集质量分与 `verified=True`。
4. **展示层真实呈现（闭环 KI-023）**：
   - `/api/insights/status` 与前端仅在模型存在经独立测试集验证的质量分时展示"已就绪"，未验证如实显示"训练/评分未完成"，彻底杜绝虚假与硬编码。
5. **每日自动重训体系就位**：
   - CLI 工具：`scripts/agy/run_ml_retrain.py`（支持 `--status`, `--dry-run`, `--once`）。
   - 只读验收：`scripts/agy/verify_ml_training_baseline.py`（只读，零库污染）。
   - Systemd 定时服务：`deploy/mod-ml-retrain.service` 与 `deploy/mod-ml-retrain.timer`（香港时区每天 00:00 业务低谷触发重训）。
