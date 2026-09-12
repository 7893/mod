# KI-082 · CI/CD 安全加固与发布能力收敛

- 状态：OPEN
- 优先级：P2
- 更新日期：2026-09-13
- 适用范围：`.github/workflows/quality.yml` deploy job、`scripts/project/publish.sh`、GitHub Secrets 配置、SSH 主机验证、fallback 快照自动更新
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-078 生产 API 文档暴露接口无频控及源站密钥解耦治理](KI-078-生产API文档暴露接口无频控及源站密钥解耦治理.md)、[数据与安全标准](../development/DATA-AND-SECURITY-STANDARD.md)、[当前部署与运维基线](../operations/USA-DEPLOYMENT-LAYOUT.md)

---

## 结论

当前 CI/CD deploy job 存在两个安全隐患：SSH 主机密钥验证被完全禁用（`StrictHostKeyChecking=no`），以及 `publish.sh` 直接从 Nginx 配置文件解析回源密钥并在 shell 变量中传递。与此同时，fallback 快照更新、完整健康探针逻辑仍在 `publish.sh` 中孤立存在，未收进 CI/CD，造成发布流程割裂——日常 push 走 CI/CD，但快照永远不自动更新，需要人工记住手跑 `publish.sh`。本 KI 登记上述问题并给出加固与收敛方案，同时明确模拟器管理的边界（永远不能自动化，保留在 `publish.sh`）。

---

## 只读证据（2026-09-13）

### 1. SSH 主机密钥验证被禁用，存在中间人攻击风险

`.github/workflows/quality.yml` 第 145 行：

```yaml
SSH_OPTS="-i ~/.ssh/id_deploy -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
```

`StrictHostKeyChecking=no` 完全跳过服务器身份验证。若 DNS 被劫持或 `USA_HOST` IP 被替换，CI/CD 会无感知地连上攻击者服务器并执行 `rsync` 和远程命令，导致生产代码被替换或服务器被入侵。USA 服务器（`193.122.180.196`）的真实指纹已在本地 `~/.ssh/known_hosts` 中，可直接提取并存入 GitHub Secret。

### 2. publish.sh 直接从 Nginx 文件解析回源密钥并绕过密钥扫描

`scripts/project/publish.sh` 第 48、123、125 行：

```bash
ORIGIN_SECRET="${CLOUDFRONT_ORIGIN_SECRET:-$(grep -m 1 -oP '...' /etc/nginx/sites-available/mod.fuming.name ...)}"  # secret-scan: allow
...
curl ... -H "X-Origin-Secret: $ORIGIN_SECRET"  # secret-scan: allow
```

密钥从文件解析后存入 shell 变量，在三处显式使用了 `# secret-scan: allow` 豁免标记绕过密钥扫描。若该变量被意外打印到日志或错误输出，密钥会泄露。正确做法是通过环境变量注入（本地从 `.env` 读，CI/CD 从 GitHub Secret 读），不从配置文件解析。

### 3. fallback 快照未纳入 CI/CD，发布后快照陈旧

CI/CD deploy job 构建并部署前端，但不更新 `frontend/src/data/fallback-snapshot.json`。该文件需要连接线上 API（`https://mod.fuming.name/api/dashboard/snapshot`）才能更新，CI/CD 容器有 SSH 进服务器的能力，可以在服务器上执行更新命令。

当前文件最后更新：`Sep 12 23:04`（人工跑的），每次发布后快照陈旧时间取决于上次手跑时间，无保证上限。

### 4. publish.sh 的完整健康探针逻辑未同步到 CI/CD

`publish.sh` 有三个探针（`/api/health`、`/api/simulator/status`、`/api/dashboard/snapshot` 契约验证），CI/CD 的探针逻辑更简单，缺少 snapshot 契约字段校验。两套流程质量不一致。

### 5. 模拟器管理边界清晰，不应纳入自动化

模拟器（`mod-simulator.service`）维护内存状态、磁盘文件（JSONL、lifecycle_state.json）和数据库事务，重启时机需要人工判断。`publish.sh` 保留模拟器管理部分是正确设计，不应改变。

---

## 影响

| 影响面 | 当前风险 |
|--------|---------|
| SSH 中间人攻击 | DNS/IP 劫持时无任何防护，可被静默替换生产服务器 |
| 回源密钥泄露 | shell 变量传递 + 豁免扫描，有日志泄露风险 |
| 快照陈旧 | 大屏降级时显示数天前的数据，用户无感知 |
| 发布流程割裂 | 日常 push 走 CI/CD，快照更新靠人工记忆，容易遗漏 |
| 探针不一致 | CI/CD 和 publish.sh 的验证质量不同，可能漏过某些故障 |

---

## 修复方案

### 修复一：SSH 主机密钥验证（最高优先）

**步骤 1**：提取 USA 服务器指纹存入 GitHub Secret

```bash
# 在本地执行，获取服务器公钥
ssh-keyscan -H 193.122.180.196
# 把输出内容存入 GitHub Secret: USA_HOST_KEY  # secret-scan: allow
```

**步骤 2**：CI/CD workflow 里写入 known_hosts

