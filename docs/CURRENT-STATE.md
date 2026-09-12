# MOD 当前状态

更新日期：2026-09-13
状态：现行事实入口
适用范围：当前运行、数据、功能、质量、安全状态与操作边界

本文是项目当前事实入口。历史多 Agent 协作状态机（调度器、agent 定义、任务与交接文件）已于
2026-09-04 归档至 `archive/legacy-collaboration/`，只作历史记录保留，不再驱动开发流程。

## 现行架构

```text
访客 -> CloudFront(全球边缘, 带回源密钥) -> Nginx(校验密钥) / -> Vue 静态文件
                                                          -> /api/ -> FastAPI -> MySQL HeatWave（库 `mod`）
```

- 2026-09-11 恢复 USA 生产部署机与 JPA 专属开发机职责分离架构（ADR-0012）：
  - **JPA（开发工作区机）**：承载源码、Git 仓库、全套开发与测试工具链（`pytest`、`vitest`、`local-harness`）及本地 Osaka MySQL 开发测试库，负责通过 `publish.sh` 门禁执行远程构建发布。
  - **USA（纯生产部署机）**：承载生产运行环境，核心服务经轻量守护器统一归并为单一 `mod.service`（由 `scripts/project/run_unified.py` 同时拉起与托管 FastAPI 8100 端口与 `mod-simulator` 仿真引擎，支持一键热重载与崩溃自愈）与 MODO `modo.service`（统一托管 8000 端口与 `modo-ingest` 节点打卡），同子网局域网连接 US MySQL HeatWave（`10.0.1.25`，< 0.2ms 极速延迟），API 隔离使用 `mod_readonly` 账号。
- 访客入口经 **AWS CloudFront** 前置（隐藏源站，见下条"源站隐藏架构"）；DNS 托管在 **Google Cloud DNS**，
  站点主机名以指向 CloudFront 分发的 CNAME 记录对外解析，DNS 层查不到源站真实 IP。同时 `usa.8n8m.cfd/mod` 支持无缝跳转访问。具体域名、分发 ID、
  回源地址等见部署配置，不写入文档。
- 2026-09-11 规范与执行 Harness 升级：正式确立 `pi`（v0.85+）为统一执行底座；将长篇规约模块化解耦至 `.pi/skills/`；
  全仓确立 `mod_db_query` 免密只读查库标准及 `make pre-flight` 增量按需测试流水线。

## 当前数据规模（2026-09-11，KI-051 扩充与 KI-077 未来数据治理后）

经 KI-051（规模扩充）、KI-052（财务真实性）与 KI-077（未来数据清理与统计重算）后，全库规模与结构如下（拟真引擎生成，非真实业务数据）：

- **单位 `org_unit` 3,202 家**（在 2,000 基础上新增约 1,202 家）：状态自然分布（未启动/准备中/
  已具备双轨条件/双轨运行中/已上线/稳定运行，比例对齐存量），上线时间铺满 2023-08 至今，接续既有
  34 省 + 8 批次分层机制；新单位人员按省份分层配置。
- **人员 `sys_user` 41,098 人**：命名取自小说/影视/游戏正面或中性角色（排除负面人物）与扩充中文名库，
  重名率约 10%、知名角色名唯一、无不雅/谐音；每单位经办人齐备，无"无人经办"孤单据。
- **业务链规模（KI-077 清理与校准后）**：单据约 575 万、单据明细约 993 万、**会计凭证约 490 万**、
  凭证分录约 1,566 万、单据凭证关联约 490 万、集成结果约 481 万（成功 456 万）、双轨对账约 6,090 条（一致率约 96.1%）。
  时间分布 2023-08 至今日（2026-09-11），未来日期数据已全部清理，无单据或凭证时间跨越今日。
- **会计科目真实化（KI-052/KI-077）**：凭证分录由单一「银行存款/应付账款」重构为符合《企业会计准则》的
  多科目借贷（管理费用各明细/库存商品/在建工程/主营业务收入/固定资产清理/进项税/销项税等 15+ 科目），
  按单据类型与明细费用类别记账，含增值税进销项（招待费进项不抵扣、采购 13%、工程 9%、收入 6%）。
  **全库 490 万凭证借贷 0 不平、0 孤儿**（HeatWave 加速校验）。清理未来数据未破坏任何存量勾稽。
- **统计汇总与双轨核对治理（KI-077）**：`daily_stats` 累计汇总值已完成重算校准，彻底修复 KI-051 以来
  累计值落后历史断层；清理了 `dual_run_result` 中 2.6 万条跨越至 2027 年的未来对账数据，并在前后端
  查询中加入日期边界过滤；模拟器日配额熔断看门狗已重置恢复平稳运行（`RUNNING / SUCCESS`）。
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
  - **B 屏台账区号规范化（方案 A）**：将建设进度下钻台账中原非连续的 `B-LEDGER`、`B-T1`、`B-T2` 规范化为连续顺延编号 **`B6`**（数据准备台账概览）、**`B7`**（单位建设与期初数据台账主表）、**`B8`**（台账变更审计留痕），与主屏 B1~B5 形成统一连续编号体系。
  - **前端台账交互闭环与筛选器治理**：
    - C6（`RolloutLedgerTable.vue`）和 B7（`ConstructionLedger.vue`）台账组件建立了筛选条件响应式重置闭环。切换批次、省份、状态或搜索关键字时，强制重置 `page.value = 1`；同时对 `totalPages` 设置安全边界钳位保护（`safePage`），彻底根除翻至高页码后切换筛选导致切片越界展示假性空白的交互缺陷。
    - 工具栏重构：B7 工具栏按标准层级调整为 `[搜索框 (支持单位名/联系人/省份/批次/编码/MOD-ID 及大小写宽容匹配)] -> [批次下拉] -> [省份下拉] -> [状态下拉] -> [重置按钮]`，移除 `flex-wrap` 消除折行被面板头部遮挡导致无法点击的选择器点击穿透缺陷。
    - 状态筛选动态计数与全生命周期补齐：状态下拉框重构为从 `store.entities` 动态派生带真实实体计数的选项列表（包含 `全部状态`、`未启动`、`准备中`、`建设中`、`双轨运行`、`已上线`），补齐类型系统与抽屉对 `未启动` 的支持；B5 饼图下钻使用独立的 `readinessStatus` 筛选，不再把数据准备状态错误映射成单位生命周期状态。
  - **大盘快照异步双缓冲与预热（SWR）**：改造快照缓存机制为 Stale-While-Revalidate（SWR）模式，消除 60s TTL 到期时同步穿透全库重新计算造成的 1.12s 阻塞；服务启动（lifespan）通过 `prewarm_snapshot()` 触发异步快照装载，前台 API 响应恒定控制在毫秒级（< 100ms），严格保障全场景 < 1.0s 的 SLA 红线。
  - **快照预热慢查询卡死与过期 fallback 修复（KI-061，DONE）**：
    - **日期锚点索引优化**：将 `LATEST_COMPLETED_DOCUMENT_DATE_SQL` 从全表扫描的 `MAX(DATE(submit_time))` 优化为索引友好的 `DATE(MAX(submit_time))`，借助 `idx_doc_submit_time` 消除 RAPID 587 万行全表聚合扫描，查询耗时由 >60 分钟降至 <1ms（实测 0.75ms）。
    - **SWR 状态机有界失败与熔断**：为后台快照构建独立连接增加会话级超时 `SET SESSION max_execution_time = 15000`，新增刷新超时（20s 自动释放重置）与失败退避（15s 防风暴重试）机制；使用 daemon 线程保障服务停止在 systemd 5 秒内退出。
    - **fallback 数据契约对齐**：补齐前后端 fallback 快照（`v2-sim-snapshot.json`）的 `rolloutTrend`、`operationsTrend` 及 `operations` 双轨明细字段（`dualRunConsistent`、`dualRunInconsistent`、`dualRunConsistencyPct`、`integrationSuccess`、`integrationFailed`），消除降级时 C3、D3、D6 面板假性空白。
    - **健康探针与发布门禁收紧**：`/api/health` 增加 `snapshot` 元数据（含 `source`、`status`、`last_refreshed_at`、`last_refresh_duration_ms`、`last_error`、`is_stale`、`consecutive_failures`）；`/api/dashboard/refresh-meta` 严格根据 `_snapshot_source` 真实返回 `data_version`（`live` 或 `frozen`）与 `status`（`ok` 或 `fallback`），禁止仅凭 DB 连接存在谎报 `live`；`publish.sh` 增加 C3/D3/D6 字段完整性发布门禁。
  - **前端零转圈策略（`stores/project.ts`）**：store 初始即用内置兜底快照（`data/v2-sim-snapshot.json`）预填 `snapshot`/`entities`，`loading` 初值为 `false`；`refresh()` 仅在「完全没有任何可展示数据」时才置 `loading`。因兜底数据恒存在，首屏与轮询刷新（含后端快照冷启动 >1s 的极端情形）都走静默替换，顶栏刷新指示与各屏内容区均不出现转圈/白屏。轮询刷新沿用 `silent=true`。六个屏幕（A~F）共享同一 store 快照渲染，切屏不重新请求、无独立整屏加载态；F 屏「每日简报」「风险解释」为局部按需小加载态，不影响整屏。
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
  - 访客经 Google Cloud DNS CNAME → CloudFront 分发 → 回源到一个隐蔽回源域名（DNS-only，指向源站），回源协议 https-only。
    （具体站点域名、分发 ID、回源域名、源站 IP 均见部署配置，不入文档。）
  - **回源密钥防绕过**：CloudFront 回源时注入一个自定义密钥头；源站 Nginx 校验该头，
    无正确密钥的请求（即绕过 CloudFront 直连源站 IP 或回源域名）一律 403。密钥值只存源站 Nginx 与 CloudFront 配置，不入库不入代码。
  - 效果：对站点主机名做 DNS 查询只见 CloudFront 的 IP、查不到源站；直连源站 IP / 回源域名均被 403；仅 CloudFront 回源可达。
  - 证书：viewer 侧用 us-east-1 的 ACM 证书（CloudFront 强制证书位于 us-east-1）；缓存策略 CachingDisabled
    （大屏数据动态 + SSE 实时，全站不缓存以保证正确性）；SSE 实时投影经 CloudFront 实测正常（回源超时 60s + 转发 Host 头）。
  - DNS 托管于 Google Cloud DNS（zone `fumingname`），CNAME 记录平稳指向 CloudFront 分发，解析延迟低且具备 Google 全球 Anycast 稳定性。
