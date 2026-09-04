# 大模型 CLI 脚本目录制度

更新日期：2026-09-02
状态：现行
适用范围：所有人类和大模型 CLI 创建的临时及项目脚本

## 目的

所有临时诊断、迁移草稿、截图、检查和一次性修复脚本必须有明确所有者，禁止再次散落在项目根目录。
本制度适用于 Codex、Claude Code、Kiro CLI、Antigravity/agy、GitHub Copilot 以及人工临时脚本。

## 目录映射

| 执行者 | 专用目录 | 入口约束 |
|---|---|---|
| Codex / OpenAI GPT | `scripts/codex/` | `AGENTS.md` |
| Claude Code | `scripts/claude/` | `CLAUDE.md` |
| Kiro CLI | `scripts/kiro/` | `.kiro/steering/mod-project-rules.md` |
| Antigravity / agy | `scripts/agy/` | `GEMINI.md` |
| GitHub Copilot | `scripts/copilot/` | `.github/copilot-instructions.md` |
| 人工临时脚本 | `scripts/user/` | 本文 |
| 稳定项目脚本 | `scripts/project/` | 必须有 README 和验证方式 |

## 强制规则

1. 每个 CLI 只能在自己的目录创建临时脚本，不得写入其他 CLI 的目录。
2. 禁止在项目根目录创建 `.py`、`.js`、`.mjs`、`.ts`、`.sh`、`.sql` 等散落脚本。
3. `database/`、`generator/` 和 `tools/` 中的现有脚本视为历史兼容；新的临时脚本不得放入这些目录。
4. 临时输出必须进入本目录下的 `tmp/` 或 `output/`；这两个名称已全局忽略。
5. 脚本不得硬编码密码、Token、私钥、连接串、真实人员信息或敏感主机信息。
6. 可复用脚本只有在补齐用途、参数、风险、示例和验证后，才能移入 `scripts/project/`。
7. USA 只保留部署所需的项目脚本；CLI 临时脚本默认不向 USA 同步。
8. 历史状态机保留但停用，不得借脚本目录重新启动状态机流转。

## 脚本头部要求

新脚本必须在文件头说明：用途、所有者、输入、输出、是否只读、运行环境和危险操作。
涉及数据库、服务、Nginx、云资源或远端写入时，还必须说明授权边界和回滚方式。

## 清理规则

- 任务结束后删除无价值的临时输出；需要保留的证据应脱敏并进入项目文档。
- 不再使用但仍需追溯的脚本移至 `archive/`，不要留在活动目录。
- `scripts/project/` 不接受未引用、无文档或只能运行一次的脚本。
