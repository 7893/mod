# MOD 历史文档脱敏规范

更新日期：2026-09-12
状态：现行规范
适用范围：`docs/history/` 敏感历史资料的脱敏模式、脱敏副本命名、版本化保全与自动化处理规则

---

## 一、 治理目标与双层保全原则

依据 [ADR-0004 废弃内容归档不删除](../decisions/0004-废弃内容归档不删除.md)、[文档生命周期规范](DOCUMENTATION-LIFECYCLE.md) 与 [KI-074 治理方案](../issues/KI-074-历史文档未版本化保全与语义治理闸门缺失.md)，历史资料的保全与公开安全必须实行**双层保全架构**：

1. **原件绝对不删除、不就地覆盖**：
   - 原始文档完整保留于本机 `docs/history/`，受 `docs/history/MANIFEST.sha256` 与 `scripts/project/check_history_integrity.py` 强哈希防护。
   - 任何脱敏操作不得修改或覆盖原件正文，杜绝历史事实丢失。
2. **公开仓库可见脱敏副本**：
   - 为避免真实基础设施 IP、OCI OCID、主机名、内部域名与账号标识泄露，对包含历史环境信息的原件生成命名对齐的 `.sanitized.md` 副本。
   - 脱敏副本纳入 Git 跟踪，对新克隆、各协作 Agent 与 CI 管道完全公开可见。
3. **稳定标识唯一对应**：
   - 脱敏副本与原件共享同一个稳定编号（H-001 ～ H-028 等），并在 `docs/HISTORY-CATALOG.md` 中明确登记双向映射。
4. **灾难恢复异机备份**：
   - 完整受限原件通过客户端强加密（AES-256-CBC PBKDF2 100,000 次迭代）打包外发至受限异机备份存储，配合本地恢复演练工具确保主机损毁时可百分之百无损还原。

---

## 二、 标准脱敏字典与替换模式

脱敏工具 `scripts/project/sanitize_history.py` 必须严格遵循以下替换模式字典：

| 敏感类别 | 原始示例 / 识别特征 | 脱敏替换规范 | 说明 |
|---|---|---|---|
| **内网 IP (IPv4)** | `10.0.10.27` / `10.0.0.152` | `10.0.x.x (内网地址，已脱敏)` 或 `<internal-ip>` | 保护私有子网拓扑 |
| **公网 IP (IPv4)** | `193.122.180.196` | `193.122.x.x (USA公网地址，已脱敏)` 或 `<public-ip>` | 隐藏生产宿主机真实外网 IP |
| **私网 IPv6** | `2603:c020:400d:de00:0:5dc5:c462:fc01` | `<ipv6-address (已脱敏)>` | 隐藏 IPv6 分配明细 |
| **OCI 租户 OCID** | `ocid1.tenancy.oc1...qzsena` | `<tenancy-ocid>` | 隐藏 OCI 租户唯一标识 |
| **OCI 子网 OCID** | `ocid1.subnet.oc1...7v5mya` | `<subnet-ocid>` | 隐藏 OCI 私有子网标识 |
| **Compute 实例名** | `instance-20210605-2242` | `<usa-vm-instance-id>` | 隐藏具体计算节点名称 |
| **MySQL 实例名** | `mysqldbsystem20260822145022` | `<mysql-instance-name>` | 隐藏云数据库实例真实命名 |
| **MySQL 备份标识** | `mysqlbackup20260830172017` | `<mysql-backup-id>` | 隐藏云备份任务内部标识 |
| **可用域与容错域** | `ypNq:US-ASHBURN-AD-1` / `FAULT-DOMAIN-2` | `<us-ashburn-ad>` / `<fault-domain>` | 隐藏具体 AD/FD 内部编号 |
| **生产域名** | `usa.8n8m.cfd` / `*.8n8m.cfd` | `<production-domain>` 或 `example.com` | 隐藏生产解析域名 |
| **数据库明文密码** | `IDENTIFIED BY '...'` / 环境变量 | `<db-password>` 或 `<REDACTED>` | 绝对严禁明文出现 |
| **API 密钥与 Token** | `cfat_...` / `Bearer ...` | `<cf-api-token>` / `<auth-token>` | 隐藏外部 API 凭据 |

---

## 三、 脱敏副本元数据与命名要求

1. **命名规范**：
   - 对应原件 `docs/history/{name}.md`，脱敏副本必须命名为 `docs/history/{name}.sanitized.md`。
2. **头部强制声明**：
   每份脱敏副本顶部必须包含以下标准化元数据块：
   ```markdown
   > **保全说明**：本文件为历史资料 `docs/history/<原文件名>` 的公开脱敏副本。
   > **稳定 ID**：<稳定编号，如 H-001>
   > **原件哈希 (SHA-256)**：`<原件 64 位哈希>`
   > **脱敏规范**：遵循 [SANITIZATION-RULES.md](SANITIZATION-RULES.md)，所有真实内网/公网 IP、OCID、域名及主机标识已完成安全脱敏，技术结构与演进过程 100% 保真。
   ```
3. **正文完整性**：
   - 除了将敏感词元映射替换为标准占位符外，禁止缩减、曲解、删节任何上下文、技术步骤、数据模型定义或分析结论。

---

## 四、 自动化闸门与目录联动

1. **自动化脱敏工具**：
   - 执行 `python3 scripts/project/sanitize_history.py` 自动完成所有受限文档的脱敏副本派生。
   - 执行 `python3 scripts/project/sanitize_history.py --check` 在 CI / `make check` 中执行反向泄漏扫描，若脱敏副本中残存未脱敏 IP、OCID 或敏感域名则阻断提交流程。
2. **完整性清单更新**：
   - 生成脱敏副本后，其 SHA-256 必须同步记入 `docs/history/MANIFEST.sha256`。
   - `scripts/project/check_history_integrity.py` 对原件与脱敏副本统一进行防篡改核验。
3. **历史目录登记**：
   - `docs/HISTORY-CATALOG.md` 逐条记录原件保全状态与脱敏副本文件名，保持仓库索引的一致性。
4. **Git 忽略规则对齐**：
   - `.gitignore` 保持忽略受限原件，但显式白名单开放 `!docs/history/*.sanitized.md`。
