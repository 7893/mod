# MOD 项目协作指南

更新日期：2026-09-06
状态：现行
适用范围：在 `/home/ubuntu/mod` 工作的人类开发者与所有编码 Agent

本仓库维护在主运行主机上，同机承载生产运行，不存在独立的纯部署主机。

## 接手前必读（按顺序）

1. `AGENTS.md` — 全仓库强制约束，最高优先级。
2. `ENFORCEMENT.md` — 约束如何在动作点被强制执行（闸门，不只是指导）。
3. `docs/CURRENT-STATE.md` — 当前运行时、数据与安全事实。
4. `PROJECT-LAYOUT.md` — 目录与主机边界。
5. 与任务类型匹配的领域规范 — 见 `AGENTS.md` 的"按任务类型必读规范"映射表
   （改前端读 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md`，碰数据库读 `DATA-AND-SECURITY-STANDARD.md`，
   任何改动读 `TESTING-STANDARD.md`）。按需读对应的，不必全读。

文档有冲突时，以 `AGENTS.md` 的权威顺序为准。旧的多 Agent 协作状态机已归档至
`archive/legacy-collaboration/`，不得作为活跃工作流使用。

## 标准工作流

1. 运行 `git status --short`，检查相关已有改动。
2. 查看是否有更具体的 `AGENTS.md`，然后阅读目标区域的源码、测试与当前文档。
3. 说明预期改动范围，识别需要显式授权的操作。
4. 在正确的领域目录做最小的连贯改动。
5. 为行为变更和回归修复添加或更新测试。
6. 先跑局部检查，再从仓库根目录运行 `make check`。
7. 检查 `git diff --check`、`git diff`、`git status --short`。
8. 凡事实、行为、路径、命令、数据或部署状态发生变化，必须同步更新当前文档。
9. 创建签名本地提交，一次提交一个连贯意图，提交信息格式：英文小写 Conventional Commit 类型，不超过七个词。
10. 报告验证结果、剩余风险、部署状态与提交 ID。

## 改动边界

默认只读检查。以下操作需要显式授权方可执行：数据库写入、生产服务启停、Nginx 变更、云资源变更、
破坏性清理、或向本地仓库以外发布任何内容。不得修改 `/home/ubuntu/modo` 或其他项目。

## 提交约定

- 使用 `git commit -S` 与现有签名配置。
- 提交主题使用英文小写 Conventional Commit 类型，不超过七个词。
- 每次提交保持一个连贯意图。
- 未经明确指令不得改写已有提交。
- 未经明确指令不得添加远程仓库、推送、发布 release 或创建 GitHub 仓库。
- 绝不提交密钥、本地数据、生成的 CSV 文件、构建产物、依赖缓存或 CLI 日志。

## 现行规范文档

- `docs/development/PROJECT-ORGANIZATION.md`
- `docs/development/DEVELOPMENT-STANDARD.md`
- `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md`
- `docs/development/COLLABORATION-STANDARD.md`
- `docs/development/TESTING-STANDARD.md`
- `docs/development/DOCUMENTATION-STANDARD.md`
- `docs/development/DATA-AND-SECURITY-STANDARD.md`
- `docs/development/SECRET-SCAN-HOOK-DESIGN.md`
- `docs/development/CLI-SCRIPT-POLICY.md`
