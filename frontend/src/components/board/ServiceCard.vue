<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight, GripVertical, Play, RotateCw, Square } from 'lucide-vue-next'
import type { ServiceCard } from '../../types'
import {
  accentGradient,
  formatMemory,
  formatPercent,
  formatUptime,
  statusVisual,
} from '../../utils/format'
import { cardIcon } from '../../utils/icons'

const props = defineProps<{ card: ServiceCard; compact?: boolean }>()

const emit = defineEmits<{
  (event: 'open', card: ServiceCard): void
  (event: 'action', card: ServiceCard, action: 'start' | 'stop' | 'restart'): void
}>()

const visual = computed(() => statusVisual(props.card.status?.status))
const Icon = computed(() => cardIcon(props.card.icon))
const showMetrics = computed(() => props.card.display_config?.showMetrics !== false)
const showPorts = computed(() => props.card.display_config?.showPorts !== false)
const cpu = computed(() => props.card.status?.cpu_percent ?? null)
const memory = computed(() => props.card.status?.memory_mb ?? null)
const memRatio = computed(() => {
  const used = props.card.status?.memory_mb
  const limit = props.card.status?.memory_limit_mb
  if (used === null || used === undefined || !limit) return null
  return Math.min(100, (used / limit) * 100)
})
const ports = computed(() => props.card.status?.ports ?? [])
const canControl = computed(() => ['container', 'systemd'].includes(props.card.card_type))
const typeLabel = computed(() => {
  const map: Record<string, string> = {
    container: 'DOCKER',
    systemd: 'SYSTEMD',
    port: 'PORT',
    custom: 'CUSTOM',
  }
  return map[props.card.card_type] ?? props.card.card_type.toUpperCase()
})

function act(action: 'start' | 'stop' | 'restart'): void {
  emit('action', props.card, action)
}
</script>

<template>
  <article
    class="group relative cursor-pointer overflow-hidden rounded-2xl border border-white/[0.06] bg-ink-800/60 p-4 shadow-glass backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-white/[0.14] hover:bg-ink-700/70"
    :class="compact ? 'min-h-[132px]' : 'min-h-[186px]'"
    @click="emit('open', card)"
  >
    <div
      class="pointer-events-none absolute -right-10 -top-14 h-36 w-36 rounded-full bg-gradient-to-br opacity-25 blur-2xl transition-opacity duration-500 group-hover:opacity-50"
      :class="accentGradient(card.accent)"
    />
    <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />

    <header class="relative flex items-start gap-3">
      <div
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ring-white/10"
        :class="accentGradient(card.accent)"
      >
        <component :is="Icon" class="h-[18px] w-[18px] text-icon-ink" />
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <h3 class="truncate text-[16.8px] font-semibold text-mist-100">{{ card.title }}</h3>
          <span class="shrink-0 rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10.2px] tracking-normal text-mist-500">
            {{ typeLabel }}
          </span>
        </div>
        <p class="mt-0.5 truncate text-[12.6px] text-mist-500" :class="card.subtitle ? 'font-sans' : 'font-mono'">
          {{ card.subtitle || card.target_ref }}
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-1.5">
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full rounded-full opacity-60 animate-breathe" :class="visual.dot" />
          <span class="relative inline-flex h-2 w-2 rounded-full" :class="visual.dot" />
        </span>
        <span class="text-[12.6px]" :class="visual.text">{{ visual.label }}</span>
      </div>
    </header>

    <div v-if="showMetrics" class="relative mt-4 space-y-2">
      <div v-if="compact" class="flex items-center justify-between font-mono text-[12.6px] text-mist-300">
        <span>CPU {{ formatPercent(cpu) }}</span>
        <span>{{ formatMemory(memory) }}</span>
      </div>
      <template v-else>
        <div class="flex items-center gap-2">
          <span class="w-6 font-mono text-[10.8px] uppercase tracking-wider text-mist-500">cpu</span>
          <div class="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              class="h-full rounded-full bg-gradient-to-r from-aurora-teal to-aurora-blue transition-all duration-700"
              :style="{ width: `${Math.min(100, cpu ?? 0)}%` }"
            />
          </div>
          <span class="w-14 shrink-0 text-right font-mono text-[12.6px] text-mist-300">{{ formatPercent(cpu) }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-6 font-mono text-[10.8px] uppercase tracking-wider text-mist-500">mem</span>
          <div class="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              class="h-full rounded-full bg-gradient-to-r from-aurora-violet to-aurora-violet/40 transition-all duration-700"
              :style="{ width: `${memRatio ?? Math.min(100, (memory ?? 0) / 20)}%` }"
            />
          </div>
          <span class="w-14 shrink-0 text-right font-mono text-[12.6px] text-mist-300">{{ formatMemory(memory) }}</span>
        </div>
      </template>
    </div>

    <footer class="relative mt-3 flex items-center justify-between gap-2">
      <div class="flex min-w-0 items-center gap-1.5">
        <template v-if="showPorts && ports.length">
          <span
            v-for="port in ports.slice(0, 2)"
            :key="port"
            class="rounded border border-aurora-teal/20 bg-aurora-teal/8 px-1.5 py-0.5 font-mono text-[11.4px] text-aurora-teal"
          >
            :{{ port }}
          </span>
          <span v-if="ports.length > 2" class="font-mono text-[11.4px] text-mist-500">+{{ ports.length - 2 }}</span>
        </template>
        <span v-else class="truncate text-[12px] text-mist-500">
          {{ card.status?.detail || '等待采集' }}
        </span>
      </div>

      <div class="flex shrink-0 items-center gap-2">
        <span class="font-mono text-[12px] text-mist-500">{{ formatUptime(card.status?.uptime_seconds) }}</span>
        <ChevronRight class="h-3.5 w-3.5 text-mist-500 transition-transform group-hover:translate-x-0.5 group-hover:text-mist-300" />
      </div>
    </footer>

    <!-- hover actions -->
    <div
      class="absolute right-3 top-[60px] z-10 flex items-center gap-1 rounded-lg border border-white/10 bg-ink-900/85 p-1 opacity-0 shadow-lg backdrop-blur-md transition-opacity duration-200 group-hover:opacity-100"
      @click.stop
    >
      <button
        v-if="canControl"
        type="button"
        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-mist-300 transition-colors hover:bg-white/10 hover:text-aurora-teal"
        title="重启服务"
        @click="act('restart')"
      >
        <RotateCw class="h-3.5 w-3.5" />
      </button>
      <button
        v-if="canControl && card.status?.status !== 'running'"
        type="button"
        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-mist-300 transition-colors hover:bg-white/10 hover:text-state-ok"
        title="启动服务"
        @click="act('start')"
      >
        <Play class="h-3.5 w-3.5" />
      </button>
      <button
        v-if="canControl && card.status?.status === 'running'"
        type="button"
        class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-mist-300 transition-colors hover:bg-white/10 hover:text-state-warn"
        title="停止服务"
        @click="act('stop')"
      >
        <Square class="h-3.5 w-3.5" />
      </button>
    </div>

    <div
      class="absolute left-1 top-1/2 -translate-y-1/2 cursor-grab text-mist-500/0 transition-colors group-hover:text-mist-500/70 drag-handle"
      @click.stop
    >
      <GripVertical class="h-4 w-4" />
    </div>
  </article>
</template>
