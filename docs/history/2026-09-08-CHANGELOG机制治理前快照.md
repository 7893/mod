# CHANGELOG 机制治理前快照

- 状态：历史
- 更新日期：2026-09-08
- 适用范围：KI-058 修正前的 CHANGELOG 内容、git-cliff 说明与生命周期口径
- 原始位置：`CHANGELOG.md`、`cliff.toml`、`docs/development/DOCUMENTATION-LIFECYCLE.md` 第四节
- 取代原因：原文声称存在 `v0.1.0` tag 且 CI 会生成 CHANGELOG，但仓库无任何 tag，CI 也未执行 git-cliff
- 取代来源：[KI-058](../issues/KI-058-CHANGELOG基线失真与生成链路未闭环.md)

---

## 原 `CHANGELOG.md` 完整内容

```markdown
# 变更日志

所有重要变更均由 Conventional Commits 自动生成，自 v0.1.0 起。

### Refactoring

- Migrate insights screen to cockpitpanel
```

## 原 `cliff.toml` 头部说明与 CHANGELOG 头

```toml
# git-cliff configuration — generate CHANGELOG.md from Conventional Commits.
# Changelog starts at tag v0.1.0 (2026-09-04). Generated in CI; no local toolchain required.

[changelog]
header = """
# Changelog

All notable changes are generated from Conventional Commits since v0.1.0.
"""
```

## 原文档生命周期第四节完整内容

```markdown
## 四、变更记录（CHANGELOG）

- `CHANGELOG.md` 位于仓库根，**从规范化提交自动生成，不手写**。
- 前提已具备：提交遵循 Conventional Commits（`feat/fix/docs/refactor/...`，见 commit-msg 闸门）。
- 起点：从 tag `v0.1.0`（2026-09-04）起计，早期不规范提交不纳入。
- 工具：git-cliff，配置见根目录 `cliff.toml`；**不安装到本地开发环境**，发版时用二进制临时生成。
- 生成方式（发版时执行，方案 C）：
  - 打新版本 tag 后，生成本次区间的条目并前置到 CHANGELOG：
    `git-cliff --config cliff.toml --tag vX.Y.Z --unreleased --prepend CHANGELOG.md`
  - 或全量重生成：`git-cliff --config cliff.toml --output CHANGELOG.md`
  - git-cliff 以二进制运行（按平台架构下载，如 aarch64/x86_64），用后即弃，不进依赖树、不进 PATH。
- 它回答“版本间变了什么”，与 CURRENT-STATE（“现在什么样”）互补。
- 未来若需全自动，可另建独立 workflow 并授予最小写权限；当前采用发版手动生成以避免自动提交与写权限复杂度。
```
