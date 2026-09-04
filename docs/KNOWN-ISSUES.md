# 已知问题登记册

更新日期：2026-09-04
状态：现行
适用范围：已发现但尚未修复的业务、数据、系统与清理类问题

本文只登记问题，不作为执行授权。修复任一条目前需按 `ENFORCEMENT.md` 与
`docs/development/DATA-AND-SECURITY-STANDARD.md` 确认范围、只读核查、备份与授权。
体制类改进（约束、规范、文档、组织、流程）不在本文，另行推进。

条目状态取值：OPEN（待处理）、IN-PROGRESS（处理中）、DONE（已完成，保留供追溯）。

---

## 数据正确性

### KI-001 · 省级今日新增恒为 0，与总览不一致
- 状态：DONE（2026-09-04，本地已修复，尚未部署）
- 现象：驾驶舱省级 `todayAdded` 求和为 0，但总览 `docsTodayAdded` 为非零值（如 805），二者对不上。
- 根源：`backend/app/services/dashboard_v2.py` 省级 SQL 中 `0 AS todayAdded` 为未实现的占位值；
  总览 `docs_today_added` 取自 `daily_stats.doc_today` 的真实值。
- 影响：省级下钻的“今日新增”是假数据；R3 一致性契约无法成立。
- 原证据：`backend/tests/test_v2_api.py::test_v2_snapshot_internal_consistency_contract`（修复前为 `xfail`）。
- 处理：在线查询按最近完整业务日聚合单位单据并汇总到省级，总览新增量由同一省级结果求和；
  fallback 已从冻结 V2 资产只读重建，R3 一致性测试转为强制通过。

### KI-002 · 单据发生日期与快照基线日期塌缩为同一天
- 状态：DONE（2026-09-04，本地已修复，尚未部署）
- 现象：`docsAddedAsOfDate` 与 `asOfDate` 相等（均为 2026-09-03），R6 契约（二者应不同）不再成立。
- 根源：`dashboard_v2.py` overview SQL 中 `docs_as_of_date = ds.stat_date`、`as_of_date = :anchor_date`，
  且 `WHERE ds.stat_date = :anchor_date` 强制二者相等；R6 契约原本依赖“单据日期比基线日期早一天”的脆弱假设。
- 影响：R6“单据发生日期 vs 快照基线日期”区分失效。
- 原证据：同 KI-001 的一致性测试（修复前为 `xfail`）。
- 处理：保留 R6 契约；单据新增口径改为快照日前最近完整业务日，快照基线继续来自
  `daily_stats.stat_date`，两者由独立数据源派生且测试强制区分。

### KI-003 · fallback 快照文件由缺陷 SQL 生成，内含上述不一致
- 状态：DONE（2026-09-04，本地已修复，尚未部署）
- 现象：`frontend/src/data/v2-sim-snapshot.json` 静态快照曾携带 KI-001、KI-002 的不一致。
- 根源：该快照是某次用当前在线 SQL 逻辑 dump 生成的产物。
- 影响：本地/离线 fallback 展示沿用了同样的错误。
- 处理：修复 KI-001、KI-002 后，使用 `tools/v2/build_v2_snapshot.py` 从冻结 V2 资产只读重建
  `frontend/src/data/v2-sim-snapshot.json`；省级新增合计与总览一致，单据发生日与快照基线日保持区分，
  对应 `xfail` 已移除。

## 数据规模与文档漂移

### KI-004 · 生产库行数与文档记载不符
- 状态：OPEN
- 现象：`docs/CURRENT-STATE.md` 记载约 3183 万行、docs/23 记载 168 万行等，均与实际不符；
  2026-09-03 的一次授权删除后，实际约 1800 万行（见 KI-005）。
- 影响：文档作为 AI 的事实来源，过时数字会误导后续判断。
- 待处理：将数据规模类事实改为由只读查询实时派生，减少手写数字；同步订正 CURRENT-STATE 当前口径。

### KI-005 · 未上线单位历史单据已被物理删除，约 1500 万行，无恢复副本
- 状态：OPEN（已发生，记录在案）
- 现象：2026-09-03 经用户授权执行删除脚本，清除第 7、8 批等未上线单位的历史单据与凭证。
  business_document 约 488 万→231 万等，合计约删除 1500 万行，`daily_stats` 汇总被同步改写。
