# MOD 当前状态

更新日期：2026-09-07
状态：现行事实入口
适用范围：当前运行、数据、功能、质量、安全状态与操作边界

本文是项目当前事实入口。历史多 Agent 协作状态机（调度器、agent 定义、任务与交接文件）已于
2026-09-04 归档至 `archive/legacy-collaboration/`，只作历史记录保留，不再驱动开发流程。

## 现行架构

```text
浏览器 -> Nginx / -> Vue 静态文件
                 -> /api/ -> FastAPI -> MySQL HeatWave（库 `mod`）
```

- 2026-09-05 全项目迁移到主运行主机（Always Free 托管环境）。生产运行与源码工作区
  统一在同一台主机，不再区分部署目标与开发机。旧运行环境不再承载 MOD 任何组件。
- 现行入口为已配置的生产域名（见部署配置，不对外公开），DNS A/AAAA 指向当前运行主机。
- 数据库为托管 MySQL HeatWave（库 `mod`，Always Free 规格），连接主机、端口与凭据
  仅存于运行主机的本地环境文件，不写入版本库或文档。原运行环境的旧数据库实例已删除。
- 运行主机使用系统级 systemd 服务 `mod-api.service` 运行项目内 FastAPI 虚拟环境，监听
  `127.0.0.1:8100`，开机自启（enabled）。
- TLS 证书由 Google Trust Services 签发（acme.sh + Google Public CA EAB），acme.sh cron
  自动续期并重载 Nginx。
- MOD 不使用 Docker、DataEase、NocoDB 或 Cloudflare Worker 作为现行运行组件。
- `archive/legacy-cloudflare-worker/` 是未接入现行链路的历史实验原型，不部署。
- 后端包含可选的 Cloudflare Workers AI REST 适配器，代码默认关闭（`MOD_CF_AI_ENABLED` 未设置时不启用）；
  当前生产实测状态为 `UNCONFIGURED`（未配置凭据，`/api/insights/status` 返回“未配置适配器”），
  即该适配器暂未实际提供文案摘要能力；接入需显式配置 `CLOUDFLARE_ACCOUNT_ID`/`CLOUDFLARE_API_TOKEN`；它不依赖上述历史 Worker。
- Cloudflare AI Gateway `mod-gateway` 已建立并配置为本项目 LLM 调用的统一入口（成本闸门）：
  缓存 TTL 3600 秒（相同请求命中缓存不消耗模型 token，实测 MISS→HIT 生效）、限流 100 次 / 60 秒（sliding）、
  日志开启。端点形如 `https://gateway.ai.cloudflare.com/v1/<account_id>/mod-gateway/workers-ai/<model>`；
  实测经网关调用 `@cf/meta/llama-3.1-8b-instruct` 链路通畅。凭据存于运行主机环境变量，不入库不入代码。
- 每日指挥部决策简报（KI-034 第二期）：后台服务 `mod-daily-briefing.timer`（HKT 00:30 触发）调用
  `scripts/kiro/run_daily_briefing.py`，读 dashboard overview 聚合指标经 `mod-gateway` 生成研判，写入
  `mod`.`daily_briefing` 表（一天一条，主键 briefing_date）。大屏 A 屏 A1 下方一行摘要横幅只读展示，
  点击进 F 屏；接口 `GET /api/insights/briefing`。LLM 降级时不写假简报。
- 时区契约：后端与 UTC 侧一律使用 UTC；面向用户的展示时区由 `MOD_DISPLAY_TIMEZONE` 决定，
  默认 `Asia/Hong_Kong`，唯一定义在 `backend/app/config.py`。快照 `meta.displayTimezone`、实时投影
  作息节律与前端时钟均派生自该来源，不得各自写死。已知偏差：`v2_connection` 的会话时区固定
  `+08:00`（见 `backend/app/db.py` 注释），调整属数据语义变更，需单独授权。

## 数据状态

