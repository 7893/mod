# MOD — 业务系统建设推广大屏

更新日期：2026-09-06
状态：现行项目概览
适用范围：项目定位、运行架构和开发入口

MOD 是一个面向**业务系统建设与推广管控**的领导驾驶舱大屏项目，覆盖建设进度、上线推广、
风险预警、合规监督与业务运营的全生命周期展示。所有业务内容均为虚构模拟数据。

## 核心定位

- **建设管控驾驶舱**：核心观众是懂业务的高层管理者，他们会主动下钻验证。
  主线是"各单位建设/推广/上线/双轨的进展与风险"，业务单据是次线佐证。
- **高仿真业务模拟**：由常驻后台服务（`mod-simulator`）按香港时区作息节律 7×24 持续产生
  自洽的业务足迹（单据、凭证、建设事件、生命周期推进），数据实时增长，经得起下钻验证。
- **AI 协作工程实践**：设计与决策由人主导，实现由 AI 执行；配套契约、CI 闸门、签名提交、
  ADR 决策记录与文档生命周期规范，让多 Agent 协作在可控、可审计的轨道上进行。

## 技术栈

- **前端**：Vue 3 + TypeScript + ECharts + Tailwind，六屏驾驶舱（项目总览 / 建设进度 /
  上线推广 / 风险预警 / 合规监督 / 业务运营），含 34 省地图下钻、实时投影、
  骨架/物料/Token 三层契约（`CockpitPanel` + 集中 Design Token）
- **后端**：FastAPI 只读 API（`/api/*`），连接信息仅存主机本地环境文件
- **数据库**：托管 MySQL HeatWave（库 `mod`，Always Free），HeatWave 承担大规模聚合分析
- **模拟引擎**：常驻 systemd 服务 `mod-simulator`，按实时香港时区心跳持续产生业务足迹

## 运行架构

```text
浏览器 → Nginx → frontend/current/（软链，原子发布）
               → /api/* → FastAPI → MySQL (mod)
                                  → mod-simulator（后台常驻，持续写入）
```

- 生产与源码工作区同机（见 `docs/decisions/0006-single-host-consolidation.md`）
- 前后端均通过软链发布隔离（`frontend/current`、`backend/current` → `releases/<ts>/`），
  工作区修改不影响生产，发布由主控运行 `scripts/project/publish.sh` 原子切换
- 连接异常时前端自动降级为内置模拟快照

## 项目入口

| 文件 | 用途 |
|------|------|
| `AGENTS.md` | 所有人和 Agent 必须遵守的仓库硬约束（最高优先级） |
| `CONTRIBUTING.md` | 接手、开发、验证、提交流程 |
| `ENFORCEMENT.md` | 约束如何在动作点被强制执行（闸门） |
| `docs/CURRENT-STATE.md` | 当前运行、数据与架构事实的唯一入口 |
| `docs/INDEX.md` | 所有现行规范与历史资料索引 |
| `docs/KNOWN-ISSUES.md` | 已知问题看板（详情见 `docs/issues/`） |

新需求/任务用 GitHub Issues 登记；已知问题与技术债务登记于 `docs/KNOWN-ISSUES.md`。

## 本地开发

```bash
# 前端开发服务
cd frontend && pnpm install && pnpm dev
# 访问：http://127.0.0.1:4173/

# 后端环境
cd backend && uv sync --all-extras

# 提交前全量检查（必须全绿）
make check
```

## 发布

```bash
# 主控授权后运行，原子切换前后端软链、验证线上、失败自动回滚
bash scripts/project/publish.sh

# 查看实时数据状态
python3 scripts/project/inspect_state.py
```

当前运行事实以 `docs/CURRENT-STATE.md` 为准。
