<div align="center">
  <h1>MOD</h1>
  <p><strong>大型核心系统推广上线实时指挥驾驶舱</strong></p>
  <p><strong>Real-time Command Cockpit for Enterprise System Rollout</strong></p>
  <p>
    基于 Vue 3、ECharts、FastAPI 与 MySQL HeatWave AutoML 构建的企业级高密度、多屏协同决策指挥中心
  </p>

  <p>
    <a href="https://github.com/7893/mod/actions/workflows/quality.yml"><img src="https://github.com/7893/mod/actions/workflows/quality.yml/badge.svg" alt="Quality gates" /></a>
    <a href="https://github.com/7893/mod/releases/tag/v0.10.0"><img src="https://img.shields.io/badge/Release-v0.10.0-blue.svg" alt="Release: v0.10.0" /></a>
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
    <a href="THIRD_PARTY_NOTICES.md">第三方声明</a> ·
    <a href="CHANGELOG.md">变更日志</a>
  </p>
</div>

> [!IMPORTANT]
> MOD 是用于演示验证、业务仿真与工程研究的完整系统。大屏展示的 3,200+ 机构单位、41,000+ 人员、490 万财务凭证及全业务流转事件，均为自主拟真引擎生成的合规合成数据，全程不使用任何真实企业敏感数据。

---

<a id="简体中文"></a>

## 简体中文

更新日期：2026-09-23 · 状态：现行项目概览 · 现行版本：`v0.10.0`<br>
适用范围：系统定位、运行架构、六屏叙事、开发指南与仓库导航

### 一、系统概述

MOD 将跨 34 个省级行政区、数千家分级单位、多批次推进的大型核心业务系统建设推广过程，转化为一套面向高层决策与一线作战的可视化指挥驾驶舱。

它打破了传统信息化建设中“进度看周报、核对拉表格、风险靠电话”的割裂模式，把**工程建设进度、批次上线推进、业务运营佐证、双轨核对一致性、合规监督与 AI 智能研判**融为一条完整、可穿透的管理主线。每项宏观大盘结论，均可一键下钻核验至具体机构、批次、工序与原始业务证据。

### 二、六屏立体协同作战视图

驾驶舱由 6 个高密度、互相关联的专属大屏构成，所有屏幕共享全局 Pinia 响应式状态与底层数据快照：

| 屏幕模块 | 核心定位与决策重点 |
|---|---|
| **A · 项目总览 (Overview)** | 五域态势导航、省域地图与联动摘要、跨域趋势、今日变化和行动队列 |
| **B · 建设进度 (Construction)** | 建设概览、阶段任务矩阵、滞后省域、上线门禁、数据就绪和常驻台账预览 |
| **C · 上线推广 (Rollout)** | 批次当前态与历史爬坡、区域推进缺口、联系人例外和单位上线台账 |
| **D · 业务运营 (Operations)** | 单据—凭证—集成端到端链路、日吞吐、双轨核对和数据质量审计 |
| **E · 合规监督 (Compliance)** | 合规摘要、风险标签、治理工单流转、实时广播和问题下钻 |
| **F · 风险与智能研判 (Risk & AI)** | 首要瓶颈与行动优先级、风险分布、模型治理和每日决策简报 |

### 三、MOD 的核心工程特色

- **管理决策驱动的立体叙事**：每个图表与指标卡均服务于决策、对比、下钻或运营动作，拒绝华而不实的装饰性动效。
- **高拟真业务运转与严格会计勾稽**：内置受控拟真引擎，遵循《企业会计准则》全天候模拟企业作息节律（8:30-11:30, 13:30-17:00）、月末冲刺及增值税进销项真实记账。全库 490 万凭证借贷 0 不平、0 孤儿单据、0 穿越未来的违背时间数据。
- **SWR 内存快照双缓冲机制（SLA < 1.0s）**：后端采用 Stale-While-Revalidate 异步预热机制，前台接口毫秒级极速响应；内置合成快照兜底，保障极端冷启动或网络波动时页面零白屏、零转圈。
- **湖仓一体内存加速与机器学习**：MySQL HeatWave 内存集群加载 9 张核心分析大表，支撑千万级明细实时聚合计算与 AutoML 风险评分。
- **高密度响应式可视化与统一视觉契约**：Vue 3 + ECharts 6 实现 34 省份矢量地图穿透交互、跨面板联动、动态秒级时钟与自适应缩放。
- **现代软件工程与制度化治理**：
  - 本地与 CI 复用类型检查、单元测试、静态契约、构建和文档治理门禁，易漂移的测试数量不在 README 手工固化；
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
| **后端接口 (Backend)** | FastAPI、Python 3.13.15、SQLAlchemy 2.0、Uvicorn、Pydantic |
| **数据与湖仓加速 (Data)** | MySQL 8.4 HeatWave、HeatWave In-Memory Cluster、AutoML |
| **质量与安全保障 (QA)** | Pytest、Vitest、Playwright、Ruff、vue-tsc、ESLint、Stylelint、pre-commit、detect-secrets、gitlint、Lychee 与 MOD 专有契约 |
| **部署与交付运维 (Ops)** | Nginx、systemd、原子版本软链切换、GitHub Actions、Fail2ban 防护 |

