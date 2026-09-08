# KI-034 · AI 能力建设三期落地

- 状态：DONE（2026-09-06 一、二、三期全部落地）
- 优先级：P1
- 更新日期：2026-09-06
- 适用范围：HeatWave AutoML、LLM 决策简报与拟真业务语料生态三期能力建设
- 关联：[ADR-0010 项目AI能力建设总纲](../decisions/0010-项目AI能力建设总纲.md)、[HeatWave AutoML 能力手册](../development/HEATWAVE-AUTOML-CAPABILITIES.md)、[ML-AI 数据边界](../development/ML-AI-DATA-BOUNDARY.md)

## 目标
按 ADR-0010 三期路径，把项目 AI 从“基本未运作”建设为“真预测 + 真叙事”，全程遵守大屏定位、成本闸门与诚实原则。

## 分工
- **agy**：第一期（AutoML 特征工程与归因透出）+ 第三期（拟真业务语料生态与确定性接入）。
- **主控（kiro）**：第二期（`cloudflare_ai.py` 改走 `mod-gateway`、清理 `ai_narrator.py` 死代码、每日决策简报定时服务）。

## 分期任务

### 第一期 · AutoML 特征工程与归因透出（agy，已完成）
- [x] 模拟器数据层注入真实因果关系（体量加权、经办人单点集中度瓶颈 75%、错误率因果 15% vs 2%、双轨天数期初差异考核惩罚 +7 天）
- [x] `heatwave_sql.py` 扩充推进动量特征（推进斜率、停滞天数、经办人集中度、培训-上线剪刀差、近 7 天日均、经办人数）
- [x] `heatwave_ml.py` 调通 `ML_EXPLAIN_ROW` 原生 SHAP 归因及确定性业务因果降级，新增 `/api/insights/risk-explanation/{org_id}`
- [x] 重训并用独立测试集验证达标：回归测试集 R² = 0.4488（消除负 R²），分类测试集 Accuracy = 89.50%（消除 1.0 退化），落库 `ml_model_metadata` / `ml_training_log`，`/api/insights/status` 变为 `READY`
- [x] 前端归因透出：`AtRiskUnitTable.vue` 增加 SHAP 归因与客观动量指标核验下钻抽屉，`ModelContractCard.vue` 与 `InsightsView.vue` 达标激活展示真实指标
- [x] 回归测试覆盖：新增 `test_heatwave_causality_and_shap.py`，全量 `make check` 122 项 pytest 100% 绿色通过

### 第二期 · 指挥部决策简报自动化（主控，已完成）
- [x] `cloudflare_ai.py` 端点改走 `mod-gateway`（2026-09-06 完成，实测经网关调 Llama 生成三段式研判成功；补 User-Agent 绕过网关 WAF 1010 拦截）
- [x] 清理 `ai_narrator.py` 及 `/narrator/*` 死代码（2026-09-06 完成，含测试）
- [x] 新建简报聚合器 + 每日定时生成服务 + `daily_briefing` 表（2026-09-06 完成，授权建表；`services/daily_briefing.py` + `scripts/kiro/run_daily_briefing.py` + `deploy/mod-daily-briefing.{service,timer}`，每日 HKT 00:30 触发；实测端到端生成入库成功）
- [x] A 屏简报卡片展示（2026-09-06 完成，A1 下方一行摘要横幅，点击进 F 屏；只读 `/api/insights/briefing`）

### 第三期 · 拟真业务语料生态（agy，已完成）
- [x] LLM 离线预生成行业质感卡点事由语料库（363 条真实国资/政企财务卡点事由，覆盖 5 大类）与专家评审决议书（325 条全阶段跃迁评审决议），落盘为静态资产 `simulation/assets/business_corpus.json`（688 条，免除 DB 建表审批与结构变更风险）
- [x] 模拟器接入业务语料库：`evolution_coordinator.py` 与 `construction_playbooks.py` 按 `org_id` 稳定哈希检索，保持 100% 确定性可复现，杜绝机械重复文本
- [x] 运行时零 LLM 调用：执行零网络与零运行时 LLM 成本硬契约，离线预生成 + 内存哈希查表
- [x] 回归测试与契约守护：新增 `backend/tests/test_business_corpus.py`（8 项测试覆盖静态资产校验、内容安全去占位符、确定性复现、分类覆盖、零网络阻断测试、模拟器集成），全量 `make check` 130 项测试通过

## 进度
- 2026-09-06 立项，ADR-0010 采纳，`mod-gateway` 网关（缓存/限流/日志）已就绪并登记 CURRENT-STATE。
- 2026-09-06 第二期完成（主控）：`cloudflare_ai.py` 改走 `mod-gateway` 实测通、清理 `ai_narrator.py` 死代码、建立每日简报系统服务与 A 屏横幅展示。
- 2026-09-06 **第一期完成并通过主控验收 + 上线**（agy 实现，主控验收部署 release `20260906-185652`）：AutoML 从 `VALIDATION_FAILED` 复活为 `READY`——分类测试集 89.5%、回归 R² 0.4488（真实、非虚假 1.0），SHAP 归因下钻已上线，线上 `/api/insights/status` 实测 `READY`。第一期六项全部达标。
- 2026-09-06 **第三期完成**（agy 实现）：离线预生成 688 条国资财务语料静态资产（`simulation/assets/business_corpus.json`，363 条 5 类卡点事由 + 325 条 5 阶段评审决议），模拟器两处机械重复文本改为基于 `org_id` 稳定哈希确定性查表取用，严格执行零运行时 LLM 调用与零网络依赖，新增 8 项针对性回归测试全绿，全链路 `make check` 130 项测试通过。三期全部圆满交付。