- DNS 安全：CNAME 经 Google Cloud DNS 权威托管，CloudFront 全球边缘 HTTPS/TLS 1.3 终结，结合源站 Nginx 自定义回源 Secret 头校验，防 DNS 劫持与源站探测。
- 反检索/反抓取（内部交流系统，谢绝一切采集）：三层防护叠加——`robots.txt`（`Disallow: /` 且显式点名 GPTBot/ClaudeBot/
  PerplexityBot/Google-Extended/Baiduspider 等 AI 与搜索爬虫）、HTML `<meta robots/googlebot/bingbot noindex,nofollow,noarchive,nosnippet,noimageindex>`、
  HTTP 响应头 `X-Robots-Tag` 同值；并在 Nginx 层按 `User-Agent` **硬拦截** AI/检索爬虫直接返回 403（不返回任何内容），
  正常访客不受影响。robots/meta 为君子协定，Nginx UA 拦截为强制层。
- V2 六屏驾驶舱、只读 `/api/v2`、34 省地图和无刷新轮询已经实现。
- 大屏中央主标题与浏览器 `<title>` 统一为「业务系统建设推广大屏演示」（`App.vue` 顶栏 `header-main-title` 与 `frontend/index.html`）。
- 前端路由采用 hash 模式（`createWebHashHistory`），URL 形如 `https://<域名>/#/a`；刷新任意屏不依赖
  服务器 fallback、永不 404。菜单从左到右严格 A→B→C→D→E→F（/d=业务运营 OperationsView、/f=风险预警 InsightsView），
  路由/组件/zone/标签/跳转全对齐。
- 浏览器全屏模式保留顶部六屏导航、在线状态、时钟、刷新与退出全屏控制；内容画布继续按导航下方
  `command-main` 的真实尺寸等比缩放，并采用水平居中、顶部锚定；宽高比不一致产生的余量留在底部，
  不再隐藏菜单、按整块物理屏幕高度覆盖导航空间或在标题栏下留出大块空白。
- 驾驶舱实时投影只尾随常驻模拟器事务提交后追加的本机持久日志，通过 SSE 播报单据、凭证和集成事件；
  数据库快照仍是累计数字唯一事实源，前端会话脉搏不再与快照相加。当前只支持同机单 API 进程，尚无共享
  outbox、跨实例消费者位点或完整重连续播保证，具体边界见 `development/LIVE-PROJECTION.md`。
