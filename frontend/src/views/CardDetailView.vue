<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  ChevronRight,
  MessageSquare,
  Play,
  RefreshCw,
  RotateCw,
  Square,
  Trash2,
} from 'lucide-vue-next'
import { cardsApi } from '../api/cards'
import { ApiError, errorMessage } from '../api/client'
import { relativeTime, statusVisual } from '../utils/format'
import { cardIcon } from '../utils/icons'
import type { DshWorkspaceInfo, ServiceCard } from '../types'
import CardOverviewTab from '../components/card/CardOverviewTab.vue'

type TabName = 'overview' | 'chat'
const TABS: TabName[] = ['overview', 'chat']

const route = useRoute()
const router = useRouter()

const detail = ref<ServiceCard | null>(null)
const dsh = ref<DshWorkspaceInfo | null>(null)
const loading = ref(true)
const notFound = ref(false)
const busy = ref(false)
const tab = ref<TabName>('overview')
const overviewTab = ref<InstanceType<typeof CardOverviewTab> | null>(null)
let timer: number | null = null

const cardId = computed(() => String(route.params.id ?? ''))
const visual = computed(() => statusVisual(detail.value?.status?.status))
const Icon = computed(() => cardIcon(detail.value?.icon))
const canControl = computed(() => ['container', 'systemd'].includes(detail.value?.card_type ?? ''))

function normalizeTab(value: unknown): TabName {
  return TABS.includes(value as TabName) ? (value as TabName) : 'overview'
}

watch(
  () => route.query.tab,
  (value) => {
    tab.value = normalizeTab(value)
  },
  { immediate: true },
)

watch(tab, (value) => {
  const query = { ...route.query }
  if (value === 'overview') delete query.tab
  else query.tab = value
  if (query.tab !== route.query.tab) void router.replace({ path: route.path, query })
})

async function load(): Promise<void> {
  if (!cardId.value) return
  try {
    detail.value = await cardsApi.detail(cardId.value)
    notFound.value = false
    document.title = `${detail.value.title} · 永杰面板`
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound.value = true
      detail.value = null
    } else {
      ElMessage.error(errorMessage(err))
    }
  } finally {
    loading.value = false
  }
}

async function loadDsh(): Promise<void> {
  try {
    dsh.value = await cardsApi.dsh(cardId.value)
  } catch (err) {
    console.error('dsh 工作区加载失败', err)
  }
}

function startPolling(): void {
  stopPolling()
  timer = window.setInterval(() => {
    if (document.hidden) return
    void load()
  }, 6000)
}

function stopPolling(): void {
  if (timer) window.clearInterval(timer)
  timer = null
}

