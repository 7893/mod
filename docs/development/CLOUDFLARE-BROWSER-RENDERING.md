# Cloudflare 无头浏览器（Browser Rendering）使用指南与边界手册

更新日期：2026-09-07  
状态：现行参考手册  
适用范围：Cloudflare 托管无头浏览器（Browser Rendering / Browser Run）在本项目中的架构定位、Workers 绑定、Puppeteer 编排、Quick Actions 简易接口、费用限制与避坑边界  
维护角色：agy 维护，主控（kiro）审阅  

---

## 本文定位

本文是 **Cloudflare 无头浏览器（Browser Rendering / Browser Run）的系统使用与边界手册**，系统解答“什么是 Cloudflare 无头浏览器、如何通过 Workers 或 REST API 驱动、支持哪些开箱即用动作、有哪些硬性配额与限制、在本项目大屏中如何应用”。

- **关联项目资产**：
  - 仓库中的 [`workers/mod-browser/`](../../workers/mod-browser/)：已配置并跑通的无头浏览器微服务，包含 `wrangler.jsonc`（声明 `browser: { binding: "BROWSER" }`）与 `src/index.ts`（基于 Quick Action 的高分辨率大屏截图接口）。
- **与主系统运行架构的边界关系**：
  - 遵循 `docs/decisions/0006-生产与工作区合并到单一运行主机.md` 与 `docs/CURRENT-STATE.md`，主系统驾驶舱与 FastAPI 后端保持单机自治；
  - Cloudflare 无头浏览器作为**边缘辅助微服务**，用于提供**大屏自动化巡检快照、每日简报视觉出图、页面渲染归档**等异步支持，**主干大屏与数据接口绝不强依赖该服务的存活**。

---

## 一、Cloudflare 无头浏览器概述

### 1.1 什么是 Browser Rendering？

**Cloudflare Browser Rendering（现升级为 Browser Run）** 是运行在 Cloudflare 全球边缘网络上的全托管、无服务器（Serverless）Chromium 无头浏览器集群。

传统无头浏览器方案（如在本地服务器运行 Puppeteer / Playwright Docker 容器）通常面临以下痛点：
* **资源消耗巨大**：启动一个 Chrome 实例通常消耗 1~2 GB 内存与大量 CPU，极易造成小规格主机 OOM；
* **环境依赖复杂**：需要维护 Linux 字体库（中文字体包）、C++ 动态链接库、沙箱权限与安全补丁；
* **并发与僵尸进程**：长时间运行容易产生内存泄漏与僵尸进程（Zombie Chrome）。

Cloudflare Browser Rendering 将 Chromium 运行环境完全卸载到 Cloudflare 全球边缘节点，开发者只需通过 **Workers 绑定** 或 **标准 REST API** 发送指令，即可按需启停浏览器实例，按运行时长计费，用后即弃。

### 1.2 核心业务场景
1. **大屏高保真快照截图**：截取 1920×1080 / 1780×960 分辨率的 ECharts 完整渲染大屏，输出图片供外部报表或监控展示。
2. **报表打印与 PDF 归档**：将网页或富文本 HTML 实时转换为 A4 打印级矢量 PDF。
3. **动态 SPA 页面抓取与解析**：等待 JavaScript 执行完成后，提取完整 DOM 树，或直接提取为 **Markdown / 结构化 JSON**。
4. **视觉回归测试与监控**：在定时任务中巡检大屏关键组件是否正常展现，捕获前端白屏异常。

---

## 二、三种接入与使用形态

Cloudflare 提供了从“极简开箱即用”到“深度细粒度控制”的三种接入方式：

### 2.1 形态一：Workers 绑定 + Quick Actions（推荐·最简）

若只需完成常见的“截图、转 PDF、提取 HTML、转 Markdown”，直接调用开箱即用的 **Quick Actions**，完全无需手动编写复杂的 Puppeteer 页面监听与资源回收代码。这也是本项目 `workers/mod-browser/` 采用的标准形态。

#### 1. 配置 `wrangler.jsonc`
```jsonc
{
  "name": "mod-browser",
  "main": "src/index.ts",
  "compatibility_date": "2026-03-24", // 必须 >= 2026-03-24 才能支持 quickAction
  "browser": {
    "binding": "BROWSER" // 注入浏览器次级绑定
  }
}
```

