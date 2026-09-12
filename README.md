<div align="center">
  <h1>MOD</h1>
  <p><strong>大型核心系统推广上线实时指挥驾驶舱</strong></p>
  <p><strong>Real-time Command Cockpit for Enterprise System Rollout</strong></p>
  <p>
    基于 Vue 3、ECharts、FastAPI 与 MySQL HeatWave AutoML 构建的企业级高密度、多屏协同决策指挥中心
  </p>

  <p>
    <a href="https://github.com/7893/mod/actions/workflows/quality.yml"><img src="https://github.com/7893/mod/actions/workflows/quality.yml/badge.svg" alt="Quality gates" /></a>
    <a href="https://github.com/7893/mod/releases/tag/v0.9.0"><img src="https://img.shields.io/badge/Release-v0.9.0-blue.svg" alt="Release: v0.9.0" /></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT" /></a>
    <img src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white" alt="Vue 3" />
    <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white" alt="TypeScript" />
    <img src="https://img.shields.io/badge/MySQL-HeatWave-4479A1?logo=mysql&logoColor=white" alt="MySQL HeatWave" />
  </p>

  <p>
    <a href="#%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87">简体中文</a> ·
    <a href="#english">English</a> ·
    <a href="docs/INDEX.md">文档索引</a> ·
    <a href="docs/CURRENT-STATE.md">当前状态</a> ·
    <a href="docs/KNOWN-ISSUES.md">已知问题</a> ·
    <a href="CHANGELOG.md">变更日志</a>
  </p>
</div>

> [!IMPORTANT]
> MOD 是用于演示验证、业务仿真与工程研究的完整系统。大屏展示的 3,200+ 机构单位、41,000+ 人员、490 万财务凭证及全业务流转事件，均为自主拟真引擎生成的合规合成数据，全程不使用任何真实企业敏感数据。

---

<a id="简体中文"></a>

## 简体中文

更新日期：2026-09-13 · 状态：现行项目概览 · 现行版本：`v0.9.0`<br>
适用范围：系统定位、运行架构、六屏叙事、开发指南与仓库导航

### 一、系统概述

MOD 将跨 34 个省级行政区、数千家分级单位、多批次推进的大型核心业务系统建设推广过程，转化为一套面向高层决策与一线作战的可视化指挥驾驶舱。

它打破了传统信息化建设中“进度看周报、核对拉表格、风险靠电话”的割裂模式，把**工程建设进度、批次上线推进、业务运营佐证、双轨核对一致性、合规监督与 AI 智能研判**融为一条完整、可穿透的管理主线。每项宏观大盘结论，均可一键下钻核验至具体机构、批次、工序与原始业务证据。

### 二、六屏立体协同作战视图

驾驶舱由 6 个高密度、互相关联的专属大屏构成，所有屏幕共享全局 Pinia 响应式状态与底层数据快照：

| 屏幕模块 | 核心定位与决策重点 |
|---|---|
| **A · 项目总览 (Overview)** | 全局战况总览、关键运营规模、上线推进节奏、指挥部决策横幅与收官信号 |
| **B · 建设进度 (Construction)** | 阶段里程碑穿透、工序任务结构、人员培训考核、期初数据准备与单位建设主台账 |
| **C · 上线推广 (Rollout)** | 34 省级地图下钻、8 个推广批次全景、区域双轨就绪度与上线积压瓶颈分析 |
| **D · 业务运营 (Operations)** | 真实单据与凭证流转、接口集成吞吐、财务双轨核对一致率（~96%）与数据质量审计 |
| **E · 合规监督 (Compliance)** | 多层级合规态势、批次合规横向对比、规则校验雷达与历史困难户重点预警 |
| **F · 风险与智能研判 (Risk & AI)** | 风险特征集中度、HeatWave AutoML 特征贡献归因、模型就绪评估与每日决策研判简报 |

### 三、MOD 的核心工程特色

- **管理决策驱动的立体叙事**：每个图表与指标卡均服务于决策、对比、下钻或运营动作，拒绝华而不实的装饰性动效。
- **高拟真业务运转与严格会计勾稽**：内置受控拟真引擎，遵循《企业会计准则》全天候模拟企业作息节律（8:30-11:30, 13:30-17:00）、月末冲刺及增值税进销项真实记账。全库 490 万凭证借贷 0 不平、0 孤儿单据、0 穿越未来的违背时间数据。
- **SWR 内存快照双缓冲机制（SLA < 1.0s）**：后端采用 Stale-While-Revalidate 异步预热机制，前台接口毫秒级极速响应；内置合成快照兜底，保障极端冷启动或网络波动时页面零白屏、零转圈。
- **湖仓一体内存加速与机器学习**：MySQL HeatWave 内存集群加载 9 张核心分析大表，支撑千万级明细实时聚合计算与 AutoML 风险评分。
- **高密度响应式可视化与统一视觉契约**：Vue 3 + ECharts 6 实现 34 省份矢量地图穿透交互、跨面板联动、动态秒级时钟与自适应缩放。
- **现代软件工程与制度化治理**：
  - 前后端测试全绿（29 个前端测试文件 148 个用例 + 24 个后端治理测试全部通过）；
  - CI/CD 启用 OpenSSH ControlMaster 连接多路复用，极大提升自动化部署可靠性；
  - 彻底停用 GitHub Issues，全面转向内聚受控的本地已知问题（KI）生命周期治理体系（[ADR-0014](docs/decisions/0014-停用GitHub-Issues统一使用本地KI问题跟踪体系.md)）；
  - 基于 `git-cliff` 2.13.1 锁定版本自动生成结构化发布变更日志。

