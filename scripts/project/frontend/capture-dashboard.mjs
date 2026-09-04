/**
 * Purpose: capture a local MOD dashboard screenshot for visual review.
 * Owner: project
 * Input: MOD_SCREENSHOT_URL and MOD_SCREENSHOT_PATH environment variables.
 * Output: one PNG file; read-only against the target web application.
 * Environment: local development only; requires Playwright.
 */
import { chromium } from 'playwright'

const targetUrl = process.env.MOD_SCREENSHOT_URL || 'http://127.0.0.1:4173/'
const outputPath = process.env.MOD_SCREENSHOT_PATH || '/tmp/mod-dashboard.png'

(async () => {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } })
  const page = await context.newPage()
  await page.goto(targetUrl, { waitUntil: 'networkidle' })
  await page.waitForTimeout(3000)
  await page.screenshot({ path: outputPath, fullPage: true })
  await browser.close()
})()
