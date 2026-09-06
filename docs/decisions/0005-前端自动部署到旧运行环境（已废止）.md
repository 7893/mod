# ADR-0005: 启用前端到 USA 的自动 CD

- 状态：已被取代（superseded by ADR-0006，2026-09-05）
- 日期：2026-09-04

> 取代通知（2026-09-05）：项目已整体迁移到单一运行主机（生产与源码工作区同机），跨主机的前端自动 CD
> 及其 `deploy.yml` 已废止删除。本 ADR 仅作历史决策留档，不再生效。现行决策见 ADR-0006。

## 背景
项目已公开于 GitHub 并具备 CI。为跑通完整 CI/CD 流水线，需决定是否自动部署到 USA。
此前建议保持手动部署，避免把生产访问权托管给第三方（尤其公开仓库）。

## 决策
启用前端自动 CD：push `main` → CI（Quality gates）通过 → `deploy.yml` 自动构建并 rsync
前端 `dist` 到 USA。仅前端，部署前自动备份，不涉及后端/数据库/服务/Nginx。

## 理由
- 用户明确要求跑通全自动流水线，接受相应权衡。
- 通过加固把风险降到最小：仅 `main` 的 `workflow_run` 触发（不在 PR 触发）、依赖 CI 成功、
  仅前端、部署前备份、用完即删私钥。
- 后端/服务/Nginx/数据库等高危变更**不纳入自动化**，仍须人工授权，风险面被限制在“前端静态资源”。

## 后果
- 新增 GitHub Secrets：`USA_SSH_KEY`、`USA_HOST`、`USA_USER`（USA 访问凭据托管于 GitHub）。
- 相应更新 `AGENTS.md`、`ENFORCEMENT.md`（闸门 D 例外）、`SECRETS-AND-CONFIG.md`。
- 已接受的风险：公开仓库 CI 持有 USA 前端部署权；若需收紧，可改为 `workflow_dispatch` 手动触发
  或改用专用受限部署密钥（后续可另立 ADR 调整）。