- 拟真引擎第一步（技术验证载体）已落地（`backend/app/simulation/`）：实现费用报销剧本（`ExpensePlaybook`）多表完整足迹生成与安全写库器（`SimulationWriter`），单事务原子落库 6 张表（`business_document`、`business_document_line`、`accounting_voucher`、`accounting_voucher_line`、`document_voucher_link`、`integration_result`）并级联同步 `daily_stats`；以存量治理成果为硬约束（时间线接续存量最新日期只向前生长、经办人 100% 命中本单位名录、仅限已上线单位门禁、只增不删、零 schema 变更、运行审计留痕）；开关 `MOD_SIMULATION_ENGINE_ENABLED` 默认关闭（`false`）；已通过 100 笔小试落库实测，KI-017 零回归。
- 拟真引擎第二步（建设管控主线 + B模式生命周期推进器）已落地并已实测写库（`backend/app/simulation/` 与 `archive/legacy-scripts/agy/run_step2_batch_write.py`）：
  - 核心模块：实现 7 类建设管控剧本生成器（入池、数据准备、培训认证、接口联调、双轨核对、跃迁评审、批次推进，`construction_playbooks.py`）、6 阶段生命周期状态机推进器（`lifecycle_advancer.py`，严格执行“只进不退、持续达标 N 天才跃迁、跃迁评审留痕快照”三条铁律）、快慢电影演进协调器与矛盾咬合机制（`evolution_coordinator.py`，~4% 自然涌现困难户与决策支撑风险视角 100% 咬合自洽）、建设安全事务写库器（`construction_writer.py`）；
  - 严格分批写库落地：经主控授权，使用独立可控批量写库脚本（`archive/legacy-scripts/agy/run_step2_batch_write.py`）执行 2026-09-05 建设主线业务足迹真实落库。写前自动对 7 张受影响表生成全量快照备份（`scripts/agy/output/backups/construction_backup_20260905_131434.json`，43.37 MB），按 2,000 行/批分 3 批逐批 commit（单事务单批次），实时打印进度与 ID 区间，累计安全写入 4,178 行；
  - 当前数据规模：`org_unit` 2,000 家（未启动 760、准备中 238、已具备双轨条件 49、双轨运行中 205、已上线 282、稳定运行 466）；`construction_task` 62,104 行（新增 2,194 行）；`rollout_status_snapshot` 144,870 行（新增 20 行带专家决议留痕快照）；`training` 5,520 行（新增 476 行）；`dual_run_result` 30,288 行（新增 1,230 行）；`data_readiness` 2,000 行（238 行同步更新）；
  - 验收脚本隔离与零回归：验收脚本（`archive/legacy-scripts/agy/verify_step2_dry_run.py`）严格保持纯只读，与写库入口彻底分离，杜绝验收重复写库。写后 8 条硬闸门全量复测 100% PASS，KI-017 零回归。
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
  - 模型解释来源显式化：接口使用 `explanationSource` 区分真实 `HEATWAVE_SHAP`、后端可追溯规则 `RULE_BASED` 和 `UNAVAILABLE`；只有第一类可标示 SHAP，前端不再伪造权重或现场指标；
  - 库内批量预测评分完成（各 2,000 行），元数据全量落库 `ml_model_metadata` / `ml_training_log`，`/api/insights/status` 状态晋升为 `READY`；
  - 前端归因透出联动：`AtRiskUnitTable.vue` 按来源展示模型解释、规则研判或不可用空态，切换单位采用缓存与 latest-wins；`InsightsView.vue` 分别展示真实可用模型数量并如实保留负 R²。HeatWave AutoML 的能力清单与边界见 [HeatWave AutoML 能力与边界手册](development/HEATWAVE-AUTOML-CAPABILITIES.md)。
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
  - 常驻模拟服务低频节律触发（`simulation/runtime_service.py`）：按周新增 1~3 家滚动预算受控偶发入池，保持平缓自然增长；全量回归测试套件 `test_org_onboarding.py` 通过，`make check` 全绿（后端/前端测试数量以 `make check` 实时输出为准，不在文档中手写以免失真）。
- 前端自动化测试体系基于 Vitest 5 + @vue/test-utils 2 + happy-dom（测试文件与用例数量以 `make check` 实时输出为准），实现秒级执行与 100% 离线 Mock，覆盖：
  - `useScaleScreen.ts`：普通/全屏模式视口等比计算、clamp 范围约束、零尺寸防御与生命周期事件解绑；
  - `useInsightsStatus.ts` 与 `useDailyBriefing.ts`：只读轮询、卸载停表与网络异常优雅降级；
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
  - **A/B/C 面板面积再平衡**：A2/A3 改为固定具名行比分配并扩大密集的 A3，A4 收敛为紧凑趋势区；B 屏上排 B2/B3 扩大、下排 B4/B5 略缩；C3 改为左侧 8 列跨两行的主分析画布，C4/C5 在右侧 4 列上下叠放，C4 删除与排行图重复的摘要卡，C5 收为小环图配三行指标。A 屏 AI 简报始终预留固定高度且内容居中，异步返回只填充槽位、不再下压主体画布；
  - **A4/A6 趋势与质效**：累计上线改用轻量折线、双轨运行改用柱形，移除重复快照页脚；运营质效由三张拥挤指标卡收敛为双轨主数与凭证/接口成功率横向比较图，业务量明细下沉至 tooltip；
  - **B2/B4 建设与培训**：B 屏骨架保持 12 列，B2/B4 各占 8 列承担主分析，B3/B5 各占 4 列承担排行与准备度；B2 将拥挤线条重构为 8 阶段 × 3 状态的 24 格任务矩阵，并以八轴雷达轮廓补充阶段均衡判断；B4 以四类培训应到/实到/通过/认证分组柱、培训场次构成环图和总体认证漏斗组成三图全景，避免大面板只承载少量同质数字；
  - **B5 期初数据准备度**：移除与环图图例重复的 4 个状态按钮，改为点击扇区直接按状态下钻单位台账；
  - **C2/C5 推广与联系人**：C2 明确为“各批次单位推进状态”，比较 8 个批次已上线/双轨/待推进单位构成，并以固定可见高度修复原 77px 折叠画布；联系人纯数字面板改为覆盖环图配合三项精简指标；
  - **D4 凭证质量**：原三张同权数字卡与说明横幅重构为成功率环形仪表、凭证/分录规模对比条和平均分录数结构事实，缺失异常数继续明确显示接口未提供；
  - **D1/E1/F1 领域指挥盘**：D1 用业务单据、会计凭证与接口集成规模谱配合平均明细/分录效率；E1 用真实派生合规率仪表、监督分层条和主要风险 TOP 3，缺失合规率显示 `—`；F1 移除小环中心叠字，改为独立风险总数、三类风险比较条和两项真实 AutoML 独立测试质量门禁；三块主面板均取消同级内嵌框；
  - **E4 批次合规监督**：原 8 张横排卡改为合规率折线与高风险单位柱图，扩大图表画布并减少重复序列，突出批次间差异；
  - **D3/D5/D6 运营密度**：D3 将重复标签与手绘进度条合并为四阶段横向规模图；D5 将成功率、总调用与异常数集中在左侧，右侧以成功/异常结果图比较；D6 移除易叠字的小环，改为面板唯一一致率 KPI、与生命周期同源的 98% 门禁状态和一致/差异两行结果图；缺失明细继续显示明确空态；
  - **D7 数据质量金标准**：4 项规则压缩为单行状态带，主画布用于横向通过率柱状比较；真实接入快照 `quality`（`voucherBalanceErrors`、`timeOrderErrors`、`orphanLinkErrors`、`organizationsWithStatusProgression`），0 异常如实展示；
  - **F3 综合态势预警**：在确定性规则研判卡左侧新增困难户风险维度分布柱状图，直观展现准备期卡顿、双轨核对差异与建设严重滞后各维度预警单位数及集中批次，撑起版面空间；
  - **F4/F5 智能研判**：F4 两个模型改为上下质量仪表卡，正文说明下沉到悬停提示，首屏只保留真实质量、算法、目标、验证状态与两项特征；F5 将 Markdown 文字墙解析为“成效/瓶颈/行动”三列简报卡，每类首屏显示前三条且卡片悬停保留完整内容；
  - **统一图表契约**：全量走 `charts/theme.ts`（`chartPalette`、`chartInk`、`chartTooltip`、`calmAnimation`），零硬编码十六进制色值，缺失数据显示 `—`，0 值如实展示；
  - **图例空间统一**：A3/A4、B4、C2/C4、D3、E4 等笛卡尔图表的图例移入面板标题行，窄面板仅显示带悬停说明的颜色块，不再占用图内顶部或切割绘图区右侧；A2 与 B5/C5 等环图保持图形在左、精确读数或图例在右；
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
- 本地前端全局样式已收敛为 `styles/theme.css`、`base.css`、`shell.css`、`blocks.css` 四层：
  `foundation.css`、`components.css`、`utilities.css`、`page-hierarchy.css`、`dashboard-topbar.css`、
  `responsive-breakpoints.css` 及其中约 120 条无引用规则已删除，地图与投影指示器样式内聚到各自组件。
  Token 单一来源收敛为 `theme.css` 的 `@theme`：`:root` 下的 `--c-*`/`--text-*`/`--space-*`/`--radius-*`
  旧变量体系已全部删除，文字与信号色改用 Tailwind 内置 slate/sky/emerald/amber/rose，字号只保留
  `cockpit-*` 固定阶梯；图表色统一取自 `charts/theme.ts`（新增 `mapRamp`、`chartInk.textDim/onAccent`），
  地图实时光圈与浮条由调色板外的荧光青改为 sky-400。未被引用的 `AnimatedProgress.vue`、`MarkdownLite.vue`
  已删除。新增 `scripts/project/lint_frontend_styles.py` 闸门（样式文件集、色值位置、旧变量、媒体查询位置、
  死选择器、`@reference`）纳入 `make check` 与 CI。待发布并需人工视觉验收。