- V2 冻结基线：17 张表、1,685,923 行、1,497 家单位。
- 2026-09-01 的增量导入记录：8,568,654 行。
- 2026-09-02 只读核验的 USA 合计：31,838,078 行、2,000 家单位，数据日期为 2027-02-28。
- 2026-09-04 存量数据合规治理（[KI-017](issues/KI-017-存量数据清洗与主数据重整.md) 完成）：
  - 状态值污染清理：清洗 2,304,245 笔 `business_document.status` 尾部回车符，合并为干净“处理完成”；
  - 时间逆序修正：修正 344,898 笔 `approve_time < submit_time` 业务单据；
  - 孤儿凭证清理：倒序批次删除 11,144 张无关联单据凭证及 10,556 笔关联集成记录，凭证总数收敛为 1,469,547，0 孤儿、0 断键；
  - 主数据（人员）分层重整与引用闭环：`sys_user` 按体量分层扩充至 26,713 人（大单位 30~48 人、中等 14~24 人、小单位 3~5 人，均值 13.4 人/单位）；角色分化为 2,000 财务总监、2,000 项目经理、6,350 经办人、16,363 普通用户，清除所有 `\r`；修复 12,351 笔单据占位符经办人，单据经办人 100% 命中本单位名录；连带重算 4,730 场培训数据与准备度指标；`daily_stats` 实时同步对齐。
- `artifacts/v2-sim-data/` 是冻结基线，不得修改或重复导入。
- `artifacts/v2-sim-data-inc/` 是增量数据资产，数据库写入和再次导入仍需单独确认。

## 功能状态

- V2 六屏驾驶舱、只读 `/api/v2`、34 省地图和无刷新轮询已经实现。
- 浏览器全屏模式保留顶部六屏导航、在线状态、时钟、刷新与退出全屏控制；内容画布继续按导航下方
  `command-main` 的真实尺寸等比缩放，不再隐藏菜单或按整块物理屏幕高度覆盖导航空间。
- 驾驶舱包含默认启用的进程内只读实时投影，通过 SSE 展示受约束的单据、凭证和集成增量；该投影明确
  标记为演示动态，不写数据库，也不启用业务模拟器。
- 拟真引擎第一步（技术验证载体）已落地（`backend/app/simulation/`）：实现费用报销剧本（`ExpensePlaybook`）多表完整足迹生成与安全写库器（`SimulationWriter`），单事务原子落库 6 张表（`business_document`、`business_document_line`、`accounting_voucher`、`accounting_voucher_line`、`document_voucher_link`、`integration_result`）并级联同步 `daily_stats`；以存量治理成果为硬约束（时间线接续存量最新日期只向前生长、经办人 100% 命中本单位名录、仅限已上线单位门禁、只增不删、零 schema 变更、运行审计留痕）；开关 `MOD_SIMULATION_ENGINE_ENABLED` 默认关闭（`false`）；已通过 100 笔小试落库实测，KI-017 零回归。
- 拟真引擎第二步（建设管控主线 + B模式生命周期推进器）已落地并已实测写库（`backend/app/simulation/` 与 `scripts/agy/run_step2_batch_write.py`）：
  - 核心模块：实现 7 类建设管控剧本生成器（入池、数据准备、培训认证、接口联调、双轨核对、跃迁评审、批次推进，`construction_playbooks.py`）、6 阶段生命周期状态机推进器（`lifecycle_advancer.py`，严格执行“只进不退、持续达标 N 天才跃迁、跃迁评审留痕快照”三条铁律）、快慢电影演进协调器与矛盾咬合机制（`evolution_coordinator.py`，~4% 自然涌现困难户与决策支撑风险视角 100% 咬合自洽）、建设安全事务写库器（`construction_writer.py`）；
  - 严格分批写库落地：经主控授权，使用独立可控批量写库脚本（`scripts/agy/run_step2_batch_write.py`）执行 2026-09-05 建设主线业务足迹真实落库。写前自动对 7 张受影响表生成全量快照备份（`scripts/agy/output/backups/construction_backup_20260905_131434.json`，43.37 MB），按 2,000 行/批分 3 批逐批 commit（单事务单批次），实时打印进度与 ID 区间，累计安全写入 4,178 行；
  - 当前数据规模：`org_unit` 2,000 家（未启动 760、准备中 238、已具备双轨条件 49、双轨运行中 205、已上线 282、稳定运行 466）；`construction_task` 62,104 行（新增 2,194 行）；`rollout_status_snapshot` 144,870 行（新增 20 行带专家决议留痕快照）；`training` 5,520 行（新增 476 行）；`dual_run_result` 30,288 行（新增 1,230 行）；`data_readiness` 2,000 行（238 行同步更新）；
  - 验收脚本隔离与零回归：验收脚本（`scripts/agy/verify_step2_dry_run.py`）严格保持纯只读，与写库入口彻底分离，杜绝验收重复写库。写后 8 条硬闸门全量复测 100% PASS，KI-017 零回归。
