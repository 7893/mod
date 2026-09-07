# KI-041 · API 与模拟器共用可写数据库账号及公网无认证暴露风险

- 状态：OPEN
- 优先级：P0
- 更新日期：2026-09-07
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[数据与安全标准](../development/DATA-AND-SECURITY-STANDARD.md)、[ADR-0008 前后端统一软链发布隔离](../decisions/0008-前后端统一软链发布隔离.md)

## 结论

当前生产存在严重的数据库访问边界与接口暴露缺陷：
1. `mod-api.service` 与 `mod-simulator.service` 共用 `.env.systemd` 中的 `MOD_DB_USER=admin` 全权限账号（具备 SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER 等全部权限）。API 进程原则上只负责只读聚合查询，但实际具备销毁生产数据库表结构的物理权限，严重违反“默认只读”与“最小权限原则”。
2. 系统公网首页、OpenAPI 文档与快照接口均无需认证即可访问，OpenAPI 没有任何 `securitySchemes`。
3. `/api/insights/generate` 为无认证公网 POST 接口，可直接触发外部 Cloudflare Workers AI 模型调用与配额消耗。

## 2026-09-07 现场证据

- `.env.systemd` 仅定义单个 `MOD_DB_USER=admin`，由 API 与模拟器共用加载。
- 生产 MySQL 实例上 `admin` 账号具备全部 DDL/DML 权限。
- OpenAPI 规范未定义认证方案，公网无鉴权可调用 POST `/api/insights/generate`。
- 当前系统被定义为内部系统，但仅依赖 robots.txt 与 UA 拦截，缺乏实质访问控制凭据体系。

## 修复目标

- 拆分数据库账号：为 `mod-api` 配置专用只读账号（仅授权 `SELECT` 权限）；为模拟器与离线批处理配置独立写账号。
- 服务环境文件隔离：拆分各自独立的 systemd 环境配置文件。
- 变更高危/外部调用接口：为 `/api/insights/generate` 及管理接口引入内部认证机制。

## 进度

- 2026-09-07：现场核验并立项。
