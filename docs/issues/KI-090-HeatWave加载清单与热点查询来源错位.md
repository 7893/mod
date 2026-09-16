# KI-090 · HeatWave 加载清单与热点查询来源错位

- 状态：OPEN
- 优先级：P2
- 更新日期：2026-09-16
- 适用范围：HeatWave RAPID 表加载、全景快照查询、内存配额
- 来源：[KI-085 第 4 项](KI-085-核心架构缺陷与数据安全治理.md)

## 问题

[`scripts/project/heatwave_manager.py`](../../scripts/project/heatwave_manager.py) 与 [`backend/app/heatwave_watchdog.py`](../../backend/app/heatwave_watchdog.py) 的加载清单包含 `construction_task` 等表，但不含 `daily_stats`。与此同时，[`backend/app/services/dashboard.py`](../../backend/app/services/dashboard.py) 的总览、运营和趋势查询持续读取 `daily_stats`。

代码层已确认加载清单与热点查询来源不一致；是否造成生产性能损失仍需以只读执行计划、查询频率和 HeatWave 内存占用核实，不能直接凭文档执行 DDL。

## 完成定义

- [ ] 取得热点查询、执行计划、表规模和 RAPID 内存占用证据；
- [ ] 按证据确定保留、移除和新增的表清单；
- [ ] 运维脚本与看门狗共用同一份目标表配置；
- [ ] 经独立数据库授权完成变更和回退演练；
- [ ] 快照性能、HeatWave 健康检查和全量质量门禁通过。

## 操作边界

本条目不授权生产查询、HeatWave DDL、表加载或卸载。
