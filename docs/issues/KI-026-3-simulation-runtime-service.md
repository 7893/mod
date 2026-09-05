# KI-026-3 · 拟真引擎第三步：常驻后台服务·持续实时增长

- 状态：DONE（2026-09-05，agy 开发完成并通过 live 短窗口实测、8 闸门复测与故障注入验证，待主控系统级部署上线）
- 更新日期：2026-09-05
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 背景：第一步（业务佐证足迹）、第二步（建设主线 + B 模式推进器）均已落地、真实写库、主控验收全绿；
  香港作息节律引擎 `HongKongDiurnalEngine` 已存在并经主控实测（周六中午强度 0.048、周一上午 2.0+、
  月末 2.5 封顶）。缺口：节律（大脑）与写库引擎（手）尚未接线为常驻服务，当前靠手动跑脚本单日推进。
- 目标：把已验收部件组装成 7×24 常驻后台服务，按真实心跳持续、自然地写库增长，使系统任何时刻看都像
  一个活着的真实系统。不新增业务剧本、不改剧本逻辑，只做"运行化"。
- 已落实设计决策：
  1. 模拟时钟＝实时同步（模拟时间=真实香港时间，一天过一天，不加速不追赶不倒插）。
  2. 速率双重限流：作息节律柔性限流 + 滑动硬上限保险丝（每分钟≤20、每天≤5000，可配，超限暂停+告警）。
  3. 异常容灾策略：单批次自检失败回滚该批继续跑；连续 3 批失败自动触发持久化 `output/simulator_fail_closed.flag` 物理停机与 CRITICAL 审计告警。
  4. 托管架构：独立 systemd 服务配置（`deploy/mod-simulator.service`，与 mod-api 解耦），开机自启、崩溃自愈；持久化 fail-closed 标志保证重启不绕过保险丝。
- 实施完成记录：
  - F1 内核与自检：完成 `backend/app/simulation/runtime_service.py`（`SimulatorRuntimeService`、`RateLimitFuse`、`PostCycleSelfChecker`、`FailClosedManager`）与 `backend/tests/test_runtime_service.py`（覆盖熔断、自检、fail-closed、dry-run、周期推进），110 项单元测试全绿（Commit `233f399`）；
  - F2 服务化与运维工具：完成 `deploy/mod-simulator.service` 与 CLI 工具 `scripts/agy/run_simulator_service.py`，支持 `--status`、`--dry-run`、`--once`、`--clear-fail-closed`，周期落盘结构化健康心跳 `output/simulator_status.json`（Commit `ed834ae`）；
  - F3 实测与验证：
    - 短窗口 live 单步实测：周六 13:54 HKT 触发真实原子落库 1 笔业务足迹（`doc_id=5050517`），经办人命中本单位（`sys_user` 602 魏嘉怡），借贷平衡（12,603.98），时间递增（审批 14:02:21 晚于提交 13:54:30）；
    - 8 闸门与 KI-017 全量复测：10 项第一步自检与 8 项第二步硬闸门全绿通过，KI-017 零回归；
    - 故障注入验证：测试持久化 `output/simulator_fail_closed.flag`，服务立即转入 `FAIL_CLOSED` 物理阻断状态，调用拒绝（Exit code 1）；使用 `--clear-fail-closed` 成功恢复就绪状态（Exit code 0）。
- 交付物：
  - `backend/app/simulation/runtime_service.py`
  - `backend/tests/test_runtime_service.py`
  - `deploy/mod-simulator.service`
  - `scripts/agy/run_simulator_service.py`
  - `output/simulator_status.json` (心跳落盘)
- 待主控执行项：系统级 systemd 服务安装（`sudo cp deploy/mod-simulator.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now mod-simulator.service`）与上线持续监控。
- 主控上线完成（2026-09-05）：代码逐段验收 5 决策全部落实、make check 绿（110 测试）；按两段流程上线——
  先装服务保持开关关闭空跑 dry-run 观察节律正常、库不动，再置 `MOD_SIMULATION_ENGINE_ENABLED=true`
  重启开真实写库。实测：服务 `enabled`（开机自启）+`active`+`Restart=always`（崩溃自愈），jpa 重启
  自动继续；库按实时香港时钟自然增长（周六下午低强度、约每分钟 1 笔）、最新记录时间戳跟随真实时钟、
  KI-017 全表零回归、限流与 fail-closed 正常。**拟真引擎常驻服务已正式上线运行。**
- 运维约定：模拟器长期常驻；主控每日巡检一次（数据增长、作息曲线、阶段演化、KI-017 零回归、审计与
  fail-closed 状态），异常即报。
- 后续待办（治本）：验收/自测脚本（`verify_sim_step1.py`、服务 `--once` 等）历史上会真实落库造成重复
  污染（已由主控多次备份并级联清理，仅保留 2026-09-04 正式验收批）；待 agy 改为一律 dry-run 或写后
  回滚，验收脚本绝不持久落库。
