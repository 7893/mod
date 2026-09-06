import { ref, onMounted } from 'vue'

/**
 * 每日指挥部决策简报（ADR-0010 第二期）。
 * 只读后台已生成的简报，大屏零交互、打开即见；不触发任何模型调用。
 */
export interface DailyBriefing {
  status: string
  briefingDate?: string
  content?: string
  model?: string
  generatedAt?: string
}

export function useDailyBriefing() {
  const apiBase = `${import.meta.env.BASE_URL}api`
  const briefing = ref<DailyBriefing | null>(null)
  const loading = ref(true)

  async function fetchBriefing(): Promise<void> {
    loading.value = true
    try {
      const res = await fetch(`${apiBase}/insights/briefing`)
      briefing.value = await res.json()
    } catch {
      briefing.value = { status: 'no_briefing' }
    } finally {
      loading.value = false
    }
  }

  onMounted(fetchBriefing)

  return { briefing, loading, fetchBriefing }
}
