# MOD 文档索引

更新日期：2026-09-12
状态：现行索引
适用范围：当前规范、项目资料、历史基线、运维记录与证据入口

## 当前必读

1. [AGENTS.md](../AGENTS.md)：仓库硬约束与事实优先级。
2. [ENFORCEMENT.md](../ENFORCEMENT.md)：红线在动作点的强制执行方式（闸门，而非仅须知）。
3. [CONTRIBUTING.md](../CONTRIBUTING.md)：接手、开发、验证、文档和提交流程。
4. [CURRENT-STATE.md](CURRENT-STATE.md)：当前运行、数据、质量与操作边界的唯一事实入口。
5. [PROJECT-LAYOUT.md](../PROJECT-LAYOUT.md)：项目目录和运行主机边界。
6. [KNOWN-ISSUES.md](KNOWN-ISSUES.md)：已知问题看板（已发现问题的看板列表，各 issue 详情见 [issues/](issues/)；新需求/任务用 GitHub Issues 登记）。
7. [CHANGELOG.md](../CHANGELOG.md)：从公开就绪基线开始、由锁定版本 git-cliff 生成的发布变更快照。
8. [HISTORY-CATALOG.md](HISTORY-CATALOG.md)：冻结历史的稳定编号、可见性、哈希与备份状态目录。

### 本轮重大缺陷

- [KI-076 前端展示事实、组合布局与视觉回归缺口](issues/KI-076-FRONTEND-PRESENTATION-CONTRACT.md)

配套验收：[前端视觉回归](development/FRONTEND-VISUAL-VERIFICATION.md)。
修订前原文：[2026-09-11 前端规范历史切片](history/2026-09-11-FRONTEND-STANDARDS.md)。
- [KI-070 驾驶舱跨屏业务口径与交互状态不一致](issues/KI-070-驾驶舱跨屏业务口径与交互状态不一致.md)
- [KI-071 F 屏模型就绪与 SHAP 归因来源失真](issues/KI-071-F屏模型就绪与SHAP归因来源失真.md)
- [KI-072 常驻模拟器生命周期编排、事务与安全状态未闭环](issues/KI-072-常驻模拟器生命周期编排事务与安全状态未闭环.md)
- [KI-073 实时投影与持久化模拟器双轨事件链事实分裂](issues/KI-073-实时投影与持久化模拟器双轨事件链事实分裂.md)
- [KI-074 历史文档未版本化保全与语义治理闸门缺失](issues/KI-074-历史文档未版本化保全与语义治理闸门缺失.md)
- [KI-075 前后端审计后遗留的死接口、静态兜底与命名残留](issues/KI-075-前后端审计后遗留死接口静态兜底与命名残留.md)
- [KI-078 生产API文档暴露接口无频控及源站密钥解耦治理](issues/KI-078-生产API文档暴露接口无频控及源站密钥解耦治理.md)

## 现行维护规范

- [本地通用 Harness 接入](development/LOCAL-HARNESS.md)：领域读取、摘要验收与回滚。
- [ADR-0011](decisions/0011-local-harness.md)：公共包与项目适配分离。
- [ADR-0012](decisions/0012-恢复USA生产部署机与JPA专属开发机架构.md)：恢复 USA 生产部署机与 JPA 专属开发机职责分离架构。
- [ADR-0013](decisions/0013-DNS迁移至GoogleCloudDNS与CloudFront边缘加速.md)：全球边缘加速与权威 DNS 迁移至 Google Cloud DNS 与 CloudFront。
- [Harness 入口迁移前原文](history/2026-09-11-HARNESS-ENTRYPOINTS.md)：旧入口完整保全。

