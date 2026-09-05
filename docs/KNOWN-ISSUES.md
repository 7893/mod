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
- 状态：DONE（2026-09-04）
- 现象：`docs/CURRENT-STATE.md` 记载约 3183 万行、docs/23 记载 168 万行等，均与实际不符；
  2026-09-03 的一次授权删除后，实际约 1800 万行（见 KI-005）。
- 影响：文档作为 AI 的事实来源，过时数字会误导后续判断。
- 处理结果：已在 `docs/CURRENT-STATE.md` 订正并对齐当前库内真实规模，将存量治理（KI-017）清洗后的凭证总数（1,469,547）与人员总数（26,713）全量回写。

### KI-005 · 未上线单位历史单据已被物理删除，约 1500 万行，无恢复副本
- 状态：DONE（2026-09-05 关闭，接受既成事实）
- 现象：2026-09-03 经用户授权执行删除脚本，清除第 7、8 批等未上线单位的历史单据与凭证。
  business_document 约 488 万→231 万等，合计约删除 1500 万行，`daily_stats` 汇总被同步改写。
- 说明：删除本身为授权操作；此处登记的是“无备份/恢复副本、且 CURRENT-STATE 未同步更新”这一执行层缺口。
- 相关脚本已归档至 `archive/legacy-db-scripts/clean_unlaunched_org_data.py`（不再运行）。
- 关闭结论（2026-09-05）：删除不可逆且无副本，不存在恢复方案（既成事实，接受）；CURRENT-STATE 的数据规模
  已在 KI-004/KI-017 治理后订正为真实值（凭证 1,469,547、人员 26,713 等），待办已满足，关闭。

## 生产运行与配置

### KI-006 · USA 生产 Cloudflare AI 开关与文档口径不一致
- 状态：DONE（2026-09-05 关闭，统一口径为"已启用"）
- 现象：原 USA `.env.systemd` 中 `MOD_CF_AI_ENABLED=true`，而 `CURRENT-STATE.md` 表述为"默认未启用"。
- 影响：文档与实际运行配置不符。
- 关闭结论（2026-09-05）：迁移到当前运行主机后核实——CF AI 实际启用（`MOD_CF_AI_ENABLED=true` + 凭据齐备），
  仅用于驾驶舱文案摘要生成、只读不写库、无数据安全风险。经用户决策**保持启用**。已订正 `CURRENT-STATE.md`
  口径：代码默认关闭、生产已显式启用、用途只读文案；并与"不展示未生成预测"（KI-023）解耦表述。

### KI-007 · 本地已修复内容尚未部署到 USA
- 状态：DONE（2026-09-05，随迁移消解）
- 进展（2026-09-05）：项目已整体迁移到主运行主机，生产与源码工作区同机运行。前端 `dist` 由本机
  构建并直接由本机 Nginx 提供，后端由本机 systemd 服务运行最新代码，不再存在"本地已修复但生产滞后"
  的差异。原基于 `deploy.yml` 的跨主机自动部署已随迁移删除。
