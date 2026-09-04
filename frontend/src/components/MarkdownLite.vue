<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ content?: string | null }>()

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** 行内标记：内容已提前转义，这里只在纯文本上套我们自己的白名单标签，无注入风险。 */
function inline(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

const html = computed(() => {
  const raw = props.content ?? ''
  if (!raw.trim()) return ''
  const lines = escapeHtml(raw).replace(/\r\n?/g, '\n').split('\n')
  const out: string[] = []
  let list: 'ul' | 'ol' | null = null

  const closeList = () => {
    if (list) {
      out.push(`</${list}>`)
      list = null
    }
  }

  for (const line of lines) {
    const t = line.trim()
    if (!t) {
      closeList()
      continue
    }
    const heading = t.match(/^(#{1,4})\s+(.*)$/)
    if (heading) {
      closeList()
      const level = Math.min(heading[1].length + 1, 5)
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`)
      continue
    }
    const ordered = t.match(/^\d+[.)]\s+(.*)$/)
    if (ordered) {
      if (list !== 'ol') {
        closeList()
        out.push('<ol>')
        list = 'ol'
      }
      out.push(`<li>${inline(ordered[1])}</li>`)
      continue
    }
    const bullet = t.match(/^[-*•]\s+(.*)$/)
    if (bullet) {
      if (list !== 'ul') {
        closeList()
        out.push('<ul>')
        list = 'ul'
      }
      out.push(`<li>${inline(bullet[1])}</li>`)
      continue
    }
    closeList()
    out.push(`<p>${inline(t)}</p>`)
  }
  closeList()
  return out.join('')
})
</script>

<template>
  <div class="md-lite" v-html="html"></div>
</template>
