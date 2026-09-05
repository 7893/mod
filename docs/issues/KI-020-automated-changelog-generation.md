# KI-020 · 自动生成 CHANGELOG

- 状态：DONE（2026-09-04，方案 C：工具+规范就位，发版手动生成）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 背景：已具备 Conventional Commits 规范与 commit-msg 闸门，但尚无 CHANGELOG，变更历史只能靠 `git log`。
- 处理：引入 git-cliff（配置 `cliff.toml`），从 tag `v0.1.0` 起计；生成初始 `CHANGELOG.md`；
  发版生成方式写入 `DOCUMENTATION-LIFECYCLE.md` 第四节。工具以二进制临时运行，不装入本地环境、不进依赖树。
- 未采用 CI 全自动：避免写权限与自动提交复杂度；未来需要时可另建独立 workflow。
