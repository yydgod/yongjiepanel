<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import Sortable from 'sortablejs'
import { LayoutGrid, Wand2 } from 'lucide-vue-next'
import ServiceCard from './ServiceCard.vue'
import { useBoardStore } from '../../stores/board'
import type { ServiceCard as ServiceCardType } from '../../types'

const emit = defineEmits<{
  (event: 'open', card: ServiceCardType): void
  (event: 'action', card: ServiceCardType, action: 'start' | 'stop' | 'restart'): void
  (event: 'create'): void
}>()

const store = useBoardStore()
const container = ref<HTMLElement | null>(null)
let sortable: Sortable | null = null

onMounted(() => {
  if (!container.value) return
  sortable = Sortable.create(container.value, {
    animation: 180,
    handle: '.drag-handle',
    ghostClass: 'opacity-40',
    dragClass: 'scale-[1.02]',
    onEnd: () => {
      if (!container.value) return
      const ids = Array.from(container.value.querySelectorAll<HTMLElement>('[data-card-id]'))
        .map((node) => node.dataset.cardId)
        .filter((id): id is string => Boolean(id))
      void store.reorder(ids)
    },
  })
})

onBeforeUnmount(() => {
  sortable?.destroy()
  sortable = null
})
</script>

<template>
  <div>
    <div v-if="store.error" class="mb-3 rounded-xl border border-state-bad/25 bg-state-bad/8 px-4 py-3 text-[14.4px] text-state-bad">
      数据加载失败：{{ store.error }}。请确认后端已启动（127.0.0.1:8000）。
    </div>

    <div
      v-if="store.filteredCards.length"
      ref="container"
      class="grid gap-3"
      :class="store.viewMode === 'grid'
        ? 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4'
        : 'grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5'"
    >
      <div
        v-for="(card, index) in store.filteredCards"
        :key="card.id"
        :data-card-id="card.id"
        class="animate-fade-up"
        :style="{ animationDelay: `${Math.min(index * 40, 320)}ms` }"
      >
        <ServiceCard
          :card="card"
          :compact="store.viewMode === 'compact'"
          @open="emit('open', $event)"
          @action="(c, a) => emit('action', c, a)"
        />
      </div>
    </div>

    <div
      v-else-if="!store.loading"
      class="flex flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-white/[0.09] bg-white/[0.015] px-6 py-20 text-center"
    >
      <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.04] ring-1 ring-white/10">
        <LayoutGrid class="h-5 w-5 text-mist-500" />
      </div>
      <div>
        <p class="text-[16.8px] font-medium text-mist-100">没有匹配的服务卡片</p>
        <p class="mt-1 text-[14.4px] text-mist-500">调整筛选条件，或让 AI 根据一句描述为你生成一张卡片。</p>
      </div>
      <button type="button" class="btn-primary" @click="emit('create')">
        <Wand2 class="h-4 w-4" />
        用 AI 创建卡片
      </button>
    </div>

    <div v-else class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
      <div v-for="index in 4" :key="index" class="h-[186px] animate-pulse rounded-2xl border border-white/[0.05] bg-white/[0.02]" />
    </div>
  </div>
</template>
