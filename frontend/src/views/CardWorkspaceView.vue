<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-vue-next'
import { cardsApi } from '../api/cards'
import { errorMessage } from '../api/client'
import type { DshWorkspaceInfo } from '../types'

const route = useRoute()
const router = useRouter()
const info = ref<DshWorkspaceInfo | null>(null)
const loading = ref(true)
const error = ref('')
const frameKey = ref(0)

const cardId = computed(() => String(route.params.id ?? ''))
const title = computed(() => info.value?.title || '工作区')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    info.value = await cardsApi.dsh(cardId.value)
    document.title = `${title.value} · dsh 工作区`
  } catch (err) {
    error.value = errorMessage(err)
    info.value = null
  } finally {
    loading.value = false
  }
}

function reload(): void {
  frameKey.value += 1
}

onMounted(load)
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center gap-2">
      <button type="button" class="btn-ghost h-9" @click="router.push('/board')">
        <ArrowLeft class="h-4 w-4" />
        返回应用面板
      </button>
      <div class="min-w-0">
        <h1 class="truncate text-[19.2px] font-semibold text-mist-100">{{ title }}</h1>
        <p class="truncate text-[12px] text-mist-500">
          dsh 原生工作区 · {{ info?.path || '加载中…' }}
        </p>
      </div>
      <div class="ml-auto flex items-center gap-1.5">
        <button type="button" class="btn-ghost h-9" :disabled="loading" @click="reload">
          <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
        <a
          v-if="info?.url"
          :href="info.url"
          target="_blank"
          rel="noreferrer"
          class="btn-ghost h-9"
        >
          <ExternalLink class="h-3.5 w-3.5" />
          新窗口
        </a>
      </div>
    </div>

    <div v-if="loading" class="glass-panel p-10 text-center text-[13.2px] text-mist-500">
      正在连接 dsh 工作区…
    </div>

    <div v-else-if="error" class="glass-panel p-10 text-center">
      <p class="text-[15.6px] text-state-bad">{{ error }}</p>
      <button type="button" class="btn-primary mt-3" @click="load">重试</button>
    </div>

    <div v-else-if="!info?.configured" class="glass-panel p-10 text-center">
      <p class="text-[15.6px] text-mist-100">该卡片还没有可用的 dsh 工作区</p>
      <p class="mt-1 text-[12.6px] text-mist-500">{{ info?.reason || '请先运行工作区迁移脚本' }}</p>
      <RouterLink to="/board" class="btn-ghost mt-3 inline-flex">返回应用面板</RouterLink>
    </div>

    <div v-else class="overflow-hidden rounded-2xl border border-white/[0.08] bg-white">
      <iframe
        :key="frameKey"
        :src="info.url"
        title="dsh 工作区"
        class="h-[calc(100vh-168px)] min-h-[560px] w-full border-0"
        allow="clipboard-read; clipboard-write"
      />
    </div>
  </div>
</template>
