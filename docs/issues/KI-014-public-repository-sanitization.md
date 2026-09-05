# KI-014 · 上 GitHub 公开仓库前的净化工程

- 状态：DONE（2026-09-04，已按路线 A 变体完成并公开）
- 更新日期：2026-09-04
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 完成方式：净化活跃区全部敏感值（IP/OCID/CF账号/密码/域名脱敏或改环境变量）；`archive/`、
  `database/`、`generator/`、`docs/history/`、真实 nginx conf 等经 `.gitignore` 排除；旧 `.git`
  历史打包备份至 `archive/`（本地留存），`git init` 重建干净历史；公开仓库 github.com/7893/mod，
  多轮全量机密扫描确认零泄露。
- 目标：将本仓库发布为 GitHub 公开仓库，并启用 GitHub Actions CI。
- 前提判断：当前**不具备**公开条件；版本库（含 Git 历史）存在多类敏感信息，直接公开会泄露。

**需要处理的三层敏感信息**（缺一层都不算净化完成）：

1. 源码配置值 —— 基本达标，仍需补全
   - 活跃 backend 已由环境变量驱动（USA 从 `.env.systemd` 读 `MOD_DB_HOST` 等）。
   - 待办：补全 `.env.example`，把数据库主机、账号、Cloudflare Account ID、域名等所有需要的
     变量名以占位符形式列全；确认活跃代码无遗漏的硬编码值。
2. 文档与注释中的明文敏感信息 —— 环境变量覆盖不到，须逐处脱敏改写
   - 内网 IP 内网数据库地址（脱敏）：出现在 `database/`、`generator/`、`docs/18`、`docs/tasks/` 等。
   - USA 公网 IP（如 `USA公网地址（脱敏）`）：出现在 `docs/18`、`docs/20` 及归档 benchmark。
   - OCI OCID（tenancy/user）：`docs/18` 等。
   - Cloudflare Account ID、真实域名（现行 生产域名（脱敏），历史 `历史域名（脱敏）`、`历史域名（脱敏）`）：
     `AGENTS.md`、`README.md`、`deploy/nginx/` 等。
   - 待办：将上述真实值改写为脱敏占位符或中性描述。
3. Git 历史中的敏感信息 —— 最易被忽略，公开后 `git log` 可翻出
   - 明文密码 管理员口令（脱敏）、上述 IP/OCID 均存在于历史提交中。
   - 两条路线（择一）：
     - 路线 A（推荐）：新建干净公开仓库，仅导入脱敏后的当前快照，不带历史。
     - 路线 B：对原仓库用 `git filter-repo` 清除历史敏感信息（高风险，重写全部提交哈希，需专门授权）。

**公开配套（净化完成后）：**
- 添加 `LICENSE`（当前缺失）。
- 添加 GitHub Actions workflow，在 CI 侧执行凭据扫描与 `make check`（同时解决 KI-012 的不可绕过第二道）。
- CI 仅做检查，不做部署：**不建议**在公开仓库配置到 USA 的 CD，避免把 SSH 私钥/服务器地址托管到 GitHub；
  部署继续手动或置于私有渠道。CI 使用 fallback 快照，不连生产数据库、不接触 USA。

- 建议：作为独立任务系统执行，不零敲碎打；执行前按 ENFORCEMENT 确认范围与授权。

**进展与净化前置（2026-09-04）**
- 已补全 `.env.example`（列全代码实际读取的全部变量，占位/空值，无真实值）。
- 已新增 `docs/development/SECRETS-AND-CONFIG.md` 规范（.env / GitHub Secrets / 公开净化）。
- 只读扫描的敏感信息清单（活跃区需处理，归档/历史区另议）：
  - 内网 IP 内网数据库地址（脱敏）：活跃文件 `database/verify_mod_s_v2_readonly.py`、`generator/v2/generate_v3.py`、
    `docs/tasks/*`；历史区 `docs/history/18`。
  - Cloudflare Account ID：活跃文件 `scripts/claude/shoot.sh`、`workers/mod-browser/src/index.ts`。
  - OCI OCID：仅 `docs/history/18`（历史区）。
  - 明文密码：集中在 `archive/legacy-db-scripts/*`（归档区）与 `docs/KNOWN-ISSUES.md`（问题描述引用）。
  - 真实域名 生产域名（脱敏）：多处（本就对外的站点域名，按需判断是否脱敏）。
- 路线选择：用户倾向路线 B（清洗历史）。分析意见：B 为高危不可逆操作（重写全历史、可能使既有
  签名失效、与 USA git 及并发工作冲突），性价比低；推荐路线 A（新仓库、当前净化状态为起点、不带历史）
  同样避免自建 HTML 且风险极低。最终路线待用户确认；无论 A/B 均须先完成上述活跃区脱敏前置。
- GitHub 公开后可直接使用其 Actions（CI 已就绪）与仓库 Secrets 管理机密。
