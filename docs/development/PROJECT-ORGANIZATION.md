# 项目组织约束

更新日期：2026-09-02
状态：现行
适用范围：项目目录、源码分层、文件规模、脚本和文档位置

## 主机职责

- 运行主机 `/home/ubuntu/mod`：唯一源码、Git、文档、测试、工具、数据和历史资产目录，同机承载生产运行
  （后端服务、前端 `dist`、拟真引擎常驻服务）。不再有独立的纯部署主机（见 ADR-0006）。
- 环境文件只留在使用它的主机，永远不进入 Git 或历史归档。

## 后端边界

- `backend/app/api*.py`：路由、参数和响应编排，不堆积查询构建与领域算法。
- `backend/app/services/`：应用用例、快照构建和跨数据源编排。
- `backend/app/integrations/`：HeatWave、Cloudflare 等外部平台适配器。
- `backend/app/simulation/`：保留但默认不用的模拟器领域模型；不得绕过安全门禁启动。
- 旧导入路径如有调用方依赖，可保留小型兼容门面，但新代码必须直接使用领域模块。

## 前端边界

- 页面组件放在 `frontend/src/views/`，可复用组件放在 `frontend/src/components/`。
- 全局样式入口仅负责按顺序导入；样式分别放入 `frontend/src/styles/` 的基础、组件、页面和响应式文件。
- 不手工拆改 Element Plus、ECharts 或其他第三方产物；优化通过源码导入与构建配置完成。

## 大文件规则

- 自研源码目标不超过 400 行；超过 600 行必须拆分，或在代码评审说明不能拆分的领域原因。
- 拆分以职责和领域为边界，不以机械编号命名，不建立 `misc`、`helpers`、`common2` 等垃圾桶目录。
- 生成数据、生成客户端、第三方组件库和不可维护的封版产物不适用行数限制。

## 脚本与文档

- 各大模型 CLI 只能写入 `scripts/<owner>/`，具体规则见 `CLI-SCRIPT-POLICY.md`。
- 可复用且经审阅的项目脚本才可进入 `scripts/project/`。
- 开发规范归 `docs/development/`，部署运维归 `docs/operations/`，历史状态机只读保留。
- 完整开发、协作、测试、文档和数据安全要求分别见本目录对应的 `*-STANDARD.md`。
