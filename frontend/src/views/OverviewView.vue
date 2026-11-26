<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  Activity,
  CircleAlert,
  LayoutGrid,
  RefreshCw,
  Server,
  ShieldCheck,
} from 'lucide-vue-next'
import { hostApi } from '../api/host'
import { errorMessage } from '../api/client'
import { useBoardStore } from '../stores/board'
import { useThemeStore } from '../stores/theme'
import type { HostOverview } from '../types'
import { formatGb, formatUptime, relativeTime } from '../utils/format'
import KpiGrid from '../components/overview/KpiGrid.vue'
import TrendChart from '../components/overview/TrendChart.vue'
import CorePanel from '../components/overview/CorePanel.vue'
import DiskPanel from '../components/overview/DiskPanel.vue'
import NetworkPanel from '../components/overview/NetworkPanel.vue'
import ProcessPanel from '../components/overview/ProcessPanel.vue'

const board = useBoardStore()
const theme = useThemeStore()

const overview = ref<HostOverview | null>(null)
const loading = ref(false)
const error = ref('')
let timer: number | null = null

const history = computed(() => overview.value?.history ?? [])
const health = computed(() => {
  const status = overview.value?.health?.status ?? 'unknown'
  const map: Record<string, { label: string; chip: string; dot: string }> = {
    ok: { label: '运行健康', chip: 'bg-state-ok/12 text-state-ok', dot: 'bg-state-ok' },
    warning: { label: '资源告警', chip: 'bg-state-warn/12 text-state-warn', dot: 'bg-state-warn' },
    critical: { label: '资源紧张', chip: 'bg-state-bad/12 text-state-bad', dot: 'bg-state-bad' },
    unknown: { label: '等待采样', chip: 'bg-white/[0.06] text-mist-500', dot: 'bg-mist-500' },
  }
  return map[status] ?? map.unknown
})

const resSeries = computed(() => [
  { key: 'cpu' as const, name: 'CPU %', color: theme.colors[0] },
  { key: 'mem' as const, name: '内存 %', color: theme.colors[1] },
])
const netSeries = computed(() => [
  { key: 'net_down' as const, name: '下行', color: theme.colors[0] },
  { key: 'net_up' as const, name: '上行', color: theme.colors[1] },
])
const ioSeries = computed(() => [
  { key: 'disk_read' as const, name: '读取', color: theme.colors[0] },
  { key: 'disk_write' as const, name: '写入', color: theme.colors[2] },
])

async function load(force = false): Promise<void> {
  if (!force) loading.value = false
  else loading.value = true
  try {
    overview.value = force ? await hostApi.sample() : await hostApi.overview()
    error.value = ''
  } catch (err) {
    error.value = errorMessage(err)
    console.error('主机指标加载失败', err)
  } finally {
    loading.value = false
  }
}

function startPolling(intervalMs: number): void {
  stopPolling()
  timer = window.setInterval(() => {
    if (document.hidden) return
    void load()
  }, intervalMs)
}

function stopPolling(): void {
  if (timer) window.clearInterval(timer)
  timer = null
}

onMounted(async () => {
  await load()
  startPolling((overview.value?.interval ?? 3) * 1000)
})

onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="space-y-4">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-[26.4px] font-semibold tracking-tight text-mist-100">服务器总览</h1>
          <span class="flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11.4px]" :class="health.chip">
            <span class="h-1.5 w-1.5 rounded-full animate-breathe" :class="health.dot" />
            {{ health.label }}
          </span>
        </div>
        <p class="mt-1 truncate text-[13.2px] text-mist-300">
          <span class="font-mono text-mist-100">{{ overview?.system.hostname || '—' }}</span>
          · {{ overview?.system.os || '读取中' }}
          · 已运行 {{ formatUptime(overview?.system.uptime_seconds) }}
          · 每 {{ overview?.interval ?? 3 }}s 采样
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span class="hidden text-[11.4px] text-mist-500 sm:inline">
          更新于 {{ relativeTime(overview?.collected_at) }}
        </span>
        <button type="button" class="btn-ghost h-9" :disabled="loading" @click="load(true)">
          <RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin' : ''" />
          立即刷新
        </button>
        <RouterLink to="/board" class="btn-primary h-9">
          <LayoutGrid class="h-4 w-4" />
          应用面板
        </RouterLink>
      </div>
    </header>

    <div
      v-if="error || (overview && !overview.available)"
      class="flex flex-wrap items-center gap-2 rounded-xl border border-state-bad/25 bg-state-bad/8 px-4 py-3 text-[13.2px] text-state-bad"
    >
      <CircleAlert class="h-4 w-4" />
      主机指标不可用：{{ error || overview?.error?.message }}
      <button type="button" class="btn-ghost ml-auto h-7 px-2 text-state-bad" @click="load(true)">重试</button>
    </div>

    <template v-if="overview?.available">
      <KpiGrid :overview="overview" />

      <div class="grid gap-3 lg:grid-cols-3">
        <section class="glass-panel p-4 lg:col-span-2">
          <div class="mb-1 flex items-center justify-between">
            <h2 class="label-caps">CPU / 内存趋势（近 6 分钟）</h2>
            <span class="font-mono text-[11.4px] text-mist-500">{{ history.length }} samples</span>
          </div>
          <TrendChart :points="history" :series="resSeries" :max="100" unit="%" height="206px" />
        </section>
        <CorePanel :cpu="overview.cpu" :system="overview.system" />
      </div>

      <div class="grid gap-3 lg:grid-cols-2">
        <section class="glass-panel p-4">
          <div class="mb-1 flex items-center justify-between">
            <h2 class="label-caps">网络吞吐</h2>
            <span class="text-[11.4px] text-mist-500">
              累计 ↓ {{ overview.network.total_recv_gb }} GB · ↑ {{ overview.network.total_sent_gb }} GB
            </span>
          </div>
          <TrendChart :points="history" :series="netSeries" unit="KB/s" height="176px" />
        </section>

        <section class="glass-panel p-4">
          <div class="mb-1 flex items-center justify-between">
            <h2 class="label-caps">磁盘 IO</h2>
            <span class="text-[11.4px] text-mist-500">
              总容量 {{ formatGb(overview.disk.total_gb) }}
            </span>
          </div>
          <TrendChart :points="history" :series="ioSeries" unit="KB/s" height="176px" />
        </section>
      </div>

      <div class="grid items-start gap-3 lg:grid-cols-3">
        <div class="lg:col-span-2">
          <DiskPanel :disk="overview.disk" />
        </div>
        <NetworkPanel :network="overview.network" />
      </div>

      <div class="grid items-start gap-3 lg:grid-cols-3">
        <div class="lg:col-span-2">
          <ProcessPanel :processes="overview.processes" />
        </div>

        <section class="glass-panel p-4">
          <div class="flex items-center gap-2">
            <Server class="h-4 w-4 text-aurora-teal" />
            <h2 class="text-[15.6px] font-semibold text-mist-100">系统信息</h2>
          </div>
          <dl class="mt-2 divide-y divide-white/[0.04] text-[12.6px]">
            <div class="flex justify-between gap-3 py-1.5">
              <dt class="text-mist-500">CPU 型号</dt>
              <dd class="max-w-[62%] truncate text-right text-mist-100" :title="overview.system.cpu_model">
                {{ overview.system.cpu_model }}
              </dd>
            </div>
            <div class="flex justify-between gap-3 py-1.5">
              <dt class="text-mist-500">核心 / 架构</dt>
              <dd class="font-mono text-mist-100">
                {{ overview.system.cores }} / {{ overview.system.arch }}
              </dd>
            </div>
            <div class="flex justify-between gap-3 py-1.5">
              <dt class="text-mist-500">内核</dt>
              <dd class="font-mono text-mist-100">{{ overview.system.kernel }}</dd>
            </div>
            <div class="flex justify-between gap-3 py-1.5">
              <dt class="text-mist-500">进程 / 用户</dt>
              <dd class="font-mono text-mist-100">
                {{ overview.system.process_count }} / {{ overview.system.user_count }}
              </dd>
            </div>
            <div class="flex justify-between gap-3 py-1.5">
              <dt class="text-mist-500">服务卡片</dt>
              <dd class="flex items-center gap-2 font-mono text-[11.4px]">
                <span class="text-state-ok">{{ board.stats.running }}</span>
                <span class="text-state-warn">{{ board.stats.warning }}</span>
                <span class="text-state-bad">{{ board.stats.unavailable + board.stats.unknown }}</span>
              </dd>
            </div>
          </dl>
          <RouterLink
            to="/board"
            class="mt-3 flex items-center justify-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] py-2 text-[12px] text-mist-300 transition-colors hover:border-aurora-teal/30 hover:text-mist-100"
          >
            <ShieldCheck class="h-3.5 w-3.5" />
            查看 {{ board.stats.total }} 张服务卡片
          </RouterLink>
        </section>
      </div>
    </template>

    <div v-else-if="!error" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div v-for="index in 4" :key="index" class="h-[130px] animate-pulse rounded-2xl border border-white/[0.05] bg-white/[0.02]" />
      <div class="col-span-full flex items-center gap-2 text-[13.2px] text-mist-500">
        <Activity class="h-4 w-4 animate-pulse" />
        正在读取主机指标…
      </div>
    </div>
  </div>
</template>
