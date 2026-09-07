# KI-046 · 数据库依赖双重 yield 与发布健康探针掩盖故障

- 状态：OPEN
- 优先级：P1
- 更新日期：2026-09-07
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-039 模拟器状态接口脱节](KI-039-模拟器状态接口与独立常驻进程脱节并返回500.md)

## 结论

当前系统错误处理与健康探针存在严重的设计与实现隐患：
1. `backend/app/db.py:25` 中的 `connection()` 依赖把整个生成器 `yield` 包裹在宽泛的 `try ... except Exception:` 中，并在异常发生时执行第二次 `yield None`。这严重违反了 FastAPI 生成器依赖协议（PEP 342/380），会导致框架抛出二次致命错误 `RuntimeError: generator didn't stop after throw()`，彻底掩盖真实的业务异常。
2. `/api/health` 接口在数据库连接失败时仍然返回 HTTP 200（降级返回 `disconnected`），健康探针缺乏明确的故障指示。
3. 发布脚本 `publish.sh` 历史上使用 `|| true` 吞掉健康检查输出，数据库完全宕机时仍可能误报发布成功。
4. 多个接口直接将 `str(e)` 拼接进 JSON 返回，在发生 SQL 报错时直接暴露表名、字段、SQL 语法及内部连接信息。

## 修复目标

- 重构 `connection()` 生成器依赖：遵循标准 context manager / generator 范式，不捕获路由内部异常进行二次 yield。
- 收紧 `/api/health` 与发布探针语义：明确数据库连通性作为健康的核心硬指标。
- 敏感异常脱敏：全局替换未脱敏的 `str(e)` 抛出，统一由异常处理器转换为安全结构化响应。

## 进度

- 2026-09-07：现场核验并立项。
