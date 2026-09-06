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

### 第一期 · AutoML 特征工程与归因透出（agy，进行中）
- [ ] 模拟器数据层注入真实因果关系（消除“过度可分”与“无因果”）
- [ ] `heatwave_sql.py` 扩充推进动量特征（推进斜率、停滞天数、经办人集中度、培训-上线剪刀差）
- [ ] `heatwave_ml.py` 调通 `ML_EXPLAIN_ROW` SHAP 归因；评估是否引入 forecasting / anomaly_detection
- [ ] 重训并用独立测试集验证；达标才展示，未达标如实标注
- [ ] D/F 屏下钻抽屉展示 Top3 风险归因标签
- [ ] 回归测试覆盖（KI 铁律：行为变更必须加回归测试）

### 第二期 · 指挥部决策简报自动化（主控 + 后续派单）
- [ ] `cloudflare_ai.py` 端点改走 `mod-gateway`（主控先行）
- [ ] 清理 `ai_narrator.py` 及 `/narrator/*` 死代码（主控先行）
- [ ] 新建简报聚合器 + 每日定时生成服务 + `daily_briefing` 表（需建表授权）
- [ ] A 屏 / F 屏简报卡片展示

### 第三期 · 拟真业务语料生态（押后）
- [ ] LLM 离线生成行业质感卡点事由语料库
- [ ] 生命周期跃迁自动生成《专家评审决议书》

## 进度
- 2026-09-06 立项，ADR-0010 采纳，`mod-gateway` 网关（缓存/限流/日志）已就绪并登记 CURRENT-STATE。
