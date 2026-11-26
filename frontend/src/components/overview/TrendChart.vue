<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { HostHistoryPoint } from '../../types'
import { useThemeStore } from '../../stores/theme'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = withDefaults(
  defineProps<{
    points: HostHistoryPoint[]
    series: { key: keyof HostHistoryPoint; name: string; color: string }[]
    unit?: string
    max?: number
    height?: string
  }>(),
  { unit: '', height: '196px' },
)

const theme = useThemeStore()

function clockLabel(ts: string): string {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

const option = computed(() => {
  const light = theme.isLight
  const axisLine = light ? 'rgba(15,23,42,0.12)' : 'rgba(255,255,255,0.08)'
  const splitLine = light ? 'rgba(15,23,42,0.07)' : 'rgba(255,255,255,0.05)'
  const axisLabel = light ? '#64748B' : '#5F7085'
  const legendText = light ? '#334155' : '#9AA9BE'
  const labels = props.points.map((point) => clockLabel(point.ts))

  return {
    textStyle: { fontFamily: '"Noto Sans SC", Inter, system-ui, sans-serif' },
    animationDuration: 300,
    grid: { left: 4, right: 8, top: 30, bottom: 2, containLabel: true },
    legend: {
      right: 0,
      top: 0,
      itemWidth: 8,
      itemHeight: 8,
      icon: 'roundRect',
      textStyle: { color: legendText, fontSize: 12 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: light ? 'rgba(255,255,255,0.97)' : 'rgba(13,20,29,0.94)',
      borderColor: light ? 'rgba(15,23,42,0.12)' : 'rgba(255,255,255,0.1)',
      textStyle: { color: light ? '#0F172A' : '#E8EEF6', fontSize: 13 },
      valueFormatter: (value: number) => `${Number(value).toFixed(1)} ${props.unit}`.trim(),
      axisPointer: { lineStyle: { color: 'rgba(120,150,170,0.35)' } },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLine: { lineStyle: { color: axisLine } },
      axisLabel: {
        color: axisLabel,
        fontSize: 11,
        interval: Math.max(0, Math.floor(labels.length / 5) - 1),
      },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      max: props.max,
      splitLine: { lineStyle: { color: splitLine } },
      axisLabel: {
        color: axisLabel,
        fontSize: 11,
        formatter: (value: number) =>
          props.unit === 'KB/s' && Math.abs(value) >= 1000
            ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`
            : `${value}`,
      },
    },
    series: props.series.map((item, index) => ({
      name: item.name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      data: props.points.map((point) => Number(point[item.key] ?? 0)),
      lineStyle: { width: 1.7, color: item.color },
      areaStyle:
        index < 2
          ? {
              opacity: 0.14,
              color: item.color,
            }
          : undefined,
    })),
  }
})

const hasData = computed(() => props.points.length > 0)
</script>

<template>
  <div class="relative" :style="{ height }">
    <VChart v-if="hasData" :option="option" autoresize class="h-full w-full" />
    <div
      v-else
      class="flex h-full items-center justify-center rounded-xl border border-dashed border-white/[0.07] text-[13.2px] text-mist-500"
    >
      正在积累采样数据（每 3 秒一次）…
    </div>
  </div>
</template>
