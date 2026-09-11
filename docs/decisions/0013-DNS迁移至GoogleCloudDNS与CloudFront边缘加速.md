# ADR-0013: 全球边缘加速与权威 DNS 迁移至 Google Cloud DNS 与 CloudFront

- 状态：采纳
- 日期：2026-09-12

## 背景
为保障指挥大屏的全球 Anycast 极速访问并隐藏真实源站 IP，生产主机已恢复美东纯生产机（USA）架构（ADR-0012）。原域名解析与回源方案需同步升级，解决源站 IP 暴露、跨洲回源延迟高、SSL 证书集中管理以及回源安全防护（防止直接绕过 CDN 扫描源站）的问题。

## 决策
1. **权威 DNS 托管**：主域名与站点主机名全面切换托管至 Google Cloud DNS（托管区域 `fumingname`），站点域名以 CNAME 记录接入 AWS CloudFront 全球 CDN 分发。
2. **边缘证书与加速**：CloudFront 使用部署在 `us-east-1` 区域的 AWS ACM 托管证书，为终端访客提供全球就近 Anycast TLS 1.3 协商与网络加速。
3. **安全回源与源站隐藏**：CloudFront 与 USA 生产机之间采用 HTTPS 回源，源站 Nginx 部署 Let's Encrypt 证书；CloudFront 回源请求中注入自定义密钥头（`X-Origin-Secret`），源站 Nginx 对缺失或错误密钥的直连请求一律执行 403 拦截，杜绝公网对源站真实 IP 的刺探。
4. **SSE 与动态适配**：配置 CloudFront 缓存策略为 `CachingDisabled` 并调整源站读取超时（60s），兼顾驾驶舱高频动态刷新与 SSE（Server-Sent Events）只读实时投影长连接。

## 理由
- **Google Cloud DNS 权威高可靠**：具备 100% SLA 与全球顶级 Anycast 解析网络，且与多云架构解耦。
- **CloudFront 边缘安全与性能**：全球数百边缘 PoP 点就近接入，DDoS 防护与 ACM 证书自动化免维护续期。
- **源站隐藏与防刺探**：DNS 解析对外仅暴露 CloudFront 边缘 Anycast IP，公网直接扫描 USA 生产机 IP 或回源域名均被 Nginx 密钥门禁拦截，形成多层纵深防御。

## 后果
- 权威 NS 记录由 Google Cloud DNS 统一管理，不再依赖旧解析体系；
- 生产源站（USA）Nginx 配置与 CloudFront 回源必须保持 `X-Origin-Secret` 密钥强一致；
- 同步更新项目门面 `README.md` 架构图与事实入口 `docs/CURRENT-STATE.md`。