### 四、系统运行架构

```text
                ┌─────────────────────────────────────────────┐
                │               Global DNS / CDN              │
                │         Edge Acceleration & Security        │
                └──────────────────────┬──────────────────────┘
                                       │ HTTPS / TLS
                                       ▼
                ┌─────────────────────────────────────────────┐
                │              Nginx Origin Gate              │
                │         Reverse Proxy & Path Routing        │
                └─────────┬─────────────────────────┬─────────┘
                          │ (Static Assets)         │ (API Proxy /api/*)
                          ▼                         ▼
                ┌───────────────────┐     ┌───────────────────┐
                │     Vue 3 SPA     │     │  FastAPI Backend  │
                │   Responsive UI   │     │   Read-Only API   │
                └─────────┬─────────┘     └─────────┬─────────┘
                          │ (Offline SWR)           │ (Query & Cache)
                          ▼                         ▼
                ┌───────────────────┐     ┌───────────────────┐
                │  Bundled Snapshot │     │   MySQL HeatWave  │
                │   Offline Guard   │     │ In-Memory & AutoML│
                └───────────────────┘     └─────────▲─────────┘
                                                    │ (Transaction Feed)
                                                    │ (Autonomous Loop)
                                          ┌─────────┴─────────┐
                                          │   mod-simulator   │
                                          │  Synthetic Engine │
                                          └───────────────────┘
```

**架构分层说明**：
- **边缘防护与全球加速（Global DNS / CDN）**：提供基于边缘节点的 DDoS 防护、TLS 终结与就近访问加速。
- **源站反向代理门禁（Nginx Origin Gate）**：统一安全门禁，严格隔离私网服务，负责 `/assets/*` 前端静态资源直发与 `/api/*` 后端接口安全反向代理。
- **前端交互驾驶舱（Vue 3 SPA）**：基于 Vue 3、TypeScript 与 ECharts 构建的响应式指挥看板，内置离线快照兜底（Bundled Snapshot），保障冷启动与网络波动时零白屏、零转圈。
- **高性能后端核心（FastAPI Backend）**：只读高性能异步业务接口层，基于 SWR 机制异步预热内存缓存，保持全接口 SLA < 1.0s。
- **湖仓一体数据与机器学习底座（MySQL HeatWave）**：支撑千万级明细列存内存分析与 AutoML 智能风险研判模型。
- **高保真业务仿真引擎（mod-simulator）**：全天候按真实作息节律驱动业务单据与会计凭证演化推进，为系统提供合规合成数据源。

标准生产交付由 GitHub Actions 流水线在代码 push 至 `main` 分支时自动触发全量门禁检验与生产机原子软链部署；运行凭据严格保留在代码库之外。

### 五、技术栈矩阵

| 架构层级 | 核心技术选型 |
|---|---|
| **前端大屏 (Frontend)** | Vue 3.5、TypeScript 5.9、Pinia、ECharts 6.1、Tailwind CSS、Vite |
| **后端接口 (Backend)** | FastAPI、Python 3.12+、SQLAlchemy 2.0、Uvicorn、Pydantic |
| **数据与湖仓加速 (Data)** | MySQL 8.4 HeatWave、HeatWave In-Memory Cluster、AutoML |
| **质量与安全保障 (QA)** | Pytest、Vitest、Playwright、Ruff、vue-tsc、文档保全与凭据扫描闸门 |
| **部署与交付运维 (Ops)** | Nginx、systemd、原子版本软链切换、GitHub Actions、Fail2ban 防护 |

### 六、本地快速启动

