<script setup lang="ts">
import { computed, ref } from 'vue'
import { Bot, Cpu, Gauge, MessageSquare, Waypoints } from 'lucide-vue-next'
import type { ServiceCard } from '../../types'
import { formatMemory, formatPercent, formatUptime, relativeTime } from '../../utils/format'
import LogPanel from './LogPanel.vue'
import MetricsChart from './MetricsChart.vue'

const props = defineProps<{ card: ServiceCard }>()

const emit = defineEmits<{
  (event: 'changed'): void
  (event: 'open-chat'): void
}>()

const logPanel = ref<InstanceType<typeof LogPanel> | null>(null)

const showLogs = computed(() => ['container', 'systemd'].includes(props.card.card_type))

defineExpose({ refreshLogs: () => logPanel.value?.load() })
</script>

<template>
  <div class="grid items-start gap-3 lg:grid-cols-3">
    <div class="space-y-3 lg:col-span-2">
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps flex items-center gap-1"><Cpu class="h-3 w-3" />CPU</div>
          <div class="stat-mono mt-1 text-[21.6px]">{{ formatPercent(card.status?.cpu_percent) }}</div>
        </div>
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps flex items-center gap-1"><Gauge class="h-3 w-3" />内存</div>
          <div class="stat-mono mt-1 text-[21.6px]">{{ formatMemory(card.status?.memory_mb) }}</div>
        </div>
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps">运行时长</div>
          <div class="stat-mono mt-1 text-[21.6px]">{{ formatUptime(card.status?.uptime_seconds) }}</div>
        </div>
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps flex items-center gap-1"><Waypoints class="h-3 w-3" />端口</div>
          <div class="stat-mono mt-1 truncate text-[21.6px]">
            {{ card.status?.ports?.length ? card.status.ports.map((p) => `:${p}`).join(' ') : '—' }}
          </div>
        </div>
      </div>

      <div v-if="card.status?.error" class="rounded-xl border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.8px] text-state-bad">
        {{ card.status.error.code }} · {{ card.status.error.message }}
      </div>

      <section class="glass-panel p-4">
        <div class="mb-1 flex items-center justify-between">
          <span class="label-caps">资源趋势（近 15 分钟）</span>
          <span class="text-[12px] text-mist-500">{{ card.status?.detail }}</span>
        </div>
        <MetricsChart :points="card.history ?? []" height="220px" />
      </section>

      <section v-if="showLogs" class="glass-panel p-4">
        <LogPanel ref="logPanel" :card-id="card.id" :card-type="card.card_type" />
      </section>
    </div>

    <div class="space-y-3">
      <section class="glass-panel p-4">
        <div class="flex items-center gap-2">
          <Bot class="h-4 w-4 text-aurora-violet" />
          <h2 class="text-[15.6px] font-semibold text-mist-100">dsh 工作区</h2>
          <span class="ml-auto rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[10.2px] uppercase text-mist-400">
            native
          </span>
        </div>
        <p class="mt-2 text-[12.6px] leading-relaxed text-mist-500">
          对话、文件、终端与模型均由 dsh 原生界面提供；模型在 dsh「设置 → 模型」中配置，面板不保存模型 Key。
        </p>
        <div class="mt-3">
          <button type="button" class="btn-primary w-full justify-center" @click="emit('open-chat')">
            <MessageSquare class="h-3.5 w-3.5" />
            进入 dsh 工作区
          </button>
        </div>
      </section>

      <section class="glass-panel p-4">
        <div class="label-caps mb-2">卡片信息</div>
        <dl class="space-y-1.5 text-[12.6px]">
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">类型</dt>
            <dd class="font-mono text-mist-100">{{ card.card_type }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">目标对象</dt>
            <dd class="max-w-[62%] truncate font-mono text-mist-100" :title="card.target_ref">{{ card.target_ref }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">分组</dt>
            <dd class="truncate text-mist-100">{{ card.group_name }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">采集于</dt>
            <dd class="text-mist-100">{{ relativeTime(card.status?.collected_at) }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">创建时间</dt>
            <dd class="text-mist-100">{{ relativeTime(card.created_at) }}</dd>
          </div>
        </dl>
      </section>

    </div>
  </div>
</template>
