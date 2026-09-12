import { test, expect } from './fixtures'

test('KI-080: old briefing and synthetic model limits are visible on A and F', async ({ page }) => {
  await page.route('**/api/insights/briefing', route => route.fulfill({ json: {
    status: 'ok', isStale: true, freshness: 'stale', briefingDate: '2026-09-10',
    content: '## 当前概况\n- 上线率为80%，原因需要进一步核实。',
  } }))
  await page.route('**/api/insights/status', route => route.fulfill({ json: {
    automlStatus: 'EXPERIMENTAL', businessValidated: false,
    hw_ml: { status: 'ready', models: {
      regression: { quality: 0.99 }, classifier: { quality: 0.98 },
    } },
  } }))
  await page.goto('/#/a')
  await expect(page.getByText('历史简报 2026-09-10')).toBeVisible()
  await page.getByText('历史简报 2026-09-10').click()
  await expect(page.locator('[data-zone="F4"]')).toContainText('拟合分不代表未来预测能力')
  await expect(page.locator('[data-zone="F4"]')).toContainText('实验已评估')
  await expect(page.locator('[data-zone="F4"]')).not.toContainText('推理就绪')
  await expect(page.locator('[data-zone="F5"]')).toContainText('历史简报 · 今日尚未更新')
  await expect(page.locator('[data-zone="F5"]')).toContainText('上线率为80%')
  await page.clock.runFor(1800)
  const clipped = await page.locator('[data-zone]').evaluateAll(nodes => nodes.filter(node => {
    const r = node.getBoundingClientRect()
    return r.width > 0 && (r.left < -1 || r.right > innerWidth + 1 || r.bottom > innerHeight + 1)
  }).map(node => node.getAttribute('data-zone')))
  expect(clipped).toEqual([])
  await page.screenshot({ path: `output/ki080-${test.info().project.name}.png` })
})
