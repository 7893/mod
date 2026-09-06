# KI-031 · 后端软链发布隔离（与前端统一发布范式）

- 状态：DONE（2026-09-06，四阶段全部完成）
- 更新日期：2026-09-06
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)、[ADR-0008](../decisions/0008-symlink-release-isolation.md)、[KI-030](KI-030-governance-evolution.md)

## 背景
前端已有软链发布隔离（`frontend/current → releases/<ts>/`，KI-030 建议5）。
后端 systemd 服务仍直接读工作区 `backend/app/`，存在"改到一半影响生产"的风险。
目标：前后端统一软链发布范式，工作区随意修改不影响生产，发布时原子切换。

## 执行计划（主控执行）

### 阶段一 · 后端软链结构（不停服，先建结构）
- 建 `backend/releases/` 目录
- 将现有 `backend/app/` + `.venv/` 复制到 `backend/releases/<ts>/`
- 创建 `backend/current` 软链指向该 release

### 阶段二 · systemd 服务切换到软链路径
- 更新 `mod-api.service`：`WorkingDirectory` 与 `ExecStart` 改为读 `backend/current/`
- 备份旧配置，重载 systemd，验证服务正常

### 阶段三 · 统一发布脚本
- 将 `scripts/project/publish_frontend.sh` 升级为 `scripts/project/publish.sh`
- 统一覆盖前后端：build → make check → 复制 backend/app + .venv → 切换前后端软链 →
  reload nginx + restart mod-api → 验证健康 → 自动回滚（如失败）
- 更新 AGENTS.md 与 ENFORCEMENT.md 的发布相关约束

### 阶段四 · 收尾
- `backend/releases/` 加入 `.gitignore`
- 更新 CURRENT-STATE.md、ADR-0008 状态

## 约束
- 每步先备份、先验证，可回退
- 切换 systemd 路径时先 `nginx -t` / `systemctl status` 确认服务正常
- 发布脚本执行需主控显式授权，agy 不得直接调用

## 进度
- 文档/决策已记录（ADR-0008、KI-031）
- 执行待开始

## 完成记录（2026-09-06 主控执行）
- 阶段一：建 `backend/releases/<ts>/`，复制 `backend/app/`，建 `backend/current` 软链。
- 阶段二：`mod-api.service` 的 `WorkingDirectory` 改为 `backend/current/`（备份 .bak-pre-symlink），
  daemon-reload + restart，验证 HTTP 200、进程 cwd 指向 releases/ ✓。
- 阶段三：`publish_frontend.sh` 升级为统一的 `scripts/project/publish.sh`，整合前后端软链切换、
  make check、reload Nginx + restart mod-api、健康验证、失败自动回滚、旧版本清理（保留最近5个）。
- 阶段四：`backend/releases/` 和 `backend/current` 加入 `.gitignore`；更新 `AGENTS.md` 发布约束；
  旧的 `publish_frontend.sh` 保留但已被 `publish.sh` 取代（前端发布请用统一脚本）。
