# 约束与文档收敛前现状切片

更新日期：2026-09-17
状态：历史
适用范围：`docs/CURRENT-STATE.md` 中被 2026-09-17 现行事实取代的 CI/CD、部署拓扑、功能路径与质量基线描述
原始位置：`docs/CURRENT-STATE.md` 的实现、运行事实、质量基线与工程治理段落
切片时间：2026-09-17
取代原因：原文与仓库实现及 2026-09-17 只读核验结果不符；现行事实包括 CI `deploy` job、JPA/USA 分离、MySQL outbox、顶层 `simulation/` 及最新测试基线。
新事实链接：[当前状态](../CURRENT-STATE.md)、[密钥与配置管理规范](../development/SECRETS-AND-CONFIG.md)

## 撤下的完整原文

- 本地 Git hooks 已强制执行凭据扫描、`make check` 和提交信息格式；GitHub Actions workflow 已在仓库
  落地，远端启用后在拉取请求和推送中复用同一闸门，不包含部署或生产访问。

## 撤下的运行主机原文

- 正式服务已在当前运行主机重启并采用默认关闭门禁，日志确认业务模拟器未启用，不再创建写库连接。
- 当前运行主机的 `/home/ubuntu/mod` 现为源码工作区与生产运行的唯一位置；代码、工具、文档、
  数据与历史资产均以该主机为唯一事实源。

## 撤下的功能与质量原文

- V2 六屏驾驶舱、只读 `/api/v2`、34 省地图和无刷新轮询已经实现。
- 驾驶舱实时投影只尾随常驻模拟器事务提交后追加的本机持久日志，通过 SSE 播报单据、凭证和集成事件；
  数据库快照仍是累计数字唯一事实源，前端会话脉搏不再与快照相加。当前只支持同机单 API 进程，尚无共享
  outbox、跨实例消费者位点或完整重连续播保证，具体边界见 `development/LIVE-PROJECTION.md`。
- 拟真引擎第一步（技术验证载体）已落地（`backend/app/simulation/`）：实现费用报销剧本（`ExpensePlaybook`）多表完整足迹生成与安全写库器（`SimulationWriter`），单事务原子落库 6 张表（`business_document`、`business_document_line`、`accounting_voucher`、`accounting_voucher_line`、`document_voucher_link`、`integration_result`）并级联同步 `daily_stats`；以存量治理成果为硬约束（时间线接续存量最新日期只向前生长、经办人 100% 命中本单位名录、仅限已上线单位门禁、只增不删、零 schema 变更、运行审计留痕）；开关 `MOD_SIMULATION_ENGINE_ENABLED` 默认关闭（`false`）；已通过 100 笔小试落库实测，KI-017 零回归。
- 拟真引擎第二步（建设管控主线 + B模式生命周期推进器）已落地并已实测写库（`backend/app/simulation/`）：
- 前端：Vue 3、TypeScript、Vite；当前 23 个测试文件、112 项 Vitest 单测、类型检查与生产构建通过。
- 后端：FastAPI、SQLAlchemy；当前 230 项 pytest 测试通过（新增 KI-065 对称走势快照测试，全量离线测试 100% 通过）；KI-060 已将 Starlette `TestClient` 的开发依赖
  从已弃用的 `httpx` 回退路径迁移至精确锁定的 `httpx2==2.12.0`，并将对应弃用警告设为测试失败。
