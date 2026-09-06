# KI-026 · 拟真引擎第二步：建设管控主线 + B模式生命周期推进器

- 状态：DONE（2026-09-05 完成代码实现、单元测试 100 项全绿、8 条硬闸门全量 dry-run 审计验证通过，且经主控授权已完成第一轮真实写库落地：写入前 7 表完整备份、严格 2000 行/批分批提交与进度留痕、事后 8 闸门只读复测全绿，KI-017 零回归）
- 更新日期：2026-09-05
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 背景：拟真引擎第一步（费用报销业务佐证足迹 + 安全写库器）已落地并验收全绿（100 笔小试落库、
  KI-017 零回归），机制地基已验证。第一步属业务佐证（次线）。
- 目标：实现 `docs/development/BUSINESS-SIMULATION-ENGINE.md` 定义的**建设管控主线（逼真主角）**——
  7 类建设事件（入池、数据准备、培训认证、接口联调、双轨核对、跃迁评审、批次推进）的完整多表足迹，
  加 **B 模式生命周期推进器**（单位阶段由真实指标驱动跃迁：只进不退、持续达标 N 天才跃迁、跃迁走
  “申请→评审→状态变更→留痕”、少数单位喂成困难户），并使困难户与风险预测读同一事实源、天然自洽（矛盾咬合）。
- 范围与顺序（5 个阶段全部按规范独立提交、独立验证）：
  - 阶段 A（commit `aff0044`）：建设事件足迹模型 + 确定性校验（`construction_models.py`，不连库不写库，26 项单测）。
  - 阶段 B（commit `a6bdf82`）：7 类建设管控剧本生成器（`construction_playbooks.py`、`scripts/agy/dry_run_construction_playbooks.py`，因果门禁严格，经办人 100% 取自本单位人员，12 项单测）。
  - 阶段 C（commit `a53e157`）：B 模式 6 阶段状态机推进器（`lifecycle_advancer.py`，严格执行“只进不退、持续达标 N 天才跃迁、跃迁评审留痕快照”三条铁律，4 项单测）。
  - 阶段 D（commit `20ae0dc`）：快慢电影演进协调器 + 矛盾咬合机制（`evolution_coordinator.py`、`scripts/agy/dry_run_evolution_meshing.py`，~4% 自然涌现困难户与风险视图 100% 咬合自洽，3 项单测）。
  - 阶段 E（commit `341cf24`）：8 条硬闸门全量 dry-run 自检通过（`scripts/agy/verify_step2_dry_run.py`，0 数据库修改）+ 事务写库器与自动快照备份（`construction_writer.py`，3 项单测）。
  - 写库执行轮（本轮提交）：
    - 写入前全量备份：7 张受影响表完整备份至 `scripts/agy/output/backups/construction_backup_20260905_131434.json`（43.37 MB，耗时 5.78s）；
    - 严格分批单事务提交：按 2,000 行/批分 3 批逐批 commit（批次 1: 2,001 行；批次 2: 2,000 行；批次 3: 177 行），实时打印行数、事件数与累积进度，无超大事务；
    - 累计真实落库 4,178 行：`org_unit` 20 行跃迁更新（已上线 282，稳定运行 466）、`rollout_status_snapshot` 20 行专家决议留痕快照（总 144,870）、`data_readiness` 238 行指标同步、`training` 476 行认证记录（总 5,520）、`dual_run_result` 1,230 行双轨核对（总 30,288）、`construction_task` 2,194 行任务足迹联动更新（总 62,104）；
    - 验收脚本独立纯只读：`scripts/agy/verify_step2_dry_run.py` 严格保持只读（0 写库），与批量写入入口 `scripts/agy/run_step2_batch_write.py` 彻底解耦；
    - 事后 8 闸门全绿核验：落库后立即针对 live MySQL 运行 8 闸门只读核查，全部 PASS 通过，KI-017 零回归。
- 写库纪律：开关 `MOD_SIMULATION_ENGINE_ENABLED` 默认关闭；具备写入前自动备份（`backup_affected_tables`）、批量 commit 与进度审计日志；写库与验收脚本物理分离。
- 验收（8 条硬闸门实测）：①四级下钻加总一致 (2000单位层层咬合 PASS) ②阶段跃迁只进不退 (状态机硬约束保证 PASS) ③跃迁有过程有留痕 (评审决议+快照归档完备 PASS) ④横截面自洽 (未上线单位零越界业务 PASS) ⑤KI-017 零回归 (经办人100%命中本单位、借贷平衡、无污染与逆序 PASS) ⑥接续存量时间线无倒插 (锚定存量最新业务日 PASS) ⑦困难户与风险预测矛盾咬合 (同一事实源 100% 一致 PASS) ⑧工程与安全开关受控 (make check 绿、安全开关受控 PASS)。
- 分工：设计与验收由主控 agent 负责；实现由 agy 执行（脚本 `scripts/agy/`）。派工单见
  `scripts/kiro/tmp/mod-task-dispatch.html`（滚动更新的单一派单文件，同步于 sga 文件目录）。
- 主控独立验收（2026-09-05，非 agy 自检）：主控对 live MySQL 独立 SQL 复测 8 闸门全绿——
  经办人命中/时间逆序/状态污染/孤儿凭证全表=0；20 单位「已上线→稳定运行」方向前进无倒退；
  org_unit 状态与 9-05 快照一致（mismatch=0）；未上线单位零正式业务；新记录日期 2026-09-05 晚于基线
  2026-09-04 无倒插；make check 绿、100 项测试。**主控验收通过。**
- 后续项（登记）：
  1. 数据库账号：经决策 MOD 继续使用 admin 连库（真值仅存运行主机本地 `.env.systemd`/`.env.local`，
     均 gitignored，绝不入库）；`.env.example` 已改为中性占位并注明真值只留本地。原「建专用非 admin
     写账号」提醒**取消**（按用户决策）。
  2. `scripts/agy/run_step2_batch_write.py` 与 `backend/app/simulation/runtime_service.py` 的 DB fallback 已清除硬编码废弃账号名 `mod_v2_writer`，改为必须由本地 env 传入，缺失即阻断报错。
  3. 当前仅写入 2026-09-05 单日足迹；持续按天生长（运行化/连续跑）由第三步（KI-026-3）承接。
- 关联：KI-017（存量治理，本步零破坏零回归）、KI-023/KI-015（决策支撑真实性，矛盾咬合的盾侧）。
