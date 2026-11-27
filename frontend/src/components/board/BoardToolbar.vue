<script setup lang="ts">
import { computed } from 'vue'
import { LayoutGrid, List, RefreshCw, Search, SlidersHorizontal, Wand2 } from 'lucide-vue-next'
import { useBoardStore } from '../../stores/board'

const emit = defineEmits<{
  (event: 'create'): void
}>()

const store = useBoardStore()

const groupChips = computed(() => [
  { name: '', label: '全部分组', count: store.cards.length },
  ...store.groups.map((group) => ({ name: group.name, label: group.name, count: group.count })),
])

const statusChips = [
  { value: '', label: '全部状态' },
  { value: 'running', label: '运行中' },
  { value: 'warning', label: '告警' },
  { value: 'stopped', label: '已停止' },
  { value: 'unavailable', label: '不可用' },
]
</script>

<template>
  <div class="space-y-3">
    <div class="flex flex-wrap items-center gap-3">
      <div class="group relative min-w-[220px] flex-1">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-mist-500" />
        <input
          v-model="store.filters.q"
          type="search"
          placeholder="搜索卡片名称、容器、端口或备注…"
          class="h-10 w-full rounded-xl border border-white/[0.07] bg-white/[0.03] pl-9 pr-3 text-[15.6px] text-mist-100 placeholder:text-mist-500 outline-none transition-colors focus:border-aurora-teal/50 focus:bg-white/[0.05]"
        />
      </div>

      <el-select
        v-model="store.filters.type"
        placeholder="全部类型"
        clearable
        class="w-[140px]"
        size="large"
      >
        <el-option label="全部类型" value="" />
        <el-option
          v-for="spec in store.meta.items"
          :key="spec.kind"
          :label="spec.label"
          :value="spec.kind"
        />
      </el-select>

      <div class="flex items-center gap-1 rounded-xl border border-white/[0.07] bg-white/[0.03] p-1">
        <button
          v-for="mode in (['grid', 'compact'] as const)"
          :key="mode"
          type="button"
          class="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg transition-colors"
          :class="store.viewMode === mode ? 'bg-white/[0.08] text-mist-100' : 'text-mist-500 hover:text-mist-300'"
          :title="mode === 'grid' ? '标准网格' : '紧凑视图'"
          @click="store.viewMode = mode"
        >
          <LayoutGrid v-if="mode === 'grid'" class="h-4 w-4" />
          <List v-else class="h-4 w-4" />
        </button>
      </div>

      <button type="button" class="btn-ghost h-10" title="立即刷新" @click="store.refresh()">
        <RefreshCw class="h-3.5 w-3.5" :class="store.loading ? 'animate-spin' : ''" />
        <span class="hidden sm:inline">刷新</span>
      </button>

      <button
        type="button"
        class="btn-primary h-10"
        title="在 dsh 中让 AI 创建工作区、启动服务并生成卡片"
        @click="emit('create')"
      >
        <Wand2 class="h-4 w-4" />
        AI 创建卡片
      </button>
    </div>

    <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div class="flex flex-wrap items-center gap-1.5">
        <button
          v-for="chip in groupChips"
          :key="chip.name || 'all'"
          type="button"
          class="cursor-pointer rounded-full border px-3 py-1 text-[13.8px] transition-all"
          :class="store.filters.group === chip.name
            ? 'border-aurora-teal/40 bg-aurora-teal/10 text-aurora-teal'
            : 'border-white/[0.07] bg-white/[0.02] text-mist-300 hover:border-white/15 hover:text-mist-100'"
          @click="store.filters.group = chip.name"
        >
          {{ chip.label }}
          <span class="ml-1 font-mono text-[12px] opacity-70">{{ chip.count }}</span>
        </button>
      </div>

      <div class="ml-auto flex items-center gap-1.5">
        <SlidersHorizontal class="h-3.5 w-3.5 text-mist-500" />
        <button
          v-for="chip in statusChips"
          :key="chip.value || 'all'"
          type="button"
          class="cursor-pointer rounded-md px-2 py-1 text-[13.8px] transition-colors"
          :class="store.filters.status === chip.value
            ? 'bg-white/[0.08] text-mist-100'
            : 'text-mist-500 hover:text-mist-300'"
          @click="store.filters.status = chip.value"
        >
          {{ chip.label }}
        </button>
      </div>
    </div>
  </div>
</template>
