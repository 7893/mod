# KI-107 · HeatWave 原生 SHAP 权限边界与预生成缺口

- 状态：IN-PROGRESS
- 优先级：P1
- 更新日期：2026-09-23
- 适用范围：HeatWave AutoML 每日重训、风险解释结果持久化、只读 API 与 F 屏归因展示
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-071](KI-071-F屏模型就绪与SHAP归因来源失真.md)、[AutoML 能力边界](../development/HEATWAVE-AUTOML-CAPABILITIES.md)、[AI 数据边界](../development/ML-AI-DATA-BOUNDARY.md)

---

## 当前证据

1. 生产分类模型及 SHAP explainer 已训练完成，但 API 使用 `mod_readonly`，只具备业务 schema 的
   `SELECT` 权限；直接调用 `sys.ML_EXPLAIN_ROW` 会进入多个内部例程授权链，最小授权无法稳定闭环；
2. 曾试验的两个精确 `EXECUTE` 授权已全部撤销，生产 API 账号恢复原只读授权，无残留权限扩大；
3. 2026-09-23 只读性能探针显示，三行调用在 3 秒上限内被中断，单行调用在 10 秒上限内仍被中断；
   在线请求现场计算会造成慢响应和重复算力消耗；
4. 当前生产接口因此诚实返回 `RULE_BASED`，没有把规则解释冒充为原生 SHAP。
5. 获得 Owner 授权后的 10 行生产探针成功：18.4 秒生成 10/10 行，10/10 都包含有效
   `attributions`，输出含 7 个归因列；两张临时工作表和探针文件均已清理，残留为 0。
6. 按 3,207 行、321 批线性估算，单次全量 SHAP 约需 98 分钟；原有 systemd 600 秒超时不足，
   `mod-ml-retrain.service` 已调整为 3 小时并部署生产，线上读取值为 `TimeoutStartUSec=3h`。
7. 签名提交 `c58775f` 经 GitHub Actions 运行 `35867791872` 发布为 `20260923-133434`；质量门、部署、
   API 健康、HeatWave 12/12、重训练 timer 与 `mod.service` 均通过验收。首轮持久化结果尚未生成，
   线上解释接口按设计继续返回 `RULE_BASED`。

## 决策

采用后台预生成方案，不扩大公网 API 数据库身份的权限：

1. 每日管理员重训任务在 SHAP explainer 训练完成后，使用 `ML_EXPLAIN_TABLE` 生成解释；
2. 风险特征表超过十列，严格按 MySQL 9.4.1+ 官方限制将每批输入控制为最多 10 行；
3. 所有批次先写入隔离候选表，校验行数和 `attributions` 完整性后再原子切换；
4. 保留上一版解释表作为回滚快照；任一批次失败时不切换，API 继续读取旧快照或诚实降级；
5. API 只在特征 SHA-256 指纹和模型训练时间同时匹配时接受快照，阻断失败重训后的旧解释错配；
6. API 只查询 `mod.ml_risk_explanation`，不再执行任何 `sys` ML 例程，也不新增数据库账号。

## 完成定义

- [x] 本地代码移除 API 请求内的 `ML_EXPLAIN_ROW`，改为只读查询预生成结果；
- [x] 预生成实现具备 10 行批次上限、全量校验、失败保留和原子切换；
- [x] 回归测试覆盖真实 SHAP 解析、旧快照拒绝、规则降级、批次限制与失败不切换；
- [x] 完整 `make check` 通过；
- [x] 10 行生产探针返回完整原生 SHAP 并且临时对象全部清理；
- [x] GitHub Actions、生产健康检查与 3 小时 systemd 超时配置通过验收；
- [ ] 经数据库变更闸门授权后，在生产创建结果表并完成首轮生成；
- [ ] 验证 API 返回 `HEATWAVE_SHAP`、API 账号权限仍为只读、上一版快照可恢复；
- [ ] 完成首轮生成和读路径验收后关闭 KI。

## 生产变更边界（尚未执行）

- 精确目标：生产数据库 `mod` 中 `ml_risk_explanation`、`ml_risk_explanation_previous` 及三个临时工作表；
- 影响范围：只复制 `ml_feat_risk` 特征并写入派生解释，不修改业务源表、模型目录或账号授权；
- 恢复方案：当前表仅在全量成功后原子切换，上一版保留为 `ml_risk_explanation_previous`；必要时反向重命名恢复；
- 验收查询：核对源表/解释表行数、JSON `attributions` 完整性、API 来源标记、账号 `SHOW GRANTS`；
- 当前状态：代码与 3 小时 systemd 配置已部署；10 行临时探针已执行并清理；未执行生产持久结果表
  DDL 或首轮全量生成。
