# KI-003 · fallback 快照文件由缺陷 SQL 生成，内含上述不一致

- 状态：DONE（2026-09-04，本地已修复，尚未部署）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`frontend/src/data/v2-sim-snapshot.json` 静态快照曾携带 KI-001、KI-002 的不一致。
- 根源：该快照是某次用当前在线 SQL 逻辑 dump 生成的产物。
- 影响：本地/离线 fallback 展示沿用了同样的错误。
- 处理：修复 KI-001、KI-002 后，使用 `tools/v2/build_v2_snapshot.py` 从冻结 V2 资产只读重建
  `frontend/src/data/v2-sim-snapshot.json`；省级新增合计与总览一致，单据发生日与快照基线日保持区分，
  对应 `xfail` 已移除。