async function doAction(action: 'start' | 'stop' | 'restart'): Promise<void> {
  if (!detail.value) return
  if (action !== 'start') {
    try {
      await ElMessageBox.confirm(
        `${action === 'restart' ? '重启' : '停止'} ${detail.value.title}（${detail.value.target_ref}）会短暂中断服务，操作将记入审计日志。`,
        '确认操作',
        { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }
  busy.value = true
  try {
    const result = await cardsApi.action(detail.value.id, action)
    ElMessage.success(result.summary)
    await load()
    overviewTab.value?.refreshLogs()
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    busy.value = false
  }
}

async function removeCard(): Promise<void> {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(`删除卡片「${detail.value.title}」？仅移除看板配置，不影响真实服务。`, '删除卡片', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await cardsApi.remove(detail.value.id)
    ElMessage.success('卡片已删除')
    await router.push('/board')
  } catch (err) {
    ElMessage.error(errorMessage(err))
  }
}

async function refresh(): Promise<void> {
  busy.value = true
  await load()
  busy.value = false
}

onMounted(async () => {
  await Promise.all([load(), loadDsh()])
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
  document.title = '永杰面板 · 服务器管理看板'
})
</script>

<template>
  <div class="space-y-4">
    <nav class="flex items-center gap-1.5 text-[12px] text-mist-500">
      <RouterLink to="/board" class="transition-colors hover:text-mist-100">应用面板</RouterLink>
      <ChevronRight class="h-3 w-3" />
      <span class="truncate text-mist-300">{{ detail?.title || '卡片详情' }}</span>
    </nav>

    <template v-if="detail">
      <header class="glass-panel relative overflow-hidden p-4">
        <div class="pointer-events-none absolute -right-16 -top-20 h-44 w-44 rounded-full bg-aurora-teal/10 blur-3xl" />
        <div class="relative flex flex-wrap items-start gap-3">
          <button type="button" class="btn-ghost h-10 w-10 shrink-0 justify-center p-0" title="返回上一页" @click="router.back()">
            <ArrowLeft class="h-4 w-4" />
          </button>
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-white/12 to-white/[0.03] ring-1 ring-white/10">
            <component :is="Icon" class="h-5 w-5 text-aurora-teal" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h1 class="truncate text-[22.8px] font-semibold text-mist-100">{{ detail.title }}</h1>
              <span class="flex items-center gap-1.5 rounded-full border border-white/[0.08] px-2 py-0.5 text-[11.4px]" :class="visual.text">
                <span class="h-1.5 w-1.5 rounded-full animate-breathe" :class="visual.dot" />
                {{ visual.label }}
              </span>
            </div>
            <p class="mt-0.5 truncate text-[13.2px] text-mist-500">
              {{ detail.card_type }} · {{ detail.target_ref }} · {{ detail.group_name }}
              · 采集于 {{ relativeTime(detail.status?.collected_at) }}
            </p>
          </div>
          <div class="flex items-center gap-1.5">
            <button type="button" class="btn-ghost h-9" :disabled="busy" @click="refresh">
              <RefreshCw class="h-3.5 w-3.5" :class="busy ? 'animate-spin' : ''" />
              刷新
            </button>
            <button type="button" class="btn-ghost h-9 px-2 text-state-bad" title="删除卡片" @click="removeCard">
              <Trash2 class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <div class="relative mt-3 flex flex-wrap items-center gap-1.5">
          <button v-if="canControl" type="button" class="btn-ghost h-8" :disabled="busy" @click="doAction('restart')">
            <RotateCw class="h-3.5 w-3.5" />
            重启
          </button>
          <button
            v-if="canControl && detail.status?.status === 'running'"
            type="button"
            class="btn-ghost h-8"
            :disabled="busy"
            @click="doAction('stop')"
          >
            <Square class="h-3.5 w-3.5" />
            停止
          </button>
          <button
            v-if="canControl && detail.status?.status !== 'running'"
            type="button"
            class="btn-ghost h-8"
            :disabled="busy"
            @click="doAction('start')"
          >
            <Play class="h-3.5 w-3.5" />
            启动
          </button>
          <button type="button" class="btn-ghost h-8" @click="tab = 'chat'">
            <MessageSquare class="h-3.5 w-3.5" />
            进入 dsh 工作区
          </button>
        </div>
      </header>

      <el-tabs v-model="tab">
        <el-tab-pane label="概览" name="overview">
          <CardOverviewTab
            ref="overviewTab"
            :card="detail"
            @changed="load"
            @open-chat="tab = 'chat'"
          />
        </el-tab-pane>

        <el-tab-pane label="dsh 工作区" name="chat">
          <div class="glass-panel h-[calc(100vh-330px)] min-h-[520px] overflow-hidden p-1.5">
            <iframe
              v-if="dsh?.configured && dsh.url"
              :src="dsh.url"
              title="dsh 工作区"
              class="h-full w-full rounded-lg border-0 bg-white"
              allow="clipboard-read; clipboard-write"
            />
            <div v-else class="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
              <p class="text-[15.6px] text-mist-100">dsh 工作区尚未就绪</p>
              <p class="text-[12.6px] text-mist-500">{{ dsh?.reason || '请先迁移该卡片为 dsh 工作区' }}</p>
            </div>
          </div>
        </el-tab-pane>

      </el-tabs>
    </template>

    <div v-else-if="loading" class="glass-panel p-8 text-center text-[13.2px] text-mist-500">
      正在加载卡片详情…
    </div>

    <div v-else-if="notFound" class="glass-panel flex flex-col items-center gap-3 p-12 text-center">
      <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.04] ring-1 ring-white/10 text-[20.4px]">
        ?
      </div>
      <div>
        <p class="text-[15.6px] font-medium text-mist-100">卡片不存在或已被删除</p>
        <p class="mt-1 text-[12.6px] text-mist-500">请检查链接中的卡片 ID，或返回应用面板重新选择。</p>
      </div>
      <RouterLink to="/board" class="btn-primary">
        <ArrowLeft class="h-4 w-4" />
        返回应用面板
      </RouterLink>
    </div>
  </div>
</template>