- 历史（2026-09-04）：迁移前前端曾由 `deploy.yml` 自动构建并 rsync 到旧部署环境；该机制已停用。

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
- 状态：DONE（2026-09-04 全部四阶段完成）
- 背景：老模拟器已停用（USA 未配置 `MOD_SIMULATOR_ENABLED`/`MOD_DB_WRITE_URL`，数据不再增长）。
  经 2026-09-04 只读体检，存量数据在“硬自洽”上通过，但在“格式整洁”与“分布真实感”上不达标。
  本次严格按分阶段、备份、dry-run、分批事务更新及严格事后断言执行，完成全部四类治理目标：
  1. **Phase 1 · 状态值污染清理（Commit: `684824b`）**：
     - 清洗 2,304,245 行 `business_document.status` 尾部隐藏回车符 `\r`，与干净状态合并为 1,970,957 行“处理完成”，回车污染清零；
     - 备份文件：`scripts/agy/output/backups/phase1_status_backup.csv`（53.47 MB）。
  2. **Phase 2 · 时间逆序修正（Commit: `3797a7d`）**：
     - 分批修正 344,898 笔 `approve_time < submit_time` 单据（重设为 `submit_time + random(1~72h)`），逆序数清零；
     - 备份文件：`scripts/agy/output/backups/phase2_inverted_time_backup.csv`（16.05 MB）。
  3. **Phase 3 · 孤儿凭证与关联集成删除（Commit: `f770276`）**：
     - 倒序分批删除 11,144 个无关联单据凭证及关联的 10,556 笔 `integration_result`；
     - 保持 0 孤儿、0 断键，凭证数收敛至 1,469,547，借贷分录 2,939,094 条 100% 保持平衡；
     - 备份文件：`phase3_orphan_vouchers_backup.csv` 与 `phase3_orphan_integration_backup.csv`。
  4. **Phase 4 · 主数据重整与全链路引用闭环（Commit: `6f3a7d9`）**：
     - 人员体量分层扩充：2,000 个单位依据体量分层为大单位（30~48人，247家）、中等单位（14~24人，616家）、较小活跃（9~13人，90家）、准备中（6~8人，287家）、未启动（3~5人，760家），总人数扩充至 26,713 人（均值 13.4 人/单位）；
     - 角色分化：每单位 1 名财务总监（2,000 人）、1 名项目经理（2,000 人）、经办人 6,350 人、普通用户 16,363 人，职位与角色尾部回车符彻底清零；
     - 全链路引用 100% 闭环：保留活跃经办人名录，修复 12,351 笔占位符单据经办人，单据经办人 100% 命中本单位人员名录（0 未匹配单据，0 占位符单据）；
     - 级联重算：4,730 场培训数据期望与实际人数约束在单位人员规模内，`data_readiness` 准备度达标率格式统一，`daily_stats` 实时对齐（用户 26,713、凭证 1,469,547、集成 1,382,379）；
     - 备份文件：`scripts/agy/output/backups/phase4_*_backup.csv`。