- 拟真引擎第三步（常驻后台服务 · 持续实时增长）已落地（`backend/app/simulation/runtime_service.py`、`deploy/mod-simulator.service`、`scripts/agy/run_simulator_service.py`）：
  - 核心架构：将作息大脑 `HongKongDiurnalEngine`（24h 曲线、周末抑制、月末峰值、泊松突发）与已验证写库执行器装配为常驻后台服务 `SimulatorRuntimeService`，时钟严格对齐当前香港真实时间（`sim_time = current HKT`，不加速、不追赶、不倒插历史）；
  - 双重限流与硬保险丝：柔性作息强度与泊松间隔调度 + 滑动硬上限保险丝（每分钟 ≤ 20 笔、每天 ≤ 5000 笔可配，超限自动安全暂停并记审计日志）；
  - 周期后自检与自动容灾：每周期单事务写后自动执行确定性自检（单据与行金额求和一致、借贷平衡、时间严格递增、经办人命中本单位）；单批次自检失败立即回滚重试；连续失败达到阈值（3 次）自动触发持久化 `output/simulator_fail_closed.flag` 物理阻断写库，重启保持阻断，拒绝静默污染；
  - 服务化与运维管理：提供独立 systemd 配置文件（`deploy/mod-simulator.service`，与 `mod-api.service` 解耦）和 CLI 运维管理工具（`scripts/agy/run_simulator_service.py`），支持 `--status`、`--dry-run`、`--once`、`--clear-fail-closed`；每周期落盘结构化健康心跳（`output/simulator_status.json`）；安全开关 `MOD_SIMULATION_ENGINE_ENABLED` 默认关闭；短窗口实测与 8 闸门复测全绿。
  - 上线状态（2026-09-05，主控授权）：服务已系统级安装并 `enable --now`，`MOD_SIMULATION_ENGINE_ENABLED=true` 开启真实写库，常驻运行中；开机自启、崩溃自愈、运行主机重启自动继续；库按实时香港时钟自然增长、KI-017 全表零回归；主控每日巡检。
- V1 回退代码仍保留，但不作为后续功能目标。
- HeatWave AutoML 已完成特征工程重构、真实重训与独立切分验证达标（KI-034 第一期落地）：
  - 模拟器因果数据层改造：注入体量加权、经办人单点集中度瓶颈（75%）、错误率因果与期初数据差异双轨考核惩罚（+7天），从根因上彻底消除标签过度可分与周期节律缺失；
  - 特征表扩充动量特征：`mod.ml_feat_risk_train` 与 `mod.ml_feat_doc_delta_train` 扩充近 14 天推进斜率、任务停滞天数、经办人集中度、培训-报错剪刀差等核心字段；
  - 库内重训与独立测试集验证达标：风险分类模型 `MOD_RISK_CLASSIFIER` 独立测试集准确率达 89.50%（Precision 90.61%, Recall 86.77%, F1 88.65%，消除 1.0 退化）；单据量回归模型 `MOD_REGRESSION_MODEL` 独立测试集 R² 达 0.4488（MAE 0.7237，彻底消除负 R²）；
  - SHAP 库内原生可解释性调通：接入 `sys.ML_EXPLAIN_ROW(..., JSON_OBJECT('prediction_explainer', 'shap'))` 与确定性偏离兜底，提供 GET `/api/insights/risk-explanation/{org_id}` API 输出 Top 3 致险因子及百分比权重；
  - 库内批量预测评分完成（各 2,000 行），元数据全量落库 `ml_model_metadata` / `ml_training_log`，`/api/insights/status` 状态晋升为 `READY`；
  - 前端归因透出联动：`AtRiskUnitTable.vue` 增加 SHAP 归因与客观动量指标核验下钻抽屉，`ModelContractCard.vue` 与 `InsightsView.vue` 达标激活展示真实指标；自动化回归测试 122 项全绿。HeatWave AutoML 的能力清单与边界见 [HeatWave AutoML 能力与边界手册](development/HEATWAVE-AUTOML-CAPABILITIES.md)。
