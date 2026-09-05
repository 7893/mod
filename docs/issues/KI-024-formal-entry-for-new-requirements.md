# KI-024 · 缺少新需求/任务的正式登记入口

- 状态：DONE（2026-09-04）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`KNOWN-ISSUES.md` 记录“已发现的问题/缺陷”，`docs/decisions/` 记录“已做的决策”，
  但“新需求/新功能/待办任务”没有对称的正式登记处——目前散落在对话中，易丢失、不可追溯。
  `docs/tasks/` 是已停用协作流程的残留，不承担此职责。
- 影响：需求与问题不对称；新想法没有沉淀容器，违背“想清楚的东西必须记录下来让人/AI 遵循”的原则。
- 处理：启用 GitHub Issues 作为需求与任务的正式登记入口。在 `.github/ISSUE_TEMPLATE/` 建立 `feature_request.md`（新需求）与 `task.md`（任务待办）模板，包含标题、背景与业务价值、技术范围与验收要点；并在 `README.md` 与 `docs/INDEX.md` 明确增加指引：新需求/任务用 GitHub Issues 登记，已发现问题的登记见 KNOWN-ISSUES.md。存量 KNOWN-ISSUES 保持原位供追溯。