```yaml
- name: Deploy to USA Production Node
  env:
    TARGET_HOST: ${{ secrets.USA_HOST || secrets.DEPLOY_HOST_IP }}
    TARGET_KEY: ${{ secrets.USA_SSH_KEY || secrets.DEPLOY_SSH_KEY }}
    TARGET_KNOWN_HOST: ${{ secrets.USA_HOST_KEY }}  # 新增
  run: |
    mkdir -p ~/.ssh
    echo "$TARGET_KEY" > ~/.ssh/id_deploy
    chmod 600 ~/.ssh/id_deploy

    # 写入已知主机指纹，启用严格验证
    echo "$TARGET_KNOWN_HOST" >> ~/.ssh/known_hosts

    SSH_OPTS="-i ~/.ssh/id_deploy -o StrictHostKeyChecking=yes -o ConnectTimeout=10"
```

### 修复二：回源密钥改为环境变量注入

**publish.sh** 中删除从 Nginx 文件解析的逻辑：

```bash
# 删除这行
ORIGIN_SECRET="${CLOUDFRONT_ORIGIN_SECRET:-$(grep ...)}"  # secret-scan: allow

# 改为：直接从环境变量读，本地在 .env 里配置
ORIGIN_SECRET="${CLOUDFRONT_ORIGIN_SECRET:?CLOUDFRONT_ORIGIN_SECRET is not set}"  # secret-scan: allow
```

本地 `.env`（已在 `.gitignore` 中）：
```
CLOUDFRONT_ORIGIN_SECRET=<实际密钥>  # secret-scan: allow
```

CI/CD 如需用到（目前 deploy job 不需要，仅 publish.sh 本地用），可加 GitHub Secret `CLOUDFRONT_ORIGIN_SECRET`。

### 修复三：CI/CD 自动更新 fallback 快照

在 deploy job 的"切软链、重启服务、健康验证"之后，SSH 进服务器执行快照更新：

```yaml
# 在健康探针通过后，新增步骤
- name: Update fallback snapshot
  run: |
    ssh $SSH_OPTS ubuntu@"$TARGET_HOST" bash << 'EOF'
      cd /home/ubuntu/mod
      # 等 API 稳定后从本机 API 更新快照
      SNAP=$(curl -sf http://127.0.0.1:8100/api/dashboard/snapshot || echo "")
      if echo "$SNAP" | grep -q '"rolloutTrend"'; then
        echo "$SNAP" > /tmp/new_snapshot.json
        python3 scripts/project/build_fallback_snapshot.py --from-file /tmp/new_snapshot.json
        echo "Fallback snapshot updated."
      else
        echo "Snapshot not ready, skipping fallback update."
      fi
    EOF
```

这样每次 CI/CD 部署后，快照自动更新为当时的最新数据，大屏降级时最多展示上次部署时的数据。

### 修复四：CI/CD 探针补齐 snapshot 契约验证

在 CI/CD 健康探针部分补充 snapshot 字段校验，与 `publish.sh` 对齐：

```bash
# 现有探针后追加
SNAP=""
for i in $(seq 1 10); do
  sleep 2
  SNAP=$(curl -sf http://127.0.0.1:8100/api/dashboard/snapshot || true)
  if echo "$SNAP" | grep -q '"rolloutTrend"'; then
    echo "Snapshot probe passed on attempt $i"
    break
  fi
  echo "Waiting for snapshot (attempt $i)..."
done

if ! echo "$SNAP" | grep -q '"rolloutTrend"'; then
  echo 'Snapshot contract probe failed!'
  exit 1
fi
```

### publish.sh 保留范围（不变）

以下内容继续保留在 `publish.sh`，不纳入 CI/CD：

- 模拟器状态检查（发布前确认 `RUNNING`）
- 模拟器重启判断（人工决策）
- 状态文件备份（`lifecycle_state.json`、`fuse_state.json`）
- 应急直连发布（CI/CD 不可用时的备用通道）

---

## 完成定义

- [ ] GitHub Secret `USA_HOST_KEY` 已配置服务器公钥指纹
- [ ] CI/CD SSH 连接改为 `StrictHostKeyChecking=yes`，验证通过
- [ ] `publish.sh` 中 Nginx 文件解析逻辑删除，改为环境变量读取
- [ ] 本地 `.env` 已配置 `CLOUDFRONT_ORIGIN_SECRET`，无豁免标记
- [ ] CI/CD deploy job 新增快照自动更新步骤
- [ ] CI/CD 健康探针补齐 snapshot 契约字段校验
- [ ] `make check` 全量通过，无新增 secret-scan 告警
- [ ] 发布一次验证新流程端到端正常

---

## 依赖与授权

- 需要 GitHub 仓库 Settings 权限（新增 Secret `USA_HOST_KEY`）
- `publish.sh` 修改影响应急发布通道，需项目 Owner 授权
- CI/CD workflow 修改需 main 分支 push 权限
- 不依赖其他未关闭 KI

## 进度

- 2026-09-13 立项登记（OPEN）。来源为对 `.github/workflows/quality.yml` 和 `scripts/project/publish.sh` 的直接安全审计，结合 fallback 快照更新流程的缺口分析。
