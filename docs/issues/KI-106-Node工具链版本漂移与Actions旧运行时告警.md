# KI-106 · Node 工具链版本漂移与 Actions 旧运行时告警

- 状态：IN-PROGRESS
- 优先级：P2
- 更新日期：2026-09-23
- 适用范围：本地 JavaScript 工具链、前端包元数据、GitHub Actions 质量门与部署工作流
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[开发标准](../development/DEVELOPMENT-STANDARD.md)、[测试标准](../development/TESTING-STANDARD.md)

---

## 结论

项目实际已在本地与 CI 使用 Node 24，但仓库没有版本文件，前端 `package.json` 也没有声明 Node 与 pnpm
约束；外部开发者无法从仓库自动复现维护者工具链。同时质量与部署工作流仍引用内部声明 Node 20 的旧版
JavaScript Actions，GitHub Runner 只能强制以 Node 24 兼容执行并持续产生弃用告警。

本 KI 最初按 Node 24 LTS 建立仓库单一事实源；项目所有者随后决定将目标更新为 Node 26.10.0 与
pnpm 12.6.0。Node 26 在实施日仍为 Current、尚未进入 LTS，因此采用精确版本固定、完整本地质量门与 CI
验收控制风险。该变更不改变浏览器运行时代码、后端 Python 运行时或生产服务进程。

## 只读证据（2026-09-23）

1. 开发机由 asdf 提供 `Node v24.19.0`，而仓库中没有 `.tool-versions`、`.node-version` 或 `.nvmrc`；
2. `.github/workflows/quality.yml` 两个任务均手写 `node-version: "24"`，只能固定主版本，不能固定补丁版本；
3. `frontend/package.json` 没有 `engines.node` 与 `packageManager`，尽管 CI 实际使用 pnpm 11.22.0；
4. CI 告警点名 `actions/checkout@v4`、`actions/setup-node@v4`、`actions/setup-python@v5`、
   `astral-sh/setup-uv@v6` 与 `pnpm/action-setup@v4` 仍声明 Node 20；
5. 上述 Actions 的现行稳定版本均已声明 `runs.using: node24`。

## 影响分析

1. **开发结果漂移**：不同贡献者可能使用 Node 22、24 或未来版本，只有 CI 才暴露差异；
2. **工具链不可复现**：Node 与 pnpm 没有仓库级权威版本，干净克隆不能自动选择与 CI 相同的环境；
3. **CI 前向风险**：旧 Action 当前只是被 Runner 强制兼容执行，后续可能因 Node 20 完全移除而失败；
4. **告警噪声**：持续的弃用告警会掩盖新的真实流水线问题。

## 治理方案

1. 新增仓库级 `.tool-versions`，精确固定 Node 26.10.0 与 pnpm 12.6.0；
2. 在前端 `package.json` 声明兼容的 Node 26 范围、Node 26 类型定义与精确 `packageManager`；
3. GitHub Actions 改为从 `.tool-versions` 读取 Node，并升级到原生 Node 24 的稳定 Action 版本；
4. README 与 `CURRENT-STATE.md` 同步公共开发前提；
5. 增加回归检查，阻断版本文件、包元数据和工作流再次漂移。

## 完成定义

- [x] 仓库存在唯一、精确、可由本地 asdf 与 GitHub Actions 共用的 Node 版本文件；
- [x] 前端包元数据明确 Node 26.10.0 与 pnpm 12.6.0 约束；
- [x] 质量、部署与变更日志工作流不再引用已知的 Node 20 Action 版本；
- [x] CI 的两个 Node 安装步骤均读取同一版本文件，不再分别手写版本；
- [x] 公共快速启动文档与当前事实同步；
- [x] 工具链一致性回归测试及全量 `make check` 通过；
- [ ] GitHub Actions 使用新配置完成质量与部署任务，且不再产生 Node 20 Action 运行时告警。

## 本地实施与验证（2026-09-23）

- 已安装并由仓库 `.tool-versions` 选择 Node.js 26.10.0 与 pnpm 12.6.0；`node --version` 返回
  `v26.10.0`，`pnpm --version` 返回 `12.6.0`；
- `quality.yml`、`changelog.yml` 已升级到当前稳定 Action 版本；逐一核验这些版本的 `action.yml`，
  `actions/checkout`、`actions/setup-node`、`actions/setup-python`、`astral-sh/setup-uv`、
  `pnpm/action-setup` 与 `actions/upload-artifact` 均声明 `runs.using: node24`；
- pnpm 12 已生成包含精确包管理器依赖的环境锁文档，Node 类型定义同步到 26.6.2；普通安装与
  `pnpm install --frozen-lockfile` 均通过；
- Harness 前端与工具领域定向检查通过；全量 `make check` 通过，包括后端 280 项、前端 169 项、
  项目脚本 32 项，以及 lint、类型检查、生产构建、文档治理、链接和公开资产扫描；
- 变更尚未提交、推送或部署，最后一项需由 GitHub 执行新工作流后验收，本 KI 保持 `IN-PROGRESS`。
