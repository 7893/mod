<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Sparkles } from 'lucide-vue-next'
import type { BlockTone } from './types.ts'

/** 分节要点列表：纵向分节、正文全文换行展示，绝不截断。用于 AI 简报等只读研判文本。 */
export interface BriefingSectionRow {
  title: string
  items: string[]
  tone?: BlockTone
}

defineProps<{ sections: BriefingSectionRow[] }>()

const icons = { success: CheckCircle2, warning: AlertTriangle } as Record<string, typeof Sparkles>
const iconFor = (tone?: BlockTone) => icons[tone ?? ''] ?? Sparkles
</script>

<template>
  <div class="briefing">
    <section v-for="section in sections" :key="section.title" class="briefing__section">
      <header class="briefing__head" :class="`is-${section.tone || 'default'}`">
        <component :is="iconFor(section.tone)" :size="13" class="briefing__icon" />
        <b class="briefing__title">{{ section.title }}</b>
        <span class="briefing__count">{{ section.items.length }} 条</span>
      </header>
      <ol class="briefing__items">
        <li v-for="(item, index) in section.items" :key="item" class="briefing__item">
          <span class="briefing__index">{{ index + 1 }}.</span>
          <span>{{ item }}</span>
        </li>
      </ol>
    </section>
  </div>
</template>