- 拟真业务语料生态落地（KI-034 第三期，遵循 ADR-0010 与零运行时成本原则）：
  - 离线预生成静态语料资产（`simulation/assets/business_corpus.json`，688 条）：含 363 条符合真实国资政企财务质感的卡点事由（覆盖历史数据清洗、银企直联/税企接口、双轨平账尾差、交叉权签矩阵、流程合规等 5 大维度）与 325 条阶段跃迁《专家组上线评审决议书》专业措辞，去除虚构姓名与占位符；
  - 模拟器确定性接入：`simulation/evolution_coordinator.py` 接入 `get_friction_reason(org_id)`，约 4% 困难户卡点事由从原 3 条固定死文本扩展为 363 条多样化真实事由；`simulation/construction_playbooks.py` 接入 `get_transition_review_notes(from_status, to_status, org_id)`，替换固定模板；均基于 `org_id` 稳定 MD5 哈希查表，同一单位全程一致，保持 100% 确定性可复现；
  - 运行时零成本与零依赖：语料一次性离线生成，运行时严格本地查表，零 LLM 实时调用，零网络开销，免除 DB 建表与结构变更风险；新增 8 项回归测试，全量 `make check` 130 项测试全绿。
- 前端自动化测试体系从 0 到 1 落地：基于 Vitest 5 + @vue/test-utils 2 + happy-dom 搭建测试基座，编写 8 个核心测试套件、59 项单测，实现毫秒级执行与 100% 离线 Mock，覆盖：
  - `useScaleScreen.ts`：普通/全屏模式视口等比计算、clamp 范围约束、零尺寸防御与生命周期事件解绑；
  - `useAiInsights.ts` 与 `useDailyBriefing.ts`：完整状态机流转、并发节流、429 限流捕获与网络异常优雅降级；
  - `formatters/metrics.ts`：千分位与百分比格式化及各类边界数值（null/undefined/NaN/0/负数）安全保护；
  - `stores/project.ts` 与 `liveProjection.ts`：快照加载、键名递归驼峰化（fixKeys）、审计记录生成、实时投影有序应用与重置；
  - `utils/modelEvaluation.ts`：严格落实 KI-023/KI-028/ADR-0010 诚实模型判定契约（R² > 0 回归有效性、(0.5, 1.0) 分类有效性及整体 READY 判定）；
  - `utils/qualityMetrics.ts`：质量合规率、双轨一致性与困难户风险维度分布聚合纯函数运算及缺失边界防呆；
  - 门禁打通：`pnpm test` 正式纳入 `Makefile` 的 `frontend-check` 目标，与 typecheck 和 build 并列守护前端质量。
- 面板信息密度平衡与图表化已覆盖 B/C/D/E/F 屏的高收益区域：
  - **B2 阶段任务分布**：原 8 张横排指标卡收敛为已完成/进行中/未开始横向堆叠图，阶段完成率贴近对应条形展示；
  - **C2/C5 推广与联系人**：批次工序卡改为 8 批次上线/双轨/待推进堆叠图；联系人纯数字面板改为覆盖环图配合三项精简指标；
  - **E4 批次合规监督**：原 8 张横排卡改为合规率折线与重点监督/高风险单位柱图，统一呈现批次间差异；
  - **D6 双轨核对**：引入基于 `echarts` + `charts/theme.ts` 的一致率环形图（`dualRunConsistent` vs `dualRunInconsistent`），中心展示对账一致率百分比，对称呼应 D5 阶梯条，彻底消除纯数字卡片的空旷感；
  - **D7 数据质量金标准**：将原 4 项纯静态标签升级为“4 项金标准稽核规则卡 + 横向通过率柱状图”组合面板，真实接入快照 `quality`（`voucherBalanceErrors`、`timeOrderErrors`、`orphanLinkErrors`、`organizationsWithStatusProgression`），0 异常如实展示，配合 147 万凭证 / 231 万单据 / 2000 家单位真实核验规模与 100% 达标率；
  - **F3 综合态势预警**：在确定性规则研判卡左侧新增困难户风险维度分布柱状图，直观展现准备期卡顿、双轨核对差异与建设严重滞后各维度预警单位数及集中批次，撑起版面空间；
  - **统一图表契约**：全量走 `charts/theme.ts`（`chartPalette`、`chartInk`、`chartTooltip`、`calmAnimation`），零硬编码十六进制色值，缺失数据显示 `—`，0 值如实展示；
  - **质量缺失态修正**：D7 缺失稽核规模、异常数或状态演进数据时不再回填 100%/0 异常/2000 家，卡片与图表统一显示 `—`。