- 本地台账层已去重：C6/B7/F 屏三个表格组件的搜索框、筛选下拉、分页条、调态抽屉收敛为
  `components/ledger/` 四个物料，分页状态机、抽屉编辑、省份/批次/状态顺序表与带计数选项构造分别
  收敛为 `usePagedList`、`useEntityEditor`、`utils/entityOptions.ts`（均配套单测），三组件由 1234 行降至
  约 790 行；`AtRiskUnitTable` 补齐总页数收缩到 0 时的最小页钳位。待发布。
- 本地 C/D/E/F 屏已收敛到积木库：新增 `blocks/CommandBand`、`NoteBanner`、`EmptyNote`，`MetricGrid`/`StatList`
  增加 `flat` 平铺形态，`StatusList` 增加 `wrap`；四屏手写的指挥带栅格、事实栏、D7 核验四卡、F3 告警卡、
  F4/F5 提示条与六处空态全部改为积木 + 数据映射，四视图由 1462 行降至约 1220 行。E 屏合规监督与
  F 屏困难户的风险判定收敛为 `utils/riskRules.ts` 单一来源（配套单测），E5 清单改用台账物料并补齐
  筛选变动回第 1 页；F3 页脚门禁文案改为读取 `businessRules`（此前硬编码 95% 与实际 98% 门禁不一致）。
  已用无头 Chromium 在 1920×1080 下对 C/D/E/F 四屏做渲染冒烟，无控制台错误。待发布并需人工视觉验收。
- 本地前端展示格式化已收口到 `formatters/metrics.ts`：新增 `formatDateTime`（顶栏时钟、AI 生成时间、
  台账审计时间共用），视图/组件/图表 tooltip/store 中 30 余处 `toLocaleString`/`Intl.*` 全部改为
  `formatCount`/`formatDateTime`，数字展示统一 zh-CN 千分位、空值统一 `—`。待发布。
- 本地后端单位状态词表已收口到 `backend/app/business_rules.py` 单一来源：`ORG_LIFECYCLE_STAGES`/
  `BATCH_LIFECYCLE_STAGES`（原 `simulation/construction_models.py` 定义处改为转引）、`LAUNCHED_STATUSES`
  「已上线族」、`ACTIVE_BUSINESS_STATUSES`、数据库六态→前端五态的 `DISPLAY_STATUS_MAPPING`（原散在
  `dashboard_sections.py`）、SQL 片段 `SQL_LAUNCHED_STATUSES` 与三处重复的推断批次 `SQL_INFERRED_BATCH_ID`；
  `dashboard.py`/`dashboard_sections.py`/`heatwave_sql.py`/`simulation/engine_context.py`
  中 40 余处状态字面量改为引用常量，`public_business_rules()` 新增只读 `orgStages`/`launchedStatuses`。
  新增 `tests/test_business_rules.py` 契约测试（词表有序唯一、映射覆盖全部状态、SQL 模块禁止散写状态
  字面量）。未改变任何 SQL 语义。待发布。
- 本地 D7/F3/F5 去模板化：新增积木 `blocks/BriefingList`，F5 每日简报由三列彩色底卡+截断改为纵向分节全文
  展示；D7 核验卡去掉无语义的进度轨与胶囊标签；F3 分布图去掉面板内底卡并隐藏与柱标重叠的坐标刻度。
  已在 1920×1080 无头渲染核对，无控制台错误。待发布并需人工视觉验收。
- 本地后端 KI-027 补遗：`PageV2→Page`、`build_dashboard_snapshot_v2→build_dashboard_snapshot`，docstring/错误消息中
  残留的 `/api/v2/`、`V2`、`USA` 字样清除，删除无引用死 schema `RefreshMeta`/`Overview`；因 `scripts/kiro/run_daily_briefing.py`
  （生产简报定时任务）仍按旧名导入且目录归 Kiro，`dashboard.py` 暂留一行兼容别名，待 Kiro 迁移后删除。待发布。
- 本地删除旧「五层模型」模拟器死代码：`backend/app/business_simulator.py`、`backend/app/simulator_config.py`、
  `simulation/models.py` 及其专属测试 `test_business_simulator.py`（约 1,400 行）。三者未被 `main.py`、任何 systemd
  服务或 `simulation/runtime_service.py` 引用，仅被自身测试引用；环境变量 `MOD_SIMULATOR_ENABLED`/`MOD_DB_WRITE_URL`
  随之从 `.env.example` 移除（生产 `.env.systemd` 中的同名行已无读取方，可在下次运维时清理）。现行拟真引擎
  唯一入口为 `scripts/agy/run_simulator_service.py` → `simulation/runtime_service.py`，门禁 `MOD_SIMULATION_ENGINE_ENABLED`。
  注：`scripts/kiro/ki051_stage2_parallel.py`（KI-051 已完成的一次性脚本，Kiro 目录）曾导入 `simulation.models.TimePatternSystem`，
  若需重跑须由 Kiro 自行调整。pytest 249→230。待发布。
- 本地后端异常处理收口：Ruff 新增 `S110`/`SIM105` 闸门（`backend/pyproject.toml`），`backend/app` 内 15 处
  `try/except: pass` 全部处理——连接关闭/任务取消等清理型改为 `contextlib.suppress`（看门狗行解析收窄为
  `IndexError/TypeError/KeyError`），`heatwave_ml.py` 中评分表读取失败、SHAP 归因失败由静默变为 `warning` 日志
  （只记异常类名），`prediction_json` 解析收窄为 `ValueError/TypeError/AttributeError`。行为不变，可观测性提升。待发布。
- 本地拟真引擎 `simulation/` 首次纳入 Ruff 闸门（`make check`），清零 34 项：修复 `pool_onboarding.py` 未导入 `Tuple`
  的真实 `NameError` 隐患（类型注解在运行期求值路径）、5 处分号多语句、4 处 `l` 歧义变量名、1 处未用变量；13 处
  `try/except: pass` 按同一原则处理——语料资产加载失败改为 `warning`、失败审计自身失败改为 `warning`、AI 响应 JSON
  提取收窄为 `JSONDecodeError`、临时文件 unlink/chmod 收窄为 `OSError`、错误路径 rollback 用 `suppress(Exception)`。待发布。
