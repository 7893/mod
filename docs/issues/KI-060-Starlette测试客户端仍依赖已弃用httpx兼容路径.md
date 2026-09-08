# KI-060 · Starlette 测试客户端仍依赖已弃用 httpx 兼容路径

- 状态：DONE（2026-09-08）
- 优先级：P3
- 更新日期：2026-09-08
- 适用范围：`backend/pyproject.toml`、`backend/uv.lock`、使用 FastAPI/Starlette `TestClient` 的后端测试及 CI 测试环境
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[开发规范](../development/DEVELOPMENT-STANDARD.md)、[测试规范](../development/TESTING-STANDARD.md)

---

## 问题

后端执行 `pytest` 和 `make check` 时稳定出现以下非阻断警告：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
```

截至 2026-09-08，只读核查确认当前依赖锁定结果为 FastAPI `0.141.1`、Starlette `1.6.0`、
httpx `0.28.1`。Starlette `1.6.0` 的测试客户端优先导入 `httpx2`；环境未安装该包时会回退到
`httpx` 并发出上述警告。仓库多组 API、模拟器状态和 HeatWave 测试均通过
`fastapi.testclient.TestClient` 使用这条兼容路径。

登记时后端全量测试均可通过，因此这不是现行功能故障，也不影响生产请求链路；但继续依赖已弃用的
回退路径会使未来依赖升级存在测试基础设施突然失效的风险，并让真正新增的弃用警告被持续噪音掩盖。

## 根因边界

1. `backend/pyproject.toml` 的开发依赖仍精确锁定 `httpx==0.28.1`，没有声明 Starlette 当前推荐的测试传输依赖。
2. `backend/uv.lock` 如实锁定了旧回退组合，干净环境安装后可以稳定复现警告。
3. 业务代码未发现直接导入或调用 `httpx`；现有用途集中在测试客户端的间接依赖，因此迁移范围原则上仅限开发/测试依赖。
4. 警告来自已安装依赖的明确弃用分支，不能通过 pytest 忽略规则、warnings filter 或降低检查等级掩盖。

## 处置建议

1. 先依据 FastAPI、Starlette 和目标 HTTP 客户端版本的官方兼容说明，确认受支持的精确版本组合与迁移边界。
2. 在 `backend/pyproject.toml` 中调整开发依赖并重新生成 `backend/uv.lock`；保持生产依赖集合不被无关扩大。
3. 保持 `TestClient` 的请求、异常传播、lifespan、Cookie、重定向和 WebSocket 语义兼容；若目标包存在 API 差异，集中修改测试夹具，不在业务代码中增加兼容分支。
4. 增加一个将 `StarletteDeprecationWarning` 视为失败的回归检查，防止后续依赖解析重新落回已弃用路径。
5. 在干净依赖环境中运行后端全量测试及仓库 `make check`，确认锁文件可复现且无该警告。

## 禁止性做法

- 不得仅用 `filterwarnings=ignore`、命令行参数或环境变量隐藏警告。
- 不得无边界升级全部 Python 依赖；变更应限制在已核验的兼容组合及其必要传递依赖。
- 不得因测试迁移改变生产 API 行为、数据库连接方式或模拟器运行状态。

## 验收标准

- [x] `backend/pyproject.toml` 与 `backend/uv.lock` 对测试客户端依赖的声明一致，可在干净环境复现安装。
- [x] 后端全量测试不再出现本 KI 记录的 `StarletteDeprecationWarning`。
- [x] 有自动化回归检查阻止测试客户端重新使用已弃用的 `httpx` 回退路径，且不是通过忽略警告实现。
- [x] 现有 API、lifespan、异常传播及相关模拟器测试保持通过。
- [x] `make check` 全量通过，无新增依赖冲突或弃用警告。
- [x] 若兼容组合或标准安装命令发生变化，同步更新相应现行开发文档。

## 实施授权边界

本 KI 仅登记已发现的测试依赖技术债，不授权生产发布、服务启停、数据库操作或无关依赖升级。
实施时须先只读核验目标版本的官方兼容范围，再按依赖变更验证矩阵执行。

## 实施结果（2026-09-08）

- 依据 Starlette 现行依赖说明，将开发依赖 `httpx==0.28.1` 替换为 `httpx2==2.12.0`，并由 `uv`
  重新生成锁文件；生产依赖未扩大。
- 为 setuptools 增加明确的 `app*` 包发现范围，排除同机发布目录 `current/`、`releases/` 与测试目录，
  使标准命令 `uv sync --all-extras --locked` 可重复完成，不再依赖 `--no-install-project` 绕行。
- 新增 `test_testclient_dependency.py`，直接断言 Starlette 实际使用 `httpx2`；pytest 同时把
  `StarletteDeprecationWarning` 提升为错误，禁止重新落回旧兼容路径或用过滤器掩盖。
- 后端全量 208 项测试通过，警告为零；仓库全量检查通过。测试期间观察到的 AnyIO 卡死经最小复现确认
  只发生在受限执行沙箱内，相同程序在沙箱外立即完成，不归因于 `httpx` 或生产 API。
