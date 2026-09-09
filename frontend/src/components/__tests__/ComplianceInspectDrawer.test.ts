import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ComplianceInspectDrawer, { type ComplianceIssueUnit } from '../ComplianceInspectDrawer.vue'

describe('ComplianceInspectDrawer', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  const mockUnit: ComplianceIssueUnit = {
    id: 872,
    name: '武当贸易集团有限公司',
    province: '山西',
    batch: '第六批',
    owner: '张三',
    status: '准备中',
    construction: 85,
    openingData: 80,
    voucherRate: 92,
    level: '高',
    tags: ['准备期卡顿', '超期挂账'],
    primaryIssue: '准备期卡顿',
    detailNote: '测试要点描述',
  }

  const mockIssue = {
    id: 'ISS-20260908-0872',
    unitId: 872,
    unitName: '武当贸易集团有限公司',
    province: '山西',
    batchId: 6,
    issueType: '准备期卡顿',
    severity: 'MEDIUM',
    status: 'IN_PROGRESS',
    owner: '省信通前置网络保障小组·赵伟',
    title: '《关于武当贸易集团有限公司基础环境与组织权限配置超期未打通的通报》',
    description: '深入研判根因分析',
    aiEnriched: 1,
    reworkCount: 1,
    createdAt: '2026-09-08 10:00:00',
    updatedAt: '2026-09-08 12:00:00',
    resolvedAt: null,
  }

  const mockTimeline = [
    {
      id: 1,
      issueId: 'ISS-20260908-0872',
      action: '专项排查',
      actor: '技术攻坚组',
      detail: '现场排查完成',
      occurredAt: '2026-09-08 10:05:00',
    },
  ]

  it('renders issue status machine, specialist, and action buttons', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        if (url.includes('/api/governance/issues?')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ total: 1, items: [mockIssue] }),
          })
        }
        if (url.includes('/timeline')) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(mockTimeline),
          })
        }
        return Promise.resolve({ ok: false })
      })
    )

    const wrapper = mount(ComplianceInspectDrawer, {
      props: { unit: mockUnit },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('武当贸易集团有限公司')
    expect(wrapper.text()).toContain('ISS-20260908-0872')
    expect(wrapper.text()).toContain('二次返工 x1')
    expect(wrapper.text()).toContain('省信通前置网络保障小组·赵伟')
    expect(wrapper.text()).toContain('一键督办（指挥部令）')
    expect(wrapper.text()).toContain('AI深度研判')
    expect(wrapper.text()).toContain('专项排查')
  })

  it('emits close event when close button is clicked', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ items: [] }),
      })
    )

    const wrapper = mount(ComplianceInspectDrawer, {
      props: { unit: mockUnit },
    })
    await flushPromises()

    const closeBtn = wrapper.find('header button')
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('treats CLOSED as an archived terminal state with no write actions', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes('/timeline') ? mockTimeline : {
        total: 1,
        items: [{ ...mockIssue, status: 'CLOSED' }],
      }),
    })))
    const wrapper = mount(ComplianceInspectDrawer, { props: { unit: mockUnit } })
    await flushPromises()

    expect(wrapper.text()).toContain('已闭环归档')
    expect(wrapper.text()).not.toContain('一键督办（指挥部令）')
    expect(wrapper.text()).not.toContain('AI深度研判')
  })

  it('does not let a slower old unit request overwrite the current unit', async () => {
    let resolveOld!: (value: unknown) => void
    const oldResponse = new Promise((resolve) => { resolveOld = resolve })
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
      if (url.includes('unit_id=872')) return oldResponse
      if (url.includes('unit_id=873')) return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ total: 1, items: [{ ...mockIssue, id: 'ISS-NEW', unitId: 873, unitName: '新单位' }] }),
      })
      if (url.includes('/timeline')) return Promise.resolve({ ok: true, json: () => Promise.resolve([]) })
      return Promise.resolve({ ok: false })
    }))
    const wrapper = mount(ComplianceInspectDrawer, { props: { unit: mockUnit } })
    await wrapper.setProps({ unit: { ...mockUnit, id: 873, name: '新单位' } })
    await flushPromises()
    resolveOld({ ok: true, json: () => Promise.resolve({ total: 1, items: [mockIssue] }) })
    await flushPromises()

    expect(wrapper.text()).toContain('ISS-NEW')
    expect(wrapper.text()).not.toContain('ISS-20260908-0872')
  })
})
