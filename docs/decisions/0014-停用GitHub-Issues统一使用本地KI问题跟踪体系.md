# ADR-0014 · 停用 GitHub Issues，统一使用本地 KI 问题跟踪体系

更新日期：2026-09-13
状态：现行
适用范围：问题跟踪、缺陷登记、GI 编号体系

---

## 决策

**停用 GitHub Issues 作为问题跟踪工具，所有问题、缺陷与技术债登记统一使用本地 KI（Known Issue）体系。** GI（GitHub Issue）编号体系同步废止，历史 GI-001~004 编号仅作归档，不再维护。

---

## 背景

项目早期曾并行使用两套跟踪体系：
- **GitHub Issues（GI 编号）**：#1~#4，均为功能性需求描述
- **本地 KI 文档（KI 编号）**：`docs/issues/KI-xxx.md`，包含详细证据、分析与修复方案

随着项目演进，本地 KI 体系已成为唯一实际运作的问题跟踪渠道，KI 编号已累计至 KI-082。GitHub Issues 长期处于停滞状态，4 个 Issue 均已关闭，与本地 KI 完全脱节，形成信息孤岛。KI-064 曾专门修复 GI/KI 口径混用导致的文档引用错误，进一步确认双轨并存没有价值。

---

## 决策理由

**选择本地 KI 而非 GitHub Issues 的原因：**

1. **信息完整性**：本地 KI 包含只读证据（代码行号、实际检查结果）、影响分析、完整修复方案和完成定义清单，GitHub Issues 的文本框不适合这种结构化内容。

2. **与代码同仓库**：KI 文档与源码、部署配置在同一 Git 仓库，变更可以原子提交，不会出现代码修了但 Issue 未更新的漂移。

3. **治理机制已建立**：`docs/KNOWN-ISSUES.md` 是 KI 的索引看板，`make check` 会检查文档治理合规性，`MANIFEST.sha256` 保证历史 KI 不被篡改。这套机制在 GitHub Issues 上无法复现。

4. **AI Agent 协作**：多个 AI Agent 直接读写本地文档，GitHub Issues 需要额外的 API 调用和权限管理。

5. **私有信息安全**：KI 文档可能包含内网 IP、服务名、数据库结构等敏感信息，本地文档通过 `.gitignore` 和脱敏规则管理，GitHub Issues 公开可见。

---

## 后果

- GitHub Issues 功能在仓库设置中保持开启（供外部贡献者提交反馈），但项目内部问题跟踪不使用此功能。
- 所有新发现的问题、缺陷和技术债直接登记为 KI，遵循 `docs/development/DOCUMENTATION-STANDARD.md` 规范。
- GI-xxx 编号体系废止。历史文档中出现的 GI-001~004 引用均视为旧版本记录，不再更新。
- 任何 AI Agent 或协作者发现问题时，直接新建 `docs/issues/KI-xxx.md` 并更新 `docs/KNOWN-ISSUES.md`，不得在 GitHub Issues 新建条目。

---

## 关联

- KI-064：GI 编号口径与 GitHub Issue 状态不一致（已修复，本决策为其最终收尾）
- [已知问题看板](../KNOWN-ISSUES.md)
- [文档规范](../development/DOCUMENTATION-STANDARD.md)
