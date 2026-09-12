import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  outputDir: './output/browser-results',
  snapshotPathTemplate: '{testDir}/screenshots/{projectName}/{arg}{ext}',
  reporter: [['list'], ['html', { outputFolder: 'output/browser-report', open: 'never' }]],
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000, toHaveScreenshot: { animations: 'disabled', maxDiffPixelRatio: 0.05 } },
  use: {
    baseURL: 'http://127.0.0.1:4187', locale: 'zh-CN', timezoneId: 'Asia/Shanghai',
    trace: 'retain-on-failure', serviceWorkers: 'block',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1920, height: 1080 } } },
    { name: 'compact', use: { viewport: { width: 1366, height: 768 } } },
  ],
  webServer: {
    command: 'pnpm exec vite preview --mode visual --host 127.0.0.1 --port 4187 --strictPort',
    url: 'http://127.0.0.1:4187', reuseExistingServer: false,
  },
})