- 前端状态词表已与后端四态对齐：`RolloutStatus` 去掉幻影「建设中」，`EntityRow.rawStatus` 与 `api.py` 的 `rawStatus` 过滤死分支一并删除；后端新增 `CONSTRUCTION_CRITICAL_RATE`/`DISPLAY_STATUSES` 并通过 `businessRules.risk.constructionCriticalRate`/`lifecycle.displayStatuses` 下发。建设滞后只评估「双轨运行」，准备中走「准备期卡顿」，合规标签枚举加入「准备期卡顿」；F3 风险维度门禁文案与高危数由规则和单位级判定派生；「正式上线」口径统一为「已上线」。
- A 屏规则告警（`insights.ruleBasedAlerts`）由 `dashboard_sections.compose_rule_based_alerts(rollout_rows, voucher_success_pct)` 从批次推进事实派生：双轨批次家数与加权建设度、已推进批次上线家数与占比、在建/储备批次进度均取自 `rollout_rows`，不再写死「91.9%」「400 家 62.7%」「全量投产」等与真数据矛盾的字面量。前端 `overview` 类型去掉后端不返回的 `leadershipAttention`，补 `issuesSummaryText`/`batches`；删除无引用的 `frontend/src/data/sim-snapshot.json`。
- A3 批次推进阶梯改为「建设完成度」「上线率」两条并列条形，不再把分母不同的两项指标堆叠在同一根条里；E 屏批次合规率在批次无单位时返回 `null`（图上留空），不再用 `|| 1` 兜底成 100%；`LiveActivityTicker` 删除三条虚构 fallback 活动，接口为空时显示「暂无治理活动记录」并隐藏翻页控件；F 屏高危单位数按单位级 `riskLevel` 统计。
- 数据源徽标如实：`/api/dashboard/snapshot` 响应新增 `meta.source`（live/fallback），前端 `dataSource` 据此判定，不再把 SWR 返回的兜底缓存当作真库数据。前端删除无任何视图消费的 `useAiInsights.ts`（生成按钮状态机、action token、`/insights/latest` 拉取共 180 行）及其测试，改为 40 行类型化 `useInsightsStatus.ts` 只读轮询 `/api/insights/status`（`InsightsStatus` 类型覆盖 `hw_ml`/`predictions`/`cf_ai`，`InsightsView` 去掉全部 `as any`）；`DashboardView` 首屏动效定时器与 `ChinaMap` 横幅定时器在卸载时清理。
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
- 前端：Vue 3、TypeScript、Vite；当前 23 个测试文件、112 项 Vitest 单测、类型检查与生产构建通过。
- 后端：FastAPI、SQLAlchemy；当前 230 项 pytest 测试通过（新增 KI-065 对称走势快照测试，全量离线测试 100% 通过）；KI-060 已将 Starlette `TestClient` 的开发依赖
  从已弃用的 `httpx` 回退路径迁移至精确锁定的 `httpx2==2.12.0`，并将对应弃用警告设为测试失败。
- 大屏图表细节优化（KI-065，DONE）：
  - 全屏 Tooltip 越界治理：`charts/theme.ts` 的 `chartTooltip` 基线统一加入 `confine: true`，`RolloutView.vue` 与 `ChinaMap.vue` 补齐该约束，确保全屏 28 处图表在面板边缘悬浮时不溢出面板容器、不被相邻卡片遮挡。
  - A4 时间轴居中：`backend/app/services/dashboard.py` 优化走势快照窗口构建算法，剔除增量试点噪声（`HAVING COUNT(*) > 100`），构建以今日（09-09）为中心的 7 节点对称时间窗（3 过去 + 今日居中 + 3 未来），`OverviewTrendChart.vue` 配套增加对称截窗逻辑，今日刻度稳定落在横轴中间。
  - C5 覆盖率环图去字留白：`charts/panelOptions.ts::createCoverageOption` 移除环心标题与“单位覆盖率”文字，避免在小尺寸环图内挤占重叠，数值与分布改由受限 Tooltip 呈现。
- 风险派生数据真实性与界面体验优化（KI-066 / KI-067，DONE）：
  - E/F 屏风险真实派生（KI-066）：`backend/app/services/dashboard_sections.py::build_entities` 引入 `dual_run_result` CTE 预聚合，派生各单位真实凭证一致率（`voucherRate`），不再恒为 `None`；E 屏与 F 屏「双轨核对差异」与「借贷试算不平风险」维度恢复正常触发与自愈能力，单次聚合查询维持在 ~40ms 亚秒级。
  - 金标稽核诚实性重构（KI-066）：`backend/app/services/dashboard.py` 将未执行全量离线扫表的借贷平衡、时序逻辑与孤儿链路 3 项异常数由硬编码 `0` 改为如实上报 `None`，恪守 KI-023 诚实性纪律，前端优雅降级展示为 unknown 灰色状态与 `—`；保留第四项经真库日结核验的组织状态演进追踪（`org_total`）。
  - E 屏与 A1 语义分工澄清（KI-066）：E 屏 E5 面板副标题明确“单位指标态现场判定（阈值派生）与治理工单处置流转”分工；A1 顶部总览将演示投影会话计数澄清为「实时集成脉搏」，并采用 sky-400 色调与真库今日增量（emerald-400）进行视觉区隔。
  - B2 雷达图 Tooltip 补齐百分号（KI-067）：`frontend/src/charts/constructionOptions.ts::createTaskStageRadarOption` 增加自定义 formatter，各阶段完成率读数规范补齐 `%` 后缀，语义严谨。
  - D7 数据质量金标准面板界面重构：`frontend/src/views/OperationsView.vue` 将四项金标准规则重构为左侧 7 列 2x2 科技感指标矩阵排布（含借贷平衡、时序逻辑、孤儿链路、状态演进），强化数字字号、合规率微型进度条与状态色标；右侧 5 列对齐承载实际核验覆盖规模条形图，不更改任何指标读数与展示内容，全面提升大屏视觉美感与信息层级。
  - E 屏布局流向优化：`frontend/src/views/IssuesView.vue` 将治理自愈动态广播流（`LiveActivityTicker`）从屏顶移至 E1「合规监督指挥盘」下方，首屏顶部优先展现全网合规大盘与 TOP3 风险维度，紧随其后呈现动态自愈事件流。
- 双轨运行真实性演进落地与对账维度穿透（KI-053，DONE P3）：
  - 真实财务差异语料化（`simulation/construction_models.py`）：建立三大对账类别 15 组高保真专业语料库（`DUAL_RUN_DIFFERENCE_REASONS`，涵盖总账汇率截断时差、跨期预付账款挂账重分类、资产折旧尾差等真实事由），底表模型扩展 `difference_reason` 字段并落实勾稽校验；
  - 财务周期强节律机制（`simulation/construction_playbooks.py`）：引入月末结账期（自然月 26~31 日及月初 1~2 日）差异与核对量自然脉冲逻辑，动态匹配《差异专项排查与单边冲销》或《月末试算平衡核验》建设任务；
  - 驾驶舱 D6 细分对账穿透（`backend/app/services/dashboard.py`，`OperationsView.vue`）：后端扩展 `dualRunBreakdown` 细分维度统计，前端 D6 面板在一致率仪表下直观呈现月末科目余额（92.5%）、凭证借贷汇总（93.2%）与单据金额（92.7%）三大核心财务对账通过率；
  - 测试套件全量覆盖：231 项 pytest 与 112 项 Vitest 自动化测试 100% 通过。
- 双轨核对一致率分子分母同源闭环（KI-069，DONE P2）：
  - 根因消除（`backend/app/services/dashboard.py`）：将 `dualRunConsistencyPct` 与 `dualRunResult` 的计算分母由 `daily_stats.dual_run_count` 滞后快照修正为 `dual_run_result` 实时聚合总数（`dual_consistent + dual_inconsistent`），分子分母严格同源，彻底杜绝线上因模拟器增长导致一致率超过 100%（如 102.65%）的穿帮缺陷；
  - 前端防御性收敛（`frontend/src/utils/qualityMetrics.ts`）：`calcDualRunConsistency` 增加 `safeTotal = Math.max(total, c)` 防护，确保大屏仪表一致率数值恒定在 `[0, 100]` 区间，并与 D6 穿透细分口径完美对齐；
  - 勾稽与测试：全库行数 `full_rows` 同步使用实时 `dualRunResult`，新增前后端回归测试断言，`make check` 全绿。
