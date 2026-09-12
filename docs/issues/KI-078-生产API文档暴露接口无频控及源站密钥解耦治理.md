# KI-078 · 生产 API 文档暴露、接口无频控及源站密钥解耦治理

- 状态：DONE
- 优先级：P1
- 更新日期：2026-09-12
- 适用范围：FastAPI 生产交互文档屏蔽、Nginx 请求频率限制（Rate Limiting）、源站回源密钥模板化与源码解耦
- 关联：[已知问题看板](../KNOWN-ISSUES.md)、[KI-041 API 与模拟器共用可写数据库账号及公网无认证暴露](KI-041-API与模拟器共用可写数据库账号及公网无认证暴露.md)、[数据与安全标准](../development/DATA-AND-SECURITY-STANDARD.md)、[ADR-0012 恢复 USA 生产部署机与 JPA 专属开发机架构](../decisions/0012-恢复USA生产部署机与JPA专属开发机架构.md)

---

## 结论

在保持“驾驶舱全站公开、免鉴权浏览”的产品定位前提下，已全面完成网络与应用安全基线加固：
1. **生产交互文档与架构规范公网屏蔽（深度防御）**：
   - 应用层：[`backend/app/main.py`](../../backend/app/main.py) 实现 `should_enable_docs()`，当 `MOD_ENV=production` 且未显式指定 `MOD_ENABLE_DOCS=1` 时，强制将 `docs_url`、`redoc_url` 与 `openapi_url` 置为 `None`，杜绝接口模式公网泄漏；
   - 网关层：[`deploy/nginx/mod.conf.example`](../../deploy/nginx/mod.conf.example) 新增 `location ~ ^/api/(docs|openapi\.json)` 硬拦截规则直接响应 HTTP 404，形成双层物理阻断。
2. **API 请求频率限制与防刷控制（Rate Limiting）**：
   - 网关层新增 [`deploy/nginx/conf.d/mod_ratelimit.conf`](../../deploy/nginx/conf.d/mod_ratelimit.conf)，提取真实客户端 IP（优先解析 `X-Forwarded-For` 最左客户端 IP，回退至 `$remote_addr`）；
   - 普通 API 读接口配置 `zone=mod_api_limit`（单客户端 IP 25r/s，允许突发 `burst=50`）；
   - 治理工单流转等敏感写入接口配置 `zone=mod_write_limit`（单客户端 IP 2r/s，允许突发 `burst=5`）；
   - 超频统一返回 `HTTP 429 Too Many Requests`，有效遏制公网恶意爬虫高并发扫库与工单状态乱刷。
3. **源站回源密钥模板化与源码彻底脱敏**：
   - 移除原配置模板中硬编码的密钥字符串，新增片段模板 [`deploy/nginx/snippets/mod-origin-secret.conf.example`](../../deploy/nginx/snippets/mod-origin-secret.conf.example)；
   - 生产环境真实密钥独立存储于主机私有文件 `/etc/nginx/snippets/mod-origin-secret.conf`（权限 `0600`，不入库不入代码）；
   - 站点配置通过 `include /etc/nginx/snippets/mod-origin-secret.conf;` 引入，代码仓库彻底消除明文凭据残留与豁免标记。

---

## 背景与排查事实

在 2026-09-12 安全基线评估中，排查出以下安全薄弱点：
1. **API 文档公网可见**：FastAPI 原先默认开启 `docs_url="/api/docs"` 与 `openapi_url="/api/openapi.json"`，且 Nginx 前向代理直接放行。任何公网访客均可直接浏览 Swagger UI，一键导出全量 API 规范与底层字段。
2. **缺乏请求频控与防刷保护**：由于大屏设计为免登开放系统，任何访客或爬虫均可并发请求 `/api/v2/snapshot`，或高频调用 `POST /api/governance/issues/{id}/dispatch` 与 `enrich` 写入接口，极易耗尽后端数据库连接池或污染工单流转历史。
3. **回源密钥硬编码于模板**：`deploy/nginx/mod.conf` 本地文件中包含明文 `X-Origin-Secret` 字符串，虽配置了 `# secret-scan: allow`，但若模板外泄则会导致源站真实 IP 失去防护屏障。

---

## 修复实施细节

### 1. 应用层 FastAPI 文档开关

修改 [`backend/app/main.py`](../../backend/app/main.py)：
```python
def should_enable_docs() -> bool:
    env_flag = os.getenv("MOD_ENABLE_DOCS")
    if env_flag is not None:
        return env_flag.lower() in ("1", "true", "yes", "on")
    return get_settings().environment != "production"

enable_docs = should_enable_docs()

app = FastAPI(
    title="MOD API",
    version="0.3.0",
    docs_url="/api/docs" if enable_docs else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if enable_docs else None,
    lifespan=lifespan,
)
```

### 2. Nginx 限流与防刷区域定义

新增 [`deploy/nginx/conf.d/mod_ratelimit.conf`](../../deploy/nginx/conf.d/mod_ratelimit.conf)：
```nginx
map $http_x_forwarded_for $client_real_ip {
    ""                  $remote_addr;
    "~^([^,\s]+)"       $1;
    default             $remote_addr;
}

limit_req_zone $client_real_ip zone=mod_api_limit:10m rate=25r/s;
limit_req_zone $client_real_ip zone=mod_write_limit:10m rate=2r/s;
limit_req_status 429;
```

并在站点配置中装配至对应 `location`：
```nginx
location ~ ^/api/(docs|openapi\.json) {
    return 404;
}

location ~ ^/api/governance/issues/[^/]+/(dispatch|enrich)$ {
    limit_req zone=mod_write_limit burst=5 nodelay;
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 30s;
    add_header Cache-Control "no-store" always;
    add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet, noimageindex" always;
}

location ^~ /api/ {
    limit_req zone=mod_api_limit burst=50 nodelay;
    proxy_pass http://127.0.0.1:8100/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 30s;
    add_header Cache-Control "no-store" always;
    add_header X-Robots-Tag "noindex, nofollow, noarchive, nosnippet, noimageindex" always;
}
```

### 3. 源站回源密钥片段解耦

新增 [`deploy/nginx/snippets/mod-origin-secret.conf.example`](../../deploy/nginx/snippets/mod-origin-secret.conf.example)，站点配置通过 `include /etc/nginx/snippets/mod-origin-secret.conf;` 引用。服务器真实文件设置 `0600` 权限，与 Git 彻底隔离。

---

## 验证与验收证据

1. **自动化单测回归**：
   - 增补 `backend/tests/test_api.py` 单元测试，验证 `should_enable_docs()` 在开发与生产环境下的切换逻辑，以及生产模式下 `/api/docs` 和 `/api/openapi.json` 返回 404。
   - 全量后端单测全绿通过（`make backend-check`）。
2. **Nginx 语法核验与部署验证**：
   - JPA 本地与 USA 生产机双端执行 `sudo nginx -t` 均成功验证语法；
   - 实测线上 `curl -I https://mod.fuming.name/api/docs` 与 `/api/openapi.json` 均严格返回 404；
   - 线上主接口 `/api/health` 与 `/api/v2/snapshot` 正常服务。
3. **文档一致性与生命周期核验**：
   - `python3 scripts/project/check_doc_links.py` 检查 0 坏链；
   - `python3 scripts/project/check_document_governance.py` 校验通过；
   - `python3 scripts/project/check_doc_sync.py` 通过。
