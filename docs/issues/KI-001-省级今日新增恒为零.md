# KI-001 · 省级今日新增恒为 0，与总览不一致

- 状态：DONE（2026-09-04，本地已修复，尚未部署）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：驾驶舱省级 `todayAdded` 求和为 0，但总览 `docsTodayAdded` 为非零值（如 805），二者对不上。
- 根源：`backend/app/services/dashboard_v2.py` 省级 SQL 中 `0 AS todayAdded` 为未实现的占位值；
  总览 `docs_today_added` 取自 `daily_stats.doc_today` 的真实值。
- 影响：省级下钻的“今日新增”是假数据；R3 一致性契约无法成立。
- 原证据：`backend/tests/test_v2_api.py::test_v2_snapshot_internal_consistency_contract`（修复前为 `xfail`）。
- 处理：在线查询按最近完整业务日聚合单位单据并汇总到省级，总览新增量由同一省级结果求和；
  fallback 已从冻结 V2 资产只读重建，R3 一致性测试转为强制通过。