#### 2. Worker 代码实现（截取大屏快照）
```typescript
export interface Env {
  BROWSER: any;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const targetUrl = url.searchParams.get('url') || 'https://example.com/';
    const width = parseInt(url.searchParams.get('width') || '1780', 10);
    const height = parseInt(url.searchParams.get('height') || '960', 10);

    try {
      // 一行调用完成无头浏览器启动、导航、渲染、截图与释放
      const resp = await env.BROWSER.quickAction('screenshot', {
        url: targetUrl,
        viewport: { width, height },
        gotoOptions: { waitUntil: 'load' },
        waitForTimeout: 4000, // 为 ECharts 地图与动画留出 4 秒渲染缓冲
      });

      return resp; // 直接返回 image/png 响应
    } catch (err: any) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500 });
    }
  }
};
```

#### 3. 支持的常用 Quick Actions 清单
* `screenshot`：网页高清截屏（支持视口控制、全页面滚动截屏 `fullPage: true`）。
* `pdf`：生成 PDF 打印文件（支持纸张格式、页眉页脚、背景打印）。
* `content`：获取 JS 渲染后的最终静态 HTML 文本。
* `markdown`：智能清洗网页噪声，将网页正文内容提取为整洁的 Markdown 文档。
* `scrape`：基于 CSS 选择器（Selectors）直接抽取指定 DOM 节点内容。

---

### 2.2 形态二：Workers + Puppeteer 深度编排（`@cloudflare/puppeteer`）

当需要执行复杂的用户交互（如点击按钮、填写表单、登录认证、拦截网络请求）时，使用官方针对 Workers 优化的 Puppeteer 客户端。

#### 1. 安装依赖
```bash
npm install @cloudflare/puppeteer --save-dev
```

#### 2. 编排示例与会话生命周期
```typescript
import puppeteer from '@cloudflare/puppeteer';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // 启动一个托管的 Chromium 实例
    const browser = await puppeteer.launch(env.BROWSER);
    
    try {
      const page = await browser.newPage();
      await page.setViewport({ width: 1920, height: 1080 });
      await page.goto('https://example.com', { waitUntil: 'networkidle0' });

      // 执行交互动作
      await page.click('#login-button');
      await page.waitForSelector('.dashboard-loaded');

      const imgBuffer = await page.screenshot({ type: 'png' });
      return new Response(imgBuffer, { headers: { 'Content-Type': 'image/png' } });
    } finally {
      // 核心铁律：必须在 finally 块中显式关闭，防止实例泄漏与并发超额
      await browser.close();
    }
  }
};
```

> **会话复用（Session Reuse）进阶**：  
> 频繁 `launch` 会带来 1~2 秒的 Chromium 冷启动。可通过 `puppeteer.connect(env.BROWSER, { sessionId })` 复用已有存活的会话，大幅降低耗时与并发占用。

---

### 2.3 形态三：REST API 直接调用（免部署 Worker）

外部服务器（如我们的 Python 自动化脚本或后端服务）无需编写和部署任何 Worker，只需持有具备 `Browser Rendering - Edit` 权限的 Cloudflare API Token，即可通过标准 HTTP POST 请求直接触发渲染。

* **API 端点模式**：
  `POST https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/browser-rendering/<action>`
* **请求头**：
  `Authorization: Bearer <CLOUDFLARE_API_TOKEN>`
  `Content-Type: application/json`
* **请求体（JSON）**：
  ```json
  {
    "url": "https://example.com/dashboard",
    "viewport": { "width": 1920, "height": 1080 },
    "waitForTimeout": 3000
  }
  ```

---

## 三、计费模式、配额与硬性限制

### 3.1 计费模式与免费额度

| 计划层级 | 包含的使用额度 | 并发上限 | 超额计费单价 |
|---|---|---|---|
| **Free 免费计划** | 每天 **10 分钟** 浏览器运行时间 | 最多 **3 个** 并发实例 | 不支持超额扩展（额度用尽即 429） |
| **Workers Paid 付费计划** | 每月包含 **10 小时** 运行时长<br>包含 **10 个** 并发浏览器通道 | 最多支持 **200 个** 并发实例 | • 时长超额：**$0.09 / 小时**<br>• 并发超额：**$2.00 / 并发实例** |

*注：Quick Actions 与原生 Puppeteer 共享相同的底层运行时间与并发池。*

### 3.2 运行与系统硬限制

1. **会话空闲超时（Idle Timeout）**：
   - 浏览器实例建立后，如果连续 **60 秒** 没有交互或命令输入，Cloudflare 后台会自动强行终止并销毁该实例，防止无意泄漏产生天价账单。
