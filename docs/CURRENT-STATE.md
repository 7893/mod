# MOD 当前状态

更新日期：2026-09-08
状态：现行事实入口
适用范围：当前运行、数据、功能、质量、安全状态与操作边界

本文是项目当前事实入口。历史多 Agent 协作状态机（调度器、agent 定义、任务与交接文件）已于
2026-09-04 归档至 `archive/legacy-collaboration/`，只作历史记录保留，不再驱动开发流程。

## 现行架构

```text
访客 -> CloudFront(全球边缘, 带回源密钥) -> Nginx(校验密钥) / -> Vue 静态文件
                                                          -> /api/ -> FastAPI -> MySQL HeatWave（库 `mod`）
```

- 2026-09-05 全项目迁移到主运行主机（Always Free 托管环境）。生产运行与源码工作区
  统一在同一台主机，不再区分部署目标与开发机。旧运行环境不再承载 MOD 任何组件。
- 访客入口经 **AWS CloudFront** 前置（隐藏源站，见下条"源站隐藏架构"）；DNS 托管在 Route53，
  站点主机名以指向 CloudFront 分发的 Alias 记录对外解析，DNS 层查不到源站真实 IP。具体域名、分发 ID、
  回源地址等见部署配置，不写入文档。

## 当前数据规模（2026-09-08，KI-051/KI-052 落地后）

经 KI-051（规模扩充）与 KI-052（财务凭证真实性深化）后，全库规模与结构如下（拟真引擎生成，非真实业务数据）：

- **单位 `org_unit` 约 3,193 家**（在 2,000 基础上新增约 1,187 家）：状态自然分布（未启动/准备中/
  已具备双轨条件/双轨运行中/已上线/稳定运行，比例对齐存量），上线时间铺满 2023-08 至今，接续既有
  31 省 + 8 批次分层机制；新单位人员按省份分层配置。
- **人员 `sys_user` 约 41,060 人**：命名取自小说/影视/游戏正面或中性角色（排除负面人物）与扩充中文名库，
  重名率约 10%、知名角色名唯一、无不雅/谐音；每单位经办人齐备，无"无人经办"孤单据。
- **业务链规模**：单据约 587 万、单据明细约 1,012 万、**会计凭证约 502 万**、凭证分录约 1,607 万、
  单据凭证关联约 502 万、集成结果约 494 万。时间分布 2023-08 至今，按真实节律（工作日多/周末少、
  月末与季度末高峰、节假日低谷、东八区作息）。
- **会计科目真实化（KI-052）**：凭证分录由单一「银行存款/应付账款」重构为符合《企业会计准则》的
  多科目借贷（管理费用各明细/库存商品/在建工程/主营业务收入/固定资产清理/进项税/销项税等 15+ 科目），
  按单据类型与明细费用类别记账，含增值税进销项（招待费进项不抵扣、采购 13%、工程 9%、收入 6%）。
  **全库 502 万凭证借贷 0 不平、0 孤儿**（HeatWave 加速校验）。存量历史凭证已全量改造，与新生成一致。
- **作息节律（拟真引擎）**：核心工作时间 8:30-11:30 与 13:30-17:00，午休回落，提交时刻随机（非整点打卡）；
  早到/加班/周末/节假日加班为偶发且随机，不成固定规律；财务周期性高强度（月末结账、季度末、报税期）
  加班概率显著升高。逻辑见 `simulation/models.py`（时间系数）与 `simulation/expense_playbook.py`
  （`_sample_worktime`）。
- HeatWave 列存对核心大表加速仍有效，容量健康（扩充后列存占用在 16GB 集群内）。
- **大屏面板真实性修正（KI-057）**：六屏面板全面复查后消除若干编造/硬编码兜底——C4 移除编造的
  上线率兜底（`|| 37.4`）、C1/C4 覆盖省份数改为按数据派生；F3 移除写死的过时批次假数字兜底，
  无真实规则告警时显示中性空态；E/F 屏困难户/合规风险不再用 `id % 7`/`id % 11`/`id <= 1000` 机械
  规则造标签，改为仅依据真实运行指标（凭证率、建设进度、期初数据、状态、真实 batchId）派生。
- **ML 特征表动态重建（KI-055）**：每日重训（`mod-ml-retrain`）流程首步已改为从当前业务表重建
  特征表（`ml_feat_risk` / `ml_feat_doc_delta`，`FROM org_unit` 无范围限制），使模型每次自动纳入
  当前全部单位与最新业务数据，不再训练冻结的历史特征。数据扩充后模型质量随真实全量数据提升
  （分类约 90%、回归 $R^2$ 约 0.88，真值以 `ml_model_metadata` 落库记录为准），评分覆盖当前全部单位。