### 六、本地快速启动

前置开发环境：Python 3.13.15、[`uv`](https://docs.astral.sh/uv/)、Node.js 26.10.0、pnpm 12.6.0 与 Make。
Node 与 pnpm 版本的仓库级事实源为 `.tool-versions`；asdf 用户可在仓库根目录运行 `asdf install`。

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
> 仓库不分发中国地图几何数据；地图默认显示未配置状态。部署者只有在自行确认数据授权、现势性与适用法规后，
> 才应通过 `VITE_CHINA_MAP_GEOJSON_URL` 提供兼容 ECharts 的 GeoJSON `FeatureCollection`。

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
| [SUPPORT.md](SUPPORT.md) / [SECURITY.md](SECURITY.md) | 公共支持边界与私密漏洞报告前提 |
| [第三方组件与数据来源声明 (THIRD_PARTY_NOTICES.md)](THIRD_PARTY_NOTICES.md) | 第三方组件声明、中国地图数据隔离策略与使用边界 |
| [当前状态事实 (CURRENT-STATE.md)](docs/CURRENT-STATE.md) | 当前运行环境、数据规模与技术事实的唯一官方入口 |
| [文档总索引 (INDEX.md)](docs/INDEX.md) | 现行架构、开发标准、ADR 决策、历史资料与操作边界总览 |
| [已知问题看板 (KNOWN-ISSUES.md)](docs/KNOWN-ISSUES.md) | 系统技术债务与缺陷看板（已按 ADR-0014 闭环管理） |
| [变更日志 (CHANGELOG.md)](CHANGELOG.md) | 基于 git-cliff 由语义化提交自动生成的版本发行历史 |

### 八、开源许可

MOD 自研代码遵循 [MIT License](LICENSE) 开源协议。仓库、依赖锁与默认构建均不包含中国地图几何数据；
地图能力仅在部署者通过 `VITE_CHINA_MAP_GEOJSON_URL` 显式提供并自行确认合规的数据源后启用。
第三方组件声明及地图使用边界见[第三方组件与数据来源声明](THIRD_PARTY_NOTICES.md)。

---

<a id="english"></a>

## English

Updated: 2026-09-23 · Status: Active project overview · Current release: `v0.10.0`<br>
Scope: System positioning, architecture, 6-screen storytelling, development guide, and repository navigation

### 1. System Overview

MOD transforms the complex, multi-stage rollout of an enterprise-level core business system across 34 provincial regions and thousands of sub-units into a high-density, decision-ready visual command center.

It replaces the traditional, fragmented approach of "tracking progress via status reports, reconciling data across spreadsheets, and resolving risks through phone calls" with a unified, drillable management thread connecting **construction milestones, rollout readiness, operational evidence, dual-run accounting reconciliation, compliance posture, and AI-driven decision briefings**. Every top-level finding can be seamlessly drilled down into specific organizations, batches, stages, and raw business records.

### 2. Six Coordinated Command Views

The command cockpit comprises 6 dense, interconnected screens sharing global Pinia reactive state and in-memory data snapshots:

| Screen | Core Purpose & Decision Focus |
|---|---|
| **A · Overview** | Five-domain navigation, regional map and linked summaries, cross-domain trends, daily changes, and action queue |
| **B · Construction** | Construction overview, stage matrix, lagging regions, go-live gates, data readiness, and persistent ledger preview |
| **C · Rollout** | Current and historical batch progress, regional rollout gaps, contact exceptions, and unit rollout ledger |
| **D · Operations** | End-to-end document, voucher, and integration flow, daily throughput, dual-run reconciliation, and quality audits |
| **E · Compliance** | Compliance summary, risk tags, governance workflow, live activity, and issue drill-down |
| **F · Risk & Intelligence** | Primary bottlenecks, action priorities, risk distribution, model governance, and daily decision briefings |

### 3. Key Engineering Highlights

- **Decision-Centric Visual Storytelling**: Every chart and card directly supports decision-making, comparative analysis, drill-down, or operational follow-up.
- **High-Fidelity Synthetic Operations & Rigorous Accounting**: Powered by an autonomous simulation engine following standard enterprise accounting rules. Generates realistic diurnal rhythms (8:30-11:30, 13:30-17:00), month-end closing surges, and VAT input/output tracking. Across 4.9M vouchers, there are exactly 0 debit/credit imbalances, 0 orphan records, and 0 future date anomalies.
- **SWR In-Memory Snapshot Double Buffering (SLA < 1.0s)**: Employs Stale-While-Revalidate caching for millisecond API responses with asynchronous backend prewarming. Bundled fallback snapshots guarantee zero white-screen and zero-spinner resilience even during cold starts or network fluctuations.
- **Lakehouse In-Memory Acceleration & AutoML**: 9 core analytics tables are loaded into the MySQL HeatWave in-memory cluster, enabling instant multi-million row aggregations and automated risk scoring.
- **Dense, Responsive Visualization**: Vue 3 and ECharts 6 deliver interactive 34-region map penetration, cross-panel filtering, a real-time ticking clock, and auto-scaling layouts.
- **Enterprise Engineering Rigor**:
  - Local and CI workflows share type, unit, static-contract, build, and documentation gates; volatile test counts are derived rather than copied into this README;
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
| **Backend** | FastAPI, Python 3.13.15, SQLAlchemy 2.0, Uvicorn, Pydantic |
| **Data & Acceleration** | MySQL 8.4 HeatWave, HeatWave In-Memory Cluster, AutoML |
| **Quality & Assurance** | Pytest, Vitest, Playwright, Ruff, vue-tsc, ESLint, Stylelint, pre-commit, detect-secrets, gitlint, Lychee, and MOD-specific contracts |
| **Operations & Delivery** | Nginx, systemd, atomic release symlinks, GitHub Actions, Fail2ban |

### 6. Local Quick Start

Prerequisites: Python 3.13.15, [`uv`](https://docs.astral.sh/uv/), Node.js 26.10.0, pnpm 12.6.0, and Make.
The repository-level Node and pnpm version source is `.tool-versions`; asdf users can run `asdf install` from the repository root.

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
> The repository does not distribute China map geometry, so the map honestly reports an unconfigured source by default.
> A deployer may set `VITE_CHINA_MAP_GEOJSON_URL` to an ECharts-compatible GeoJSON `FeatureCollection` only after
> independently confirming its authorization, currency, and regulatory suitability.

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
| [SUPPORT.md](SUPPORT.md) / [SECURITY.md](SECURITY.md) | Public support boundaries and private vulnerability reporting prerequisites |
| [Third-Party Notices (THIRD_PARTY_NOTICES.md)](THIRD_PARTY_NOTICES.md) | Third-party component notices, China-map data isolation policy, and usage boundaries |
| [Current State (CURRENT-STATE.md)](docs/CURRENT-STATE.md) | Canonical source of truth for runtime, data, and architecture facts |
| [Documentation Index (INDEX.md)](docs/INDEX.md) | Master directory for architecture standards, ADRs, operations, and history |
| [Known Issues (KNOWN-ISSUES.md)](docs/KNOWN-ISSUES.md) | Defect and technical debt tracker (governed per ADR-0014) |
| [Changelog (CHANGELOG.md)](CHANGELOG.md) | Automated release history generated from verified Git commits |

### 8. License

MOD-authored code is released under the [MIT License](LICENSE). The repository, dependency lock, and default build
contain no China map geometry. Map rendering is enabled only when a deployer explicitly supplies a source through
`VITE_CHINA_MAP_GEOJSON_URL` after independently confirming compliance. See the
[Third-Party Notices](THIRD_PARTY_NOTICES.md) for component notices and map-use boundaries.
