import { onMounted, onUnmounted, ref } from 'vue'
import type { InsightsData } from '../stores/project.ts'
import type { RiskPrediction } from '../utils/riskRules.ts'

export interface HeatWaveModelStatus {
  status: 'ready' | 'not_evaluated' | 'unavailable' | string
  algorithm?: string
  quality?: number | null
  verified?: boolean
}

/** `/api/insights/status` 的响应：快照 insights 叠加 HeatWave 与 Cloudflare 子系统状态。 */
export interface InsightsStatus extends InsightsData {
  /** 后端按真实模型质量判定：READY / VALIDATION_FAILED / NOT_EVALUATED。 */
  automlStatus?: string
  hw_ml?: {
    status: string
    verified?: boolean
    models?: { regression?: HeatWaveModelStatus; classifier?: HeatWaveModelStatus }
    message?: string
  }
  predictions?: RiskPrediction[]
  cf_ai?: { status: string; message?: string }
}

const POLL_INTERVAL_MS = 60_000

/** 只读轮询研判子系统状态；不触发任何模型生成。 */
export function useInsightsStatus() {
  const status = ref<InsightsStatus | null>(null)
  const error = ref<string | null>(null)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  async function fetchStatus(): Promise<void> {
    try {
      const res = await fetch(`${import.meta.env.BASE_URL}api/insights/status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      status.value = (await res.json()) as InsightsStatus
      error.value = null
    } catch (e) {
      error.value = e instanceof Error ? e.message : '网络异常'
    }
  }

  onMounted(() => {
    fetchStatus()
    pollTimer = setInterval(fetchStatus, POLL_INTERVAL_MS)
  })
  onUnmounted(() => {
    if (pollTimer !== null) clearInterval(pollTimer)
  })

  return { status, error, fetchStatus }
}
