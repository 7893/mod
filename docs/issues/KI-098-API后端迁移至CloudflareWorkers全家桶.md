# KI-098 · API 后端迁移至 Cloudflare Workers 全家桶

- 状态：DONE
- 优先级：P2
- 创建日期：2026-09-16
- 更新日期：2026-09-21
- 适用范围：后端架构、实时推送、缓存、定时任务、部署流程

## 背景

当前后端使用 Python FastAPI + 手写 SWR 缓存 + 手写 SSE 实时推送 + systemd 定时任务，代码量约 4000 行，维护面广。

Cloudflare Workers 全家桶（Workers、Durable Objects、Workflows、KV、Hyperdrive、Cron Triggers）可以大幅简化架构，预计减少 ~3100 行代码。

## 架构方案

```
静态资源：用户 → CloudFront → Nginx → 静态文件（保持不变）

API 请求：用户 → Cloudflare Workers → Hyperdrive → MySQL HeatWave
                      │
                      ├── Durable Objects (实时推送/WebSocket)
                      ├── Workflows (模拟器任务编排)
                      ├── KV (快照缓存)
                      ├── Workers AI (已在用)
                      └── Cron Triggers (定时任务)
```

## 迁移范围

| 当前实现 | 迁移到 | 预计省掉 |
|----------|--------|----------|
| FastAPI (~3000 行) | Workers (TypeScript) | ~2200 行 |
| SSE + outbox (~400 行) | Durable Objects | ~350 行 |
| SWR 内存缓存 (~200 行) | Workers KV | ~170 行 |
| systemd timer + 脚本 (~150 行) | Cron Triggers | ~100 行 |
| publish.sh (~300 行) | wrangler deploy | ~280 行 |
| **总计** | | **~3100 行** |

## 迁移阶段

### 阶段 1：基础设施准备
- [ ] 创建 Workers 项目结构
- [ ] 配置 Hyperdrive 连接 MySQL HeatWave
- [ ] 配置 KV namespace
- [ ] 验证 Workers → HeatWave 连通性

### 阶段 2：核心 API 迁移
- [ ] `/api/health` 健康探针
- [ ] `/api/dashboard/snapshot` 快照接口 + KV 缓存
- [ ] `/api/organizations` 分页查询
- [ ] 其他只读接口

### 阶段 3：实时推送迁移
- [ ] Durable Objects 实现 WebSocket 广播
- [ ] 前端从 SSE 切换到 WebSocket
- [ ] 删除 outbox/broker/journal 代码

### 阶段 4：定时任务迁移
- [ ] Cron Triggers 实现每日简报生成
- [ ] Cron Triggers 实现模拟器调度（或 Workflows）
- [ ] 删除 systemd timer

### 阶段 5：清理
- [ ] 删除 FastAPI 后端代码
- [ ] 删除 Nginx API 代理配置
- [ ] 更新部署流程为 wrangler deploy

## 风险与约束

1. **Python → TypeScript 重写**：业务逻辑需要全部重写
2. **HeatWave ML**：Workers 无法直接调用 HeatWave AutoML，需要保留一个轻量 Python 服务或改用 Workers AI
3. **模拟器 CPU 限制**：Workers 单请求 50ms CPU 限制，长任务需拆成 Queues/Workflows
4. **前端 API 域名切换**：需要配置 CORS 或使用子域名

## 完成定义

- [ ] 所有 API 端点在 Workers 上运行
- [ ] 实时推送通过 Durable Objects 实现
- [ ] 定时任务通过 Cron Triggers 实现
- [ ] FastAPI 后端代码删除
- [ ] 部署通过 wrangler 完成
- [ ] 生产环境稳定运行 7 天

## 2026-09-21 Owner 终止追踪

项目 Owner 因不再持有本历史 KI 的完整业务语境，决定终止追踪。本条 `DONE` 只表示
不再列入当前待办，不表示上述迁移已实施或验收；未勾选项原样保留。本条所述内容
属于未采纳的架构提案，不代表 MOD 当前使用 Cloudflare Workers 承载 API。
后续不重开或据此直接施工；如果重新考虑平台迁移，应先作为新架构决策重新评估，而不是恢复本 KI。
见 [ADR-0023](../decisions/0023-清空存量KI并按当前复现重新登记.md)。

## 相关决策

- [ADR-0016](../decisions/0016-退役项目级R2备份链路.md)：已退役 R2 备份
- [KI-088](KI-088-通用基础能力重复自研与工具链收敛缺口.md)：工具链收敛目标