前置开发环境：Python 3.12+、[`uv`](https://docs.astral.sh/uv/)、Node.js、pnpm 与 Make。

```bash
# 1. 启动后端 API 服务（终端 1）
cd backend
uv sync --all-extras
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100

# 2. 启动前端驾驶舱（终端 2）
cd frontend
pnpm install
pnpm dev
# 本地访问：http://127.0.0.1:5173/
```

> 前端已内置离线合成快照数据，无需配置本地数据库即可完整体验六屏联动交互。若需连接数据库，请参考 `docs/development/` 配置本地环境文件。

提交代码前请执行全量质量门禁：

```bash
make check
```

### 七、核心文档导航

| 关键文档 | 用途说明 |
|---|---|
| [AGENTS.md](AGENTS.md) | 人类与 AI 编码助手必须严格遵守的仓库红线与最高约束 |
| [ENFORCEMENT.md](ENFORCEMENT.md) | 在提交、测试、发布动作点强制执行的安全与治理闸门 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 标准开发、自验、文档同步与原子提交工作流 |
| [当前状态事实 (CURRENT-STATE.md)](docs/CURRENT-STATE.md) | 当前运行环境、数据规模与技术事实的唯一官方入口 |
| [文档总索引 (INDEX.md)](docs/INDEX.md) | 现行架构、开发标准、ADR 决策、历史资料与操作边界总览 |
| [已知问题看板 (KNOWN-ISSUES.md)](docs/KNOWN-ISSUES.md) | 系统技术债务与缺陷看板（已按 ADR-0014 闭环管理） |
| [变更日志 (CHANGELOG.md)](CHANGELOG.md) | 基于 git-cliff 由语义化提交自动生成的版本发行历史 |

### 八、开源许可

MOD 遵循 [MIT License](LICENSE) 开源协议。

---

<a id="english"></a>

## English

Updated: 2026-09-13 · Status: Active project overview · Current release: `v0.9.0`<br>
Scope: System positioning, architecture, 6-screen storytelling, development guide, and repository navigation

### 1. System Overview

MOD transforms the complex, multi-stage rollout of an enterprise-level core business system across 34 provincial regions and thousands of sub-units into a high-density, decision-ready visual command center.

It replaces the traditional, fragmented approach of "tracking progress via status reports, reconciling data across spreadsheets, and resolving risks through phone calls" with a unified, drillable management thread connecting **construction milestones, rollout readiness, operational evidence, dual-run accounting reconciliation, compliance posture, and AI-driven decision briefings**. Every top-level finding can be seamlessly drilled down into specific organizations, batches, stages, and raw business records.

### 2. Six Coordinated Command Views

The command cockpit comprises 6 dense, interconnected screens sharing global Pinia reactive state and in-memory data snapshots:

| Screen | Core Purpose & Decision Focus |
|---|---|
| **A · Overview** | Macro progress, rollout velocity, operational scale, executive headline, and closure signals |
| **B · Construction** | Stage milestones, task structures, personnel training, data preparation, and unit ledgers |
| **C · Rollout** | 34-region map drill-down, 8 rollout batches, regional dual-run readiness, and backlog analysis |
| **D · Operations** | Document/voucher throughput, integration metrics, dual-run reconciliation (~96%), and quality audits |
| **E · Compliance** | Hierarchical compliance posture, batch cross-comparison, rule radar, and lagging-unit alerts |
| **F · Risk & Intelligence** | Risk feature concentration, HeatWave AutoML attribution, model readiness, and daily decision briefings |

### 3. Key Engineering Highlights

- **Decision-Centric Visual Storytelling**: Every chart and card directly supports decision-making, comparative analysis, drill-down, or operational follow-up.
- **High-Fidelity Synthetic Operations & Rigorous Accounting**: Powered by an autonomous simulation engine following standard enterprise accounting rules. Generates realistic diurnal rhythms (8:30-11:30, 13:30-17:00), month-end closing surges, and VAT input/output tracking. Across 4.9M vouchers, there are exactly 0 debit/credit imbalances, 0 orphan records, and 0 future date anomalies.
- **SWR In-Memory Snapshot Double Buffering (SLA < 1.0s)**: Employs Stale-While-Revalidate caching for millisecond API responses with asynchronous backend prewarming. Bundled fallback snapshots guarantee zero white-screen and zero-spinner resilience even during cold starts or network fluctuations.
- **Lakehouse In-Memory Acceleration & AutoML**: 9 core analytics tables are loaded into the MySQL HeatWave in-memory cluster, enabling instant multi-million row aggregations and automated risk scoring.
- **Dense, Responsive Visualization**: Vue 3 and ECharts 6 deliver interactive 34-region map penetration, cross-panel filtering, a real-time ticking clock, and auto-scaling layouts.
- **Enterprise Engineering Rigor**:
  - Full test suite passing (29 frontend test suites with 148 specs + 24 backend and governance checks);
  - CI/CD hardened with OpenSSH ControlMaster connection multiplexing for rapid, reliable deployments;
  - GitHub Issues deprecated in favor of a locally governed Known Issues (KI) lifecycle system ([ADR-0014](docs/decisions/0014-停用GitHub-Issues统一使用本地KI问题跟踪体系.md));
  - Reproducible release changelogs generated automatically with pinned `git-cliff` 2.13.1.

### 4. System Architecture

```text
                ┌─────────────────────────────────────────────┐
                │               Global DNS / CDN              │
                │         Edge Acceleration & Security        │
                └──────────────────────┬──────────────────────┘
                                       │ HTTPS / TLS
                                       ▼
                ┌─────────────────────────────────────────────┐
                │              Nginx Origin Gate              │
                │         Reverse Proxy & Path Routing        │
                └─────────┬─────────────────────────┬─────────┘
                          │ (Static Assets)         │ (API Proxy /api/*)
                          ▼                         ▼
                ┌───────────────────┐     ┌───────────────────┐
                │     Vue 3 SPA     │     │  FastAPI Backend  │
                │   Responsive UI   │     │   Read-Only API   │
                └─────────┬─────────┘     └─────────┬─────────┘
                          │ (Offline SWR)           │ (Query & Cache)
                          ▼                         ▼
                ┌───────────────────┐     ┌───────────────────┐
                │  Bundled Snapshot │     │   MySQL HeatWave  │
                │   Offline Guard   │     │ In-Memory & AutoML│
                └───────────────────┘     └─────────▲─────────┘
                                                    │ (Transaction Feed)
                                                    │ (Autonomous Loop)
                                          ┌─────────┴─────────┐
                                          │   mod-simulator   │
                                          │  Synthetic Engine │
                                          └───────────────────┘
```

**Architecture Layer Breakdown**:
- **Global DNS / CDN**: Edge-level DDoS protection, TLS termination, and accelerated static asset routing.
- **Nginx Origin Gate**: Origin-side security ingress routing `/assets/*` to frontend static artifacts and reverse-proxying `/api/*` to the FastAPI backend.
- **Vue 3 SPA**: Interactive command cockpit built with Vue 3, TypeScript, and ECharts, featuring bundled snapshot fallbacks to guarantee zero spinners during cold starts or network lags.
- **FastAPI Backend**: Read-only asynchronous service layer utilizing SWR prewarming caches to uphold strict SLA < 1.0s.
- **MySQL HeatWave**: Lakehouse in-memory columnar acceleration for multi-million row aggregations and integrated AutoML risk attribution.
- **mod-simulator**: High-fidelity autonomous simulation engine driving realistic enterprise business transaction and accounting voucher streams.

Standard production delivery runs through GitHub Actions CI/CD upon push to `main` with full quality gates and atomic release symlinks on the dedicated production host. Runtime credentials remain strictly outside Git.

### 5. Technology Stack Matrix

| Layer | Core Technologies |
|---|---|
| **Frontend** | Vue 3.5, TypeScript 5.9, Pinia, ECharts 6.1, Tailwind CSS, Vite |
| **Backend** | FastAPI, Python 3.12+, SQLAlchemy 2.0, Uvicorn, Pydantic |
| **Data & Acceleration** | MySQL 8.4 HeatWave, HeatWave In-Memory Cluster, AutoML |
| **Quality & Assurance** | Pytest, Vitest, Playwright, Ruff, vue-tsc, credential scanning, doc gates |
| **Operations & Delivery** | Nginx, systemd, atomic release symlinks, GitHub Actions, Fail2ban |

### 6. Local Quick Start

Prerequisites: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), Node.js, pnpm, and Make.

