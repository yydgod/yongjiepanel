<script setup lang="ts">
import { computed } from 'vue'
import { Cpu, HardDrive, MemoryStick, Network } from 'lucide-vue-next'
import type { HostOverview } from '../../types'
import {
  formatGb,
  formatMbAsGb,
  formatPercent,
  formatRate,
  usageTone,
} from '../../utils/format'

const props = defineProps<{ overview: HostOverview }>()

const cpu = computed(() => props.overview.cpu)
const memory = computed(() => props.overview.memory)
const disk = computed(() => props.overview.disk)
const network = computed(() => props.overview.network)

const tiles = computed(() => [
  {
    key: 'cpu',
    label: 'CPU 使用率',
    icon: Cpu,
    value: formatPercent(props.overview.cpu.percent),
    hint: `${props.overview.system.cores} 核${props.overview.cpu.freq_mhz ? ` · ${props.overview.cpu.freq_mhz} MHz` : ''}`,
    extra: `负载 ${props.overview.system.load?.[0] ?? '—'}`,
    percent: props.overview.cpu.percent,
  },
  {
    key: 'memory',
    label: '内存使用',
    icon: MemoryStick,
    value: formatPercent(props.overview.memory.percent),
    hint: `${formatMbAsGb(props.overview.memory.used_mb)} / ${formatMbAsGb(props.overview.memory.total_mb)}`,
    extra: props.overview.memory.swap_total_mb
      ? `Swap ${formatPercent(props.overview.memory.swap_percent)}`
      : '无 Swap',
    percent: props.overview.memory.percent,
  },
  {
    key: 'disk',
    label: '磁盘占用',
    icon: HardDrive,
    value: formatPercent(props.overview.disk.percent),
    hint: `${formatGb(props.overview.disk.used_gb)} / ${formatGb(props.overview.disk.total_gb)}`,
    extra: `${props.overview.disk.partitions.length} 个挂载点`,
    percent: props.overview.disk.percent,
  },
  {
    key: 'network',
    label: '网络吞吐',
    icon: Network,
    value: `↓ ${formatRate(props.overview.network.down_kbps)}`,
    hint: `↑ ${formatRate(props.overview.network.up_kbps)}`,
    extra: `累计 ↓ ${props.overview.network.total_recv_gb} GB`,
    percent: null,
  },
])
</script>

<template>
  <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
    <article v-for="tile in tiles" :key="tile.key" class="glass-panel relative overflow-hidden p-4">
      <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-aurora-teal/50 to-transparent" />
      <div class="flex items-start justify-between">
        <div class="min-w-0">
          <div class="label-caps flex items-center gap-1.5">
            <component :is="tile.icon" class="h-3.5 w-3.5" />
            {{ tile.label }}
          </div>
          <div class="stat-mono mt-1.5 truncate text-[26.4px] font-semibold leading-none">
            {{ tile.value }}
          </div>
        </div>
        <span
          v-if="tile.percent !== null"
          class="shrink-0 rounded px-1.5 py-0.5 text-[10.8px]"
          :class="usageTone(tile.percent).chip"
        >
          {{ tile.percent >= 75 ? '注意' : '正常' }}
        </span>
      </div>

      <div v-if="tile.percent !== null" class="mt-3 h-1 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          class="h-full rounded-full bg-gradient-to-r transition-all duration-700"
          :class="usageTone(tile.percent).bar"
          :style="{ width: `${Math.min(100, tile.percent)}%` }"
        />
      </div>

      <div class="mt-2 flex items-center justify-between gap-2 text-[12px] text-mist-500">
        <span class="truncate">{{ tile.hint }}</span>
        <span class="shrink-0 text-[11.4px]">{{ tile.extra }}</span>
      </div>
    </article>
  </div>
</template>
