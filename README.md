# MOD

更新日期：2026-09-04
状态：现行项目概览
适用范围：项目定位、运行架构和本地开发入口

MOD 是一个**下一代 AI 驱动开发**的领导驾驶舱与大屏可视化项目：设计与决策由人主导，
代码由 AI 生成，并以一整套约束、闸门与规范保证工程质量。它面向“数智财务运营管控”场景，
覆盖建设、推广、双轨运行到运营的全生命周期展示。

三个定位关键词：

- **AI 驱动开发**：人做设计与判断，AI 做实现；配套契约、pre-commit/CI 闸门、签名提交、
  ADR 决策记录与文档生命周期规范，让 AI 协作在可控、可审计、可演进的轨道上进行。
- **千万级数据大屏**：以真实规模（千万级行、数千家单位）的模拟数据验证 MySQL HeatWave
  的秒级聚合能力——不是几百条的玩具演示，而是能扛住真实体量的技术底座。
- **高仿真业务模拟**：由业务事件驱动生成自洽的单据、凭证、问题与生命周期演进，
  让“看起来在真实运转的系统”经得起细节推敲；配合 HeatWave AutoML 做风险与增量研判。

技术栈：Vue 3 + TypeScript + ECharts 前端，FastAPI 只读 API，MySQL HeatWave 存算。
前端为六屏驾驶舱（总览 / 建设 / 推广 / 运营 / 问题风险 / 智能研判），含 34 省地图下钻、
实时投影、契约化面板（CockpitPanel + 集中 Design Token）。所有业务内容均为虚构模拟数据。

## 设计原则

- 一个系统同时支持 S（模拟）、M（人工填报）、P（生产对接）三种模式。
- 先形成“填报—校验—汇总—展示—下钻—追溯”的完整闭环。
- 第一版采用一个静态前端和一个只读 API，不引入微服务、消息队列和独立 OLAP 数据库。
- MySQL 保存明细，HeatWave 承担大规模聚合分析。
- 模拟、人工填报和生产数据相互隔离。
- 前端遵循骨架/物料/Token 三层契约；代码守骨架与数字，AI 填内容与呈现。

## 项目入口

- `AGENTS.md`：所有人和编码 Agent 必须遵守的仓库硬约束。
- `CONTRIBUTING.md`：接手、开发、验证、文档和签名提交流程。
- `PROJECT-LAYOUT.md`：目录结构、环境边界和统一路径规则。
- `docs/CURRENT-STATE.md`：当前运行、数据与改进状态的唯一事实入口。
- `docs/INDEX.md`：现行规范与全部历史资料索引。
- `docs/KNOWN-ISSUES.md`：已知问题看板（各 issue 详情见 `docs/issues/`；新需求/任务用 GitHub Issues 登记）。
- `docs/history/21-V2数据与项目目录现状基线.md`：V2 冻结基线历史记录。
- `artifacts/v2-sim-data/`：V2 封版数据。
- `docs/tasks/`：当前和历史任务书；任务书文件本身不等于操作授权。

## 运行架构

```text
浏览器 -> Nginx / -> Vue 静态文件
                 -> /api/v2 -> FastAPI -> MySQL HeatWave mod_s_v2
```

- Vue 负责领导驾驶舱、项目台账、运营分析和问题风险页面。
- FastAPI 只提供查询接口，不向匿名访问者开放数据库写操作。
- 页面读取 USA 的 `mod_s_v2`；连接异常时显示内置模拟快照和异常提示。
- 快照结果在 API 进程内缓存 60 秒，避免反复扫描全部明细表。
- 现有 `modo_db`、MODO 服务和其他 Nginx 路由保持隔离。

当前演示入口为已配置的生产域名（见部署配置，不对外公开）。历史旧入口均已停用。

## 本地开发

开发环境为 JPA，生产演示环境为 USA：

```bash
cd /home/ubuntu/mod/frontend
pnpm install
pnpm dev
```

本地访问：`http://127.0.0.1:4173/`。生产构建使用 `pnpm build`。

首次准备后端环境：

```bash
cd /home/ubuntu/mod/backend
uv sync --all-extras
```

提交前从项目根目录运行完整本地检查：

```bash
make check
```

已实现 V2 六屏、34 省地图下钻、项目台账、业务运营链路、问题风险和智能研判。所有业务内容均为
虚构模拟数据，在线统计读取 USA 的 `mod_s_v2`。

当前运行事实和操作边界以 `docs/CURRENT-STATE.md` 为准。`docs/history/07-当前部署与运维基线.md`
和 `docs/history/21-V2数据与项目目录现状基线.md` 均作为历史基线保留。

JPA `/home/ubuntu/mod` 是唯一源码和 Git 工作区；USA 同名目录是纯部署目录。后续维护必须遵守
`CONTRIBUTING.md` 和 `docs/development/` 下的现行规范。历史本地协作状态机保留但不再使用。
