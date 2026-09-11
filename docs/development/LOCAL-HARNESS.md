# 本地通用 Harness 接入

更新日期：2026-09-11
状态：现行
适用范围：MOD 接入本机通用 Pi 工具、按需上下文与摘要验收

## 职责与入口

公共实现位于本机 `/home/ubuntu/local-harness/`，全局 Pi 设置只加载公共 `extension.ts`。
MOD 的 `.pi/extensions/mod-harness.ts` 由项目目录自动发现，保留查库、模拟器状态和 pre-flight 兼容入口。
项目 `.pi/settings.json` 不再重复声明扩展路径，旧 JSON 保存在公共包的 `archive/2026-09-11/`。
公共工具不包含 MOD 数据库或生产地址，其他未接入项目只读识别，不执行候选脚本。

## 按领域加载

`AGENTS.md` 为简短公共红线，`.pi/harness.json` 提供领域引用和检查命令。
前端任务只加载公共边界和前端契约；涉及 API/数据时再扩展到对应领域。工具返回索引或指定章节，
每次最多 120 行、12,000 字符，附原始行号、内容哈希、下一页位置；失效引用报错，不回退全文。
其余 CLI 入口只指向 AGENTS 和领域索引，不再重复要求全文加载。
旧入口完整保存在[迁移前原文](../history/2026-09-11-HARNESS-ENTRYPOINTS.md)，不作为现行指令加载。
Skill 继续作为导航使用，详细规则仍以现行标准为唯一来源。本轮未复制或改写领域标准。

## 检查与报告

```bash
node /home/ubuntu/local-harness/cli.mjs context --scope frontend
node /home/ubuntu/local-harness/cli.mjs read --scope frontend --ref 3
node /home/ubuntu/local-harness/cli.mjs check --scope frontend
node /home/ubuntu/local-harness/cli.mjs check --scope frontend --run
make pre-flight
node /home/ubuntu/local-harness/cli.mjs check --full --run
```

`check` 默认只计划；没有 scope 时按所有未提交变更选择领域，显式 scope 会报告排除的领域。
输出只含检查状态和私有日志路径；失败详情按需读取。全量验收仍运行 `make check`，Git hook/CI 不变。
执行前校验本机注册的 manifest 哈希；修改检查配置后须审核命令再更新批准，不能自动批准任意项目。
报告包含工作树前后指纹，变化时标记过期；不缓存通过结果。超时和取消均失败。
已有 pre_flight.sh 原始实现保留为公共包缺席时的兼容回退，公共包存在时直接调用统一入口。
运行会产生本地日志和正常测试/构建产物，不发布生产、不启动模拟器、不执行数据库查询。

## 限制与回滚

这不是 Shell 沙箱，不能拦截其他 CLI 的所有执行；检查脚本仍需审阅。现有项目信任设置本轮未改变。
不宣称具体 token 节省比例：测量入口长度和工具输出，实际费用需后续任务统计。
本轮仅正式接入 MOD；Lens/PaddlePal/lens-sdk 等可识别脚本名称，但没有执行授权和领域配置。
恢复公共包 archive 中的全局/项目 JSON 即恢复原加载方式；原始 CLI 入口见历史切片。
决策见 [ADR-0011](../decisions/0011-local-harness.md)。

## 本轮验证（2026-09-11）

任务范围补充：现在可用 `task --target KI-076 --intent investigate` 获取只读排查计划，
目标引用和文件都带选择原因；检查由该 KI 的映射选择，不被无关工作树变更扩大。
investigate 禁止执行检查，repair/accept 仍须显式运行；accept 列出完整门禁、视觉构建、视觉回归和人工要求。
`passed` 只表示自动检查通过，不代表 KI 已关闭。此前领域模式保持兼容。
本次只验证 harness 工作流，不实际排查、修复或关闭 KI-076；旧实现和配置完整保存在公共包 archive 中。
本次公共包 19 项隔离测试通过，Pi loader 加载成功；排查模式加 `--run` 实测返回失败且没有执行检查。
无目标的既有增量门禁通过，目标验收仅核对计划，没有运行视觉测试或替 KI 作出结案判断。

- 公共包 14 项隔离测试通过，覆盖跨项目识别、引用分页、路径越界、检查批准、失败、超时、取消和结果过期。
- Pi 0.85.1 loader 成功加载公共和 MOD 扩展，工具/命令无重名；没有调用模型或数据库。
- MOD 的 `make pre-flight` 与经公共入口执行的全量 `make check` 均通过，验收期间工作树指纹一致。
- Lens、PaddlePal、lens-sdk、80 仅做只读发现验证，没有接入执行命令。
- AGENTS 入口由 11,892 字节缩为 3,772 字节，减少约 68%；这是入口文本体积，不是整个任务的 token 节省率。
- 公共包独立本地 Git 提交为 `ce489b1`；配置原文的恢复哈希已核验。