- 说明：删除本身为授权操作；此处登记的是“无备份/恢复副本、且 CURRENT-STATE 未同步更新”这一执行层缺口。
- 相关脚本已归档至 `archive/legacy-db-scripts/clean_unlaunched_org_data.py`（不再运行）。
- 待处理：确认是否需要恢复方案；核对删除后各表实际行数并订正 CURRENT-STATE。

## 生产运行与配置

### KI-006 · USA 生产 Cloudflare AI 开关与文档口径不一致
- 状态：OPEN
- 现象：USA `.env.systemd` 中 `MOD_CF_AI_ENABLED=true`，而 `CURRENT-STATE.md` 表述为“默认未启用”。
- 影响：文档与实际运行配置不符。
- 待处理：确认生产实际策略，统一文档与配置口径。

### KI-007 · 本地已修复内容尚未部署到 USA
- 状态：IN-PROGRESS（前端已全自动 CD，后端待评估）
- 进展（2026-09-04）：前端到 USA 已由 CI/CD 流水线全自动部署（push main → CI 通过 →
  `deploy.yml` 自动构建并 rsync 前端 dist，部署前自动备份）。前端修复自动上线，不再需要手动部署。
- 待处理：后端侧修复（时区统一、区域一致性 SQL、快照口径等）未纳入自动化部署；
  是否需要同步到 USA 后端、以何种方式（受 ENFORCEMENT 后端变更授权约束），待评估。

## 前端与构建

