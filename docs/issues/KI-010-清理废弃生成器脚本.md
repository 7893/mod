# KI-010 · database/、generator/ 内无凭据的废弃文件待清理

- 状态：DONE（2026-09-05）
- 更新日期：2026-09-05
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`database/`（generate/verify 之外的历史脚本）与 `generator/v2/`（generate_v2/v3、incremental、
  config、dictionary、test 等）仍留有不再使用的历史文件；本次仅归档了含明文凭据的 8 个脚本。
- 说明：这些文件不含凭据，不属于“泄漏清理”范围，故未在早前处理。
- 处置（2026-09-05）：数据生产已由拟真引擎（`backend/app/simulation/` + 常驻服务）取代旧的"批量生成 CSV
  再导入"范式。将 `generator/v2/` 全部 7 个文件（generate_v2/v3、incremental_generator、config、
  config_v3、dictionary、test_generate_v2）与 `database/import_mod_s_v2_incremental.py` 移入本地忽略的
  回收站 `archive/legacy-db-scripts/`；`generator/` 空目录已移除。`database/` 仅保留只读验收工具
  `verify_mod_s_v2_readonly.py`（仍可用于库合规核验）。这些均为 gitignored 文件，不影响版本库；运行中的
  引擎/服务均不依赖被归档文件（已核验）。同步更新 `AGENTS.md` 与 `PROJECT-LAYOUT.md` 消除"规则称保留、
  实际已废弃"的漂移。
