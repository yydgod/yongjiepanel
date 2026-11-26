<script setup lang="ts">
import { ref, watch } from 'vue'
import { Download, RefreshCw } from 'lucide-vue-next'
import { cardsApi } from '../../api/cards'
import { errorMessage } from '../../api/client'

const props = withDefaults(defineProps<{ cardId: string; cardType: string; active?: boolean }>(), {
  active: true,
})

const content = ref('')
const loading = ref(false)
const error = ref('')
const lines = ref(120)
const follow = ref(true)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await cardsApi.logs(props.cardId, lines.value)
    content.value = response.content || '(无日志输出)'
  } catch (err) {
    error.value = errorMessage(err)
    content.value = ''
  } finally {
    loading.value = false
  }
}

function download(): void {
  const blob = new Blob([content.value], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `card-${props.cardId}-logs.txt`
  link.click()
  URL.revokeObjectURL(url)
}

// 立即加载：兼容标签页首次渲染与卡片切换两种场景
watch(
  () => [props.cardId, props.active] as const,
  () => {
    if (props.active !== false) void load()
  },
  { immediate: true },
)

defineExpose({ load })
</script>

<template>
  <div class="space-y-2">
    <div class="flex flex-wrap items-center gap-2">
      <span class="label-caps">日志尾部</span>
      <el-select v-model="lines" size="small" class="w-[92px]" @change="load">
        <el-option :value="60" label="60 行" />
        <el-option :value="120" label="120 行" />
        <el-option :value="240" label="240 行" />
      </el-select>
      <label class="flex cursor-pointer items-center gap-1.5 text-[13.2px] text-mist-300">
        <input v-model="follow" type="checkbox" class="h-3 w-3 accent-aurora-teal" />
        跟随最新
      </label>
      <div class="ml-auto flex items-center gap-1">
        <button type="button" class="btn-ghost h-7 px-2" :disabled="loading" @click="load">
          <RefreshCw class="h-3 w-3" :class="loading ? 'animate-spin' : ''" />
          刷新
        </button>
        <button type="button" class="btn-ghost h-7 px-2" @click="download">
          <Download class="h-3 w-3" />
          导出
        </button>
      </div>
    </div>

    <div
      v-if="cardType === 'port' || cardType === 'custom'"
      class="rounded-xl border border-dashed border-white/[0.08] px-4 py-8 text-center text-[14.4px] text-mist-500"
    >
      该类型卡片没有容器 / unit 日志。可让 agent 通过 get_status 读取实时指标。
    </div>

    <div v-else-if="error" class="rounded-xl border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.8px] text-state-bad">
      {{ error }}
    </div>

    <pre
      v-if="content"
      class="max-h-[260px] overflow-auto rounded-xl border border-white/[0.06] bg-ink-950/70 p-3 font-mono text-[12.6px] leading-relaxed text-mist-300"
    >{{ content }}</pre>
    <div
      v-else
      class="rounded-xl border border-dashed border-white/[0.08] px-4 py-6 text-center text-[13.8px] text-mist-500"
    >
      {{ loading ? '正在读取日志…' : '（无日志输出）' }}
    </div>
  </div>
</template>
