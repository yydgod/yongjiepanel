<script setup lang="ts">
import { computed } from 'vue'
import { Activity, Cpu, Gauge, ShieldCheck, TriangleAlert, Wifi } from 'lucide-vue-next'
import { useBoardStore } from '../../stores/board'
import { formatPercent, relativeTime } from '../../utils/format'

const store = useBoardStore()

const tiles = computed(() => [
  {
    key: 'running',
    label: '运行中',
    value: store.stats.running,
    icon: ShieldCheck,
    tone: 'text-state-ok',
    bar: 'from-state-ok/60 to-state-ok/0',
  },
  {
    key: 'warning',
    label: '告警',
    value: store.stats.warning,
    icon: TriangleAlert,
    tone: 'text-state-warn',
    bar: 'from-state-warn/60 to-state-warn/0',
  },
  {
    key: 'unavailable',
    label: '不可用',
    value: store.stats.unavailable + store.stats.stopped + store.stats.unknown,
    icon: Wifi,
    tone: 'text-state-bad',
    bar: 'from-state-bad/60 to-state-bad/0',
  },
  {
    key: 'total',
    label: '卡片总数',
    value: store.stats.total,
    icon: Activity,
    tone: 'text-aurora-blue',
    bar: 'from-aurora-blue/60 to-aurora-blue/0',
  },
])

</script>

<template>
  <div class="grid grid-cols-2 gap-3 lg:grid-cols-5">
    <div
      v-for="tile in tiles"
      :key="tile.key"
      class="glass-panel relative overflow-hidden px-4 py-3.5"
    >
      <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r" :class="tile.bar" />
      <div class="flex items-start justify-between">
        <div>
          <div class="label-caps">{{ tile.label }}</div>
          <div class="mt-1.5 flex items-baseline gap-1.5">
            <span class="stat-mono text-[31.2px] font-semibold leading-none">{{ tile.value }}</span>
            <span class="text-[12px] text-mist-500">项</span>
          </div>
        </div>
        <component :is="tile.icon" class="h-4 w-4" :class="tile.tone" />
      </div>
    </div>

    <div class="glass-panel relative col-span-2 overflow-hidden px-4 py-3.5 lg:col-span-1">
      <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-aurora-violet/60 to-aurora-teal/0" />
      <div class="label-caps">卡片对话</div>
      <div class="mt-1.5 flex items-center gap-2">
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full animate-breathe rounded-full bg-aurora-teal/60" />
          <span class="relative inline-flex h-2 w-2 rounded-full bg-aurora-teal" />
        </span>
        <span class="truncate text-[14.4px] font-medium text-aurora-teal">dsh 原生工作区</span>
      </div>
      <div class="mt-1 flex items-center gap-3 text-[12px] text-mist-500">
        <span class="inline-flex items-center gap-1">
          <Cpu class="h-3 w-3" />{{ formatPercent(store.stats.avgCpu) }}
        </span>
        <span class="inline-flex items-center gap-1">
          <Gauge class="h-3 w-3" />同步 {{ relativeTime(store.lastSynced) }}
        </span>
      </div>
    </div>
  </div>
</template>