- **批次映射对新增单位修正（KI-056）**：`dashboard.py` 与 `dashboard_sections.py` 的 `batch_mapped`
  原按旧 2000 家的 id 区间硬编码，导致 KI-051 新增单位（id > 2005）被 `ELSE 8` 全部错归第八批，
  C6 单位台账等面板出现"仅第八批有数据、省份筛选为空"。已修正为：存量单位（id ≤ 2005）保留原
  status+id 映射，新增单位直接采用 `org_unit.batch_id` 真实批次，双轨/第八批优先判定；修复后 C6
  八个批次与 34 省份均有数据。
- **全场景秒级响应 SLA 与台账筛选分页死锁治理（KI-059）**：
  - **前端台账交互闭环**：C6（`RolloutLedgerTable.vue`）和 B-T1（`ConstructionLedger.vue`）台账组件建立了筛选条件响应式重置闭环。切换批次、省份、状态或搜索关键字时，强制重置 `page.value = 1`；同时对 `totalPages` 设置安全边界钳位保护（`safePage`），彻底根除翻至高页码后切换筛选导致切片越界展示假性空白（“只有第八批有数据，前面没数据；而且省份选择了也没东西”）的交互缺陷；下拉框选项增加包含实体计数的友好标签（如 `第一批 (150家)`、`北京 (43家)`），并提供一键重置筛选与空状态引导按钮。
  - **大盘快照异步双缓冲与预热（SWR）**：改造快照缓存机制为 Stale-While-Revalidate（SWR）模式，消除 60s TTL 到期时同步穿透全库重新计算造成的 1.12s 阻塞；服务启动（lifespan）通过 `prewarm_snapshot()` 触发异步快照装载，前台 API 响应恒定控制在毫秒级（< 100ms），严格保障全场景 < 1.0s 的 SLA 红线。
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

- 源站隐藏架构（AWS CloudFront 前置，隐藏源站 IP）：
  - 访客经 Route53 Alias → CloudFront 分发 → 回源到一个隐蔽回源域名（DNS-only，指向源站），回源协议 https-only。
    （具体站点域名、分发 ID、回源域名、源站 IP 均见部署配置，不入文档。）
  - **回源密钥防绕过**：CloudFront 回源时注入一个自定义密钥头；源站 Nginx 校验该头，
    无正确密钥的请求（即绕过 CloudFront 直连源站 IP 或回源域名）一律 403。密钥值只存源站 Nginx 与 CloudFront 配置，不入库不入代码。
  - 效果：对站点主机名做 DNS 查询只见 CloudFront 的 IP、查不到源站；直连源站 IP / 回源域名均被 403；仅 CloudFront 回源可达。
  - 证书：viewer 侧用 us-east-1 的 ACM 证书（CloudFront 强制证书位于 us-east-1）；缓存策略 CachingDisabled
    （大屏数据动态 + SSE 实时，全站不缓存以保证正确性）；SSE 实时投影经 CloudFront 实测正常（回源超时 60s + 转发 Host 头）。
  - 未迁移域名托管到 Cloudflare（DNS 在 Route53）；CloudFront 免费额度远超本项目用量。
- DNS 安全（DNSSEC）：站点所在 zone 已在 Route53 启用 DNSSEC 签名（KSK 由一枚 us-east-1 的 KMS 非对称密钥
  ECC_NIST_P256 / SIGN_VERIFY 承载），并已在域名注册商（TLD 层）登记对应 DS 记录，全链校验通过、多解析器实测 NOERROR。
  防 DNS 劫持/应答篡改。密钥标识、DS 摘要、KeyTag 等敏感值见云端配置，不入文档。
- 反检索/反抓取（内部交流系统，谢绝一切采集）：三层防护叠加——`robots.txt`（`Disallow: /` 且显式点名 GPTBot/ClaudeBot/
  PerplexityBot/Google-Extended/Baiduspider 等 AI 与搜索爬虫）、HTML `<meta robots/googlebot/bingbot noindex,nofollow,noarchive,nosnippet,noimageindex>`、
  HTTP 响应头 `X-Robots-Tag` 同值；并在 Nginx 层按 `User-Agent` **硬拦截** AI/检索爬虫直接返回 403（不返回任何内容），
  正常访客不受影响。robots/meta 为君子协定，Nginx UA 拦截为强制层。
