# USA 项目目录整理记录

执行日期：2026-09-02
状态：已完成的历史运维记录
适用范围：2026-09-02 USA 目录收敛与风险修复

## 范围

本次只整理 `/home/ubuntu/mod`、同步已验证的项目文件并加强搜索引擎禁止索引配置。
没有删除数据库、V2 数据、环境文件、虚拟环境或其他项目文件。

## 归档结果

- `backup/20260901` → `archive/backups/20260901/`
- 根层 V1 后端和数据库备份 → `archive/backups/20260901/`
- `artifacts/legacy-v1-sim-data` → `archive/legacy-v1/artifacts/`
- `artifacts/v3-sim-data`、`artifacts/v3-tmp` → `archive/experimental-v3/`
- `tools-staging` → `archive/staging/`
- 旧版根层生成器 → `archive/legacy-v1/generator/`
- 旧建库与账号工具 → `archive/legacy-v1/database/`
- 前端生成 JS、tsbuildinfo、旧截图 → `archive/workbench/frontend/`
- 旧路径 Nginx 与重复部署配置 → `archive/legacy-deploy/`

所有项目资产均采用同文件系统内移动归档，没有删除。同步前备份位于
`archive/backups/20260902-maintenance/`。

## 防索引

- `https://历史域名（脱敏）/robots.txt` 返回 `User-agent: *` 和 `Disallow: /`。
- HTML 包含通用 robots、Googlebot 和 Bingbot 的 `noindex` meta。
- 页面与 API 均返回 `X-Robots-Tag: noindex, nofollow, noarchive, nosnippet, noimageindex`。
- Nginx 配置检查通过并完成平滑 reload。

## 后续完成事项

- 系统级重复服务已停止并禁用，只保留用户级 `mod-api.service`。
- 用户级服务重启后日志确认模拟器未启用，8100 仅有一个 Uvicorn 进程监听。
- 远端 5,063,531,245 字节历史归档已校验迁回 JPA 的 `archive/usa-history/`。
- USA 项目目录收敛为 `USA-DEPLOYMENT-LAYOUT.md` 规定的纯部署结构。
