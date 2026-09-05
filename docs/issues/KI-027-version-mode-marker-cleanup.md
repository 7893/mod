# KI-027 · 版本/模式标记深度整治（唯一正统，去 v1/v2/v3、去 s_v2）

- 状态：DONE（2026-09-05，三批全部完成并验证）
- 更新日期：2026-09-05
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)、[ADR-0006](../decisions/0006-single-host-consolidation.md)

## 背景与目标
项目历史上散落 v1/v2/v3 版本标记与 `mod_s`（S=模拟模式）库名标记，造成"看起来有多版本/多模式"的混乱。
实际上：v1 已死（`api.py` 定义 `/api/v1` 但 `main.py` 未挂载、前端不调）、v3 已归档（旧生成器）、
整个库本就是唯一的模拟演习环境（无混合模式）。目标是**全局唯一正统、干净命名，不再分 v1/v2/v3、不在库名带 s_v2**：
- 库名 `mod_s_v2` → `mod`
- API `/api/v2` → `/api`
- 代码模块 `api_v2.py`/`dashboard_v2.py`/`schemas_v2.py` → 去 `_v2`
- 环境变量 `MOD_V2_DB_*` → 统一 `MOD_DB_*`；去掉 `mod_s` 幽灵默认值与 `db_name_v2` 双轨
- 删除 v1 死代码（`api.py` + 仅被其引用的 `schemas.py`）
- 模式说明：整个 `mod` 库即模拟演习环境，靠文档说明，不引入 `mode` 字段（当前无同库多模式需求）

## 硬约束
- 库改名期间先停模拟器（fail-closed 开关），先备份，用同实例 `RENAME TABLE` 搬表（元数据操作、秒级、不复制数据），改配置后重启验证，KI-017 全绿后再删空旧库。
- 不改表结构、不删业务数据；连接凭据仅存本地环境文件。
- 分批执行、每批 make check + 服务验证、可回退。

## 分批执行
- 第一批（安全，不碰运行库）：删 v1 死代码；模块改名去 `_v2`；环境变量统一 `MOD_DB_*`、去 `mod_s`/`db_name_v2` 双轨。
- 第二批（API）：`/api/v2` → `/api`（后端路由 + 前端调用 + Nginx location 同步切换）。
- 第三批（库名，最高风险）：停模拟器 → 备份 → `RENAME TABLE` 搬到新库 `mod` → 改所有连接与硬编码 → 重启 → KI-017 验证 → 删空旧库。

## 进度
- 第一批（完成，commit 1082ed3）：删 v1 死代码（`api.py`+`schemas.py`）；模块去 `_v2`
  （`api_v2.py→api.py`、`schemas_v2.py→schemas.py`、`dashboard_v2.py→dashboard.py`、`test_v2_api.py→test_api.py`）；
  环境变量统一 `MOD_DB_*`，去 `MOD_V2_DB_*` fallback、`mod_s` 幽灵默认与 `db_name_v2`/`database_url_v2` 双轨；
  合并 db.py 双 engine 为单一 `connection`。110 测试绿、后端验证正常。
- 第二批（完成，commit 4f14488）：API 路由 `/api/v2`→`/api`（后端 2 个 prefix + 前端 3 处 + Nginx SSE 精确 location
  同步切换）；health 响应去 `version` 字段；`data_version` 去 `v2.0-` 前缀。前后端/SSE 全部 200，旧路径 404。
- 第三批（完成，2026-09-05）：库名 `mod_s_v2`→`mod`。停模拟器 → 全库备份（184MB 留底）→ 同实例
  `RENAME TABLE` 搬 25 表到新库 → 改 config/3 writer 默认值、`.env.systemd`/`.env.local`/`.env.example` 的
  `MOD_DB_NAME`、heatwave_sql 跨库限定名（加反引号，因 `mod` 是 MySQL 保留字）→ 重启 mod-api + mod-simulator
  验证 → KI-017 全表零回归、数据完整（2000 单位/26713 人）、模拟器恢复写入 → 删空的旧库 mod_s_v2。
- **整治完成：全局唯一正统，无 v1/v2/v3，库名 `mod`、API `/api`、模块无 `_v2`、环境变量 `MOD_DB_*`。**
- 注意事项（留档）：`mod` 是 MySQL 保留字，SQL 中显式引用库名须用反引号 `` `mod` ``；连接参数（database='mod'）不受影响。
- 待 agy 处理（不代改他人目录）：`scripts/agy/` 下脚本仍硬编码旧库名 `mod_s_v2` 与 `MOD_V2_DB_NAME`
  （`phase1~4_*`、`run_step2_batch_write`、`dry_run_*` 的 `ALLOWED_DB_NAME`/默认值）。phase1~4 是 KI-017
  一次性历史脚本已执行完；但 `run_step2_batch_write`/`dry_run_*` 若将来再跑，会因库名守卫指向已改名的
  `mod_s_v2` 而失败——待 agy 统一改为 `mod` + `MOD_DB_NAME`。
- 本地验收工具已更新：`database/verify_mod_s_v2_readonly.py` → `database/verify_mod_readonly.py`，
  库名引用改 `mod`、变量改 `MOD_DB_NAME`（gitignored，本地工具）。
- 防复发约束（2026-09-05）：已在 `AGENTS.md` 项目组织节新增"单一正统命名"硬约束——禁止给一方代码/文件/类/
  库名/表名/API 路由追加 `_v2`/`_v3`/`_s` 等版本或模式后缀来"迭代"，就地演进、迭代靠 git 历史承载；
  保留旧版走 archive 归档而非主线并存。豁免外部依赖版本、已冻结数据资产、ADR/KI 编号、有序迁移脚本编号。
