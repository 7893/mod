# MOD

更新日期：2026-09-04
状态：现行项目概览
适用范围：项目定位、运行架构和本地开发入口

MOD 是“新一代数智财务运营管控平台”建设、推广、双轨运行和后续运营阶段使用的在线项目台账与领导驾驶舱。

当前状态：正式演示路线采用 Vue + FastAPI + MySQL HeatWave。USA 页面和 API 已接入
`mod_s_v2`；最近交接记录中的数据规模为 10,240,985 行、2,000 家单位。DataEase、
NocoDB、Docker 和历史 Cloudflare Worker 原型均不属于现行运行路线。

## 设计原则

- 一个系统同时支持 S（模拟）、M（人工填报）、P（生产对接）三种模式。
- 先形成“填报—校验—汇总—展示—下钻—追溯”的完整闭环。
- 第一版采用一个静态前端和一个只读 API，不引入微服务、消息队列和独立 OLAP 数据库。
- MySQL 保存明细，HeatWave 承担大规模聚合分析。
- 模拟、人工填报和生产数据相互隔离。
- 现有 `modo_db` 及 USA 节点上的其他业务均不属于本项目，不得修改。

## 项目入口

- `AGENTS.md`：所有人和编码 Agent 必须遵守的仓库硬约束。
- `CONTRIBUTING.md`：接手、开发、验证、文档和签名提交流程。
- `PROJECT-LAYOUT.md`：目录结构、环境边界和统一路径规则。
- `docs/CURRENT-STATE.md`：当前运行、数据与改进状态的唯一事实入口。
- `docs/INDEX.md`：现行规范与全部历史资料索引。
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
