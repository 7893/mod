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
  mode: 'display_projection'
}

export interface LiveProjectionCounts {
  documents: number
  vouchers: number
  integrations: number
}

type ProjectionHandler = (event: LiveProjectionEvent) => void

function parseEvent(raw: string): LiveProjectionEvent {
  const value = JSON.parse(raw) as Record<string, unknown>
  return {
    id: String(value.id),
    sequence: Number(value.sequence),
    occurredAt: String(value.occurred_at),
    businessType: value.business_type as LiveProjectionEvent['businessType'],
    increments: value.increments as LiveProjectionCounts,
    cumulative: value.cumulative as LiveProjectionCounts,
    projectionId: String(value.projection_id),
    unitName: value.unit_name ? String(value.unit_name) : undefined,
    province: value.province ? String(value.province) : undefined,
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
    eventSource.onmessage = (message) => {
      try {
        const event = parseEvent(message.data)
        onEvent(event)
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
