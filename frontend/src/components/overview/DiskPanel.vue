<script setup lang="ts">
import { HardDrive } from 'lucide-vue-next'
import type { HostOverview } from '../../types'
import { formatGb, formatRate, usageTone } from '../../utils/format'

defineProps<{ disk: HostOverview['disk'] }>()
</script>

<template>
  <section class="glass-panel p-4">
    <div class="flex flex-wrap items-center gap-2">
      <HardDrive class="h-4 w-4 text-aurora-teal" />
      <h2 class="text-[15.6px] font-semibold text-mist-100">磁盘分区</h2>
      <div class="ml-auto flex items-center gap-3 text-[11.4px] text-mist-500">
        <span>读 {{ formatRate(disk.read_kbps) }}</span>
        <span>写 {{ formatRate(disk.write_kbps) }}</span>
      </div>
    </div>

    <div class="mt-3 space-y-2.5">
      <div
        v-for="part in disk.partitions"
        :key="part.mountpoint"
        class="rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2.5"
      >
        <div class="flex items-center gap-2">
          <span class="truncate font-mono text-[13.2px] text-mist-100">{{ part.mountpoint }}</span>
          <span class="shrink-0 rounded border border-white/[0.08] px-1.5 py-0.5 font-mono text-[10.2px] text-mist-500">
            {{ part.fstype }}
          </span>
          <span class="ml-auto shrink-0 font-mono text-[12px]" :class="usageTone(part.percent).text">
            {{ part.percent.toFixed(1) }}%
          </span>
        </div>
        <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
          <div
            class="h-full rounded-full bg-gradient-to-r transition-all duration-700"
            :class="usageTone(part.percent).bar"
            :style="{ width: `${Math.min(100, part.percent)}%` }"
          />
        </div>
        <div class="mt-1.5 flex items-center justify-between font-mono text-[11.4px] text-mist-500">
          <span class="truncate">{{ part.device }}</span>
          <span>{{ formatGb(part.used_gb) }} / {{ formatGb(part.total_gb) }}</span>
        </div>
      </div>

      <div v-if="!disk.partitions.length" class="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-center text-[13.2px] text-mist-500">
        未读取到磁盘分区信息
      </div>
    </div>
  </section>
</template>