- [development/README.md](development/README.md)：现行开发规范导航。
- [issues/](issues/)：已知问题独立文档目录（各问题完整上下文、分析与处理记录）。
- [development/PROJECT-ORGANIZATION.md](development/PROJECT-ORGANIZATION.md)：源码分层、文件规模和目录职责。
- [development/DEVELOPMENT-STANDARD.md](development/DEVELOPMENT-STANDARD.md)：后端、前端、配置、依赖和兼容性要求。
- [development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md](development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md)：前端六屏规划与骨架、物料、Token 三层契约约束。
- [development/COLLABORATION-STANDARD.md](development/COLLABORATION-STANDARD.md)：人类和编码 Agent 的接手、协作与交付要求。
- [development/TESTING-STANDARD.md](development/TESTING-STANDARD.md)：变更类型、最低验证和生产验收矩阵。
- [development/DOCUMENTATION-STANDARD.md](development/DOCUMENTATION-STANDARD.md)：文档分类、格式、事实更新和历史保全要求。
- [development/DOCUMENTATION-LIFECYCLE.md](development/DOCUMENTATION-LIFECYCLE.md)：活/死分类、当前切片、ADR、CHANGELOG 与保全闸门。
- [decisions/](decisions/)：架构决策记录（ADR），编号只增、正文只增不减。
- [development/DATA-AND-SECURITY-STANDARD.md](development/DATA-AND-SECURITY-STANDARD.md)：数据、数据库、凭据、远端和恢复边界。
- [development/SECRETS-AND-CONFIG.md](development/SECRETS-AND-CONFIG.md)：运行时配置、GitHub Secrets 与敏感信息净化。
- [development/SECRET-SCAN-HOOK-DESIGN.md](development/SECRET-SCAN-HOOK-DESIGN.md)：凭据扫描和提交信息闸门实现。
- [development/SANITIZATION-RULES.md](development/SANITIZATION-RULES.md)：历史资料脱敏规则与版本化保全标准。
- [development/CLI-SCRIPT-POLICY.md](development/CLI-SCRIPT-POLICY.md)：各 CLI 专属脚本目录制度。
- [development/LIVE-PROJECTION.md](development/LIVE-PROJECTION.md)：驾驶舱只读实时投影的数据流与边界。
- [development/BUSINESS-SIMULATION-ENGINE.md](development/BUSINESS-SIMULATION-ENGINE.md)：业务驱动拟真引擎设计规范。
- [development/SIMULATION-PIPELINE-SPEC.md](development/SIMULATION-PIPELINE-SPEC.md)：全生命周期批次工序、储备池与因果约束。
- [development/SIMULATION-DIURNAL-SPEC.md](development/SIMULATION-DIURNAL-SPEC.md)：AI 业务语义、作息节律、体量二八定律与自愈闭环。
- [development/DASHBOARD-REFRESH-MECHANISM.md](development/DASHBOARD-REFRESH-MECHANISM.md)：动态刷新与无刷新轮询机制。
- [development/ML-AI-DATA-BOUNDARY.md](development/ML-AI-DATA-BOUNDARY.md)：AutoML/Cloudflare AI 最小数据边界与授权清单。
- [development/HEATWAVE-AUTOML-CAPABILITIES.md](development/HEATWAVE-AUTOML-CAPABILITIES.md)：HeatWave AutoML 能力与边界手册。
- [development/HEATWAVE-USAGE-AND-BOUNDARIES.md](development/HEATWAVE-USAGE-AND-BOUNDARIES.md)：HeatWave 当前使用现状、免费边界和运维建议。
- [development/CAPACITY-ESTIMATION.md](development/CAPACITY-ESTIMATION.md)：容量评估工具说明。
- [development/GOVERNANCE-AND-COLLABORATION.md](development/GOVERNANCE-AND-COLLABORATION.md)：协作机制与文档治理架构阐释。
- [development/CLOUDFLARE-BROWSER-RENDERING.md](development/CLOUDFLARE-BROWSER-RENDERING.md)：Cloudflare Browser Rendering 测试与使用边界。
- [development/DUAL-RUN-DEFINITION.md](development/DUAL-RUN-DEFINITION.md)：双轨运行的业务定义、进入与退出条件。
- [development/GOVERNANCE-SIMULATION-SYNTHESIS.md](development/GOVERNANCE-SIMULATION-SYNTHESIS.md)：合规治理因果模拟与动态自愈生态系统架构演进总纲。

## 需求与设计

下列编号文档均是阶段性或历史资料，除非 `CURRENT-STATE.md` 明确引用，否则不构成当前操作指令。

> 说明：以下历史过程文档因可能含遗留真实主机/OCID 等信息，按 `.gitignore` 仅保留在本地、不发布到仓库，
> 故此处只列名不设链接。

- 01-产品与业务设计-待确认.md
- 02-数据模型-待确认.md
- 03-技术架构与实施计划.md
- 08-模拟数据V2生成与验收规范-待最终确认.md

