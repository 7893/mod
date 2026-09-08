# KI-058 · CHANGELOG 基线失真与生成链路未闭环

- 状态：DONE（2026-09-08）
- 优先级：P2
- 更新日期：2026-09-08
- 适用范围：`cliff.toml`、`CHANGELOG.md`、CHANGELOG 基线、生成入口、CI 验证和版本标签产物
- 关联：[KI-020 自动生成 CHANGELOG](KI-020-自动生成CHANGELOG.md)、[KI-054 文档历史保全](KI-054-文档生命周期约束与历史内容保全闸门.md)、[文档生命周期](../development/DOCUMENTATION-LIFECYCLE.md)

---

## 问题

KI-020 将 git-cliff 配置与初始 `CHANGELOG.md` 视为已完成，但只读核查发现：

1. `cliff.toml`、`CHANGELOG.md` 和生命周期规范都声称从 `v0.1.0` 起计，仓库实际没有任何 Git tag。
2. `cliff.toml` 注释声称在 CI 生成，生命周期规范却说发版时人工临时执行，现有 CI 中没有 git-cliff。
3. `CHANGELOG.md` 仅有一条旧的 Refactoring 记录，没有反映公开基线之后的实际提交。
4. 本机没有安装 git-cliff，项目也没有统一的本地生成入口、版本锁定和配置验证。

## 根因

- 将“配置文件存在”误当成“发版链路已闭环”。
- 基线标签没有实际创建，也没有对基线存在性做自动检查。
- CHANGELOG 是“每次提交都更新”还是“版本标签时生成”没有单一口径。

## 决策

1. 不伪造从未存在的 `v0.1.0` 发布标签，也不在本任务擅自创建或推送标签。
2. 以真实存在的首个公开就绪提交 `35280a1d75e50478bc68dda4d64e7a9ac27f40dc` 为明示基线，用独立基线文件供本地与 CI 共用。
3. `CHANGELOG.md` 作为发布时生成的冻结产物，不要求每次提交自动回写，避免自动提交和写权限。
4. 普通 CI 校验基线、配置和已保存 CHANGELOG 的结构；版本 tag 或人工触发时用锁定版本的 git-cliff 生成只读归档产物，不自动提交、推送或发布。
5. 修改原口径前先把旧 `CHANGELOG.md`、`cliff.toml` 说明和生命周期第四节完整保存为历史切片。

## 验收标准

- [x] 历史旧口径与原 CHANGELOG 内容已完整保存，没有删除历史内容。
- [x] 基线指向真实提交并可验证为 `HEAD` 祖先，不再宣称存在虚假 tag。
- [x] git-cliff 版本锁定，本地与 CI 使用同一配置、基线和生成语义。
- [x] `CHANGELOG.md` 已根据真实 Git 历史重新生成，原始内容在历史切片中保留。
- [x] CI 会验证 CHANGELOG 配置，版本 tag/人工触发会生成可下载产物，不获取写权限。
- [x] 自动化回归测试与全量 `make check` 通过。

## 实施结果

- 新增 `.git-cliff-baseline`，锁定到真实存在的公开就绪提交 `35280a1d75e50478bc68dda4d64e7a9ac27f40dc`，质量闸门同时验证其存在且为 `HEAD` 祖先。
- `cliff.toml` 与 CI 均锁定 git-cliff 2.13.1；GitHub Action 进一步锁定到 v4.8.0 发布提交 `f50e11560dce63f7c33227798f90b924471a88b5`。
- 使用官方 Linux aarch64 二进制生成完整 CHANGELOG，下载包 SHA-256 已核对为 `9619b7f0c584229f8a2331c1905afe88bd938bdc9102926c2073836a42f02455`，重新生成结果与入库文件逐字节一致。
- 新增本地生成器、契约检查器、只读 CHANGELOG 产物工作流和 5 项专项回归测试；共有 13 项项目治理脚本测试通过。
- 原始 CHANGELOG、虚假 tag 口径与原生命周期规则已完整保存到带日期历史切片，KI-020 追加勘误而未改写原记录。
