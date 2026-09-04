# MOD 当前状态

更新日期：2026-09-04
状态：现行事实入口
适用范围：当前运行、数据、功能、质量、安全状态与操作边界

本文是项目当前事实入口。历史多 Agent 协作状态机（调度器、agent 定义、任务与交接文件）已于
2026-09-04 归档至 `archive/legacy-collaboration/`，只作历史记录保留，不再驱动开发流程。

## 现行架构

```text
浏览器 -> Nginx / -> Vue 静态文件
                 -> /api/ -> FastAPI -> MySQL HeatWave mod_s_v2
```

- 现行入口为已配置的生产域名（见部署配置，不对外公开）。旧入口已停用且不再解析。
- USA 使用用户级 systemd 运行项目内 FastAPI 虚拟环境，监听 `127.0.0.1:8100`。
- MOD 不使用 Docker、DataEase、NocoDB 或 Cloudflare Worker 作为现行运行组件。
- `archive/legacy-cloudflare-worker/` 是未接入现行链路的历史实验原型，不部署。
- 后端包含可选的 Cloudflare Workers AI REST 适配器，但默认关闭；它不依赖上述历史 Worker。
- 时区契约：后端与 UTC 侧一律使用 UTC；面向用户的展示时区由 `MOD_DISPLAY_TIMEZONE` 决定，
  默认 `Asia/Hong_Kong`，唯一定义在 `backend/app/config.py`。快照 `meta.displayTimezone`、实时投影
  作息节律与前端时钟均派生自该来源，不得各自写死。已知偏差：`v2_connection` 的会话时区固定
  `+08:00`（见 `backend/app/db.py` 注释），调整属数据语义变更，需单独授权。

## 数据状态

- V2 冻结基线：17 张表、1,685,923 行、1,497 家单位。
- 2026-09-01 的增量导入记录：8,568,654 行。
- 2026-09-02 只读核验的 USA 合计：31,838,078 行、2,000 家单位，数据日期为 2027-02-28。
- `artifacts/v2-sim-data/` 是冻结基线，不得修改或重复导入。
- `artifacts/v2-sim-data-inc/` 是增量数据资产，数据库写入和再次导入仍需单独确认。

## 功能状态

- V2 六屏驾驶舱、只读 `/api/v2`、34 省地图和无刷新轮询已经实现。
- 驾驶舱包含默认启用的进程内只读实时投影，通过 SSE 展示受约束的单据、凭证和集成增量；该投影明确
  标记为演示动态，不写数据库，也不启用业务模拟器。
- V1 回退代码仍保留，但不作为后续功能目标。
- HeatWave AutoML 特征表已建立；训练/评分仍未完成。
- Cloudflare AI 默认未启用，不应把未生成的预测展示为真实结果。
- 本地接口与前端已将建设、问题、单位与运营屏统一到数据库当前快照口径；缺失指标展示为 `—` 或明确的
  “未提供”，不再以冻结基线数值替代实时结果。该变更尚未部署到 USA。
- 本地已修复省级单据新增与总览不一致问题：在线查询按快照日前最近完整业务日聚合，fallback 已从
  冻结 V2 资产只读重建，并恢复 R3 省级合计与 R6 日期区分契约。该变更尚未部署到 USA。
- 本地前端已修复 1440 宽度导航重叠和 1920×1080 驾驶舱首屏溢出，地图色阶改为按当前数据动态
  缩放；智能研判关闭态不再暗示存在现行 Cloudflare Worker。该变更尚未部署到 USA。
- 本地 B 屏建设进度已迁移到 `CockpitPanel`、具名 Grid 与统一 Token，旧 `construction.css`
  及关联遗留规则已删除，缺失建设数据不再使用硬编码数值回填。该变更尚未部署到 USA。
- 页面 meta、根 `robots.txt`、Nginx 与 API 响应均设置禁止索引指令。

## 运行安全状态

- USA 重复的系统级 `mod-api.service` 已停止并禁用；仅保留用户级服务监听 `127.0.0.1:8100`。
- 正式服务已重启并采用默认关闭门禁，日志确认业务模拟器未启用，不再创建写库连接。
- USA `/home/ubuntu/mod` 仅作为部署目录；代码、工具、文档、数据与历史资产以 JPA 为唯一事实源。

## 本地质量基线

- 前端：Vue 3、TypeScript、Vite；`pnpm exec vue-tsc --noEmit --incremental false` 通过。
- 后端：FastAPI、SQLAlchemy；43 项 pytest 测试通过。
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
