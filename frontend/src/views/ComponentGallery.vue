<script setup lang="ts">
import CockpitPanel from '../components/CockpitPanel.vue'
import ChartFacts from '../components/blocks/ChartFacts.vue'
import MetricGrid from '../components/blocks/MetricGrid.vue'
import EmptyNote from '../components/blocks/EmptyNote.vue'

const items = [
  { label: '很长的业务指标名称用于验证完整文本入口', value: '123,456,789,012,345', unit: '笔' },
  { label: '缺失值', value: '—' },
  { label: '零值', value: 0 },
]
</script>

<template>
  <div class="grid grid-cols-2 grid-rows-2 gap-3 h-full" data-zone="gallery">
    <CockpitPanel title="长数字与长标题组件验收" subtitle="完整值可聚焦滚动并查看提示">
      <ChartFacts><template #chart><EmptyNote>图表未提供</EmptyNote></template><template #facts><MetricGrid :items="items" flat fill /></template></ChartFacts>
    </CockpitPanel>
    <CockpitPanel title="事实主导组合">
      <ChartFacts variant="facts-led"><template #facts><MetricGrid :items="items" flat /></template><template #chart><EmptyNote>统一空态</EmptyNote></template></ChartFacts>
    </CockpitPanel>
    <CockpitPanel title="紧凑指标"><MetricGrid :items="items" :columns="3" size="sm" /></CockpitPanel>
    <CockpitPanel title="风险面板" tone="risk"><EmptyNote>无数据不填充假数字</EmptyNote></CockpitPanel>
  </div>
</template>
