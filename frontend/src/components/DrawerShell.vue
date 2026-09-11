<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

defineProps<{ label: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()
const panel = ref<HTMLElement | null>(null)
let previousFocus: HTMLElement | null = null

function focusable() {
  return [...(panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]') ?? [])]
    .filter(el => !el.hidden && el.getAttribute('aria-hidden') !== 'true')
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    emit('close')
  }
  if (event.key !== 'Tab') return
  const nodes = focusable()
  const first = nodes[0]
  const last = nodes.at(-1)
  if (!first || !last) { event.preventDefault(); panel.value?.focus(); return }
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.value)) {
    event.preventDefault(); last.focus()
  } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.value)) {
    event.preventDefault(); first.focus()
  }
}

onMounted(async () => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  await nextTick()
  ;(focusable()[0] ?? panel.value)?.focus()
})
onUnmounted(() => { if (previousFocus?.isConnected) previousFocus.focus() })
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-end" @click.self="emit('close')" @keydown="onKey">
      <aside ref="panel" role="dialog" aria-modal="true" :aria-label="label" tabindex="-1" class="w-96 max-w-full h-full bg-slate-900 border-l border-white/10 p-5 flex flex-col gap-4 shadow-2xl overflow-y-auto">
        <slot />
      </aside>
    </div>
  </Teleport>
</template>
