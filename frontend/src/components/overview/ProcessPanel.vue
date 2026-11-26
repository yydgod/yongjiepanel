<script setup lang="ts">
import { ListTree } from 'lucide-vue-next'
import type { HostProcess } from '../../types'
import { formatPercent } from '../../utils/format'

defineProps<{ processes: HostProcess[] }>()
</script>

<template>
  <section class="glass-panel p-4">
    <div class="flex items-center gap-2">
      <ListTree class="h-4 w-4 text-aurora-blue" />
      <h2 class="text-[15.6px] font-semibold text-mist-100">TOP 进程</h2>
      <span class="ml-auto text-[11.4px] text-mist-500">按内存占用排序</span>
    </div>

    <div class="mt-2 overflow-hidden">
      <table class="w-full text-left">
        <thead>
          <tr class="text-[10.8px] uppercase tracking-wider text-mist-500">
            <th class="py-1.5 font-medium">进程</th>
            <th class="py-1.5 font-medium">PID</th>
            <th class="py-1.5 text-right font-medium">内存</th>
            <th class="py-1.5 text-right font-medium">CPU</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="proc in processes"
            :key="proc.pid"
            class="border-t border-white/[0.04] text-[12.6px] text-mist-300"
          >
            <td class="max-w-[180px] truncate py-2 text-mist-100">{{ proc.name }}</td>
            <td class="py-2 font-mono text-[11.4px] text-mist-500">{{ proc.pid }}</td>
            <td class="py-2 text-right font-mono">{{ proc.memory_mb }} MB</td>
            <td class="py-2 text-right font-mono">{{ formatPercent(proc.cpu_percent) }}</td>
          </tr>
          <tr v-if="!processes.length">
            <td colspan="4" class="py-6 text-center text-[13.2px] text-mist-500">暂无进程数据</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