- V2 六屏驾驶舱、只读 `/api/v2`、34 省地图和无刷新轮询已经实现。
- 前端路由采用 hash 模式（`createWebHashHistory`），URL 形如 `https://<域名>/#/a`；刷新任意屏不依赖
  服务器 fallback、永不 404。菜单从左到右严格 A→B→C→D→E→F（/d=业务运营 OperationsView、/f=风险预警 InsightsView），
  路由/组件/zone/标签/跳转全对齐。
- 浏览器全屏模式保留顶部六屏导航、在线状态、时钟、刷新与退出全屏控制；内容画布继续按导航下方
  `command-main` 的真实尺寸等比缩放，并采用水平居中、顶部锚定；宽高比不一致产生的余量留在底部，
  不再隐藏菜单、按整块物理屏幕高度覆盖导航空间或在标题栏下留出大块空白。
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
- HeatWave 内存加速看门狗与自愈落地（KI-049 / KI-050）：应用内置轻量看门狗模块（`app/heatwave_watchdog.py`）提供 ~1ms 级状态探测；为 API 生产只读账号 `mod_readonly` 补齐 `performance_schema.rpd_tables` 与 `rpd_table_id` 的最小 `SELECT` 权限（KI-050 闭环），消除只读观测盲区，`/api/health` 探针真实透出 `heatwave: {status, loaded_count, total_target, loaded_tables, missing_tables}`；API 进程严守 KI-041 物理只读边界只做状态观测，自愈动作解耦交由具备运维凭据的系统定时器（`deploy/mod-heatwave-watchdog.timer` 与 `service`，开机及每 5 分钟巡检）；CLI 运维工具扩展 `watchdog` 指令支持周期巡检；自动化回归测试 7 项全过（`test_heatwave_watchdog.py`，全量 195 项后端单测全绿）。
- 拟真业务语料生态落地（KI-034 第三期，遵循 ADR-0010 与零运行时成本原则）：
  - 离线预生成静态语料资产（`simulation/assets/business_corpus.json`，688 条）：含 363 条符合真实国资政企财务质感的卡点事由（覆盖历史数据清洗、银企直联/税企接口、双轨平账尾差、交叉权签矩阵、流程合规等 5 大维度）与 325 条阶段跃迁《专家组上线评审决议书》专业措辞，去除虚构姓名与占位符；
  - 模拟器确定性接入：`simulation/evolution_coordinator.py` 接入 `get_friction_reason(org_id)`，约 4% 困难户卡点事由从原 3 条固定死文本扩展为 363 条多样化真实事由；`simulation/construction_playbooks.py` 接入 `get_transition_review_notes(from_status, to_status, org_id)`，替换固定模板；均基于 `org_id` 稳定 MD5 哈希查表，同一单位全程一致，保持 100% 确定性可复现；
  - 运行时零成本与零依赖：语料一次性离线生成，运行时严格本地查表，零 LLM 实时调用，零网络开销，免除 DB 建表与结构变更风险；新增 8 项回归测试，全量 `make check` 130 项测试全绿。
- 模拟器单位动态增长落地（KI-035，第八批蓄水池入池）：
  - 真实构词法与查重生成器（`simulation/org_generator.py`）：从存量 2,000 家单位提炼 34 省历史古雅地名库（覆盖率 100%）、43 个产业行业与 19 种组织后缀，严格执行既有构词法与全库查重；为每个新单位配套 3~5 名规范真实中文人名（包含 1 名财务总监、1 名项目经理与 1~3 名业务经办人），零运行时 LLM 调用；
  - 连锁数据原子入池（`simulation/pool_onboarding.py` 与 `simulation/construction_writer.py`）：新单位以第八批、未启动、进度 0 入池，联动单事务原子生成 30 项全生命周期标准任务模板（全未开始）、全 0% 期初数据准备度、初始上线快照，并级联更新 `daily_stats.org_count` 与 `user_count`；
  - 严守第八批零业务数据铁律：严格禁止对未启动的第八批单位生成任何单据、凭证、接口集成或双轨记录，确保数据金标准 0 缺陷；
  - 批次映射 SQL 逻辑加固：修复 `dashboard.py`、`dashboard_sections.py` 与 `broker.py` 中 `batch_mapped` 判定（由 `id > 1600` 加固为 `batch_id = 8` 及 `id > 1600 AND id <= 2000` 映射至第七批），杜绝新插入单位（id > 2000）被错误归入在推批次，确保批次 1~6（1002 家）、批次 7（400 家）与批次 8（647+ 家动态增长）全网勾稽一致；
  - 常驻模拟服务低频节律触发（`simulation/runtime_service.py`）：按周新增 1~3 家滚动预算受控偶发入池，保持平缓自然增长；全量回归测试套件 `test_org_onboarding.py` 通过，`make check` 138 项后端与 67 项前端测试全绿。
