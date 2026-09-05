# KI-002 · 单据发生日期与快照基线日期塌缩为同一天

- 状态：DONE（2026-09-04，本地已修复，尚未部署）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`docsAddedAsOfDate` 与 `asOfDate` 相等（均为 2026-09-03），R6 契约（二者应不同）不再成立。
- 根源：`dashboard_v2.py` overview SQL 中 `docs_as_of_date = ds.stat_date`、`as_of_date = :anchor_date`，
  且 `WHERE ds.stat_date = :anchor_date` 强制二者相等；R6 契约原本依赖“单据日期比基线日期早一天”的脆弱假设。
- 影响：R6“单据发生日期 vs 快照基线日期”区分失效。
- 原证据：同 KI-001 的一致性测试（修复前为 `xfail`）。
- 处理：保留 R6 契约；单据新增口径改为快照日前最近完整业务日，快照基线继续来自
  `daily_stats.stat_date`，两者由独立数据源派生且测试强制区分。
