# 原生 AI 客户端本地 Harness 接入记录

更新日期：2026-09-11
状态：已完成的历史运维记录
适用范围：2026-09-11 验证 agy, Kiro, Codex 等原生客户端对 local-harness 的适配

## 范围
记录本机各个原生 AI Agent 客户端针对本项目（MOD）采用的 Harness 纪律强制注入与钩子情况。此项检查是为了验证客户端侧是否能成功遵从“按需读取上下文”和“受控自动化测试”的安全原则。

## 各端配置接入结果
各原生端均未加载完整的外部沙箱 UI，而是按照“极简短规则注入 + 启动钩子”的原生模式接入，权限仍受本地管控约束。具体情况如下：

1. **agy (Antigravity CLI)** 
   - 规则注入：`~/.gemini/GEMINI.md` 作为全局强制规则成功介入大模型系统内核。
   - 钩子执行：`~/.gemini/config/hooks.json` 配置了 `PreInvocation`，自动执行 `node /home/ubuntu/local-harness/native-hook.mjs agy`。
2. **Codex (0.153.4)**
   - 规则注入：`~/.codex/AGENTS.md` 成功部署。
   - 钩子执行：`~/.codex/hooks.json` 的 `SessionStart` 事件（监听 `startup|resume|clear|compact`）调用了对应的 hooks 脚本进行受控启动拦截。
3. **Kiro (2.21.2)**
   - 规则注入：`~/.kiro/steering/local-harness.md` 设置完成。
   - 钩子执行：不仅是全局 Pilot（`~/.kiro/agents/pilot.json`），还涵盖了特殊工作流 Agent（`pe.json`, `sa.json`, `se.json`），其 `agentSpawn` 事件均被统一代理给 `native-hook.mjs kiro`。

## 核心表现与纪律约束
- **未配置状态退化**：在非项目路径（如 `/home/ubuntu`）启动 Agent 时，钩子能正确识别并反馈 `configured: false`，主动退化为 Discovery 发现模式，防止胡乱猜测业务域并随意修改。
- **强制按需加载**：客户端均遵守新规，不再直接吞入庞大的全局文档，而是规范地调用 `node /home/ubuntu/local-harness/cli.mjs context --scope <domain>` 请求导航索引，完全实现了方法论层面“隔离复杂业务”的提效初衷。