```bash
# 1. Start Backend API Service (Terminal 1)
cd backend
uv sync --all-extras
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100

# 2. Start Frontend Cockpit (Terminal 2)
cd frontend
pnpm install
pnpm dev
# Local access: http://127.0.0.1:5173/
```

> The frontend includes bundled synthetic snapshot data, allowing complete exploration of all 6 screens without configuring a local database. To connect to a database, see `docs/development/` for environment configuration.

Run the full quality gate before committing:

```bash
make check
```

### 7. Repository Navigation

| Entry | Purpose |
|---|---|
| [AGENTS.md](AGENTS.md) | Mandatory red lines and constraints for humans and AI agents |
| [ENFORCEMENT.md](ENFORCEMENT.md) | Action-time safety and governance gates enforced during development |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Standard development, verification, doc sync, and commit workflows |
| [Current State (CURRENT-STATE.md)](docs/CURRENT-STATE.md) | Canonical source of truth for runtime, data, and architecture facts |
| [Documentation Index (INDEX.md)](docs/INDEX.md) | Master directory for architecture standards, ADRs, operations, and history |
| [Known Issues (KNOWN-ISSUES.md)](docs/KNOWN-ISSUES.md) | Defect and technical debt tracker (governed per ADR-0014) |
| [Changelog (CHANGELOG.md)](CHANGELOG.md) | Automated release history generated from verified Git commits |

### 8. License

MOD is released under the [MIT License](LICENSE).
