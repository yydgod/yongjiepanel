<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { MetricPoint } from '../../types'
import { useThemeStore } from '../../stores/theme'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = withDefaults(defineProps<{ points: MetricPoint[]; height?: string }>(), {
  height: '176px',
})

const theme = useThemeStore()

function rgba(hex: string, alpha: number): string {
  const value = hex.replace('#', '')
  const r = parseInt(value.slice(0, 2), 16)
  const g = parseInt(value.slice(2, 4), 16)
  const b = parseInt(value.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

function clockLabel(ts: string | null): string {
  if (!ts) return ''
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

const option = computed(() => {
  const labels = props.points.map((point) => clockLabel(point.ts))
  const cpu = props.points.map((point) => point.cpu ?? null)
  const mem = props.points.map((point) => point.mem ?? null)
  const [primary, secondary] = theme.colors
  const light = theme.isLight
  const axisLine = light ? 'rgba(15,23,42,0.12)' : 'rgba(255,255,255,0.08)'
  const splitLine = light ? 'rgba(15,23,42,0.07)' : 'rgba(255,255,255,0.05)'
  const axisLabel = light ? '#64748B' : '#5F7085'
  const legendText = light ? '#334155' : '#9AA9BE'
  return {
    textStyle: { fontFamily: '"Noto Sans SC", Inter, system-ui, sans-serif' },
    animationDuration: 400,
    grid: { left: 4, right: 8, top: 26, bottom: 4, containLabel: true },
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
      axisPointer: { lineStyle: { color: rgba(primary, 0.4) } },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLine: { lineStyle: { color: axisLine } },
      axisLabel: { color: axisLabel, fontSize: 11, interval: Math.max(0, Math.floor(labels.length / 5) - 1) },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: splitLine } },
      axisLabel: { color: axisLabel, fontSize: 11 },
    },
    series: [
      {
        name: 'CPU %',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: cpu,
        lineStyle: { width: 1.6, color: primary },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: rgba(primary, 0.28) },
              { offset: 1, color: rgba(primary, 0) },
            ],
          },
        },
      },
      {
        name: '内存 MB',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: mem,
        lineStyle: { width: 1.4, color: secondary },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: rgba(secondary, 0.22) },
              { offset: 1, color: rgba(secondary, 0) },
            ],
          },
        },
      },
    ],
  }
})

const hasData = computed(() => props.points.some((point) => point.cpu !== null || point.mem !== null))
</script>

<template>
  <div class="relative" :style="{ height }">
    <VChart v-if="hasData" :option="option" autoresize class="h-full w-full" />
    <div v-else class="flex h-full items-center justify-center rounded-xl border border-dashed border-white/[0.07] text-[14.4px] text-mist-500">
      正在积累采样数据（每 5 秒一次）…
    </div>
  </div>
</template>
