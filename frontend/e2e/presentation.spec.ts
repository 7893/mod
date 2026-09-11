import { test, expect, snapshot, issue } from './fixtures'

for (const screen of ['a', 'b', 'c', 'd', 'e', 'f', 'components']) {
  test(`${screen}: frozen scene and panel boundaries`, async ({ page }) => {
    await page.goto(`/#/${screen}`)
    await expect(page.locator('.link-state')).toHaveText('实时数据')
    await page.clock.runFor(1800)
    await expect(page.locator('[data-zone]').first()).toBeVisible()
    const clipped = await page.locator('[data-zone]').evaluateAll(nodes => nodes.filter(node => {
      const r = node.getBoundingClientRect()
      return r.width > 0 && (r.left < -1 || r.right > innerWidth + 1 || r.bottom > innerHeight + 1)
    }).map(node => node.getAttribute('data-zone')))
    expect(clipped).toEqual([])
    await expect(page).toHaveScreenshot(`${screen}.png`)
  })
}

test('fallback and failed refresh are honest', async ({ page }) => {
  await page.route('**/api/dashboard/snapshot', route => route.fulfill({ json: { ...snapshot, meta: { ...snapshot.meta, source: 'fallback' } } }))
  await page.goto('/#/a')
  await expect(page.locator('.link-state')).toHaveText('降级快照')
  await page.route('**/api/dashboard/snapshot', route => route.fulfill({ status: 503, json: {} }))
  await page.getByTitle('刷新数据', { exact: true }).click()
  await expect(page.locator('.link-state')).toHaveText('刷新受阻')
  await expect(page.locator('[data-zone="A1"]')).toBeVisible()
})

test('tour opens the exact event, drawer escapes the canvas and restores focus', async ({ page }) => {
  await page.goto('/#/e')
  await expect(page.getByText('治理自愈动态广播')).toBeVisible()
  await page.clock.runFor(47000)
  const inspect = page.getByRole('button', { name: '查看工单' })
  await expect(inspect).toBeVisible()
  await inspect.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText(issue.id)
  expect(await dialog.evaluate(node => !node.closest('.screen-scale-box'))).toBe(true)
  await expect(dialog).toHaveScreenshot('governance-drawer.png')
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
})

test('window resize and fullscreen retain navigation', async ({ page }) => {
  await page.goto('/#/d')
  await page.getByTitle('全屏展示', { exact: true }).click()
  await expect(page.getByTitle('退出全屏', { exact: true })).toBeVisible()
  await expect(page.locator('.command-header')).toBeVisible()
  await page.getByTitle('退出全屏', { exact: true }).click()
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.clock.runFor(100)
  const box = await page.locator('.screen-scale-box').boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(-1)
  expect(box!.x + box!.width).toBeLessThanOrEqual(1281)
})
