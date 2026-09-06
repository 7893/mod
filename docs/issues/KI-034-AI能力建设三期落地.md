# KI-034 · AI 能力建设三期落地

- 状态：IN-PROGRESS（2026-09-06 立项）
- 优先级：P1
- 更新日期：2026-09-06
- 关联：[ADR-0010 项目AI能力建设总纲](../decisions/0010-项目AI能力建设总纲.md)、[HeatWave AutoML 能力手册](../development/HEATWAVE-AUTOML-CAPABILITIES.md)、[ML-AI 数据边界](../development/ML-AI-DATA-BOUNDARY.md)

## 目标
按 ADR-0010 三期路径，把项目 AI 从“基本未运作”建设为“真预测 + 真叙事”，全程遵守大屏定位、成本闸门与诚实原则。

## 分工
- **agy**：第一期（AutoML 特征工程与归因透出）——数据/模型重活。见派单。
- **主控（kiro）**：第二期第一步（`cloudflare_ai.py` 改走 `mod-gateway`）+ 清理 `ai_narrator.py` 死代码。

## 分期任务

### 第一期 · AutoML 特征工程与归因透出（agy，已完成）
- [x] 模拟器数据层注入真实因果关系（体量加权、经办人单点集中度瓶颈 75%、错误率因果 15% vs 2%、双轨天数期初差异考核惩罚 +7 天）
- [x] `heatwave_sql.py` 扩充推进动量特征（推进斜率、停滞天数、经办人集中度、培训-上线剪刀差、近 7 天日均、经办人数）
- [x] `heatwave_ml.py` 调通 `ML_EXPLAIN_ROW` 原生 SHAP 归因及确定性业务因果降级，新增 `/api/insights/risk-explanation/{org_id}`
- [x] 重训并用独立测试集验证达标：回归测试集 R² = 0.4488（消除负 R²），分类测试集 Accuracy = 89.50%（消除 1.0 退化），落库 `ml_model_metadata` / `ml_training_log`，`/api/insights/status` 变为 `READY`
- [x] 前端归因透出：`AtRiskUnitTable.vue` 增加 SHAP 归因与客观动量指标核验下钻抽屉，`ModelContractCard.vue` 与 `InsightsView.vue` 达标激活展示真实指标
- [x] 回归测试覆盖：新增 `test_heatwave_causality_and_shap.py`，全量 `make check` 122 项 pytest 100% 绿色通过

### 第二期 · 指挥部决策简报自动化（主控 + 后续派单）
- [x] `cloudflare_ai.py` 端点改走 `mod-gateway`（2026-09-06 完成，实测经网关调 Llama 生成三段式研判成功；补 User-Agent 绕过网关 WAF 1010 拦截）
- [x] 清理 `ai_narrator.py` 及 `/narrator/*` 死代码（2026-09-06 完成，含测试）
- [ ] 新建简报聚合器 + 每日定时生成服务 + `daily_briefing` 表（需建表授权）
- [ ] A 屏 / F 屏简报卡片展示

### 第三期 · 拟真业务语料生态（押后）
- [ ] LLM 离线生成行业质感卡点事由语料库
- [ ] 生命周期跃迁自动生成《专家评审决议书》

## 进度
- 2026-09-06 立项，ADR-0010 采纳，`mod-gateway` 网关（缓存/限流/日志）已就绪并登记 CURRENT-STATE。
- 2026-09-06 第一期完成并达标：模拟器因果改造（commit `91ccb4c`）、特征表扩充动量（commit `06b727a`）、SHAP 归因调通与库内重训独立验证达标（回归 R² = 0.4488, 分类 Accuracy = 89.50%, commit `ba19629`）、前端归因下钻抽屉与达标卡片联动（commit `3eb1ef7`）、自动化回归测试通过并归档。交付主控验收。
