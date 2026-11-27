<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { RefreshCw, ScrollText, TriangleAlert } from 'lucide-vue-next'
import { errorMessage } from '../../api/client'
import { logsApi, type LogCard, type LogEntry } from '../../api/logs'

const items = ref<LogEntry[]>([])
const cards = ref<LogCard[]>([])
const feedErrors = ref<{ card_id: string; card_title: string; message: string }[]>([])
const lines = ref(60)
const cardId = ref('')
const follow = ref(true)
const onlyIssues = ref(false)
const loading = ref(false)
const error = ref('')
let timer: number | null = null

const levelClass: Record<string, string> = {
  error: 'bg-state-bad/12 text-state-bad',
  warn: 'bg-state-warn/12 text-state-warn',
  info: 'bg-aurora-teal/10 text-aurora-teal',
  debug: 'bg-white/[0.06] text-mist-500',
}
const levelLabel: Record<string, string> = {
  error: 'ERROR',
  warn: 'WARN',
  info: 'INFO',
  debug: 'DEBUG',
}

const visibleItems = computed(() =>
  onlyIssues.value
    ? items.value.filter((item) => item.level === 'error' || item.level === 'warn')
    : items.value,
)

function formatTs(ts: string | null): string {
  if (!ts) return '—'
  if (/^[A-Z][a-z]{2}\s+\d/.test(ts)) return ts.slice(-8)
  const parsed = new Date(ts.replace(' ', 'T'))
  if (Number.isNaN(parsed.getTime())) return ts
  return parsed.toLocaleTimeString('zh-CN', { hour12: false })
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const response = await logsApi.feed(lines.value, cardId.value || undefined)
    items.value = response.items
    cards.value = response.cards
    feedErrors.value = response.errors
    error.value = ''
  } catch (err) {
    error.value = errorMessage(err)
    items.value = []
    cards.value = []
    feedErrors.value = []
  } finally {
    loading.value = false
  }
}

function stopPolling(): void {
  if (timer !== null) window.clearInterval(timer)
  timer = null
}

function syncPolling(): void {
  stopPolling()
  if (!follow.value) return
  timer = window.setInterval(() => {
    if (!document.hidden) void load()
  }, 8000)
}

watch([lines, cardId], () => void load())
watch(follow, syncPolling)
onMounted(() => {
  void load()
  syncPolling()
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <section class="glass-panel overflow-hidden">
    <div class="flex flex-wrap items-center gap-2 border-b border-white/[0.06] px-4 py-3">
      <ScrollText class="h-4 w-4 text-aurora-teal" />
      <h2 class="text-[15.6px] font-semibold text-mist-100">服务日志</h2>
      <span class="text-[11.4px] text-mist-500">
        {{ visibleItems.length }} 条 · 来自 {{ cards.length }} 个服务 · 容器 / systemd 日志尾部
      </span>

      <div class="ml-auto flex flex-wrap items-center gap-2">
        <el-select v-model="cardId" size="small" class="w-[136px]" placeholder="全部服务">
          <el-option value="" label="全部服务" />
          <el-option v-for="card in cards" :key="card.id" :value="card.id" :label="card.title" />
        </el-select>
        <el-select v-model="lines" size="small" class="w-[92px]" @change="load">
          <el-option :value="60" label="60 行" />
          <el-option :value="120" label="120 行" />
          <el-option :value="200" label="200 行" />
        </el-select>
        <label class="flex cursor-pointer items-center gap-1.5 text-[12.6px] text-mist-300">
          <input v-model="onlyIssues" type="checkbox" class="h-3 w-3 accent-aurora-teal" />
          只看告警
        </label>
        <label class="flex cursor-pointer items-center gap-1.5 text-[12.6px] text-mist-300">
          <input v-model="follow" type="checkbox" class="h-3 w-3 accent-aurora-teal" />
          跟随最新
        </label>
        <button type="button" class="btn-ghost h-7 px-2" :disabled="loading" @click="load">
          <RefreshCw class="h-3 w-3" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
      </div>
    </div>

    <div v-if="error" class="border-b border-state-bad/20 bg-state-bad/8 px-4 py-2 text-[13.2px] text-state-bad">
      日志加载失败：{{ error }}
      <button type="button" class="btn-ghost ml-2 h-6 px-2 text-state-bad" @click="load">重试</button>
    </div>

    <div
      v-if="feedErrors.length"
      class="flex items-center gap-2 border-b border-state-warn/20 bg-state-warn/8 px-4 py-2 text-[12.6px] text-state-warn"
    >
      <TriangleAlert class="h-3.5 w-3.5 shrink-0" />
      <span class="truncate">
        {{ feedErrors.length }} 个服务日志不可用：{{ feedErrors.map((item) => item.card_title).join('、') }}
      </span>
    </div>

    <div class="max-h-[320px] overflow-auto bg-ink-950/50 p-3 font-mono text-[12.4px] leading-relaxed">
      <div
        v-for="(item, index) in visibleItems"
        :key="`${item.card_id}-${index}`"
        class="flex items-start gap-2 border-b border-white/[0.03] py-1 last:border-0 hover:bg-white/[0.02]"
      >
        <span class="w-[66px] shrink-0 text-mist-500" :title="item.ts || ''">{{ formatTs(item.ts) }}</span>
        <span class="w-[42px] shrink-0 rounded text-center text-[10.8px]" :class="levelClass[item.level]">
          {{ levelLabel[item.level] }}
        </span>
        <RouterLink
          :to="`/cards/${item.card_id}`"
          class="hidden w-[104px] shrink-0 truncate text-aurora-teal hover:underline sm:block"
          :title="item.card_title"
        >
          {{ item.card_title }}
        </RouterLink>
        <span class="min-w-0 flex-1 whitespace-pre-wrap break-all text-mist-300">{{ item.message }}</span>
      </div>

      <div v-if="!visibleItems.length && !error" class="px-2 py-8 text-center text-[13.2px] text-mist-500">
        {{
          onlyIssues
            ? '当前没有告警或错误日志。'
            : loading
              ? '正在读取日志…'
              : '暂无日志输出。容器 / systemd 服务产生日志后会自动显示在这里。'
        }}
      </div>
    </div>
  </section>
</template>
