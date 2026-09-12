import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 每日指挥部决策简报（ADR-0010 第二期）。
 * 只读后台已生成的简报，大屏零交互、打开即见；不触发任何模型调用。
 */
export interface DailyBriefing {
  status: string
  briefingDate?: string
  content?: string
  model?: string
  isStale?: boolean
  freshness?: string
  generatedAt?: string
}

export function useDailyBriefing() {
  const apiBase = `${import.meta.env.BASE_URL}api`
  const briefing = ref<DailyBriefing | null>(null)
  const loading = ref(true)

  let timer: ReturnType<typeof setInterval> | undefined
  let sequence = 0

  async function fetchBriefing(): Promise<void> {
    const request = ++sequence
    loading.value = !briefing.value
    try {
      const res = await fetch(`${apiBase}/insights/briefing`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (request === sequence) briefing.value = data
    } catch {
      if (request === sequence) briefing.value = { status: 'no_briefing' }
    } finally {
      if (request === sequence) loading.value = false
    }
  }

  onMounted(() => {
    void fetchBriefing()
    timer = setInterval(fetchBriefing, 60_000)
  })
  onUnmounted(() => {
    sequence++
    if (timer !== undefined) clearInterval(timer)
  })

  return { briefing, loading, fetchBriefing }
}
