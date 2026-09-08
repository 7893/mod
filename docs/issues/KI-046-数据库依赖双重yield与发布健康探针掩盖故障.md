# KI-046 · 数据库依赖双重 yield 与发布健康探针掩盖故障

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-08
- 适用范围：FastAPI 数据库依赖生命周期、健康探针、发布回滚门禁与异常脱敏
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-039 模拟器状态接口脱节](KI-039-模拟器状态接口与独立常驻进程脱节并返回500.md)

## 结论

当前系统错误处理与健康探针存在严重的设计与实现隐患：
1. `backend/app/db.py:25` 中的 `connection()` 依赖把整个生成器 `yield` 包裹在宽泛的 `try ... except Exception:` 中，并在异常发生时执行第二次 `yield None`。这严重违反了 FastAPI 生成器依赖协议（PEP 342/380），会导致框架抛出二次致命错误 `RuntimeError: generator didn't stop after throw()`，彻底掩盖真实的业务异常。
2. `/api/health` 接口在数据库连接失败时仍然返回 HTTP 200（降级返回 `disconnected`），健康探针缺乏明确的故障指示。
3. 发布脚本 `publish.sh` 历史上使用 `|| true` 吞掉健康检查输出，数据库完全宕机时仍可能误报发布成功。
4. 多个接口直接将 `str(e)` 拼接进 JSON 返回，在发生 SQL 报错时直接暴露表名、字段、SQL 语法及内部连接信息。

## 修复目标与实施

1. **重构 `connection()` 生成器依赖**：
   - 将数据库连接初始化与路由执行严格分段；
   - 连接失败时执行单次 `yield None` 并直接 `return` 结束生成器；
   - 连接成功时进入 `try: yield conn finally: conn.close()`，下游抛出异常时不捕获，交由 FastAPI 全局异常机制，杜绝二次 yield 导致的 `generator didn't stop after throw()`。
2. **收紧 `/api/health` 探针语义**：
   - 数据库离线或查询异常时统一设置 `response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE`；
   - 数据库健康时返回 HTTP 200 与 session_timezone、now_cst。
3. **加固 `publish.sh` 发布探针**：
   - 移除了 `|| true` 掩盖；
   - 发布脚本严格校验 HTTP 状态码必须为 200 且 `status == "ok"` 以及数据库时间元数据完备，否则触发自动回滚。
4. **全局异常与敏感字段脱敏**：
   - 全局替换接口中的 `str(e)` 与 `f"...{e}"` 报错，日志使用 `logger.error(..., exc_info=True)` 记录内部堆栈，向客户端返回脱敏的安全错误提示；
   - 在 FastAPI 中配置 `@app.exception_handler(500)` 全局兜底处理器，杜绝未经捕获的内部堆栈外泄。

## 进度

- 2026-09-07：现场核验并立项。
- 2026-09-08：完成 `connection()` 生成器两段式生命周期重构，收紧 `/api/health` 为 503 明确故障，加固 `publish.sh` 探针检查，完成敏感异常信息脱敏；新增 4 项单元测试并全部通过，问题已关闭。
