# 密钥与配置管理规范

更新日期：2026-09-23
状态：现行
适用范围：运行时配置、CI/CD 密钥、以及公开发布前的敏感信息管理

## 本文定位

本文规定敏感信息（凭据、主机、账号、密钥）在三个场景下的管理方式：
运行时（.env）、CI/CD（GitHub Secrets）、以及公开发布前的净化。
凭据不进代码/历史的基础原则见 `DATA-AND-SECURITY-STANDARD.md`；执行强制见 `ENFORCEMENT.md`。

## 一、运行时配置：项目级 .env

- 运行时敏感值（数据库地址/账号/密码、OCI、Cloudflare 账号与 Token、AI 开关等）
  **只从环境变量读取**，源码中不得硬编码，也不得保留可用的回退默认值。
- 实际值放主机上的 `.env`（或 `.env.systemd`），权限 600，已由 `.gitignore` 忽略，永不进仓库。
- 仓库只保留 `.env.example`：列全所有变量名 + 安全占位符/空值，不含任何真实值。
- 新增环境变量时，必须同步更新 `.env.example`、读取代码与相关文档（依 `DEVELOPMENT-STANDARD.md`）。
- 主机占位示例一律用 `127.0.0.1` 等非真实值，不得把真实内网/公网地址写进 `.env.example`。

## 二、CI/CD 密钥：GitHub Secrets

- GitHub Actions 的 `check` job 只做凭据扫描、提交校验和 `make check`，不需要生产 Secret。
- push 至 `main` 或人工触发时，`deploy` job 仅在质量闸门通过后运行；它通过仓库 Secrets
  `USA_HOST`、`USA_SSH_KEY` 与可选的 `USA_HOST_KEY` 连接 USA 生产机，执行原子 release 发布。
- JPA 开发机与 USA 生产机按 ADR-0012 分离。GitHub Actions 是默认发布渠道，
  `scripts/project/publish.sh` 是需要同等显式授权的直连备用渠道。
- CI 部署凭据只存在于 GitHub Secrets；数据库凭据和运行时 `.env.systemd` 不进入 GitHub。

## 三、公开发布前的敏感信息净化

仓库若要公开，`.env` 机制只能保证“从今往后”不进新密钥，**无法清除已存在于文件或 Git 历史中的敏感信息**。
公开前必须完成三层净化：

1. **运行时值**：确认活跃源码全部走环境变量，无硬编码（含无真实回退默认值）。
2. **文档/配置/脚本中的明文敏感值**：脱敏为占位符或中性描述，包括——
   真实内网/公网 IP、OCI OCID、Cloudflare Account ID、真实数据库账号口令等。
   （公开域名等本就对外的信息可保留，按需判断。）
3. **Git 历史**：历史提交中的敏感信息 `.env` 与 Secrets 都管不到，须单独处理——
   要么新建仓库以净化后的当前状态为起点、不导入旧历史；
   要么以 `git filter-repo` 重写历史（高风险，见 [KI-014](../issues/KI-014-公开仓库前净化工程.md)）。

归档区不享有扫描豁免或安全例外；若以后放入历史脚本，公开前必须排除或脱敏，
不得默认“归档了就安全”。

## 四、扫描与强制

- 提交经 pre-commit 与 CI 共用的 `detect-secrets` 配置拦截明文凭据；
  未受 Git 跟踪的本地材料不在暂存区扫描范围内，公开前仍须单独确认。
- `check_public_sanitization.py` 补充识别具体公网/私网地址、云资源标识、生产域名指纹和维护者
  私有资产清单；规则、测试和诊断均不得复写真实命中值。
- 当前树扫描是“从今往后”的动作点闸门，不撤回既有公开 Git 历史；历史处置仍依赖第三节的单独决策。
- 判断哪些公开入口可保留仍需人工复核；允许清单不得用来放行源站、私有拓扑或可复用认证材料。

## 五、与既有文档的关系

- 凭据不进代码/日志/历史的通则、数据分级：`DATA-AND-SECURITY-STANDARD.md`。
- 配置不硬编码、新增变量同步：`DEVELOPMENT-STANDARD.md`。
- 公开准备任务清单：[KI-014](../issues/KI-014-公开仓库前净化工程.md)。
- 执行强制与闸门：`ENFORCEMENT.md`。
