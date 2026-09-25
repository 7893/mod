# MOD 项目协作与贡献指南 (Contributing Guide)

更新日期：2026-09-23
状态：现行
适用范围：开源社区贡献者、核心维护者以及项目所有编码 Agent

---

## 第一部分：开源社区贡献者指南 (Community Contributors)

MOD 当前公开源码并接受符合质量要求的 Pull Request，但不提供通用支持或功能请求入口；边界见
[SUPPORT.md](SUPPORT.md)。

### 1. 快速上手流程 (Workflow)

1. **Fork 仓库**：在 GitHub 上将 `7893/mod` Fork 到您的个人命名空间。
2. **克隆与环境就绪**：
   ```bash
   git clone https://github.com/<your-username>/mod.git
   cd mod
   ```
   开发前置要求：Python 3.13.15、[`uv`](https://docs.astral.sh/uv/) 0.12.5、Node.js 26.10.0、pnpm 12.6.0 与 `make`。
3. **本地离线启动（无需数据库）**：
   项目内置了高保真合成数据快照（Fallback Snapshot），无需安装或连接任何数据库即可完整体验与开发前端六屏及后端 API：
   ```bash
   # 终端 1：后端只读服务
   cd backend && uv sync --all-extras
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8100

   # 终端 2：前端看板
   cd frontend && pnpm install
   pnpm dev
   # 浏览器访问 http://127.0.0.1:5173/
   ```
4. **创建工作分支**：
   ```bash
   git checkout -b fix/my-bug-fix
   # 或
   git checkout -b feat/my-feature
   ```
5. **本地质量门禁验证（极其重要）**：
   在发起提交和 PR 之前，请务必在仓库根目录执行标准公共门禁：
   ```bash
   make check
   ```
   `make check` 是项目唯一公共且可复现的质量检验入口，会自动执行：
   - 后端 Ruff 代码风格检查与 Pytest 单元测试（完全离线自洽）；
   - 前端 ESLint、Stylelint、Vue-tsc 类型检查、Vitest 单元测试与 Vite 构建；
   - 文档治理与语义契约校验。
6. **约定式提交**：
   提交信息请遵循 Conventional Commits 规范，格式为 `type: <=7-word english subject`（如 `fix: resolve china map resize layout` 或 `docs: clarify offline fallback guide`）。
7. **发起 Pull Request**：
   推送到您的远程分支后，在 GitHub 发起 PR，并在模板中勾选自检清单。CI/CD 将自动执行完整的 Quality Gates。

### 2. 协作与安全报告机制

- **日常缺陷与功能讨论**：GitHub Issues 与 Discussions 当前关闭；仓库不承诺一般问题答复或功能规划服务；
- **代码改进**：可直接发起带复现、验证和影响说明的 Pull Request，维护者确认缺陷后再映射内部 KI；
- **安全漏洞**：切勿在公开 Pull Request 中披露漏洞细节；仅在仓库 Security 页面实际显示
  **Report a vulnerability** 时使用该私密入口，完整边界见 [SECURITY.md](SECURITY.md)；
- **行为准则**：所有参与者须严格遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

---

## 第二部分：核心维护者与 Agent 内部治理规范 (Internal Governance)

本章节适用于对生产环境拥有发布权限的核心维护者以及在维护者环境中执行任务的编码 Agent。

### 1. 架构与主机职责分离 (ADR-0012)

- **开发工作区机（JPA）**：承载源码、完整开发工具链与本地测试库；
- **生产宿主机（USA）**：不初始化 Git 仓库的独立生产部署节点，核心服务由 systemd 托管；
- **发布机制**：标准发布由 GitHub Actions CI/CD 流水线在 push 至 `main` 分支并通过 Quality Gates 后自动触发；本地 `scripts/project/publish.sh` 保留为直连应急通道，必须获得显式授权方可运行。

### 2. 核心维护者红线与约束

- **约束最高优先级**：必须严格遵循 [AGENTS.md](AGENTS.md) 与 [ENFORCEMENT.md](ENFORCEMENT.md)；
- **权限与改动边界**：默认只读。数据库写入、生产服务启停、Nginx 变更、云资源调整均需显式授权；
- **凭据与脱敏零容忍**：绝不提交私钥、Token、真实 IP、私有域名或未脱敏数据；
- **已知问题（KI）生命周期治理**：内部缺陷、技术债务与架构改进统一在 [docs/KNOWN-ISSUES.md](docs/KNOWN-ISSUES.md) 与 `docs/issues/` 中闭环追踪（详见 [ADR-0014](docs/decisions/0014-停用GitHub-Issues统一使用本地KI问题跟踪体系.md)）；社区确认的有效 Bug 由维护者复现后登记转入本地 KI 看板并进行原子提交修复。

---

## 现行核心参考规范

- [项目目录布局 (PROJECT-LAYOUT.md)](PROJECT-LAYOUT.md)
- [开发通用规范 (DEVELOPMENT-STANDARD.md)](docs/development/DEVELOPMENT-STANDARD.md)
- [前端架构与视觉契约 (FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md)](docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md)
- [数据与安全标准 (DATA-AND-SECURITY-STANDARD.md)](docs/development/DATA-AND-SECURITY-STANDARD.md)
- [文档治理与生命周期规范 (DOCUMENTATION-STANDARD.md)](docs/development/DOCUMENTATION-STANDARD.md)
