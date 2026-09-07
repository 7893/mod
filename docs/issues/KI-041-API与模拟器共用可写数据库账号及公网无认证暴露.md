# KI-041 · API 与模拟器共用可写数据库账号及公网无认证暴露风险

- 状态：DONE
- 优先级：P0
- 更新日期：2026-09-08
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[数据与安全标准](../development/DATA-AND-SECURITY-STANDARD.md)、[ADR-0008 前后端统一软链发布隔离](../decisions/0008-前后端统一软链发布隔离.md)

## 结论

已彻底完成数据库只读权限边界物理隔离、服务环境变量解耦以及高危外部模型接口的鉴权防护：
1. **只读账号物理隔离**：生产 MySQL 独立创建 `mod_readonly` 专用账号，仅授予 `mod.*` 及 `ML_SCHEMA_admin.*` 的 `SELECT` 权限。实测对所有 DDL/DML 操作（INSERT, UPDATE, DELETE, CREATE, DROP）100% 物理拦截（MySQL Error 1142: Table access denied）。
2. **服务环境文件隔离**：`mod-api.service` 拆分为独立环境配置文件 `/home/ubuntu/mod/.env.api.systemd`（权限 0600），与模拟器和写任务的环境文件彻底解耦；后台写任务继续保留写账号。
3. **高危/外部接口鉴权**：
   - 变更高危接口 `POST /api/insights/generate`，强制要求内部访问凭据（`X-MOD-Auth-Token` / `Bearer` / `X-Action-Token`），未授权请求直接拦截返回 HTTP 401，杜绝公网恶意消耗 Cloudflare Workers AI 配额。
   - `GET /api/insights/status` 签发受信任会话短效 `action_token`（基于 HMAC-SHA256 与时区窗口滑动校验），前端驾驶舱平滑集成，合法用户无感操作。
   - OpenAPI 规范正式接入标准 `securitySchemes`（`ApiKeyAuth`、`BearerAuth`、`ActionTokenAuth`）。

## 2026-09-07 现场证据

- `.env.systemd` 仅定义单个 `MOD_DB_USER=admin`，由 API 与模拟器共用加载。
- 生产 MySQL 实例上 `admin` 账号具备全部 DDL/DML 权限。
- OpenAPI 规范未定义认证方案，公网无鉴权可调用 POST `/api/insights/generate`。
- 当前系统被定义为内部系统，但仅依赖 robots.txt 与 UA 拦截，缺乏实质访问控制凭据体系。

## 修复目标

- 拆分数据库账号：为 `mod-api` 配置专用只读账号（仅授权 `SELECT` 权限）；为模拟器与离线批处理配置独立写账号。
- 服务环境文件隔离：拆分各自独立的 systemd 环境配置文件。
- 变更高危/外部调用接口：为 `/api/insights/generate` 及管理接口引入内部认证机制。

## 验收证据

1. **数据库权限核验**：
   - `mod_readonly` 具备 `SELECT` 权限，成功聚合查询 `org_unit` (2002 行) 与模型元数据。
   - 故障注入 `CREATE`, `INSERT`, `UPDATE`, `DELETE`, `DROP` 五类破坏性操作，全部被 MySQL 物理拦截并返回 `OperationalError 1142`。
   - `SHOW PROCESSLIST` 确认生产 `mod-api` 实例以 `mod_readonly` 连接数据库，`mod-simulator` 仍以 `admin` 运行，职责彻底解耦。
2. **服务配置隔离**：
   - `mod-api.service` 加载 `/home/ubuntu/mod/.env.api.systemd`，权限严格受控为 `0600`。
   - 服务单元文件增加 `TimeoutStopSec=5`，避免长链接阻塞守护进程平滑重启。
3. **接口鉴权验证**：
   - 未授权访问 `POST /api/insights/generate` 返回 `HTTP 401 Unauthorized` (`{"detail": "未授权访问..."}`)。
   - 携带合法 `action_token` 或 `X-MOD-Auth-Token` 返回 `HTTP 200 OK`，正常触发受控研判。
   - `GET /api/openapi.json` 经校验包含 `securitySchemes`（`ApiKeyAuth`, `BearerAuth`, `ActionTokenAuth`）。
4. **全量回归通过**：
   - 后端 169 项单测全绿通过（`test_auth.py`, `test_api.py`, `test_runtime_service.py`）。
   - 前端 84 项单测全绿通过，类型检查与构建通过。
   - `make check` 全绿。

## 进度

- 2026-09-07：现场核验并立项。
- 2026-09-08：完成专用只读账号创建与权限验证、环境配置文件拆分、高危接口鉴权保护及 OpenAPI securitySchemes 接入，状态转为 DONE。