- 矛与盾攻防博弈与合规治理引擎（GI-004 & KI-062/KI-063 治理闭环）：
  - 昼夜作息与月末生物钟（GI-004，`simulation/governance_state_machine.py`）：引入 $k_{\text{rhythm}}$ 节律因子，工作日早晚黄金工段 1.8x 加速、午间 0.5x 放缓、夜间 22:00-07:00 彻底冻结（杜绝半夜出具验收通报虚假繁荣）、月末 25 日起叠加 1.5x 冲刺乘数，二次核验返工率动态适配。
  - 30~45 单动态平衡走廊（GI-004，`simulation/construction_propeller.py`）：实时感知未结案库存；低于 35 单时提升阻力暗礁触发率至 50% 并放缓消缺，高于 45 单时降低阻力触发率至 5% 并加速消缺，确保大盘恒定平稳呼吸，告别全绿死水与人工干预。
  - 跨屏因果涟漪网络（GI-004，E $\to$ B $\to$ C/D）：工单闭环后治理推进器只修复建设指标和阻力；单位状态必须继续由唯一 `EvolutionCoordinator/LifecycleAdvancer` 按正式门槛评审跃迁，不再由推进器直接跳到双轨运行。
  - 治理实时广播与展厅智能巡航（GI-004，`LiveActivityTicker.vue`, `KioskSpotlightTour.vue`）：E1 下方暗黑科技风走字流动态轮播专班一线处置流水；空闲 45 秒无感激活展厅聚光灯巡航 HUD 浮窗，任意交互瞬时淡出。
  - 实时治理动态接口（GI-004，`GET /api/governance/recent-activities`）：以毫秒级 SLA 供给最新工单事件流。
  - 测试套件离线自洽与凭据脱敏（KI-063）：移除了测试与代码中硬编码的内网 IP 与账号默认值，构建内存 `MockLedgerConnection` 与隔离 Mock 消除测试对真实生产库的直连与写库操作，完全符合 ENFORCEMENT 闸门 A/B 要求。
  - 模拟主循环编排收敛（KI-062/KI-072，`simulation/runtime_service.py`）：治理推进器、涓流回填和正式六阶段 `EvolutionCoordinator` 共用慢周期，由运行时独占业务事务提交权；建设成功审计在提交后记录，生命周期长期状态另行原子持久化，恢复失败进入 fail-closed。
  - 数据库就绪三张治理与配额审计表：`governance_issue`（存量 45 单）、`issue_timeline`（存量 139 条流水）、`sim_ai_quota_ledger`（日级看门狗流水账）。
  - 盾（`simulation/governance_state_machine.py`）：六态治理有限状态机、容量为 8 的专家专班调度池、15% 严苛二次返工回路、五大行业高拟真离线叙事库。
  - 矛（`simulation/construction_propeller.py`）：批次推进与阻力陷阱动力学，结合消缺解冻与推进器协同。
  - 配额看门狗（`simulation/quota_watchdog.py`）：按 HKT 业务日使用数据库行锁在外部调用前预留、调用后结算，项目侧预算为每日 3,000 Neurons；该预算闸门不等同于云厂商计费上限，也不承诺账单恒为零。
  - AI 算力挂接与零故障降级（`simulation/cf_ai_client.py`）：接入 Cloudflare Workers AI，异常或断网时平滑降级至本地离线叙事库。
  - 涓流回填流水线（`simulation/trickle_backfill.py`）：受控微批量（≤3 单）异步富化存量工单与时间线，实现历史数据真实有机充填。
  - 治理与配额端点（`backend/app/api.py`, `backend/app/services/governance.py`）：提供工单分页查询、详情透视、全景时间线、一键督办（`POST /api/governance/issues/{id}/dispatch`）、配额透视（`GET /api/governance/ai-quota`）以及单工单 AI 富化（`POST /api/governance/issues/{id}/enrich`）。
  - 前端 E/F 屏双向交互抽屉（`ComplianceInspectDrawer.vue`, `AiQuotaCapsule.vue`）：E 屏提供六态流转 Stepper、专班展示、多节点流水展示、一键督办与 AI 深度研判；终态禁止继续写操作且请求按最新目标隔离。F 屏胶囊展示项目侧每日预算状态，不把它描述为云账单保证。
  - 编号口径与线上追踪（KI-064）：治理仿真的 "GI-001~GI-004" 是文档「演进代际」叙事编号，与 GitHub Issue 真实编号 `#1~#4` 不逐一对应，权威映射见 [GOVERNANCE-SIMULATION-SYNTHESIS.md](development/GOVERNANCE-SIMULATION-SYNTHESIS.md) 第一章。承载上述能力的 GitHub Issue `#1`/`#2`/`#3`/`#4` 均已随生产发布 `20260909-095536` 上线并以 `completed` 回写关闭，当前线上无 open issue；KI（本地缺陷看板）与 GI（GitHub 新功能）分轨管理沿用 AGENTS.md 四铁律。
- Ruff 检查已清零并纳入 `make check`。
- 文档治理闸门已纳入 `make check` 与 CI：阻断已跟踪文档删除、冻结正文减损、KI 状态分裂、必需元数据缺失与现行索引漏项；核心行为变更未同步本文时直接失败，不再仅输出警告。
- CHANGELOG 从 `.git-cliff-baseline` 记录的真实公开就绪提交起计，使用锁定的 git-cliff 2.13.1 生成；质量闸门校验基线可达性、配置与生成标记，`v*` tag/人工触发工作流只上传变更日志产物，无仓库写权限。
- 本地 Git hooks 已强制执行凭据扫描、`make check` 和提交信息格式；GitHub Actions workflow 已在仓库
  落地，远端启用后在拉取请求和推送中复用同一闸门，不包含部署或生产访问。
- 本目录已开始采用 Git 管理；大体积 CSV、原始参考材料、构建产物和本地密钥不纳入版本库。

KI-060 更新前的本节原文完整保存在
[2026-09-08 本地质量基线更新前快照](history/2026-09-08-本地质量基线更新前快照.md)。

## KI-070~074 本地整改状态（2026-09-09）

本轮只修改本地代码、测试、文档和发布门禁，未写生产数据库、未启停服务、未调用外部 AI、未发布：

- [KI-070](issues/KI-070-驾驶舱跨屏业务口径与交互状态不一致.md)：业务门槛改由快照统一下发；B5 与 C4
  下钻口径、治理抽屉并发/终态、快照 latest-wins、fallback 来源以及 1920×980 缩放契约已完成本地修复。
- [KI-071](issues/KI-071-F屏模型就绪与SHAP归因来源失真.md)：模型数量、负 R²、解释来源、缺失指标和请求乱序
  已完成本地修复；未创建、重训或调用生产 HeatWave 模型。
- [KI-072](issues/KI-072-常驻模拟器生命周期编排事务与安全状态未闭环.md)：六阶段编排、事务所有权、重启状态、
  原子限流、配额预留和状态/发布门禁已闭环；新增 MySQL `GET_LOCK` 数据库级领导锁与 STANDBY 备用状态防止双实例并发写入；2026-09-13 代码已部署至 USA 生产节点并通过线上探针验证，已满足验收并关闭为 DONE。