2. **单任务执行时长上限**：
   - 单个 HTTP 请求在 Workers 下受到 Workers 运行时 CPU/超时限制（标准请求通常为 30~60 秒），复杂爬虫任务不可无限期等待。
3. **本地开发调试约束**：
   - `env.BROWSER.quickAction` 与 `@cloudflare/puppeteer` **不支持纯本地离线模拟**。
   - 本地运行 `wrangler dev` 时，必须附加 **`--remote`** 参数（`npx wrangler dev --remote`），让本地代码将浏览器指令代理到 Cloudflare 真实的边缘 Chromium 集群。

---

## 四、核心避坑指南（Gotchas）与生产防线

> [!CAUTION]
> **无头浏览器生产注意事项**  
> 运行无头浏览器在跨网络渲染、权限穿透和资源控制方面具有特殊性，必须遵循以下防范原则：

### 1. 僵尸实例与会话泄漏（并发暴毙）
* **现象**：调用几次后接口突然报错 `429 Too Many Requests` 或 `Concurrency limit reached`。
* **根因**：在编写自定义 Puppeteer 代码时，未将 `browser.close()` 放在 `finally` 块中。当页面加载出错或抛出异常时，代码提前退出，留下了仍在后台计费并占用并发名额的无头实例。
* **防线**：使用 Quick Actions（自动安全释放），或在 Puppeteer 模式下严密编写 `try...finally { await browser.close(); }`。

### 2. 单页应用（SPA）渲染等待与“骨架屏穿帮”
* **现象**：截取 Vue/React 大屏时，截出来的图片是全黑的面板或带有初始占位符 `—`，图表和地图没画出来。
* **根因**：Chromium 导航触发 `load` 事件时，仅代表 HTML/JS 资源包下载完毕；此时 Vue 的异步挂载、ECharts 地图 GeoJSON 解析以及后端 `/api/` 数据请求仍在进行中。
* **防线**：
  * Quick Actions 模式必须配置 **`waitForTimeout: 3000 ~ 5000`**；
  * 或在 Puppeteer 模式中使用 `page.waitForSelector('.echarts-ready')`，在大屏渲染完毕后给 DOM 增加一个就绪标记类供浏览器精准捕捉。

### 3. 源站防爬虫（WAF / 403）自相残杀
* **现象**：无头浏览器访问项目自身的大屏 URL 时返回 403 Forbidden。
* **根因**：项目在 Nginx 层与 CloudFront 层设置了严格的“拦截 AI 与无头爬虫”规则（按 Headless Chrome 的默认 User-Agent 进行了 403 阻断）。
* **防线**：
  * 无头浏览器必须自定义注入正常的桌面级 User-Agent（如 `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...`）；
  * 或者直接通过 CloudFront 允许的回源路径，并携带专属的回源验证头。

### 4. 私有网络回源限制（SSRF 防御）
* **限制**：Cloudflare 边缘浏览器出于公有云安全规范，**默认禁止访问私有保留地址**（如 `http://127.0.0.1:8100` 或 `http://10.0.1.25`）。
* **口径**：测试或截图必须使用外网可达的公网合法域名，不可尝试用它做源站本地端口探测。

---

## 五、在本项目（MOD 系统）中的最佳实践定位

1. **项目独立资产**：
   - 保持 [`workers/mod-browser/`](../../workers/mod-browser/) 作为独立的轻量 Worker 维护；
   - 核心功能聚焦于高分辨率截图（1780×960、1920×1080），为外部简报、汇报材料提供一键出图。
2. **与主线系统解耦**：
   - 驾驶舱主系统不依赖该 Worker 的状态；
   - 任何涉及自动截图的任务（如每日决策简报配图），通过脚本异步触发，即使无头浏览器超时或欠费，主大屏依然保持 100% 稳健可用。

---

## 六、官方权威参考来源

* [Cloudflare Browser Rendering Documentation](https://developers.cloudflare.com/browser-rendering/)
* [Browser Rendering - Quick Actions Guide](https://developers.cloudflare.com/browser-rendering/quick-actions/)
* [Cloudflare Puppeteer API Reference](https://developers.cloudflare.com/browser-rendering/platform/puppeteer/)
* [Browser Rendering Limits & Pricing](https://developers.cloudflare.com/browser-rendering/platform/limits-and-pricing/)