### KI-008 · 前端全六屏旧 CSS 全部清零，全面契约化完成
- 状态：DONE（2026-09-04）
- 现象：A–F 全六屏已全量完成 Tailwind + CockpitPanel + 集中 Token 迁移；各屏专属旧 CSS 全部物理清零。
- 依据：`docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 迁移现状章节。
- 处理进展：
  - 2026-09-04 完成 C 屏（推广上线 RolloutView.vue）迁移，物理删除 `rollout.css`（404 行），
    中部三栏沉淀 Token `--grid-template-columns-rollout-mid`，通过 `make check` 与 1920x1080 视觉验收（Commit `eb8212a`）。
  - 2026-09-04 完成 D 屏（业务运营 OperationsView.vue）迁移，物理删除 `operations.css`（295 行），
    网格沉淀 Token `--grid-template-columns-operations` / `--grid-template-rows-operations`，通过 `make check` 与 1920x1080 视觉验收（Commit `c88e66b`）。
  - 2026-09-04 完成 E 屏（问题清单 IssuesView.vue）迁移，物理删除 `issues.css`（97 行），
    顶部栏沉淀 Token `--grid-template-columns-issues-top`，通过 `make check` 与 1920x1080 视觉验收；同步修复 KI-018 中 RolloutView 残留的 `text-[10px]`（Commit `3640b27`）。
  - 2026-09-04 完成 F 屏（智能研判 InsightsView.vue）迁移，物理删除 `insights.css`（380 行），
    网格沉淀 Token `--grid-template-columns-insights` / `--grid-template-rows-insights`，重构 `ModelContractCard.vue` 契约化，通过 `make check` 与 1920x1080 视觉验收。全站存量专属旧 CSS 正式清零归零。
- 处理结论：六屏旧 CSS 清理与 CockpitPanel 迁移全面闭环。

### KI-009 · 前端构建存在超过 500kB 的 chunk 警告
- 状态：OPEN
- 现象：`pnpm build` 提示 DashboardView、theme、index 等 chunk 超过 500kB（非阻断）。
- 待处理：按需做动态 import 代码分割或 manualChunks 优化。

## 代码清理

### KI-010 · database/、generator/ 内无凭据的废弃文件待清理
- 状态：OPEN
- 现象：`database/`（如 generate/verify 之外的历史脚本）与 `generator/v2/`（generate_v2、dictionary、
  config、test 等）仍留有不再使用的历史文件；本次仅归档了含明文凭据的 8 个脚本。
- 说明：这些文件不含凭据，不属于“泄漏清理”范围，故未在本轮处理。
- 待处理：逐个确认去留，废弃者移入 `archive/`（回收站）；同步 `AGENTS.md` 中 database/generator 的
  grandfather 描述，消除“规则称保留、实际已废弃”的漂移。

### KI-011 · 历史明文凭据仍存在于 archive 内容与 Git 历史中
- 状态：OPEN（按当前决策接受）
- 现象：明文口令仍存在于 `archive/legacy-db-scripts/` 文件与 Git 历史提交中。
- 说明：按用户决策，此为实验性、不公开项目，密码不更换，上生产将更换数据库，故接受现状；
  归档已使其退出活跃代码路径与 pre-commit 扫描范围。
- 待处理（可选）：若未来需要彻底抹除，需重写 Git 历史（如 git filter-repo），属高风险操作，另行授权。

### KI-023 · AutoML 就绪状态与模型质量分带有硬编码兜底，可能展示未生成的结果
- 状态：OPEN
- 现象：`GET /api/v2/insights/status` 在 HeatWave 适配器报告 `ready` 时，无条件写入
  `automlStatusDisplay="已就绪"`、`trainingAuthorized=True` 与"实时提供日增单据与批次延期风险预测"文案；
  模型质量分通过 `reg_info.get("quality", 0.942)`、`cls_info.get("quality", 0.915)` 取值，
  适配器未返回真实质量时以硬编码默认值填充。
- 根源：`backend/app/api_v2.py` `insights_status` 中的展示字段与真实训练/评分结果未解耦，
  且使用了"以默认值形式提供事实"的写法。
- 影响：与 `docs/CURRENT-STATE.md`"训练/评分仍未完成""不应把未生成的预测展示为真实结果"直接冲突；
  在训练未完成时，前端仍会呈现具体的模型质量数字，观众无法分辨其真伪。
- 定性：这是展示层的事实伪造风险，与 `ENFORCEMENT.md` 闸门 A 反对的"以默认值形式落地不可信事实"同构，
  只是伪造对象由凭据变为模型质量；原则 5"派生优于手写"同样要求该数值只能来自真实评分结果。
- 待决策与待处理：
  - 移除 `quality`/`algorithm` 的硬编码兜底默认值；适配器未提供真实值时，字段应缺省或显式标记为未提供。
  - 就绪文案须由真实训练与评分状态派生；未完成训练时显式展示"未训练/未评分"，不得表述为"已就绪"。
  - 需补充覆盖"适配器 ready 但无质量数据"路径的测试，防止回归。

## 机制待补

### KI-012 · CI 侧闸门缺失（本地 hook 可被绕过）
- 状态：DONE（2026-09-04，已在公开仓库 GitHub Actions 生效并多次跑绿）
- 现象（原）：本地 pre-commit 可被 `git commit --no-verify` 绕过，仓库无 CI。
- 处理：`.github/workflows/quality.yml` 在 push/PR 触发，执行凭据扫描 + 提交信息校验 + `make check`，
  作为不可绕过的第二道；仓库已公开，CI 实际运行并通过。

### KI-013 · 声明式权限仅覆盖单一 CLI（绑定停用流程部分已消除）
- 状态：DONE（2026-09-04）
- 现象：原 `.kiro/agents/` 权限体系仅对 Kiro 会话生效，其他 CLI 会话无等效强制防护。
- 进展（2026-09-04）：绑定已停用协作状态机的整套 Kiro agent 定义已随调度器归档至
  `archive/legacy-collaboration/`，“绑定停用流程”这一子问题已消除。
- 处理：凭据、质量和提交信息规则已下沉到版本库 Git hooks，并由 CI 复用同一项目脚本；
  所有 CLI 经由 Git 提交时使用同一动作点闸门，远端检查负责拦截本地绕过。


## 公开发布准备

### KI-014 · 上 GitHub 公开仓库前的净化工程
- 状态：DONE（2026-09-04，已按路线 A 变体完成并公开）
- 完成方式：净化活跃区全部敏感值（IP/OCID/CF账号/密码/域名脱敏或改环境变量）；`archive/`、
  `database/`、`generator/`、`docs/history/`、真实 nginx conf 等经 `.gitignore` 排除；旧 `.git`
  历史打包备份至 `archive/`（本地留存），`git init` 重建干净历史；公开仓库 github.com/7893/mod，
  多轮全量机密扫描确认零泄露。
- 目标：将本仓库发布为 GitHub 公开仓库，并启用 GitHub Actions CI。
- 前提判断：当前**不具备**公开条件；版本库（含 Git 历史）存在多类敏感信息，直接公开会泄露。

**需要处理的三层敏感信息**（缺一层都不算净化完成）：

1. 源码配置值 —— 基本达标，仍需补全
   - 活跃 backend 已由环境变量驱动（USA 从 `.env.systemd` 读 `MOD_DB_HOST` 等）。
   - 待办：补全 `.env.example`，把数据库主机、账号、Cloudflare Account ID、域名等所有需要的
     变量名以占位符形式列全；确认活跃代码无遗漏的硬编码值。
2. 文档与注释中的明文敏感信息 —— 环境变量覆盖不到，须逐处脱敏改写
   - 内网 IP 内网数据库地址（脱敏）：出现在 `database/`、`generator/`、`docs/18`、`docs/tasks/` 等。
   - USA 公网 IP（如 `USA公网地址（脱敏）`）：出现在 `docs/18`、`docs/20` 及归档 benchmark。
   - OCI OCID（tenancy/user）：`docs/18` 等。
   - Cloudflare Account ID、真实域名（现行 生产域名（脱敏），历史 `历史域名（脱敏）`、`历史域名（脱敏）`）：
     `AGENTS.md`、`README.md`、`deploy/nginx/` 等。
   - 待办：将上述真实值改写为脱敏占位符或中性描述。
3. Git 历史中的敏感信息 —— 最易被忽略，公开后 `git log` 可翻出
   - 明文密码 管理员口令（脱敏）、上述 IP/OCID 均存在于历史提交中。
   - 两条路线（择一）：
     - 路线 A（推荐）：新建干净公开仓库，仅导入脱敏后的当前快照，不带历史。
     - 路线 B：对原仓库用 `git filter-repo` 清除历史敏感信息（高风险，重写全部提交哈希，需专门授权）。

**公开配套（净化完成后）：**
- 添加 `LICENSE`（当前缺失）。
- 添加 GitHub Actions workflow，在 CI 侧执行凭据扫描与 `make check`（同时解决 KI-012 的不可绕过第二道）。
- CI 仅做检查，不做部署：**不建议**在公开仓库配置到 USA 的 CD，避免把 SSH 私钥/服务器地址托管到 GitHub；
  部署继续手动或置于私有渠道。CI 使用 fallback 快照，不连生产数据库、不接触 USA。

- 建议：作为独立任务系统执行，不零敲碎打；执行前按 ENFORCEMENT 确认范围与授权。

**进展与净化前置（2026-09-04）**
- 已补全 `.env.example`（列全代码实际读取的全部变量，占位/空值，无真实值）。
- 已新增 `docs/development/SECRETS-AND-CONFIG.md` 规范（.env / GitHub Secrets / 公开净化）。
- 只读扫描的敏感信息清单（活跃区需处理，归档/历史区另议）：
  - 内网 IP 内网数据库地址（脱敏）：活跃文件 `database/verify_mod_s_v2_readonly.py`、`generator/v2/generate_v3.py`、
    `docs/tasks/*`；历史区 `docs/history/18`。
  - Cloudflare Account ID：活跃文件 `scripts/claude/shoot.sh`、`workers/mod-browser/src/index.ts`。
  - OCI OCID：仅 `docs/history/18`（历史区）。
  - 明文密码：集中在 `archive/legacy-db-scripts/*`（归档区）与 `docs/KNOWN-ISSUES.md`（问题描述引用）。
  - 真实域名 生产域名（脱敏）：多处（本就对外的站点域名，按需判断是否脱敏）。
- 路线选择：用户倾向路线 B（清洗历史）。分析意见：B 为高危不可逆操作（重写全历史、可能使既有
  签名失效、与 USA git 及并发工作冲突），性价比低；推荐路线 A（新仓库、当前净化状态为起点、不带历史）
  同样避免自建 HTML 且风险极低。最终路线待用户确认；无论 A/B 均须先完成上述活跃区脱敏前置。
- GitHub 公开后可直接使用其 Actions（CI 已就绪）与仓库 Secrets 管理机密。



## AI/ML 结果可信度

### KI-015 · risk_flag 分类模型在训练集上自评分，准确率不可信
- 状态：OPEN
- 现象：`ml_score_risk` 全部 2000 行预测与真实 `risk_flag` 完全一致（match 100%），
  `ml_results` 概率非 0 即 1（如 `{"probabilities":{"0":0.0,"1":1.0}}`），无正常概率分布。
- 只读核查（2026-09-04）：
  - `ml_score_risk` 与 `ml_feat_risk` 是同一批 2000 个 org（overlap=2000）——即在训练集上评分。
  - 非单特征硬泄漏：无任一特征与标签完全共线；risk_flag=1 组的 `unresolved_issues`(4.8 vs 2.0)、
    `high_risk_issues`(1.43 vs 0.51) 明显高于 =0 组，其余特征两组接近。
  - 数据高度可分 + 训练集自评分共同导致 100% 假象；真实泛化准确率未知。
- 影响：该风险模型当前无泛化验证，100% 准确率是假象，不得作为“AI 预测能力”对外展示或用于决策。
- 对比：回归模型 `ml_score_doc_delta` 表现正常（MAE≈2.22，均值≈6.06，预测为有误差的连续值），可信度较高。
- 待处理：对 risk_flag 做 train/test split（或交叉验证）后重新训练与评估，得到真实准确率；
  在展示层区分“模型已训练”与“模型已验证”，未经独立验证的指标不得展示为真实预测结果
  （呼应 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 的“不得把未生成/未验证预测展示为真实结果”）。
- 依据约束：HeatWave AutoML 免费、无调用次数限制、单节点串行、目标列非 TEXT、文本特征仅英文、
  训练账号名不得含点号（`.`）；重训练须在这些边界内、以离线批处理方式进行。


### KI-016 · 提交信息格式无机制校验
- 状态：DONE（2026-09-04）
- 现象：pre-commit 闸门只校验代码内容（凭据扫描 + make check），不校验 commit message 格式；
  不符合 `AGENTS.md` 提交约定的信息可以通过。实例：`77f5e5a "Fix regional snapshot consistency"`
  （应为英文小写、带 type 前缀、不超过 7 词，如 `fix: derive regional document additions`）。
- 影响：提交历史风格不一致；提交规范停留在“须知”，未成“闸门”。
- 依据约定：`AGENTS.md` Git 节——英文、不超过 7 词、单一意图；`git commit -S` 签名。
- 处理：新增 `.githooks/commit-msg` 与共享 `scripts/project/validate_commit_message.py`，校验英文小写
  Conventional Commit type 和七词上限；CI 对提交范围执行同一规则。


## 存量数据合规治理

### KI-017 · 存量数据清洗与主数据重整（处置三：清洗后由新引擎接管）
- 状态：OPEN（高优先级）
- 背景：老模拟器已停用（USA 未配置 `MOD_SIMULATOR_ENABLED`/`MOD_DB_WRITE_URL`，数据不再增长）。
  经 2026-09-04 只读体检，存量数据在“硬自洽”上通过，但在“格式整洁”与“分布真实感”上不达标，
  不完全符合 `docs/development/BUSINESS-SIMULATION-ENGINE.md` 的自洽要求。
- 处置方向（已定）：**处置三——清洗现有脏数据，之后由新业务拟真引擎在干净基础上只增接管**；
  不整体推倒（库内均为模拟数据，但无需清空重来）。

**A. 已通过的检查（无需处理，仅记录基线）**
- 因果门禁：未上线单位无业务单据。
- 勾稽：凭证数 ≤ 单据数；关联链无断链；凭证借贷平衡（抽样）。
- 主数据引用完整性：抽样 5000 笔单据经办人 100% 命中该单位人员表。
- 主数据无孤岛：每个单位均有人员与建设任务；总量比例合理（约 7.8 人/单位、30 任务/单位）。

**B. 交易数据问题（需清洗）**
1. 时间逆序：约 344,898 笔 `business_document` 的 `approve_time` 早于 `submit_time`（时间倒流）。
2. 状态值污染：约 1,959,347 条“处理完成”状态尾部含隐藏回车符 `\r`（CRLF 导入污染），
   与干净值分裂为两个状态，破坏按状态过滤/统计。
3. 孤儿凭证：11,144 个凭证无 `document_voucher_link` 关联单据（待决策：判定为合理手工凭证保留，或脏数据清理）。

**C. 主数据问题（分布真实感缺失，需重整）**
1. 人员角色单一：全部 15,613 人角色均为“关键用户”，缺少财务总监/项目经理/经办人/普通用户分化。
2. 人员数不随体量：单据量最大的单位与普通单位人员数同为 12，人员数与业务体量零相关。
3. 人员数区间过窄：各单位 6–12 人，缺乏按体量分层（无大型多人单位、无微型单位）。

**D. AutoML 合规（另见 KI-015）**
- 规模、NULL、目标列类型合规；`region` 为中文，训练时不得作文本特征（需排除或编码）；
  训练写账号名须确认不含点号（`.`）。
- risk_flag 模型曾在训练集上自评分（KI-015），数据清洗后须以 train/test split 重训验证。

**待你决策的点**
- 孤儿凭证：保留（视为手工/期初凭证）还是清理？
- 主数据重整力度：仅补角色 + 拉开人员数分层，还是连联系人覆盖率、经办人引用一并重算？
- 时间逆序修正口径：`approve_time` 重设为 `submit_time` 之后的合理时间。

**依赖与顺序**
- 主数据重整会改变人员数量，连带影响经办人引用、联系人覆盖率、培训人次等，须成套调整并复查引用完整性。
- 交易数据清洗（B）相对独立，可先行。
- 清洗完成后：更新 `docs/CURRENT-STATE.md`、重建 fallback 快照、重训 AutoML（KI-015）、
  再由新引擎接管只增运行。

**安全闸门（强制，受 ENFORCEMENT 闸门 B 约束）**
- 本条目涉及大规模数据库写操作（UPDATE 百万级行），执行前必须：显式授权、只读核查确认精确范围、
  建立并校验恢复副本（导出待改表，OCI Always Free 无 PITR）、先 dry-run 打印影响行数、分批事务执行、
  改后复查问题清零且未引入新矛盾。禁止无核查的整表 UPDATE。


### KI-018 · 前端契约缺自动校验（Tailwind 任意值漏网）
- 状态：IN-PROGRESS（边界已定义，自动 lint 待做）
- 现象：`FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 契约三禁止脱离 Token 的任意值
  （如 `text-[10px]`、`bg-[#xxxxxx]`），但当前闸门（`make check` 的 typecheck/build）无法识别这类违规——
  语法合法、可正常构建，因此靠人工 review 才能发现。
- 实例：`eb8212a`（rollout 迁移）残留 1 处 `text-[10px]`，应为 `text-cockpit-xs`。
- 影响：前端契约停留在“须知 + 人工 review”，未成“闸门”；迁移过程中易漏网，长期累积会重新滋生散写样式。
- 待处理：
  1. [已修复 2026-09-04] `RolloutView.vue` 残留的 `text-[10px]` → `text-cockpit-xs`。
  2. 增加前端契约的自动校验（lint 规则），在 `frontend/` 源码中禁止 Tailwind arbitrary value
     语法（`-[...]`）用于字号/颜色/间距等已有 Token 的维度；纳入 `make check` 与 CI。
     允许合理例外（如确无对应 Token 且已在 `theme.css` 说明的），通过显式豁免而非默认放行。
     （注：arbitrary value 的允许/禁止边界已在 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 及 KI-022 中明确规范界定）
- 关联：`KI-008`（B–F 屏迁移）迁移每屏时应受此校验约束，避免边迁边引入新任意值。


## 文档治理

### KI-019 · 文档组织治理（历史归拢 + 编号 + issue 分级 + 立规）
- 状态：IN-PROGRESS（任务一与层次四已完成，任务二待做）
- 进展（2026-09-04）：
  - 层次1+2（历史归拢）已完成：22+ 个历史文档移入 `docs/history/`，修复 INDEX/README 引用，无死链（提交 c23bba1）。
  - 层次4（立规）已完成：新增 `docs/development/DOCUMENTATION-LIFECYCLE.md`（活/死分类、ADR、CHANGELOG、
    强制同步）；建立 `docs/decisions/` ADR 目录与模板，补记 ADR-0001~0004。
  - 衍生登记：CHANGELOG（KI-020）、文档在线发布（KI-021）。
  - 任务二（KNOWN-ISSUES 拆为看板 + 独立文档）待做，需挑无并发编辑时机。
- 背景：`docs/` 顶层现有 28 个编号文档（01–28）与现行文档（CURRENT-STATE、INDEX、KNOWN-ISSUES）混放，
  现行/历史难以区分；编号为流水账式且存在重复（两个 `10-`）；KNOWN-ISSUES 单文件已含 19 条、275+ 行。
  多数编号文档头部已自报“历史/已执行/已取代”，语义上已是历史，仅物理位置未跟上。

**A. 01–28 现行/历史判定（2026-09-04 只读核查）**
- 纯历史（可归档，保留原编号原名）：01、02、03、04、05、06、07、08、09、10（两个）、
  11、12、13、14、15、16、17、18、19、20、21、22。共约 22 个，多数自报“已执行/已取代/历史基线”。
- 仍现行（不归档）：24（动态刷新机制）、25（AutoML/CF-AI 数据边界）、26（容量评估工具）、
  27（全生命周期批次工序，现行基线）、28（AI 高仿真模拟规范，现行，拟真引擎依据）。
- 半现行（谨慎）：23（六屏布局，结构现行、旧 CSS 已废、已加历史通知头，且被现行前端契约引用，勿乱动）。

**B. 四层整理思路**
1. 物理归拢：新建 `docs/history/`，将纯历史文档 `git mv` 进入（保留原编号原名）；
   现行文档（24–28）挪入 `docs/development/` 对应主题或留顶层；顶层只保留现行三大件与分类子目录。
2. 编号治理：历史文档保留原编号（避免破坏历史引用）；现行文档改用语义文件名，不用数字流水号；
   重复的 `10-` 归入 history/ 后自然隔离。
3. issue 分级：`KNOWN-ISSUES.md` 保留为“看板”（每条一行：编号+标题+状态+优先级）；
   大型 issue（如 KI-017）拆到 `docs/issues/KI-<n>-<slug>.md` 独立文档；小 issue 留看板。
4. 立规防复发：补充文档组织与生命周期规范（并入或旁挂 `DOCUMENTATION-STANDARD.md`）：
   现行/历史划分、放置位置、命名规则、issue 组织方式。

**C. 执行拆分（避免与并发文档编辑冲突）**
- 任务一（先做，相对独立）：层次 1+2+4——历史归拢、现行归位、立规。一次性 `git mv` + 改引用。
- 任务二（后做，挑无人编辑时机）：层次 3——KNOWN-ISSUES 拆分。该文件被多 AI 高频读写，单独择时。

**安全注意**
- 大量 `git mv` 后，须同步修正所有引用旧路径的现行文档（INDEX、CURRENT-STATE、交叉引用），
  改完以 `grep` 复查无死链（参照归档 collaboration 的做法）。
- 归档不等于删除；历史文档只移位置、不改内容，保留可追溯。
- 动 KNOWN-ISSUES 结构前先确认工作树无他人未提交改动。


### KI-020 · 自动生成 CHANGELOG
- 状态：DONE（2026-09-04，方案 C：工具+规范就位，发版手动生成）
- 背景：已具备 Conventional Commits 规范与 commit-msg 闸门，但尚无 CHANGELOG，变更历史只能靠 `git log`。
- 处理：引入 git-cliff（配置 `cliff.toml`），从 tag `v0.1.0` 起计；生成初始 `CHANGELOG.md`；
  发版生成方式写入 `DOCUMENTATION-LIFECYCLE.md` 第四节。工具以二进制临时运行，不装入本地环境、不进依赖树。
- 未采用 CI 全自动：避免写权限与自动提交复杂度；未来需要时可另建独立 workflow。

### KI-021 · 文档在线可视化发布（供离线审阅与反馈）
- 状态：DONE（方案调整：改由 GitHub 原生 Markdown 预览解决，无需自建 HTML 站）
- 背景：负责人需在线审阅文档并反馈。
- 结论：公开到 GitHub 后，其原生 Markdown 渲染 + 目录 + 搜索 + 历史 + 评论/PR 即满足在线审阅与反馈，
  无需自建 MkDocs/HTML 站，也不碰生产 USA。原“自建文档站”方案作废。
- 前置：依赖 KI-014（仓库公开前的敏感信息净化）。


### KI-022 · 前端迁移收尾小修
- 状态：DONE（2026-09-04）
- 背景：六屏 CockpitPanel 迁移完成并已部署验收，遗留两处小项，现已全面修复闭环。
- 处理结果：
  1. **DataView 统一迁移与旧组件清零**：`frontend/src/views/DataView.vue` 全面改用 `CockpitPanel` + `MetricGrid` + 纯 Tailwind，全站组件范式彻底统一；旧存量组件 `frontend/src/components/Panel.vue` 已彻底物理删除。
  2. **Arbitrary value 治理与边界落定**：`OperationsView.vue` 中散写的 `grid-cols-[100px_1fr_80px]` 沉淀入 `theme.css`（`--grid-template-columns-ops-volume`），`min-w-[180px]` 规范化为标准 `min-w-44`；并在 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 契约三中正式明确 arbitrary value 的允许/禁止边界（禁止用于字号、颜色、间距；受控允许图表/弹性容器的防塌陷物理上下界 guardrails）。
- 关联：KI-008（六屏迁移，已全量完成）、KI-018（前端契约自动校验）。
