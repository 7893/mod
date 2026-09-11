# 前端视觉与交互回归

更新日期：2026-09-11
状态：现行
适用范围：六屏、治理巡航、抽屉及基础组件的离线浏览器验收

## 入口与隔离

关联：[KI-076](../issues/KI-076-FRONTEND-PRESENTATION-CONTRACT.md)、[前端规范](FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md)。

在 `frontend/` 执行：

```bash
pnpm exec playwright install chromium
pnpm run build:visual
pnpm run test:visual
```

`playwright.config.ts` 启动独立的 4187 端口预览，无 API 转发；测试只接受本地静态请求，全部 API 由固定夹具响应。
未知 API、写请求和外部域名请求均拒绝并使测试失败。不得改成生产 URL，不能使用真实数据库或 AI 请求替代夹具。
构建输出在 `frontend/output/visual-dist/`，失败证据与报告在同目录下的 `browser-results/`、`browser-report/`，均已忽略。
`/#/components` 是仅 visual 构建存在的组件展例，生产路由不包含该入口。

## 验收范围

- 固定时间、数据与浏览器，六屏和组件展例在 1920×1080、1366×768 下比较截图。
- 同时验证面板边界、浏览器异常、降级来源、刷新失败、窗口变化、全屏常驻导航。
- 巡航点击必须打开具体事件的工单，抽屉须在缩放画布外且可按 Escape 关闭。
- 长指标、缺失值和零值由组件展例验证；焦点循环与恢复另有单元测试。

## 基准更新

基准存于 `frontend/e2e/screenshots/`。浏览器版本由锁文件固定，字体、操作系统和架构应与基准生成环境一致。
先检查差异原因，确认为预期设计变更后才运行 `pnpm run test:visual:update`；不得以自动更新基准掩盖回溢或错位。
截图比对证明渲染没有非预期变化，不代替人的审美判断。初始基准及重大视觉变更仍需用户审阅。

## 组件与规则扩展

优先在展例中加入失败输入，再修改所属组件；D 屏作为图表事实组合试点，不要求六屏同构。
新增行为先验证空数据、长文本、超大数字、窄容器及交互恢复，再迁入页面。
