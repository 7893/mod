import { onMounted, onUnmounted, ref } from 'vue'

export interface LiveProjectionEvent {
  id: string
  sequence: number
  occurredAt: string
  businessType: 'projection_state' | 'document_created' | 'voucher_created' | 'integration_completed'
  increments: LiveProjectionCounts
  cumulative: LiveProjectionCounts
  projectionId: string
  unitName?: string
  province?: string
  storyTitle?: string
  storyDesc?: string
  amount?: string
  badgeTone?: string
  batchName?: string
  resetRequired?: boolean
  resetReason?: string
  mode: 'committed_simulation'
}

export interface LiveProjectionCounts {
  documents: number
  vouchers: number
  integrations: number
}

type ProjectionHandler = (event: LiveProjectionEvent) => boolean | void

export function parseEvent(raw: string): LiveProjectionEvent {
  const value = JSON.parse(raw) as Record<string, unknown>
  return {
    id: String(value.id),
    resetRequired: value.reset_required === true,
    resetReason: typeof value.reset_reason === 'string' ? value.reset_reason : undefined,
    sequence: Number(value.sequence),
    occurredAt: String(value.occurred_at),
    businessType: value.business_type as LiveProjectionEvent['businessType'],
    increments: value.increments as LiveProjectionCounts,
    cumulative: value.cumulative as LiveProjectionCounts,
    projectionId: String(value.projection_id),
    unitName: value.unit_name ? String(value.unit_name) : undefined,
    province: value.province ? String(value.province) : undefined,
    storyTitle: value.story_title ? String(value.story_title) : undefined,
    storyDesc: value.story_desc ? String(value.story_desc) : undefined,
    amount: value.amount ? String(value.amount) : undefined,
    badgeTone: value.badge_tone ? String(value.badge_tone) : undefined,
    batchName: value.batch_name ? String(value.batch_name) : undefined,
    mode: value.mode as LiveProjectionEvent['mode'],
  }
}

export function useLiveProjection(onEvent: ProjectionHandler) {
  const connected = ref(false)
  const recentEvent = ref<LiveProjectionEvent | null>(null)
  let eventSource: EventSource | null = null
  let clearRecentTimer: number | null = null

  const connect = () => {
    if (eventSource) return
    eventSource = new EventSource(`${import.meta.env.BASE_URL}api/live-projection/events`)
    eventSource.onopen = () => { connected.value = true }
    eventSource.onerror = () => { connected.value = false }
    eventSource.addEventListener('source_unavailable', () => { connected.value = false })
    eventSource.onmessage = (message) => {
      try {
        const event = parseEvent(message.data)
        connected.value = true
        if (event.resetRequired) recentEvent.value = null
        if (onEvent(event) === false) return
        if (event.businessType !== 'projection_state') {
          recentEvent.value = event
          if (clearRecentTimer !== null) window.clearTimeout(clearRecentTimer)
          clearRecentTimer = window.setTimeout(() => { recentEvent.value = null }, 4500)
        }
      } catch {
        // Ignore a malformed presentation event; the snapshot remains authoritative.
      }
    }
  }

  const disconnect = () => {
    eventSource?.close()
    eventSource = null
    connected.value = false
    if (clearRecentTimer !== null) window.clearTimeout(clearRecentTimer)
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return { connected, recentEvent }
}
