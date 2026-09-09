import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AtRiskUnitTable, { type AtRiskUnit } from '../AtRiskUnitTable.vue'

const unit: AtRiskUnit = {
  id: 1,
  name: '测试风险单位',
  province: '广东',
  batch: '第六批',
  owner: '项目联系人',
  status: '双轨运行',
  construction: 90,
  openingData: 95,
  voucherRate: 96,
  riskType: '双轨核对差异',
  riskLevel: '高危',
  reason: '一致率低于门槛',
}

describe('AtRiskUnitTable explanation provenance', () => {
  it('labels deterministic fallback as rule-based and never as SHAP', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'ok',
        explanationSource: 'RULE_BASED',
        topAttributions: [{
          factor: 'stagnant_days', factorName: '工期停滞过久', weightPct: 100,
          attribution: 1, description: '真实特征偏离',
        }],
      }),
    }))
    const wrapper = mount(AtRiskUnitTable, { props: { units: [unit] } })
    await wrapper.find('tbody tr').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('规则风险研判')
    expect(wrapper.text()).toContain('规则偏离度 Top 3')
    expect(wrapper.text()).not.toContain('原生 SHAP')
  })

  it('shows an explicit unavailable state instead of fabricating fixed weights', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    const wrapper = mount(AtRiskUnitTable, { props: { units: [unit] } })
    await wrapper.find('tbody tr').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('解释不可用')
    expect(wrapper.text()).toContain('当前没有可验证的风险解释')
  })
})