- [KI-073](issues/KI-073-实时投影与持久化模拟器双轨事件链事实分裂.md)：独立随机投影已移除，SSE 只消费提交后
  日志；实现基于 JSONL 的 `replay_from_id()` 与 `Last-Event-ID` 断线重放机制及日志轮转，已满足验收并关闭为 DONE。
- [KI-074](issues/KI-074-历史文档未版本化保全与语义治理闸门缺失.md)：23 份受限历史资料已通过 `scripts/project/sanitize_history.py` 自动化生成 `.sanitized.md` 脱敏副本并纳入版本库跟踪；建立 `docs/development/SANITIZATION-RULES.md` 脱敏标准；53 份历史原件与脱敏副本全部纳入 `docs/history/MANIFEST.sha256` 与 `docs/HISTORY-CATALOG.md`；交付灾备备份与本地解密演练工具 `scripts/project/backup_history_to_r2.py` 及回归测试 `scripts/project/tests/test_history_backup_drill.py`；全量灾备演练和完整性测试 100% 通过；已满足验收并关闭为 DONE。
- [KI-075](issues/KI-075-前后端审计后遗留死接口静态兜底与命名残留.md)：21 条前端逻辑审计项已全部修复（`c16530e`…`6c0421e`）；
  遗留的无消费者 AI 生成接口、静态冻结的 `insights` 段、无效 `fixKeys`、跨目录 `v2` 命名与生产环境变量残留只登记不修复，待逐项授权。
- 当前受管工具沙箱内，Python 3.13.15 的异步事件循环等待线程池任务会死锁，最小 `anyio.to_thread`
  与 Starlette/httpx2 `TestClient` 均可复现；因此本轮只完成不经过该桥接层的 198 项后端测试及完整前端、文档
  检查，不能把全量 `make check` 标为通过。该现象未在生产进程上做任何验证，也未改生产依赖或服务。

## KI-076 前端本地整改与展示契约验收（2026-09-11 至 2026-09-12）

- 治理广播每 30 秒更新，巡航使用广播同一事件列表，不再内置三条剧情；查看按工单 ID 定位，空态和读取失败不保留过时故事。
- 顶栏精准区分实时数据、降级快照与刷新受阻；提供详细业务日期及快照生成时点。
- D4/D5/D6 使用 `ChartFacts` 有限组合；指标提供完整值提示与横向阅读入口。
- 两类抽屉共用 `DrawerShell`，挂载于窗口并支持 Escape、焦点循环与恢复。
- `visual` 构建使用独立输出和无 API 代理的预览；组件展例仅在该构建开放。
- 自动化离线视觉回归套件（Playwright，20 项测试）全量通过，已完成最终验收闭环，状态转为 DONE（见 [KI-076](issues/KI-076-FRONTEND-PRESENTATION-CONTRACT.md)）。

## 前端面板视觉居中对齐优化（2026-09-12）

- `MetricGrid` 与 `CommandBand` 扩展 `align?: 'left' | 'center'` 契约，在 `blocks.css` 中增加 `.metric-grid--center` 规整网格单元格标题、数值、元信息及提示文本中轴对齐。
- **B1 面板**：首尾两段（主 KPI 建设完成度与事实指标三卡）由靠左改为居中对齐。
- **B6 面板**（数据准备台账与单位状态）：概览指标卡片（纳管总单位、当前筛选结果、期初数据完成、建设完成度 4 项）接入 `align="center"` 与 `.metric-grid--inline.metric-grid--center` 样式，补齐各指标卡内部图文与中轴居中对齐。
- **C1 面板**：推广攻坚总盘右侧事实指挥指标（纳管单位、推广批次、覆盖省份、联系人）采用居中对齐。
- **D1 面板**：规模总盘右侧数据规模与效率指标卡（数据总规模、单据平均明细、凭证平均分录）采用居中对齐。
- **D5 / D6 面板**：接口集成入账指标首段（集成成功率与调用/异常卡）、双轨运行首段（核对一致率及门禁提示）采用居中对齐。
- **D7 面板**：金标准稽核首段规则指标网格（凭证借贷平衡等核心约束指标）采用居中对齐。
- **E1 面板**：右侧主要风险维度 TOP 3 增加水平内收边距并居中，消除两端贴边分散感。
- **F1 面板**：风险研判指挥盘首段风险单位核心指标采用居中对齐，第二段风险分布条形图调整图表左右内距向中轴收拢。
- **顶栏导航、时间展示与状态控制区右对齐优化**：
  - 顶栏右上角时点调整为不显示年份，仅展示月日时分秒（`MM-DD HH:mm:ss`），在较窄屏幕（≤ 1600px）下自动精简为时分秒（`HH:mm:ss`），保留实时时钟感知；
  - 顶部外壳 `.header-status` 明确配置 `margin-left: auto;`，确保实时数据徽标、时点以及刷新/全屏等功能按钮始终吸附右侧边界居右显示；中央大屏主标题严格居中；
  - `.header-nav` 设置 `flex-shrink: 0` 并微调内边距，彻底消除“风险预警”选中高亮背景胶囊与右侧状态徽标的视觉碰撞，在 1280px～2560px 全视口梯度下均保持安全清晰的留白。
- **CI/CD 默认流水线规范化**：确立以 GitHub Actions Workflow（`.github/workflows/quality.yml`）为默认 CI/CD 发布链路，push 至 main 分支自动触发完整质量门禁、前端打包与 USA 生产机原子软链部署；`scripts/project/publish.sh` 同步更新服务重启指令为 `mod.service` 并作为应急/直连备用渠道。

## KI-078 安全基线治理与基石加固（2026-09-12）

- **API 交互文档公网屏蔽**：生产模式（`MOD_ENV=production`）下 FastAPI 默认关闭 `docs_url` 与 `openapi_url`（支持通过 `MOD_ENABLE_DOCS=1` 显式开启），源站 Nginx 新增规则直接对 `/api/docs`、`/api/docs/` 与 `/api/openapi.json` 实施硬拦截响应 404，消除接口模式与数据结构的公网信息泄露。
- **请求频控与防刷保护（Rate Limiting）**：Nginx 新增 `/etc/nginx/conf.d/mod_ratelimit.conf`，提取客户端真实 IP（优先解析 `X-Forwarded-For` 最左 IP，回退至 `$remote_addr`）；读接口配置 `zone=mod_api_limit`（25r/s，burst=50），敏感写入接口配置 `zone=mod_write_limit`（2r/s，burst=5），超频统一返回 HTTP 429 Too Many Requests，保障免登大屏在公网环境下的抗刷能力。
- **源站回源密钥模板化与源码彻底解耦**：移除原 Nginx 配置模板中硬编码的密钥明文，新增 `deploy/nginx/snippets/mod-origin-secret.conf.example`；生产真实密钥由运维部署至本地 `/etc/nginx/snippets/mod-origin-secret.conf`（权限 0600，不入 Git 仓库），通过 include 引用，代码库彻底消除明文凭据与豁免标记。

## KI-079 历史快照断档与吞吐量增量毛刺算法治理（2026-09-12）

