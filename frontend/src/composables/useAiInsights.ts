import { computed, onMounted, onUnmounted, ref } from "vue"

export function useAiInsights() {
  const apiBase = `${import.meta.env.BASE_URL}api/v2`

  // Cloudflare AI 研判状态
  type AiPhase = 'idle' | 'loading' | 'generating' | 'ok' | 'cache_hit' | 'no_cache' | 'rate_limited' | 'unavailable' | 'error'

  interface AiStatus {
    status: 'ok' | 'no_cache' | 'rate_limited' | 'unavailable' | 'error'
    quota_remaining?: number
    quota_reset_at?: string
    cached_at?: string
    message?: string
  }

  interface AiLatest {
    status: 'ok' | 'no_cache' | 'error'
    content?: string
    generated_at?: string
    model?: string
    cache_hit?: boolean
    quota_remaining?: number
    message?: string
  }

  const aiPhase = ref<AiPhase>('idle')
  const aiStatus = ref<AiStatus | null>(null)
  const aiLatest = ref<AiLatest | null>(null)
  const aiGenerating = ref(false)
  const aiError = ref<string | null>(null)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  async function fetchStatus(): Promise<void> {
    try {
      const res = await fetch(`${apiBase}/insights/status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: AiStatus = await res.json()
      aiStatus.value = data
      if (aiPhase.value === 'idle' || aiPhase.value === 'loading') {
        if (data.status === 'ok' || (data as any).status === 'ready') {
          await fetchLatest()
        } else if (data.status === 'no_cache') {
          aiPhase.value = 'no_cache'
        } else if (data.status === 'rate_limited') {
          aiPhase.value = 'rate_limited'
        } else if (data.status === 'unavailable') {
          aiPhase.value = 'unavailable'
        } else {
          aiPhase.value = 'error'
        }
      } else if (aiPhase.value === 'ok' || aiPhase.value === 'cache_hit') {
        if (data.status === 'rate_limited') aiPhase.value = 'rate_limited'
      }
    } catch (e: any) {
      if (aiPhase.value === 'idle' || aiPhase.value === 'loading') aiPhase.value = 'unavailable'
      aiError.value = e?.message ?? '网络异常'
    }
  }

  async function fetchLatest(): Promise<void> {
    try {
      const res = await fetch(`${apiBase}/insights/latest`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: AiLatest = await res.json()
      if (!data.content && (data as any).insight) {
        data.content = (data as any).insight
      }
      aiLatest.value = data
      if (data.status === 'ok') {
        aiPhase.value = data.cache_hit ? 'cache_hit' : 'ok'
      } else if (data.status === 'no_cache') {
        aiPhase.value = 'no_cache'
      } else {
        aiPhase.value = 'error'
        aiError.value = data.message ?? '获取失败'
      }
    } catch (e: any) {
      aiPhase.value = 'error'
      aiError.value = e?.message ?? '网络异常'
    }
  }

  async function triggerGenerate(): Promise<void> {
    if (aiGenerating.value) return
    aiGenerating.value = true
    aiPhase.value = 'generating'
    aiError.value = null
    try {
      const res = await fetch(`${apiBase}/insights/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        if (res.status === 429) {
          aiPhase.value = 'rate_limited'
          aiStatus.value = body
        } else {
          aiPhase.value = 'error'
          aiError.value = body?.message ?? `HTTP ${res.status}`
        }
        return
      }
      const data: AiLatest = await res.json()
      if (!data.content && (data as any).insight) {
        data.content = (data as any).insight
      }
      aiLatest.value = data
      if (data.status === 'ok') {
        aiPhase.value = data.cache_hit ? 'cache_hit' : 'ok'
        fetchStatus().catch(() => {})
      } else if (data.status === 'no_cache') {
        aiPhase.value = 'no_cache'
      } else {
        aiPhase.value = 'error'
        aiError.value = data.message ?? '生成失败'
      }
    } catch (e: any) {
      aiPhase.value = 'error'
      aiError.value = e?.message ?? '网络异常'
    } finally {
      aiGenerating.value = false
    }
  }

  function startAiPoll(): void {
    aiPhase.value = 'loading'
    fetchStatus()
    pollTimer = setInterval(() => {
      if (!aiGenerating.value) fetchStatus()
    }, 60_000)
  }

  onMounted(() => startAiPoll())
  onUnmounted(() => { if (pollTimer !== null) clearInterval(pollTimer) })

  const aiButtonLabel = computed(() => {
    if (aiGenerating.value || aiPhase.value === 'generating') return '生成中…'
    if (aiPhase.value === 'ok' || aiPhase.value === 'cache_hit') return '重新生成'
    return '生成研判'
  })

  const aiButtonDisabled = computed(() => 
    aiGenerating.value || aiPhase.value === 'rate_limited' || aiPhase.value === 'unavailable'
  )

  const quotaRemaining = computed(() => aiLatest.value?.quota_remaining ?? aiStatus.value?.quota_remaining ?? null)

  const generatedAt = computed(() => {
    const raw = aiLatest.value?.generated_at
    if (!raw) return null
    try {
      return new Date(raw).toLocaleString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    } catch { return raw }
  })


  return {
    aiPhase,
    aiStatus,
    aiLatest,
    aiGenerating,
    aiError,
    aiButtonLabel,
    aiButtonDisabled,
    quotaRemaining,
    generatedAt,
    triggerGenerate,
  }
}
