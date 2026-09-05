# KI-016 · 提交信息格式无机制校验

- 状态：DONE（2026-09-04）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：pre-commit 闸门只校验代码内容（凭据扫描 + make check），不校验 commit message 格式；
  不符合 `AGENTS.md` 提交约定的信息可以通过。实例：`77f5e5a "Fix regional snapshot consistency"`
  （应为英文小写、带 type 前缀、不超过 7 词，如 `fix: derive regional document additions`）。
- 影响：提交历史风格不一致；提交规范停留在“须知”，未成“闸门”。
- 依据约定：`AGENTS.md` Git 节——英文、不超过 7 词、单一意图；`git commit -S` 签名。
- 处理：新增 `.githooks/commit-msg` 与共享 `scripts/project/validate_commit_message.py`，校验英文小写
  Conventional Commit type 和七词上限；CI 对提交范围执行同一规则。
