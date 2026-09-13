# ADR-0015: 引入 CodeGraph 与 Graphify 增强代码导航与架构全景

- 状态：采纳
- 日期：2026-09-13

## 背景
MOD 项目包含 200+ 核心源码文件（Python、TypeScript、Vue）、数十篇已知缺陷（KI）与架构规范文档、复杂的 MySQL 库表结构，以及从仿真引擎到实时投影再到多屏驾驶舱的深层调用链路。
在以往的研发和排查过程中，AI Agent 与开发者主要依赖文本检索（`grep`/`find`）以及手动维护的 `.pi/harness.json` 静态文件清单进行定位：
1. 跨文件符号跟踪耗时长，容易产生文本匹配噪音与误报；
2. 难以快速、精确地推导某个核心符号或函数修改的全局“爆炸半径（Blast Radius）”及关联测试用例；
3. 文档、SQL 库表与代码之间存在认知断层，缺乏直观、可交互的全局系统拓扑大盘。

## 决策
在开发环境全局安装并在 MOD 项目中按需激活两大互补的代码智能与知识图谱工具：
1. **CodeGraph**：专注于纯代码符号网络与调用拓扑，作为日常开发与重构的高精度导航与影响面分析工具；
2. **Graphify**：专注于多模态资产（代码 + Markdown 文档 + SQL Schema），作为宏观系统全景拓扑测绘与架构体检工具。

## 理由
1. **精准性与执行效率互补**：
   - CodeGraph 采用原生 Rust 内核毫秒级解析 AST，能够精确计算函数/类的直接调用者（Callers）、被调用者（Callees）、改动影响范围（Impact）以及受波及的测试用例（Affected），在单次工具调用内提供行号保真的源码切片，显著减少 AI 工具调用轮次与误改风险。
   - Graphify 具备多模态穿透能力，能够将业务规则、缺陷文档、SQL DDL 与应用代码串联成图，支持 Leiden 算法业务社区聚类与最短路径寻路，并生成可直接在浏览器交互的 `graph.html` 拓扑大屏与系统体检报告 `GRAPH_REPORT.md`。
2. **零侵入与自动化运作**：
   - 两者均为开发时辅助工具，不向业务代码库注入任何生产运行时依赖。
   - CodeGraph 通过后台文件监听（300ms debounce）实现无感增量同步；Graphify 通过 Git Hook（`.githooks/post-commit`）在提交后于后台完全异步静默刷新，日常开发完全放养、零维护开销。

## 后果
1. **数据隔离与 Git 保护**：`.codegraph/`、`graphify-out/` 及 `.graphify*` 缓存已被加入 `.gitignore`，严禁提交到代码仓库。
2. **AI Agent 操作规范更新**：`AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 及全局规则已更新，要求所有 AI 工具在项目代码探查与修改前优先调用图谱能力（`codegraph_explore` / `graphify query`），禁止无目的全量 grep 翻查。
3. **环境依赖沉淀**：全局二进制 CLI（`codegraph`、`graphify`）由本机环境维护，项目缺席图谱时自动安全回退至标准文本检索与本地 Harness 门禁，不阻塞 CI/CD 流水线。
