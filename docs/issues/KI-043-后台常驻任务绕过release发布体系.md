# KI-043 · 后台写任务绕过 release 发布体系

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-08
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[ADR-0008 前后端统一软链发布隔离](../decisions/0008-前后端统一软链发布隔离.md)、[ADR-0009 拟真引擎平移](../decisions/0009-拟真引擎平移为顶层独立模块.md)、[KI-039 模拟器状态接口脱节](KI-039-模拟器状态接口与独立常驻进程脱节并返回500.md)

## 结论

已彻底完成后台常驻服务与定时任务纳入统一软链 Release 发布体系、解除可编辑安装对工作区的隐式硬编码，并清除了 API 进程内残留模拟器分支：
1. **统一 Release 打包与结构对齐**：扩展 `scripts/project/publish.sh`，在生成 `backend/releases/<TS>/` 时完整打包 `app/`、`simulation/` 及 `scripts/`，并建立 `app -> .` 软链。彻底解除 Python 虚拟环境对开发工作区的依赖。
2. **所有后台服务与定时任务纳管 Release**：
   - 更新 `mod-simulator.service`：工作目录与执行入口切换至 `/home/ubuntu/mod/backend/current`，运行 `current/scripts/agy/run_simulator_service.py`。
   - 更新 `mod-daily-briefing.service`、`mod-ml-retrain.service`、`mod-backup.service`：全部切换至 `backend/current` 软链路径。
   - 生产主机上的代码修改、分支切换或未经验收的代码被完全隔离在工作区，永不影响生产常驻与定时任务。
3. **发布与回滚双向联动**：
   - `publish.sh` 发布时原子切换软链后，同时联动平滑重启 `mod-api` 与 `mod-simulator`，并同步执行双重探针核验（`/api/health` 与 `/api/simulator/status`）。
   - 探针异常时自动执行原子回滚，同时回滚前后端软链并重启 `mod-api` 与 `mod-simulator`。
4. **彻底消除进程内双写隐患**：
   - 彻底移除 `backend/app/main.py` 中历史残留的 `_simulator_task = asyncio.create_task(run_simulator_loop(...))` 分支。API 进程专注于只读实时投影 `live_projection`，彻底杜绝双写、越权写或模式歧义。

## 2026-09-07 现场证据

- `systemctl cat mod-simulator.service` 显示直接执行工作区中的 python 脚本。
- 发布脚本 `scripts/project/publish.sh` 仅发布 `backend/app/` 并重启 `mod-api`，对后台写服务无感知。
- `backend/app/main.py:50` 存在旧模拟器分支，未彻底清理。

## 验收证据

1. **统一发布与原子切换实测**：
   - 执行 `bash scripts/project/publish.sh`，成功构建并发布 release `20260908-003625`。
   - 软链切换完成：
     - `frontend/current -> /home/ubuntu/mod/frontend/releases/20260908-003625`
     - `backend/current -> /home/ubuntu/mod/backend/releases/20260908-003625`
   - 服务重启成功：`mod-api`（PID 870883）与 `mod-simulator`（PID 870892）均运行于 `releases/20260908-003625`。
2. **运行态进程工作区解耦核验**：
   - `sudo ls -l /proc/870883/cwd` 确认指向 `/home/ubuntu/mod/backend/releases/20260908-003625`。
   - `sudo ls -l /proc/870892/cwd` 确认指向 `/home/ubuntu/mod/backend/releases/20260908-003625`。
   - `sudo cat /proc/870892/cmdline` 确认命令为 `/home/ubuntu/mod/backend/current/scripts/agy/run_simulator_service.py`。
3. **接口探针与契约核验**：
   - `/api/health` 线上返回 HTTP 200，时间与数据库连接正常。
   - `/api/simulator/status` 线上返回 HTTP 200，状态为 `RUNNING`，`fresh=True`。
4. **API 进程内无写任务**：
   - `backend/app/main.py` 的 `lifespan` 仅包含 `live_projection`，无任何后台模拟器循环。
   - `make check` 全绿通过（后端 176 单测全过，前端 84 单测全过，类型检查与构建全绿）。

## 进度

- 2026-09-07：现场核验并立项。
- 2026-09-08：完成主流程模拟器残留代码移除、统一发布脚本打包扩充、后台服务全量纳管 release 软链及线上平滑发布验收，状态转为 DONE。