- 前端构建按库分包（`vite.config.ts` `manualChunks`）：echarts / vue 全家桶 / 地图 GeoJSON / 图标各自独立 chunk，
  业务视图 chunk 从数百 KB 降至数十 KB（改动不再让用户重下 echarts），`chunkSizeWarningLimit` 上调至 700 消除噪音。
  注：`element-plus`、`vxe-table`、`@element-plus/icons-vue` 为未使用依赖，已移除。
- F 屏 F5 已由“手动点击生成研判”改为纯展示每日自动简报（与 A 屏简报同源、零交互，读 `GET /api/insights/briefing`），
  A 屏一行摘要、F 屏展示全文，消除两处 LLM 研判入口的重复。
- Cloudflare AI Gateway 用量可只读巡检：`scripts/kiro/inspect_gateway_usage.py`（缓存命中率、累计 token、错误数），
  实测缓存生效、消耗极低，支撑长期演示成本可控。
- Cloudflare AI 适配器已接入并经 `mod-gateway` 实测可用（生成每日决策简报）；无论 AI 是否启用，都不应把未生成的预测或
  未经真实评估的模型质量展示为真实结果（见 [KI-023](issues/KI-023-AutoML质量分硬编码兜底.md)，已闭环）。
- 本地接口与前端已将建设、问题、单位与运营屏统一到数据库当前快照口径；缺失指标展示为 `—` 或明确的
  “未提供”，不再以冻结基线数值替代实时结果。已随运行主机生产构建生效。
- 本地已修复省级单据新增与总览不一致问题：在线查询按快照日前最近完整业务日聚合，fallback 已从
  冻结 V2 资产只读重建，并恢复 R3 省级合计与 R6 日期区分契约。已随运行主机生产构建生效。
- 本地前端已修复 1440 宽度导航重叠和 1920×1080 驾驶舱首屏溢出，地图色阶改为按当前数据动态
  缩放；智能研判关闭态不再暗示存在现行 Cloudflare Worker。已随运行主机生产构建生效。
- 本地 B 屏建设进度已迁移到 `CockpitPanel`、具名 Grid 与统一 Token，旧 `construction.css`
  及关联遗留规则已删除，缺失建设数据不再使用硬编码数值回填。已随运行主机生产构建生效。
- 页面 meta、根 `robots.txt`、Nginx 与 API 响应均设置禁止索引指令。

## 运行安全状态

- 2026-09-05 迁移完成后旧运行环境侧清理确认：系统级与用户级 `mod-api.service` 均已停止、禁用
  并删除（用户级服务形态由 `docs/operations/USA-DEPLOYMENT-LAYOUT.md` 记录后核对发现）；旧
  部署目录已删除；旧 Nginx 站点配置及对应 TLS 证书与续期配置已删除；旧环境 `8100` 端口无监听。
  旧环境上其他无关项目未受影响。
- 正式服务已在当前运行主机重启并采用默认关闭门禁，日志确认业务模拟器未启用，不再创建写库连接。
- 当前运行主机的 `/home/ubuntu/mod` 现为源码工作区与生产运行的唯一位置；代码、工具、文档、
  数据与历史资产均以该主机为唯一事实源。

## 本地质量基线

- 前端：Vue 3、TypeScript、Vite；`pnpm exec vue-tsc --noEmit --incremental false` 通过。
- 后端：FastAPI、SQLAlchemy；当前收集 130 项 pytest 测试。
- Ruff 检查已清零并纳入 `make check`。
- 本地 Git hooks 已强制执行凭据扫描、`make check` 和提交信息格式；GitHub Actions workflow 已在仓库
  落地，远端启用后在拉取请求和推送中复用同一闸门，不包含部署或生产访问。
- 本目录已开始采用 Git 管理；大体积 CSV、原始参考材料、构建产物和本地密钥不纳入版本库。

## 操作边界

- 不运行历史协作状态机，不新增其中的任务或状态记录。
- 临时脚本必须遵守 `development/CLI-SCRIPT-POLICY.md` 的 CLI 专属目录制度。
- 实时投影的展示语义、事件链和多实例限制以 `development/LIVE-PROJECTION.md` 为准。
- 不部署历史 Cloudflare Worker。
- 不修改冻结 CSV，不重复运行历史全量导入工具。
- 数据库写入、USA 部署、服务启停、Nginx 和云资源操作仍需明确确认。
- 当前默认改进范围是本地代码、测试、文档与开发工具。
