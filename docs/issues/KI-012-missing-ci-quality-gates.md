# KI-012 · CI 侧闸门缺失（本地 hook 可被绕过）

- 状态：DONE（2026-09-04，已在公开仓库 GitHub Actions 生效并多次跑绿）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象（原）：本地 pre-commit 可被 `git commit --no-verify` 绕过，仓库无 CI。
- 处理：`.github/workflows/quality.yml` 在 push/PR 触发，执行凭据扫描 + 提交信息校验 + `make check`，
  作为不可绕过的第二道；仓库已公开，CI 实际运行并通过。