- 前端自动化测试体系基于 Vitest 5 + @vue/test-utils 2 + happy-dom，当前包含 15 个测试文件、84 项单测，实现秒级执行与 100% 离线 Mock，覆盖：
  - `useScaleScreen.ts`：普通/全屏模式视口等比计算、clamp 范围约束、零尺寸防御与生命周期事件解绑；
  - `useAiInsights.ts` 与 `useDailyBriefing.ts`：完整状态机流转、并发节流、429 限流捕获与网络异常优雅降级；
  - `formatters/metrics.ts`：千分位与百分比格式化及各类边界数值（null/undefined/NaN/0/负数）安全保护；
  - `stores/project.ts` 与 `liveProjection.ts`：快照加载、键名递归驼峰化（fixKeys）、审计记录生成、实时投影有序应用与重置；
  - `utils/modelEvaluation.ts`：严格落实 KI-023/KI-028/ADR-0010 诚实模型判定契约（R² > 0 回归有效性、(0.5, 1.0) 分类有效性及整体 READY 判定）；
  - `utils/qualityMetrics.ts`：质量合规率、双轨一致性与困难户风险维度分布聚合纯函数运算及缺失边界防呆；
  - 六屏主面板图表：阶段矩阵与雷达结构、推广积压派生、运营规模与结果图顺序、合规缺失态、小图表禁用中心文字，以及 `AnimatedNumber` 零时长刷新不产生 `NaN`；
  - 统一面板头与缩放骨架：区号/标题/小说明保持同一行，固定画布顶部锚定，窗口与全屏尺寸变化继续由 `ResizeObserver` 和 resize/fullscreen 事件触发重算；
  - 门禁打通：`pnpm test` 正式纳入 `Makefile` 的 `frontend-check` 目标，与 typecheck 和 build 并列守护前端质量。
- 面板信息密度平衡与图表化已覆盖 A/B/C/D/E/F 屏的高收益区域：
  - **A1/C1 主面板与 B1 总览带**：A1 重构为建设/上线双进度环、实时增量、运营规模谱和风险闭环四段指挥视图，闭环率移到圆环外的明确指标位，数字组件在关闭动画后的数据刷新直接更新，避免零时长计算出现 `NaN`；C1 重构为总体上线仪表、待推进/双轨/正式上线三态比较和四项推广上下文；A1/C1 内容以分隔线组织，不再在面板内嵌同级卡框；B1 保持核心进度、任务构成与上下文总览，六屏不再强制套用同一种首屏模板；
  - **A2/A3 总览侧栏**：省域重复指标卡收敛为无中心文字的建设完成率环形进度与四项明确指标，百分比不再挤入小图标，仪表兼容接口返回的数字字符串；批次图将 100% 完成的重复批次合并，保留在推批次，并以已上线/已建设待上线/待完成单条阶段构成图展示；
  - **A4/A6 趋势与质效**：累计上线改用轻量折线、双轨运行改用柱形，移除重复快照页脚；运营质效由三张拥挤指标卡收敛为双轨主数与凭证/接口成功率横向比较图，业务量明细下沉至 tooltip；
  - **B2/B4 建设与培训**：B 屏骨架保持 12 列，B2/B4 各占 8 列承担主分析，B3/B5 各占 4 列承担排行与准备度；B2 将拥挤线条重构为 8 阶段 × 3 状态的 24 格任务矩阵，并以八轴雷达轮廓补充阶段均衡判断；B4 以四类培训应到/实到/通过/认证分组柱、培训场次构成环图和总体认证漏斗组成三图全景，避免大面板只承载少量同质数字；
  - **B5 期初数据准备度**：移除与环图图例重复的 4 个状态按钮，改为点击扇区直接按状态下钻单位台账；
  - **C2/C5 推广与联系人**：C2 明确为“各批次单位推进状态”，比较 8 个批次已上线/双轨/待推进单位构成，并以固定可见高度修复原 77px 折叠画布；联系人纯数字面板改为覆盖环图配合三项精简指标；
  - **D4 凭证质量**：原三张同权数字卡与说明横幅重构为成功率环形仪表、凭证/分录规模对比条和平均分录数结构事实，缺失异常数继续明确显示接口未提供；
  - **D1/E1/F1 领域指挥盘**：D1 用业务单据、会计凭证与接口集成规模谱配合平均明细/分录效率；E1 用真实派生合规率仪表、监督分层条和主要风险 TOP 3，缺失合规率显示 `—`；F1 移除小环中心叠字，改为独立风险总数、三类风险比较条和两项真实 AutoML 独立测试质量门禁；三块主面板均取消同级内嵌框；
  - **E4 批次合规监督**：原 8 张横排卡改为合规率折线与高风险单位柱图，扩大图表画布并减少重复序列，突出批次间差异；
  - **D3/D5/D6 运营密度**：D3 将重复标签与手绘进度条合并为四阶段横向规模图；D5 将成功率、总调用与异常数集中在左侧，右侧以成功/异常结果图比较；D6 移除易叠字的小环，改为面板唯一一致率 KPI、95% 门禁状态和一致/差异两行结果图；缺失明细继续显示明确空态；
  - **D7 数据质量金标准**：4 项规则压缩为单行状态带，主画布用于横向通过率柱状比较；真实接入快照 `quality`（`voucherBalanceErrors`、`timeOrderErrors`、`orphanLinkErrors`、`organizationsWithStatusProgression`），0 异常如实展示；
  - **F3 综合态势预警**：在确定性规则研判卡左侧新增困难户风险维度分布柱状图，直观展现准备期卡顿、双轨核对差异与建设严重滞后各维度预警单位数及集中批次，撑起版面空间；
  - **F4/F5 智能研判**：F4 两个模型改为上下质量仪表卡，正文说明下沉到悬停提示，首屏只保留真实质量、算法、目标、验证状态与两项特征；F5 将 Markdown 文字墙解析为“成效/瓶颈/行动”三列简报卡，每类首屏显示前三条且卡片悬停保留完整内容；
  - **统一图表契约**：全量走 `charts/theme.ts`（`chartPalette`、`chartInk`、`chartTooltip`、`calmAnimation`），零硬编码十六进制色值，缺失数据显示 `—`，0 值如实展示；
  - **质量缺失态修正**：D7 缺失稽核规模、异常数或状态演进数据时不再回填 100%/0 异常/2000 家，卡片与图表统一显示 `—`。