### KI-018 · 前端契约缺自动校验（Tailwind 任意值漏网）
- 状态：DONE（2026-09-04）
- 现象：`FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 契约三禁止脱离 Token 的任意值
  （如 `text-[10px]`、`bg-[#xxxxxx]`），但此前闸门（`make check` 的 typecheck/build）无法识别这类违规——
  语法合法、可正常构建，因此靠人工 review 才能发现。
- 实例：`eb8212a`（rollout 迁移）残留 1 处 `text-[10px]`，应为 `text-cockpit-xs`。
- 影响：前端契约停留在“须知 + 人工 review”，未成“闸门”；迁移过程中易漏网，长期累积会重新滋生散写样式。
- 处理结果：
  1. [已修复 2026-09-04] `RolloutView.vue` 残留的 `text-[10px]` → `text-cockpit-xs`。
  2. [已修复 2026-09-04] 在 `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` 契约三与 KI-022 中界定清晰边界（禁止字号/颜色/间距等任意值，受控允许图表 min-h/max-h guardrails）。
  3. [已落地 2026-09-04] 实现项目级校验脚本 `scripts/project/lint_frontend_arbitrary_values.py`，精准拦截字号/颜色/间距/边框等禁止模式，放行受控 guardrails，并支持 `<!-- lint: allow -->` 行内显式豁免。
  4. [已接入 2026-09-04] 接入 `Makefile`（`frontend-check` 目标）及 GitHub Actions CI（`.github/workflows/quality.yml`），违规直接阻断提交与构建。
- 关联：`KI-008`（B–F 屏迁移）、`KI-022`（收尾清理）。


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


## 流程与机制缺口

### KI-024 · 缺少新需求/任务的正式登记入口
- 状态：DONE（2026-09-04）
- 现象：`KNOWN-ISSUES.md` 记录“已发现的问题/缺陷”，`docs/decisions/` 记录“已做的决策”，
  但“新需求/新功能/待办任务”没有对称的正式登记处——目前散落在对话中，易丢失、不可追溯。
  `docs/tasks/` 是已停用协作流程的残留，不承担此职责。
- 影响：需求与问题不对称；新想法没有沉淀容器，违背“想清楚的东西必须记录下来让人/AI 遵循”的原则。
- 处理：启用 GitHub Issues 作为需求与任务的正式登记入口。在 `.github/ISSUE_TEMPLATE/` 建立 `feature_request.md`（新需求）与 `task.md`（任务待办）模板，包含标题、背景与业务价值、技术范围与验收要点；并在 `README.md` 与 `docs/INDEX.md` 明确增加指引：新需求/任务用 GitHub Issues 登记，已发现问题的登记见 KNOWN-ISSUES.md。存量 KNOWN-ISSUES 保持原位供追溯。

### KI-025 · 文档与代码事实的同步无机制强制（仅靠规范与自觉）
- 状态：DONE（2026-09-04）
- 现象：`ENFORCEMENT.md` 与 `DOCUMENTATION-LIFECYCLE.md` 要求“改动改变事实（数据规模、架构、
  路径、部署状态）时必须同步 `CURRENT-STATE.md`，否则视为未完成”，但此前**无任何机制检查此项**——
  提交时不校验文档是否随代码同步。当前文档能跟上，主要靠人盯 + AI 自觉，非机制保证。
- 影响：这是体系此前最大的“须知而非闸门”缺口。换一个不上心的执行者，CURRENT-STATE 等活文档会掉队，
  而下一个 AI 以文档为事实来源，会被过时文档误导（参见 KI-004 数据规模漂移即此类）。
- 现实上限：机器无法判断“某次改动是否改变了事实”，故无法完全自动强制；只能做到“半机制”。
- 处理结果：落地方案 1（CI 软警告半机制）。新增 `scripts/project/check_doc_sync.py` 并在 CI（`.github/workflows/quality.yml`）中接入；当变更涉及 `backend/app/`、schema 或 `deploy/` 但未修改 `docs/CURRENT-STATE.md` 时，通过 `::warning` 输出 GitHub 警告注解提醒复查，警告不阻断构建，实现半机制化闭环。
- 关联：这是“用概率性的 AI 生产确定性系统”这一根本矛盾在文档层的残留——形式可机制守住，语义同步靠判断。


### KI-026 · 拟真引擎第二步：建设管控主线 + B模式生命周期推进器
- 状态：DONE（2026-09-05 完成代码实现、单元测试 100 项全绿、8 条硬闸门全量 dry-run 审计验证通过，且经主控授权已完成第一轮真实写库落地：写入前 7 表完整备份、严格 2000 行/批分批提交与进度留痕、事后 8 闸门只读复测全绿，KI-017 零回归）
- 背景：拟真引擎第一步（费用报销业务佐证足迹 + 安全写库器）已落地并验收全绿（100 笔小试落库、
  KI-017 零回归），机制地基已验证。第一步属业务佐证（次线）。
- 目标：实现 `docs/development/BUSINESS-SIMULATION-ENGINE.md` 定义的**建设管控主线（逼真主角）**——
  7 类建设事件（入池、数据准备、培训认证、接口联调、双轨核对、跃迁评审、批次推进）的完整多表足迹，
  加 **B 模式生命周期推进器**（单位阶段由真实指标驱动跃迁：只进不退、持续达标 N 天才跃迁、跃迁走
  “申请→评审→状态变更→留痕”、少数单位喂成困难户），并使困难户与风险预测读同一事实源、天然自洽（矛盾咬合）。
- 范围与顺序（5 个阶段全部按规范独立提交、独立验证）：
  - 阶段 A（commit `aff0044`）：建设事件足迹模型 + 确定性校验（`construction_models.py`，不连库不写库，26 项单测）。
  - 阶段 B（commit `a6bdf82`）：7 类建设管控剧本生成器（`construction_playbooks.py`、`scripts/agy/dry_run_construction_playbooks.py`，因果门禁严格，经办人 100% 取自本单位人员，12 项单测）。
  - 阶段 C（commit `a53e157`）：B 模式 6 阶段状态机推进器（`lifecycle_advancer.py`，严格执行“只进不退、持续达标 N 天才跃迁、跃迁评审留痕快照”三条铁律，4 项单测）。
  - 阶段 D（commit `20ae0dc`）：快慢电影演进协调器 + 矛盾咬合机制（`evolution_coordinator.py`、`scripts/agy/dry_run_evolution_meshing.py`，~4% 自然涌现困难户与风险视图 100% 咬合自洽，3 项单测）。
  - 阶段 E（commit `341cf24`）：8 条硬闸门全量 dry-run 自检通过（`scripts/agy/verify_step2_dry_run.py`，0 数据库修改）+ 事务写库器与自动快照备份（`construction_writer.py`，3 项单测）。
  - 写库执行轮（本轮提交）：
    - 写入前全量备份：7 张受影响表完整备份至 `scripts/agy/output/backups/construction_backup_20260905_131434.json`（43.37 MB，耗时 5.78s）；
    - 严格分批单事务提交：按 2,000 行/批分 3 批逐批 commit（批次 1: 2,001 行；批次 2: 2,000 行；批次 3: 177 行），实时打印行数、事件数与累积进度，无超大事务；
    - 累计真实落库 4,178 行：`org_unit` 20 行跃迁更新（已上线 282，稳定运行 466）、`rollout_status_snapshot` 20 行专家决议留痕快照（总 144,870）、`data_readiness` 238 行指标同步、`training` 476 行认证记录（总 5,520）、`dual_run_result` 1,230 行双轨核对（总 30,288）、`construction_task` 2,194 行任务足迹联动更新（总 62,104）；
    - 验收脚本独立纯只读：`scripts/agy/verify_step2_dry_run.py` 严格保持只读（0 写库），与批量写入入口 `scripts/agy/run_step2_batch_write.py` 彻底解耦；
    - 事后 8 闸门全绿核验：落库后立即针对 live MySQL 运行 8 闸门只读核查，全部 PASS 通过，KI-017 零回归。
- 写库纪律：开关 `MOD_SIMULATION_ENGINE_ENABLED` 默认关闭；具备写入前自动备份（`backup_affected_tables`）、批量 commit 与进度审计日志；写库与验收脚本物理分离。
- 验收（8 条硬闸门实测）：①四级下钻加总一致 (2000单位层层咬合 PASS) ②阶段跃迁只进不退 (状态机硬约束保证 PASS) ③跃迁有过程有留痕 (评审决议+快照归档完备 PASS) ④横截面自洽 (未上线单位零越界业务 PASS) ⑤KI-017 零回归 (经办人100%命中本单位、借贷平衡、无污染与逆序 PASS) ⑥接续存量时间线无倒插 (锚定存量最新业务日 PASS) ⑦困难户与风险预测矛盾咬合 (同一事实源 100% 一致 PASS) ⑧工程与安全开关受控 (make check 绿、安全开关受控 PASS)。
- 分工：设计与验收由主控 agent 负责；实现由 agy 执行（脚本 `scripts/agy/`）。派工单见
  `scripts/kiro/tmp/mod-task-dispatch.html`（滚动更新的单一派单文件，同步于 sga 文件目录）。
- 主控独立验收（2026-09-05，非 agy 自检）：主控对 live MySQL 独立 SQL 复测 8 闸门全绿——
  经办人命中/时间逆序/状态污染/孤儿凭证全表=0；20 单位「已上线→稳定运行」方向前进无倒退；
  org_unit 状态与 9-05 快照一致（mismatch=0）；未上线单位零正式业务；新记录日期 2026-09-05 晚于基线
  2026-09-04 无倒插；make check 绿、100 项测试。**主控验收通过。**
- 后续项（登记）：
  1. 数据库账号：经决策 MOD 继续使用 admin 连库（真值仅存运行主机本地 `.env.systemd`/`.env.local`，
     均 gitignored，绝不入库）；`.env.example` 已改为中性占位并注明真值只留本地。原「建专用非 admin
     写账号」提醒**取消**（按用户决策）。
  2. `scripts/agy/run_step2_batch_write.py` 与 `backend/app/simulation/runtime_service.py` 的 DB fallback 已清除硬编码废弃账号名 `mod_v2_writer`，改为必须由本地 env 传入，缺失即阻断报错。
  3. 当前仅写入 2026-09-05 单日足迹；持续按天生长（运行化/连续跑）由第三步（KI-026-3）承接。
- 关联：KI-017（存量治理，本步零破坏零回归）、KI-023/KI-015（决策支撑真实性，矛盾咬合的盾侧）。

### KI-026-3 · 拟真引擎第三步：常驻后台服务·持续实时增长
- 状态：DONE（2026-09-05，agy 开发完成并通过 live 短窗口实测、8 闸门复测与故障注入验证，待主控系统级部署上线）
- 背景：第一步（业务佐证足迹）、第二步（建设主线 + B 模式推进器）均已落地、真实写库、主控验收全绿；
  香港作息节律引擎 `HongKongDiurnalEngine` 已存在并经主控实测（周六中午强度 0.048、周一上午 2.0+、
  月末 2.5 封顶）。缺口：节律（大脑）与写库引擎（手）尚未接线为常驻服务，当前靠手动跑脚本单日推进。
- 目标：把已验收部件组装成 7×24 常驻后台服务，按真实心跳持续、自然地写库增长，使系统任何时刻看都像
  一个活着的真实系统。不新增业务剧本、不改剧本逻辑，只做"运行化"。
- 已落实设计决策：
  1. 模拟时钟＝实时同步（模拟时间=真实香港时间，一天过一天，不加速不追赶不倒插）。
  2. 速率双重限流：作息节律柔性限流 + 滑动硬上限保险丝（每分钟≤20、每天≤5000，可配，超限暂停+告警）。
  3. 异常容灾策略：单批次自检失败回滚该批继续跑；连续 3 批失败自动触发持久化 `output/simulator_fail_closed.flag` 物理停机与 CRITICAL 审计告警。
  4. 托管架构：独立 systemd 服务配置（`deploy/mod-simulator.service`，与 mod-api 解耦），开机自启、崩溃自愈；持久化 fail-closed 标志保证重启不绕过保险丝。
- 实施完成记录：
  - F1 内核与自检：完成 `backend/app/simulation/runtime_service.py`（`SimulatorRuntimeService`、`RateLimitFuse`、`PostCycleSelfChecker`、`FailClosedManager`）与 `backend/tests/test_runtime_service.py`（覆盖熔断、自检、fail-closed、dry-run、周期推进），110 项单元测试全绿（Commit `233f399`）；
  - F2 服务化与运维工具：完成 `deploy/mod-simulator.service` 与 CLI 工具 `scripts/agy/run_simulator_service.py`，支持 `--status`、`--dry-run`、`--once`、`--clear-fail-closed`，周期落盘结构化健康心跳 `output/simulator_status.json`（Commit `ed834ae`）；
  - F3 实测与验证：
    - 短窗口 live 单步实测：周六 13:54 HKT 触发真实原子落库 1 笔业务足迹（`doc_id=5050517`），经办人命中本单位（`sys_user` 602 魏嘉怡），借贷平衡（12,603.98），时间递增（审批 14:02:21 晚于提交 13:54:30）；
    - 8 闸门与 KI-017 全量复测：10 项第一步自检与 8 项第二步硬闸门全绿通过，KI-017 零回归；
    - 故障注入验证：测试持久化 `output/simulator_fail_closed.flag`，服务立即转入 `FAIL_CLOSED` 物理阻断状态，调用拒绝（Exit code 1）；使用 `--clear-fail-closed` 成功恢复就绪状态（Exit code 0）。
- 交付物：
  - `backend/app/simulation/runtime_service.py`
  - `backend/tests/test_runtime_service.py`
  - `deploy/mod-simulator.service`
  - `scripts/agy/run_simulator_service.py`
  - `output/simulator_status.json` (心跳落盘)
- 待主控执行项：系统级 systemd 服务安装（`sudo cp deploy/mod-simulator.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now mod-simulator.service`）与上线持续监控。
- 主控上线完成（2026-09-05）：代码逐段验收 5 决策全部落实、make check 绿（110 测试）；按两段流程上线——
  先装服务保持开关关闭空跑 dry-run 观察节律正常、库不动，再置 `MOD_SIMULATION_ENGINE_ENABLED=true`
  重启开真实写库。实测：服务 `enabled`（开机自启）+`active`+`Restart=always`（崩溃自愈），jpa 重启
  自动继续；库按实时香港时钟自然增长（周六下午低强度、约每分钟 1 笔）、最新记录时间戳跟随真实时钟、
  KI-017 全表零回归、限流与 fail-closed 正常。**拟真引擎常驻服务已正式上线运行。**
- 运维约定：模拟器长期常驻；主控每日巡检一次（数据增长、作息曲线、阶段演化、KI-017 零回归、审计与
  fail-closed 状态），异常即报。
- 后续待办（治本）：验收/自测脚本（`verify_sim_step1.py`、服务 `--once` 等）历史上会真实落库造成重复
  污染（已由主控多次备份并级联清理，仅保留 2026-09-04 正式验收批）；待 agy 改为一律 dry-run 或写后
  回滚，验收脚本绝不持久落库。
