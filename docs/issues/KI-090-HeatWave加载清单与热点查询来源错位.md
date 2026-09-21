# KI-090 · HeatWave 加载清单与热点查询来源错位

- 状态：DONE
- 优先级：P2
- 更新日期：2026-09-21
- 适用范围：HeatWave RAPID 表加载、全景快照查询、内存配额
- 来源：[KI-085 第 4 项](KI-085-核心架构缺陷与数据安全治理.md)

## 问题

[`scripts/project/heatwave_manager.py`](../../scripts/project/heatwave_manager.py) 与 [`backend/app/heatwave_watchdog.py`](../../backend/app/heatwave_watchdog.py)
原先各自维护 9 表清单，遗漏了单位投影/快照热依赖 `sys_user`、`data_readiness`和 `daily_stats`。
这使健康检查的“全部就绪”与实际分析依赖不一致，也让多表计划因关联表未全部进入 RAPID 而保留 InnoDB 路径。

生产性能、表规模与内存证据已于 2026-09-21 通过只读核查取得；这些证据只支持配置与代码决策，不自动授权生产 DDL。

## 2026-09-21 证据与代码处理

- 生产只读核查显示旧目标清单 9/9 就绪，`sys_user`、`data_readiness`、`daily_stats`
  未装载；HeatWave 节点约使用 4.605 GiB / 16.106 GiB。
- 原 C5 五表查询的计数阶段约 0.1332s、数据阶段约 0.2564s，整体约 0.3901s；执行计划没有
  RAPID，且在返回 20 行前会物化 `construction_task`、`sys_user`、`dual_run_result` 等集合。
- 表规模与内存余量证明三张表具备进入目标清单的基本条件：`sys_user` 约 41,242 行，
  `data_readiness` 约 2,020 行，`daily_stats` 约 1,148 行。它们虽小，但作为 join/聚合依赖会影响整条分析路径是否可下推。
- C5 独立五表重算已从代码中删除，改为复用全景快照的单位投影。HeatWave 目标表已收口到
  `backend/app/heatwave_tables.py`，应用看门狗与运维脚本共用同一份 12 表目标配置。
- 提交 `7a5193c` 经 GitHub Actions 运行 `35596006939` 发布成功。发布后先只读确认生产数据库为
  `mod`、缺失集合恰为上述三表，再经授权单次触发看门狗补载。三表分别耗时 0.45s、0.38s、0.28s，
  `/api/health` 已返回 12/12 `HEALTHY`且无缺失表。

## 完成定义

- [x] 取得热点查询、执行计划、表规模和 RAPID 内存占用证据；
- [x] 按证据确定保留、移除和新增的表清单；
- [x] 运维脚本与看门狗共用同一份目标表配置；
- [x] 经独立数据库授权完成三表补载变更；
- [ ] 完成一次实际回退演练（本次已核对 `SECONDARY_UNLOAD` 回退路径，未为演练主动降级生产）；
- [x] 快照性能、HeatWave 健康检查和全量质量门禁通过。

## 2026-09-21 Owner 终止追踪

项目 Owner 因不再持有本历史 KI 的完整业务语境，决定终止剩余追踪。本条 `DONE`
只表示不再列入当前待办，不表示未勾选的实际回退演练已完成；原验收状态保留。
后续不重开或据此直接施工；若同类缺陷以当前可复现故障、失败测试、生产或用户证据重新出现，
应重新核验并使用新 KI 登记。见 [ADR-0023](../decisions/0023-清空存量KI并按当前复现重新登记.md)。

## 操作边界

本条目不授权生产查询、HeatWave DDL、表加载或卸载。
