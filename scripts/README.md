# MOD scripts

临时脚本按 CLI 所有者隔离；稳定、可复用的项目脚本单独管理。完整规则见
`docs/development/CLI-SCRIPT-POLICY.md`。

- `codex/`：Codex / OpenAI GPT 专用。
- `claude/`：Claude Code 专用。
- `kiro/`：Kiro CLI 专用。
- `agy/`：Antigravity / agy 专用。
- `user/`：人工临时脚本。
- `project/`：经过审阅的稳定项目脚本。

禁止在项目根目录创建散落脚本，禁止跨 CLI 目录写入。
