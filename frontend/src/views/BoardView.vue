<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Layers, Radar } from 'lucide-vue-next'
import { cardsApi } from '../api/cards'
import { errorMessage } from '../api/client'
import { useBoardStore } from '../stores/board'
import type { ServiceCard } from '../types'
import BoardToolbar from '../components/board/BoardToolbar.vue'
import CardGrid from '../components/board/CardGrid.vue'
import StatusStrip from '../components/board/StatusStrip.vue'
import AiCardDialog from '../components/board/AiCardDialog.vue'

const board = useBoardStore()
const router = useRouter()
const aiDialogOpen = ref(false)

function openCard(card: ServiceCard): void {
  void router.push(`/cards/${card.id}`)
}

function openAiCreate(): void {
  aiDialogOpen.value = true
}

function openWorkspaceInDsh(workspaceId: string): void {
  void router.push({ name: 'dsh', query: { workspace: workspaceId } })
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

onMounted(() => {
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
          每个容器、systemd 服务或端口都是一张独立卡片；点击卡片先进入运行监控页查看 CPU、内存与日志，再切到第二页
          dsh 工作区与 AI 对话。新建卡片由 dsh 中的 AI 通过 MCP 完成：描述服务或容器需求，AI 会创建工作区、启动服务并生成卡片。
          拖拽卡片左侧手柄可编排顺序，悬停卡片即可启停服务。
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
      <BoardToolbar @create="openAiCreate" />
    </section>

    <CardGrid
      @open="openCard"
      @action="handleAction"
      @create="openAiCreate"
    />

    <AiCardDialog v-model="aiDialogOpen" @created="openWorkspaceInDsh" />
  </div>
</template>
