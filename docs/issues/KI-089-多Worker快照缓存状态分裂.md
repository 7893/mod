# KI-089 · 多 Worker 快照缓存状态分裂

- 状态：OPEN
- 优先级：P1
- 更新日期：2026-09-16
- 适用范围：FastAPI 全景快照、Uvicorn 多 Worker、缓存刷新并发
- 来源：[KI-085 第 2 项](KI-085-核心架构缺陷与数据安全治理.md)

## 问题

生产守护器 [`scripts/project/run_unified.py`](../../scripts/project/run_unified.py) 默认以 `MOD_API_WORKERS=2` 启动 Uvicorn，但 [`backend/app/api.py`](../../backend/app/api.py) 的快照内容、时间戳、刷新标志和互斥锁均为进程内全局变量。两个 Worker 会分别缓存和刷新同一份昂贵快照，客户端也可能在不同 Worker 间读到不同代际。

原专册以“当前单 Worker”为由暂缓，该依据已经失效。

## 完成定义

- [ ] 快照只有一个明确的共享事实源或生产恢复为单 Worker 且记录容量依据；
- [ ] 多并发请求不会让多个 Worker 同时重建同一代快照；
- [ ] 客户端跨 Worker 请求不会观察到快照代际倒退；
- [ ] 缓存不可用时保持现有权威快照与失败边界；
- [ ] 多进程验收通过后同步现行架构文档并关闭本项。

## 操作边界

本条目不授权部署外部缓存服务、修改生产 Worker 数或发布。
