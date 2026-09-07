# KI-043 · 后台写任务绕过 release 发布体系

- 状态：OPEN
- 优先级：P1
- 更新日期：2026-09-07
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[ADR-0008 前后端统一软链发布隔离](../decisions/0008-前后端统一软链发布隔离.md)、[ADR-0009 拟真引擎平移](../decisions/0009-拟真引擎平移为顶层独立模块.md)、[KI-039 模拟器状态接口脱节](KI-039-模拟器状态接口与独立常驻进程脱节并返回500.md)

## 结论

当前生产虽然为 `mod-api` 和前端建立了基于软链的 release 版本化发布体系，但后台常驻写进程及定时任务仍直接运行于源码工作区：
1. `mod-simulator.service`、`mod-ml-retrain.service`、`mod-daily-briefing.service` 均直接指向开发工作区源码路径（如 `/home/ubuntu/mod/scripts/agy/run_simulator_service.py`）。
2. 工作区内的代码修改、分支切换或未经验收的代码会直接被常驻进程在下一个 tick 加载或在定时任务中执行。
3. 统一发布脚本 `publish.sh` 只管理前端与 API，没有将后台服务纳入构建、验证、原子切换、进程重载或故障回滚链条。
4. API 内部（`backend/app/main.py`）仍残留另一套历史进程内模拟器启动分支，存在双写与歧义风险。

## 2026-09-07 现场证据

- `systemctl cat mod-simulator.service` 显示直接执行工作区中的 python 脚本。
- 发布脚本 `scripts/project/publish.sh` 仅发布 `backend/app/` 并重启 `mod-api`，对后台写服务无感知。
- `backend/app/main.py:50` 存在旧模拟器分支，未彻底清理。

## 修复目标

- 后台常驻服务纳管进统一版本化 release 或独立可控 release 流程。
- 统一发布与重启联动：代码发布时联动平滑重启常驻服务，保障新旧版本切换的一致性。
- 彻底移除 `backend/app/main.py` 中历史残留的进程内模拟器启动入口。

## 进度

- 2026-09-07：现场核验并立项。
