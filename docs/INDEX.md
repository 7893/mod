# MOD 文档索引

更新日期：2026-09-02
状态：现行索引
适用范围：当前规范、项目资料、历史基线、运维记录与证据入口

## 当前必读

1. `../AGENTS.md`：仓库硬约束与事实优先级。
2. `../ENFORCEMENT.md`：红线在动作点的强制执行方式（闸门，而非仅须知）。
3. `../CONTRIBUTING.md`：接手、开发、验证、文档和提交流程。
4. `CURRENT-STATE.md`：当前运行、数据、质量与操作边界的唯一事实入口。
5. `../PROJECT-LAYOUT.md`：JPA 与 USA 的目录和主机边界。
6. `KNOWN-ISSUES.md`：已发现但未修复的业务、数据、系统与清理类问题登记册。

## 现行维护规范

- `development/PROJECT-ORGANIZATION.md`：源码分层、文件规模和目录职责。
- `development/DEVELOPMENT-STANDARD.md`：后端、前端、配置、依赖和兼容性要求。
- `development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md`：前端六屏规划与骨架、物料、Token 三层契约约束。
- `development/COLLABORATION-STANDARD.md`：人类和编码 Agent 的接手、协作与交付要求。
- `development/TESTING-STANDARD.md`：变更类型、最低验证和生产验收矩阵。
- `development/DOCUMENTATION-STANDARD.md`：文档分类、格式、事实更新和安全要求。
- `development/DOCUMENTATION-LIFECYCLE.md`：文档生命周期与组织规范（活/死分类、ADR、CHANGELOG、强制同步）。
- `decisions/`：架构决策记录（ADR），编号只增、只记不改、可考证决策理由。
- `development/DATA-AND-SECURITY-STANDARD.md`：数据、数据库、凭据、远端和恢复边界。
- `development/SECRETS-AND-CONFIG.md`：运行时 .env、CI/CD GitHub Secrets 与公开前敏感信息净化。
- `development/SECRET-SCAN-HOOK-DESIGN.md`：本地与 CI 凭据扫描、提交信息闸门的现行实现说明。
- `development/CLI-SCRIPT-POLICY.md`：各 CLI 专属脚本目录制度。
- `development/LIVE-PROJECTION.md`：驾驶舱只读实时投影的数据流、边界与增长约束。
- `development/BUSINESS-SIMULATION-ENGINE.md`：业务驱动拟真引擎设计规范（设计草案，尚未实现）。
- `27-全生命周期批次工序推进与全要素动态模拟业务规范.md`：全生命周期8批次工序流水线、第八批未启动储备池与全要素因果约束。
- `28-AI驱动的高仿真业务模拟与时钟节律实施规范.md`：AI赋能的真实业务语义、香港时区作息突发、体量二八定律与异常自愈闭环。
- `operations/USA-DEPLOYMENT-LAYOUT.md`：USA 纯部署目录白名单与验收要求。

## 需求与设计

下列编号文档均是阶段性或历史资料，除非 `CURRENT-STATE.md` 明确引用，否则不构成当前操作指令。

- `history/01-产品与业务设计-待确认.md`
- `history/02-数据模型-待确认.md`
- `history/03-技术架构与实施计划.md`
- `history/08-模拟数据V2生成与验收规范-待最终确认.md`

## V1 与组件路线历史

- `history/04-阶段1精确变更清单-待批准.md`
- `history/05-USA数据库执行清单-待批准.md`
- `history/06-组件化实施基线.md`
- `history/07-当前部署与运维基线.md`

本节全部是历史路线材料，不能覆盖 `CURRENT-STATE.md`。DataEase、NocoDB、Docker 和历史 Cloudflare
Worker 均已退出当前运行架构。

## V2 生成、整改与封版

- `history/09-V2模拟数据生成实施任务书.md`
- `history/10-V2模拟数据第一轮审阅报告.md`
- `history/11-V2模拟数据第二轮执行与整改报告.md`
- `history/12-V2模拟数据第三轮执行与整改报告.md`
- `history/13-V2模拟数据第四轮执行与整改报告.md`
- `history/14-V2模拟数据第五轮执行与整改报告.md`
- `history/15-V2模拟数据第六轮执行与整改报告.md`
- `history/16-V2模拟数据指标口径修正与基准最终冻结声明.md`

## V2 数据库导入与验收

- `history/17-V2独立数据库导入方案与前置检查清单.md`
- `history/18-V2数据库导入前只读环境核查报告.md`
- `history/19-V2数据库导入执行与验收报告.md`
- `history/20-V2数据库独立复审与账号整改报告.md`

上述 V2 文档记录冻结、导入和验收时点的历史事实。当前数据库与运行状态仍以
`CURRENT-STATE.md` 和只读核验结果为准。

## 任务、运维与证据

- `../archive/legacy-collaboration/`：已归档的停用协作状态机（调度器、agent 定义、任务与交接记录）；
  只读历史，不恢复、不运行、不维护。
- `tasks/README.md`：任务书目录规则；任务书本身不等于执行授权。
- `tasks/MOD-V2数据库整改执行提示词.txt`：已完成的历史整改提示词，禁止再次执行。
- `operations/MOD-USA-手工配置与验收清单.txt`：历史 DataEase/NocoDB 手工清单，已停用，禁止执行。
- `operations/USA-DIRECTORY-MAINTENANCE-20260902.md`：USA 目录整理、防索引与遗留运行风险记录。
- `operations/USA-DEPLOYMENT-LAYOUT.md`：USA 纯部署目录允许项和部署后验收要求。
- `evidence/`：仅保存脱敏的原始验收输出。

## 编号说明

历史文档不因目录整理而重编号或删除。存在两个 `10-` 编号文档（现位于 `history/`），其中 `history/10-V2后续实施移交清单_给下一位AI的Prompt.md` 是历史交接提示词，不能替代当前任务书。
