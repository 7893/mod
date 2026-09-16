# MOD 灾难恢复操作手册 (Disaster Recovery Runbook)

- 文档版本：v2.0.0
- 更新日期：2026-09-16
- 状态：现行
- 适用范围：生产主机故障、数据库损坏下的灾难恢复

---

## 灾备策略（2026-09-16 起）

**项目级 R2 备份链路已退役**（见 [KI-095](../issues/KI-095-项目级R2备份链路退役.md)）。

当前灾备依赖：

| 数据类型 | 备份方式 | 恢复方式 |
|----------|----------|----------|
| **数据库** | MySQL HeatWave 平台自动备份（Oracle Cloud 托管） | 通过 OCI 控制台恢复 |
| **代码与配置** | GitHub 仓库 | `git clone` |
| **历史文档** | GitHub 仓库 `docs/history/` | `git clone` |

---

## 恢复流程

### 场景：主机故障需重建

1. **新建主机**：Ubuntu 24.04+，安装 Python 3.13、Node.js、Nginx

2. **拉取代码**：
   ```bash
   git clone https://github.com/7893/mod.git /home/ubuntu/mod
   ```

3. **配置环境变量**：
   - 从安全渠道获取 `.env.systemd` 和 `.env.api.systemd`
   - 配置数据库连接、Cloudflare 凭据等

4. **恢复数据库**（如需）：
   - 登录 Oracle Cloud 控制台
   - 使用 MySQL HeatWave 的备份恢复功能

5. **部署服务**：
   ```bash
   cd /home/ubuntu/mod
   bash scripts/project/publish.sh
   ```

---

## 历史备份存档

R2 存储桶 `s3://mod-backup/backups/` 中仍保留历史加密备份，直至自然过期或手动清理。如需解密，密钥保存于安全渠道。

---

## 相关文档

- [KI-042 灾难恢复能力建设](../issues/KI-042-灾难恢复能力不足与异机加密备份缺失.md)（历史，已由平台备份替代）
- [KI-095 R2 备份链路退役](../issues/KI-095-项目级R2备份链路退役.md)
