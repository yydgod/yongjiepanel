<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { RefreshCw, ExternalLink } from 'lucide-vue-next'
import { cardsApi } from '../api/cards'
import { errorMessage } from '../api/client'
import type { DshEntry } from '../types'

const route = useRoute()
const entry = ref<DshEntry | null>(null)
const loading = ref(true)
const error = ref('')
const frameKey = ref(0)
const workspaceId = computed(() => String(route.query.workspace ?? ''))
const frameSrc = computed(() => {
  const url = entry.value?.url
  if (!url) return ''
  if (!workspaceId.value) return url
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}workspace=${encodeURIComponent(workspaceId.value)}`
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    entry.value = await cardsApi.dshEntry()
  } catch (err) {
    error.value = errorMessage(err)
    entry.value = null
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
      <div>
        <h1 class="text-[22.8px] font-semibold text-mist-100">dsh 工作区</h1>
        <p class="text-[12.6px] text-mist-500">原生 dsh 界面 · 模型、文件、终端均由 dsh 提供</p>
      </div>
      <div class="ml-auto flex items-center gap-1.5">
        <button type="button" class="btn-ghost h-9" :disabled="loading" @click="reload">
          <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
        <a v-if="entry?.url" :href="entry.url" target="_blank" rel="noreferrer" class="btn-ghost h-9">
          <ExternalLink class="h-3.5 w-3.5" />
          新窗口
        </a>
      </div>
    </div>

    <div v-if="loading" class="glass-panel p-10 text-center text-[13.2px] text-mist-500">
      正在连接 dsh…
    </div>
    <div v-else-if="error" class="glass-panel p-10 text-center">
      <p class="text-[15.6px] text-state-bad">{{ error }}</p>
      <button type="button" class="btn-primary mt-3" @click="load">重试</button>
    </div>
    <div v-else-if="!entry?.configured" class="glass-panel p-10 text-center">
      <p class="text-[15.6px] text-mist-100">dsh 尚未配置</p>
      <p class="mt-1 text-[12.6px] text-mist-500">{{ entry?.reason || '请配置 DSH_BASE_URL / DSH_TOKEN' }}</p>
    </div>
    <div v-else class="overflow-hidden rounded-2xl border border-white/[0.08] bg-white">
      <iframe
        :key="`${frameKey}-${workspaceId}`"
        :src="frameSrc"
        title="dsh 工作区"
        class="h-[calc(100vh-168px)] min-h-[560px] w-full border-0"
        allow="clipboard-read; clipboard-write"
      />
    </div>
  </div>
</template>