## V1 与组件路线历史

- 04-阶段1精确变更清单-待批准.md
- 05-USA数据库执行清单-待批准.md
- 06-组件化实施基线.md
- 07-当前部署与运维基线.md

本节全部是历史路线材料，不能覆盖 `CURRENT-STATE.md`。DataEase、NocoDB、Docker 和历史 Cloudflare
Worker 均已退出当前运行架构。

## V2 生成、整改与封版

- 09-V2模拟数据生成实施任务书.md
- 10-V2模拟数据第一轮审阅报告.md
- 11-V2模拟数据第二轮执行与整改报告.md
- 12-V2模拟数据第三轮执行与整改报告.md
- 13-V2模拟数据第四轮执行与整改报告.md
- 14-V2模拟数据第五轮执行与整改报告.md
- 15-V2模拟数据第六轮执行与整改报告.md
- 16-V2模拟数据指标口径修正与基准最终冻结声明.md

## V2 数据库导入与验收

- 17-V2独立数据库导入方案与前置检查清单.md
- 18-V2数据库导入前只读环境核查报告.md
- 19-V2数据库导入执行与验收报告.md
- 20-V2数据库独立复审与账号整改报告.md
- 21-V2数据与项目目录现状基线.md
- 22-项目目录集中整理记录.md
- [23-V2六屏驾驶舱页面区域与布局规范.md](history/23-V2六屏驾驶舱页面区域与布局规范.md)

上述 V2 文档记录冻结、导入和验收时点的历史事实。当前数据库与运行状态仍以
`CURRENT-STATE.md` 和只读核验结果为准。

## 任务、运维与证据

- `archive/legacy-collaboration/`：已归档的停用协作状态机（调度器、agent 定义、任务与交接记录）；
  只读历史，不恢复、不运行、不维护。
- [历史数据库整改提示词](history/MOD-V2数据库整改执行提示词.txt)：已移入历史，禁止再次执行。
- [operations/README.md](operations/README.md)：运维文档状态与执行边界。
- [MOD-USA-手工配置与验收清单.txt](operations/MOD-USA-手工配置与验收清单.txt)：历史 DataEase/NocoDB 手工清单，已停用，禁止执行。
- [USA-DIRECTORY-MAINTENANCE-20260902.md](operations/USA-DIRECTORY-MAINTENANCE-20260902.md)：USA 目录整理、防索引与遗留运行风险记录。
- [USA-DEPLOYMENT-LAYOUT.md](operations/USA-DEPLOYMENT-LAYOUT.md)：迁移前部署目录规则，已失效，仅用于历史追溯。
- [HARNESS-REFACTOR-20260911.md](operations/HARNESS-REFACTOR-20260911.md)：记录本地 Harness 脚手架代码剥离与历史包袱归档。
- [NATIVE-CLIENT-CONFIG-20260911.md](operations/NATIVE-CLIENT-CONFIG-20260911.md)：记录本机各原生 AI Agent 客户端对 local-harness 的强制纪律接入。
- [DISASTER-RECOVERY-RUNBOOK.md](runbooks/DISASTER-RECOVERY-RUNBOOK.md)：灾难恢复与数据还原标准操作手册。
- [evidence/README.md](evidence/README.md)：脱敏验收证据的保存与使用边界。

## 编号说明

历史文档不因目录整理而重编号或删除。存在两个 `10-` 编号文档（现位于 `history/`），其中 `history/10-V2后续实施移交清单_给下一位AI的Prompt.md` 是历史交接提示词，不能替代当前任务书。

新增的脱敏历史治理快照：[2026-09-08 CHANGELOG 机制治理前快照](history/2026-09-08-CHANGELOG机制治理前快照.md)、
[2026-09-08 本地质量基线更新前快照](history/2026-09-08-本地质量基线更新前快照.md)、
2026-09-09 KI-070~074 治理前现状切片（本地存档，含敏感信息，不纳入版本库）。

- [KI-080 · AI 输出可信度与能力边界失真](issues/KI-080-AI-OUTPUT-TRUST.md)：本地修复与验收记录。

- [实时投影 outbox 切换与恢复步骤](operations/PROJECTION-OUTBOX-MIGRATION.md)：KI-081 待执行的 schema、权限和生产验收。
