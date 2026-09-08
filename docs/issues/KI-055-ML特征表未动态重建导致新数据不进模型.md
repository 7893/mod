# KI-055 · ML 特征表未动态重建导致新数据不进模型

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-08
- 适用范围：HeatWave AutoML 重训流程的特征表构建环节，使模型持续纳入增长中的最新数据
- 关联：[KI-051 模拟数据规模扩充](KI-051-模拟数据规模扩充与真实勾稽.md)、[KI-052 财务凭证科目真实性](KI-052-财务凭证科目与业务真实性深化.md)、[HeatWave AutoML 能力与边界](../development/HEATWAVE-AUTOML-CAPABILITIES.md)、`scripts/agy/train_and_evaluate_models.py`

---

## 问题

每日 ML 重训（`mod-ml-retrain`）的流程 `run_full_pipeline` 只做「检查特征表 →
切分 → 训练 → 评估 → 评分」，**第一步是检查特征表完整性，而非重建特征表**。

特征表（`ml_feat_risk`、`ml_feat_doc_delta`）的填充是历史上一次性完成的（当时约 2,000 家单位），
此后从未随业务数据增长而更新。结果：

- KI-051 将单位扩充到约 3,194 家、凭证扩到约 502 万后，特征表仍停留在 2,000 行旧数据。
- 所谓"每日重训"实际是拿同一批冻结的历史特征反复训练，**新增单位与每日新增业务数据从不进入模型**。
- 模型无法反映活的、增长的系统，重训失去意义。

这是设计缺陷：数据是动态增长的，但特征工程缺少"每次重训前从当前业务表重建特征表"的环节。

## 根因

- 重建特征表的能力其实早已存在：`backend/app/integrations/heatwave_sql.py` 定义了
  `_INSERT_FEAT_CLASSIFIER` / `_INSERT_FEAT_REGRESSION`（`FROM org_unit`，无单位范围限制，
  从当前 `construction_task`、`business_document`、`issue/risk_metric_snapshot`、`training` 等
  业务表 `GROUP BY org_id` 实时派生全部单位特征），`heatwave_ml.py` 也有 `build_feature_tables()`。
- 缺陷仅在于：`run_full_pipeline` 从未调用重建，只调用了检查。

## 修复（已执行）

在 `scripts/agy/train_and_evaluate_models.py` 中：

1. 新增 `rebuild_feature_tables(conn)`：`DELETE` 后用 `_INSERT_FEAT_*` 从当前业务表重算全部单位特征，
   复用 `heatwave_sql.py` 的既有特征 SQL（不新造口径）。
2. 在 `run_full_pipeline` 的 `check_feature_integrity` 之前接入 `rebuild_feature_tables`，
   使每次重训第一步即动态重建特征表，纳入当前全部单位与最新业务数据。

自此，单位/业务每日增长都会在下一次重训自动进入模型，无需人工干预。

## 验收证据（2026-09-08 手动触发一次全量重训）

- 特征表由旧的 2,000 行重建为覆盖当前全部单位：分类特征表与回归特征表分别按当前单位与派生规则重算
  （回归特征表行数等于当前单位数）。
- 训练/测试样本量相应增大（风险模型训练集由 1,600 增至约 5,110）。
- 模型质量随真实全量数据显著提升（真实测试集，落库于 `ml_model_metadata` / `ml_training_log`，
  以库内记录为准）：分类准确率约 90%，回归 $R^2$ 由约 0.45 提升至约 0.88。
- 全量批量评分覆盖当前全部单位（`ml_score_risk` / `ml_score_doc_delta`）。

> 说明：以上模型质量为动态派生结果，真值以 `ml_model_metadata` 落库记录为准，本文不作为长期硬编码事实。

## 影响与后续
- 每日 00:00 定时重训（`mod-ml-retrain.timer`）自此自动纳入当日最新数据，模型随系统演进而更新。
- 重训耗时随数据规模增长而上升（当前一次全量约 16 分钟），后续如需可评估增量特征或分区训练优化。

## 进度
- 2026-09-08 立项并修复、手动全量重训验证通过（DONE）。承接 KI-051/052 数据扩充后暴露的动态纳入缺口。