- KI-048 低效面板治理已完成代码实现、等待人工视觉验收：
  - A8 移除与 C5 重复的联系人覆盖，改为只展示接口失败、双轨差异与金标异常的聚合运营红线哨位；
  - B4 将培训三图压缩为一张参培认证漏斗，主画布改为期初数据、接口联调、双轨验证和用户培训四道上线门禁；
  - C3 移除以静态批次冒充趋势的柱线图，新增由历史推广快照派生的“日期 × 批次”上线率热力矩阵；
  - D3 移除与 D1/D2 重复的累计规模阶梯，新增由 `daily_stats` 派生的近 7 日单据/凭证增量与集成成功率趋势；
  - D7 保留紧凑规则状态带，主图由四根相同的 100% 合规柱改为带精确标签的实际核验覆盖规模比较；
  - 快照新增可选只读字段 `rolloutTrend` 与 `operationsTrend`，旧响应与数据库不可用降级路径保持兼容；没有新增 TPS、并发、金额阈值、越级审批或数据库触发器等无来源指标。
- 前端构建按库分包（`vite.config.ts` `manualChunks`）：echarts / vue 全家桶 / 地图 GeoJSON / 图标各自独立 chunk，
  业务视图 chunk 从数百 KB 降至数十 KB（改动不再让用户重下 echarts），`chunkSizeWarningLimit` 上调至 700 消除噪音。
  注：`element-plus`、`vxe-table`、`@element-plus/icons-vue` 为未使用依赖，已移除。
- F 屏 F5 已由“手动点击生成研判”改为纯展示每日自动简报（与 A 屏简报同源、零交互，读 `GET /api/insights/briefing`），
  A 屏一行摘要、F 屏按成效/瓶颈/行动结构化展示，完整条目保留于卡片提示，消除两处 LLM 研判入口的重复。
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

- 2026-09-07 记录的旧质量基线为前端 84 项 Vitest、后端 139 项 pytest；该数字作为历史增长节点保留，不再代表当前总数。
- 前端：Vue 3、TypeScript、Vite；当前 16 个测试文件、90 项 Vitest 单测、类型检查与生产构建通过。
- 后端：FastAPI、SQLAlchemy；当前 206 项 pytest 测试通过。
- Ruff 检查已清零并纳入 `make check`。
- 文档治理闸门已纳入 `make check` 与 CI：阻断已跟踪文档删除、冻结正文减损、KI 状态分裂、必需元数据缺失与现行索引漏项；核心行为变更未同步本文时直接失败，不再仅输出警告。
- CHANGELOG 从 `.git-cliff-baseline` 记录的真实公开就绪提交起计，使用锁定的 git-cliff 2.13.1 生成；质量闸门校验基线可达性、配置与生成标记，`v*` tag/人工触发工作流只上传变更日志产物，无仓库写权限。
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
