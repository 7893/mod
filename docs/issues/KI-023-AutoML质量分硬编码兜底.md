# KI-023 · AutoML 就绪状态与模型质量分带有硬编码兜底，可能展示未生成的结果

- 状态：DONE（2026-09-05 止血完成，消除展示层伪造）
- 更新日期：2026-09-05
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`GET /api/v2/insights/status` 在 HeatWave 适配器报告 `ready` 时，无条件写入
  `automlStatusDisplay="已就绪"`、`trainingAuthorized=True` 与"实时提供预测"文案；模型质量分通过
  `reg_info.get("quality", 0.942)`、`cls_info.get("quality", 0.915)` 取值，无真实值时以硬编码填充。
- 根因核查（2026-09-05 主控实测）：硬编码 0.942/0.915 共 6 处（`heatwave_ml.py` 4 处 + `api_v2.py` 2 处），
  前端 `InsightsView.vue` 另有 `|| 0.942 / || 0.915` 兜底 2 处；线上曾实际展示 94.2%/91.5% 与"已就绪、实时预测"，
  而库内无真实模型评估分、`ml_score_risk` 概率非 0 即 1（训练集自评分假象，见 KI-015）——确属展示层事实伪造。
- 处置（止血，C 步）：
  - 后端 `heatwave_ml.py`：4 处去硬编码，无真实 `model_quality`/`training_score` 时 `quality=None`、
    降级分支 `status=not_evaluated/not_trained`，不谎报 ready。
  - 后端 `api_v2.py insights_status`：仅当存在真实质量分才置"已就绪/trainingAuthorized=true/提供预测"文案；
    否则如实显示"训练/评分未完成"，`quality` 透传真实值或 None。
  - 前端 `InsightsView.vue`：`isReady` 改由真实质量分决定，去掉 `|| 0.942/0.915` 兜底，文案如实降级；
    `ModelContractCard.vue` 质量分为空时显示"—（训练/评分未完成）"；`project.ts` 类型支持 `quality: number|null`。
  - 实测：线上 `insights/status` 现返回 `quality:null`、`trainingAuthorized:false`、状态"待授权训练"，不再伪造。
  - make check 绿（含 vue-tsc），mod-api 已重启生效。
- 后续（B 步，真训练）：基于模拟器持续产生的真实数据做带 train/test split 的真实训练评估，取真实准确率再展示，
  并入 KI-015 一并推进。
- 待决策与待处理：
  - 移除 `quality`/`algorithm` 的硬编码兜底默认值；适配器未提供真实值时，字段应缺省或显式标记为未提供。
  - 就绪文案须由真实训练与评分状态派生；未完成训练时显式展示"未训练/未评分"，不得表述为"已就绪"。
  - 需补充覆盖"适配器 ready 但无质量数据"路径的测试，防止回归。
