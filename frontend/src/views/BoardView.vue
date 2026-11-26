<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Layers, Radar } from 'lucide-vue-next'
import { cardsApi } from '../api/cards'
import { errorMessage } from '../api/client'
import { useBoardStore } from '../stores/board'
import type { Provider, ServiceCard } from '../types'
import BoardToolbar from '../components/board/BoardToolbar.vue'
import CardGrid from '../components/board/CardGrid.vue'
import StatusStrip from '../components/board/StatusStrip.vue'
import CardFormDrawer from '../components/card/CardFormDrawer.vue'
import CardGeneratorWizard from '../components/ai/CardGeneratorWizard.vue'

const board = useBoardStore()
const route = useRoute()
const router = useRouter()

const providers = ref<Provider[]>([])
const formOpen = ref(false)
const formCard = ref<ServiceCard | null>(null)
const wizardOpen = ref(false)

async function loadProviders(): Promise<void> {
  try {
    providers.value = await cardsApi.providers()
  } catch (err) {
    console.error('供应商加载失败', err)
  }
}

function openCard(card: ServiceCard): void {
  void router.push(`/cards/${card.id}`)
}

function openCreate(): void {
  formCard.value = null
  formOpen.value = true
}

async function handleAction(card: ServiceCard, action: 'start' | 'stop' | 'restart'): Promise<void> {
  if (action !== 'start') {
    try {
      await ElMessageBox.confirm(
        `${action === 'restart' ? '重启' : '停止'}「${card.title}」会短暂中断服务，操作将写入审计日志。`,
        '确认操作',
        { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }
  try {
    const summary = await board.quickAction(card.id, action)
    ElMessage.success(summary)
  } catch (err) {
    ElMessage.error(errorMessage(err))
  }
}

function openChat(card: ServiceCard): void {
  void router.push({ path: `/cards/${card.id}`, query: { tab: 'chat' } })
}

watch(
  () => route.query.wizard,
  (value) => {
    if (value) {
      wizardOpen.value = true
      void router.replace({ path: '/board', query: {} })
    }
  },
  { immediate: true },
)

onMounted(() => {
  void loadProviders()
  void board.refreshSystem()
})
</script>

<template>
  <div class="space-y-4">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-[26.4px] font-semibold tracking-tight text-mist-100">应用面板</h1>
          <span class="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 font-mono text-[12px] text-mist-500">
            ATOMIC BOARD
          </span>
        </div>
        <p class="mt-1 max-w-2xl text-[14.4px] leading-relaxed text-mist-300">
          每个容器、systemd 服务或端口都是一张独立卡片，卡片自带专属 agent。
          拖拽卡片左侧手柄可编排顺序，悬停卡片即可启停或直接对话。
        </p>
      </div>
      <div class="flex items-center gap-3 text-[13.2px] text-mist-500">
        <span class="flex items-center gap-1.5">
          <Layers class="h-3.5 w-3.5" />
          {{ board.stats.total }} 张卡片 · {{ board.groups.length }} 个分组
        </span>
        <span class="flex items-center gap-1.5">
          <Radar class="h-3.5 w-3.5 text-aurora-teal" />
          采集周期 {{ board.system?.interval ?? 5 }}s
        </span>
      </div>
    </header>

    <StatusStrip />

    <section class="glass-panel p-4">
      <BoardToolbar @create="openCreate" @generate="wizardOpen = true" />
    </section>

    <CardGrid
      @open="openCard"
      @action="handleAction"
      @chat="openChat"
      @create="openCreate"
    />

    <CardFormDrawer
      v-model="formOpen"
      :card="formCard"
      :providers="providers"
      @saved="board.refresh()"
    />

    <CardGeneratorWizard
      v-model="wizardOpen"
      :providers="providers"
      @created="board.refresh()"
    />
  </div>
</template>