- **A4/B1 历史走势采样断档与跌零治理**：底层 `rollout_status_snapshot` 除系统全量基准切片（2,000+ 组织）外，包含模拟器日常推进或增量入库产生的零星片段（5~132 条）。原 SQL 阈值（`> 100` 或无过滤）错误采纳了未推进的零星片段导致各批次上线率跌零；提升门禁至 `HAVING COUNT(*) >= 1000` 并融合当日实时批次分布，确保走势图连续平滑。
- **D 屏 operationsTrend 天量毛刺与成功率越界治理**：当历史存量回填或断档跳变导致累积差值出现非物理天量增量（如单日跳变 341 万笔）时，`build_operations_trend` 自动按当期单据/凭证规模平滑约束；同时将 `integrationSuccessPct` 严格钳位在 `[0.0, 100.0]`，消除 `850.0%` 等逻辑错误。
- **兜底快照清洗与单测兜底**：更新 `frontend/src/data/fallback-snapshot.json` 消除历史遗留的 `850.0%` 及 354 万天量毛刺，新增单元测试覆盖跳变平滑与百分比钳位；状态转为 DONE（见 [KI-079](issues/KI-079-历史快照断档与吞吐量增量毛刺算法治理.md)）。

## 2026-09-13 AI 本地代码修正（KI-080，DONE，未部署）

此节修正本文旧 AI 能力描述，原记录保留供追溯；不据旧文推断当前线上启用状态。

- 当前两个模型使用公式生成的合成标签，API 标记 `EXPERIMENTAL` / `businessValidated=false`；F 屏保留拟合分，明确尚未验证未来预测能力。风险名单仍由业务规则产生，模型只补充特征，分类与回归结果不再互相覆盖。
- 缺失/非法概率不再回填 85%/15%；成功率 0 保留；没有正向归因时返回空列表；Top 3 权重是相对占比。
- 简报按展示时区返回新鲜度；A/F 屏标记旧简报并每分钟只读刷新。LLM 输入仍为脱敏宏观数字，提示词限定摘要和待核实事项，非有限输入与异常/截断输出被拒绝。
- 摘要适配器请求前原子计数，失败也占用当日请求次数，范围明确为当前进程；不修改全局 socket 超时。该计数不能替代持久化账本或账户预算。
- 未执行部署、数据库写入、训练评分或外部模型调用。验收记录见 [KI-080](issues/KI-080-AI-OUTPUT-TRUST.md)。

## 2026-09-13 KI-081 事务性 Outbox 与投影持久化治理（DONE，已上线）

本节修正前文基于 JSONL 的当前代码描述，历史记录保留。
- 生产 MySQL（`mod`）已完成 `sim_event_outbox_state` 与 `sim_event_outbox` 表结构初始化，模拟器快业务路径已由事务性 Outbox 全面接管（`sim_event_outbox` 与业务单据/凭证在同一 DB-API 事务中原子提交/回滚），彻底杜绝无落库事件的虚假推送；
- API 服务（`LiveProjectionBroker`）已切换至基于持久游标（`outbox:<stream_id>:<sequence>`）的数据库分页读取模式，每个连接独立维护游标，支持客户端断点续传与重连去重，游标越界/失效时显式返回 reset 指令触发前端刷新权威快照；
- 实施有界保留机制（默认保留上限 150,000 条，30 天前历史自动在后续写入事务内分批前缀清理）；旧 JSONL 归档保全不再追加写入；
- 线上 API `/api/simulator/status`（`RUNNING / SUCCESS`）与 `/api/live-projection/status`（`source_available: true`, `mode: "committed_simulation"`）均已验证就绪并稳定运行。验收记录见 [KI-081](issues/KI-081-投影事件不入库与JSONL无限增长及双轨一致性根治.md)。

## 2026-09-13 CI/CD 安全加固与模拟器重启 ID 缓冲治理（KI-082 与 KI-083，DONE）

- **CI/CD SSH 严格主机校验与部署密钥治理（KI-082）**：
  - 提取 USA 生产机公钥指纹配置到 GitHub Secrets `USA_HOST_KEY`；`.github/workflows/quality.yml` 的 deploy job 在存在该 Secret 时自动写入 `~/.ssh/known_hosts` 并启用 `StrictHostKeyChecking=yes`，消除 MITM 中间人攻击隐患；
  - 增强发布健康探针：增加 `/api/dashboard/snapshot` 契约字段探测；部署成功后自动通过 `build_fallback_snapshot.py` 刷新 fallback 快照并输出至当前 release 目录（`/home/ubuntu/mod/backend/releases/$TS/fallback-snapshot.json`），解决降级快照长期陈旧问题；
  - 治理 `scripts/project/publish.sh`：彻底移除抓取 Nginx 配置文件解析回源密钥的逻辑及所有 `# secret-scan: allow` 豁免标记，回源密钥仅从环境变量 `CLOUDFRONT_ORIGIN_SECRET` 读取，未配置时自动通过 SSH/本地直连 127.0.0.1:8100 执行探针；密钥安全扫描保持 0 告警；
  - 验收记录见 [KI-082](issues/KI-082-CICD安全加固与发布能力收敛.md)。
- **模拟器重启 ID 竞态与自愈熔断消除（KI-083）**：
  - 根因：`mod-simulator` 重启时，`IdAllocator` 读取 `MAX(id)` 与旧进程在途未提交事务存在时间窗口竞态，导致分配与已落库记录冲突并触发 `Duplicate entry`，连续 3 次失败引起 `FAIL_CLOSED_TRIPPED` 熔断；
  - 修复：在 `simulation/engine_context.py` 中引入 `DEFAULT_ID_RESTART_BUFFER = 100`，重启加载基线读取 `MAX(id)` 时自动增加缓冲，避开边界碰撞；在 `simulation/runtime_service.py` 写入异常回滚分支中重置 `_fast_baseline = None` 与 `_fast_allocator = None`，保证后续周期自愈重试时重新从数据库获取最新基线与缓冲分配器，避免死循环递增冲突；
  - 验收记录见 [KI-083](issues/KI-083-模拟器重启ID分配器竞态导致短暂熔断.md)。

## 操作边界

2026-09-11 harness 减薄补充：/pre-flight 的注册已移到全局 Pi 扩展，MOD 旧注册块注释保留，
不再承担通用命令编排；业务专用工具和测试门禁不变。

2026-09-11 harness 会话入口补充：Pi `/pre-flight` 已改为复用公共会话检查适配器，
默认计划、显式 --run 执行；调查模式不能通过该命令启动检查。终端 make/CLI 仍是独立入口。

2026-09-11 本机 harness 接入：公共包位于 `/home/ubuntu/local-harness/`，全局 Pi 加载公共扩展，
MOD 专属工具只由项目自动发现。当前入口改为按领域读取，旧入口完整保全；检查按计划运行并返回摘要与日志位置。
说明与限制见[本地 Harness](development/LOCAL-HARNESS.md)。该项仅变更本地开发工具，未发布生产。

任务范围补充：公共 harness 支持 investigate/repair/accept 及目标 KI 映射；KI-076 与 KI-079 已完成验收与关闭。

- 不运行历史协作状态机，不新增其中的任务或状态记录。
- 临时脚本必须遵守 `development/CLI-SCRIPT-POLICY.md` 的 CLI 专属目录制度。
- 实时投影的展示语义、事件链和多实例限制以 `development/LIVE-PROJECTION.md` 为准。
- 不部署历史 Cloudflare Worker。
- 不修改冻结 CSV，不重复运行历史全量导入工具。
- 数据库写入、服务启停、Nginx 和云资源操作仍需明确确认；生产发布部署默认通过 GitHub Actions CI/CD 流水线（push 至 main 分支触发 Quality gates 自动通过并部署）；本地脚本 `scripts/project/publish.sh` 保留为应急/直连备用发布通道，同样必须由项目 Owner（用户）或主控 Agent 明确授权后方可执行。
- 当前默认改进范围是本地代码、测试、文档与开发工具。
 
