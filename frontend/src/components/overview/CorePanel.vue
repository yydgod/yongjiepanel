<script setup lang="ts">
import { computed } from 'vue'
import type { HostOverview } from '../../types'
import { formatPercent, usageTone } from '../../utils/format'

const props = defineProps<{
  cpu: HostOverview['cpu']
  system: HostOverview['system']
}>()

const cores = computed(() =>
  props.cpu.per_core.map((value, index) => ({
    index,
    value,
    height: Math.max(3, Math.min(100, value)),
    tone: usageTone(value).bar,
  })),
)

const loads = computed(() => [
  { label: '1m', value: props.system.load?.[0] ?? 0 },
  { label: '5m', value: props.system.load?.[1] ?? 0 },
  { label: '15m', value: props.system.load?.[2] ?? 0 },
])
</script>

<template>
  <section class="glass-panel flex flex-col p-4">
    <div class="flex items-center justify-between">
      <h2 class="label-caps">CPU 核心</h2>
      <span class="font-mono text-[12px] text-mist-500">{{ cores.length }} cores</span>
    </div>

    <div class="mt-3 flex h-[104px] items-end gap-1.5">
      <div
        v-for="core in cores"
        :key="core.index"
        class="flex h-full flex-1 flex-col justify-end"
        :title="`Core ${core.index}: ${formatPercent(core.value)}`"
      >
        <div class="relative w-full flex-1 overflow-hidden rounded-sm bg-white/[0.05]">
          <div
            class="absolute inset-x-0 bottom-0 rounded-sm bg-gradient-to-t transition-all duration-500"
            :class="core.tone"
            :style="{ height: `${core.height}%` }"
          />
        </div>
        <span class="mt-1 text-center font-mono text-[10.2px] text-mist-500">{{ core.index }}</span>
      </div>
    </div>

    <div class="mt-3 grid grid-cols-3 gap-2 border-t border-white/[0.06] pt-2.5">
      <div v-for="load in loads" :key="load.label" class="text-center">
        <div class="stat-mono text-[16.8px] font-semibold leading-none">{{ load.value.toFixed(2) }}</div>
        <div class="mt-1 font-mono text-[10.8px] text-mist-500">load {{ load.label }}</div>
      </div>
    </div>
  </section>
</template>
