<script setup lang="ts">
import { Network } from 'lucide-vue-next'
import type { HostOverview } from '../../types'
import { formatRate } from '../../utils/format'

defineProps<{ network: HostOverview['network'] }>()
</script>

<template>
  <section class="glass-panel p-4">
    <div class="flex flex-wrap items-center gap-2">
      <Network class="h-4 w-4 text-aurora-violet" />
      <h2 class="text-[15.6px] font-semibold text-mist-100">网络接口</h2>
      <div class="ml-auto flex items-center gap-3 font-mono text-[11.4px]">
        <span class="text-state-ok">↓ {{ formatRate(network.down_kbps) }}</span>
        <span class="text-aurora-violet">↑ {{ formatRate(network.up_kbps) }}</span>
      </div>
    </div>

    <div class="mt-3 space-y-2">
      <div
        v-for="item in network.interfaces"
        :key="item.name"
        class="rounded-xl border border-white/[0.05] bg-white/[0.02] px-3 py-2.5"
      >
        <div class="flex items-center gap-2">
          <span class="font-mono text-[13.2px] text-mist-100">{{ item.name }}</span>
          <span class="truncate font-mono text-[11.4px] text-mist-500">{{ item.ip }}</span>
          <span class="ml-auto shrink-0 font-mono text-[11.4px] text-mist-300">
            ↓ {{ formatRate(item.down_kbps) }}
          </span>
        </div>
        <div class="mt-1.5 flex items-center justify-between text-[11.4px] text-mist-500">
          <span>↑ {{ formatRate(item.up_kbps) }}</span>
          <span>累计 ↓ {{ item.recv_gb }} GB · ↑ {{ item.sent_gb }} GB</span>
        </div>
      </div>

      <div v-if="!network.interfaces.length" class="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-center text-[13.2px] text-mist-500">
        未发现活跃网卡
      </div>
    </div>
  </section>
</template>
