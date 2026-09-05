# KI-009 · 前端构建存在超过 500kB 的 chunk 警告

- 状态：DONE（2026-09-05，根因是 Nginx 未压缩，已解决）
- 更新日期：2026-09-05
- 关联链接：[已知问题看板](../KNOWN-ISSUES.md)

- 现象：`pnpm build` 提示 DashboardView(434kB)、theme(471kB, 主要是 ECharts)、index(609kB) 等 chunk 超过 500kB（非阻断）。
- 真因核查（2026-09-05 主控实测）：构建警告只是表象；真正影响公网首屏的是 **Nginx 未对 JS/CSS 启用 gzip**
  （`nginx.conf` 中 `gzip on` 已开但 `gzip_types` 被注释，默认只压 text/html）、且 `/assets/` **无缓存头**——
  线上主 JS 以 609,915 字节未压缩原样传输、每次访问重下。这比代码分割严重得多、也更值得先解决。
- 处置（2026-09-05）：
  - 全局启用 `gzip_types`（覆盖 application/javascript、text/css、application/json、image/svg+xml 等）
    + `gzip_comp_level 6`、`gzip_vary on`、`gzip_min_length 1024`（`/etc/nginx/nginx.conf`，已备份）。
  - mod 站点新增 `location ^~ /assets/`：`expires 30d` + `Cache-Control public, immutable`（文件名带 hash 可安全长缓存）；
    `index.html` 保持 `no-cache`（始终取最新版本）。
  - 实测：主 JS 传输从 609,915 → 97,603 字节（gzip，降 84%），二次访问走 30 天不可变缓存；`nginx -t` 通过、
    reload 无中断；未改任何前端代码。
- 未做（评估后不做）：进一步 `manualChunks` 拆包收益低——gzip 后体积已可接受，ECharts/Vue 是图表驾驶舱刚需，
  拆分只是分散下载、增加维护复杂度，公网+压缩+缓存到位后首屏体验已充分。若未来首屏仍偏慢再评估。
