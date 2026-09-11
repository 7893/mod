# MOD 本地 Harness 剥离与归档记录

更新日期：2026-09-11
状态：已完成的历史运维记录
适用范围：2026-09-11 本地 Harness 脚手架代码剥离与历史包袱归档

## 范围
本次操作旨在清理 MOD 项目中为适配 AI Agent 所写的“土法手搓”验证脚本和过长的指导文件，将这些能力外包给宿主机原生的 `local-harness` 框架，让项目代码完全回归业务本质。

## 剥离与归档结果
1. **自定义命令外包**：移除了 `.pi/extensions/mod-harness.ts` 中手写的 `/pre-flight` 命令逻辑。剥离出的长片段归档至 `archive/pi_extensions/mod-harness.ts`。现已统一交由全局 Pi 扩展负责上下文控制与命令编排。
2. **测试脚本透明代理**：修改了 `scripts/project/pre_flight.sh`。其冗长的前后端检查 Bash 逻辑被归档至 `archive/scripts/pre_flight.sh`。现有脚本仅作 fallback 检查，优先执行 `exec node /home/ubuntu/local-harness/cli.mjs check` 作为透明代理。
3. **临时工作区打扫**：清理了根目录临时手写的测试与只读查询脚本（`check_financial_integrity.py`、`check_amount_col.py`、`test_tz.py` 等），将其移动至不入库的 `archive/scripts/` 目录。
4. **历史规则文档裁剪**：精简了 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 与 `.kiro/steering/mod-project-rules.md` 中的重复历史指导规则，被替换的历史文档长文归档进了 `docs/history/2026-09-11-HARNESS-ENTRYPOINTS.md`。

## 验证结论
- 所有旧脚手架逻辑通过 Git Commit 记录被物理剥离（`a5189ab` 等）。
- `.gitignore` 正常拦截忽略 `archive/` 目录变动，保证仓库始终干净。
- 剥离后，执行全量测试门禁（`make check`，包含代码风格、视觉以及前端测试）全部通过。
