<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, ChevronRight, ShieldAlert, Terminal } from 'lucide-vue-next'
import type { ToolCallEvent } from '../../types'

const props = defineProps<{ calls: ToolCallEvent[] }>()
const expanded = ref<Record<string, boolean>>({})

function toggle(id: string): void {
  expanded.value = { ...expanded.value, [id]: !expanded.value[id] }
}

const items = computed(() =>
  props.calls.map((call) => ({
    ...call,
    label: call.label ?? call.name,
    risk: call.risk ?? 'read',
    isError: call.ok === false,
  })),
)
</script>

<template>
  <div v-if="calls.length" class="space-y-1.5">
    <div
      v-for="call in items"
      :key="call.id"
      class="rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-1.5"
    >
      <button type="button" class="flex w-full cursor-pointer items-center gap-2 text-left" @click="toggle(call.id)">
        <ShieldAlert v-if="call.risk === 'destructive'" class="h-3 w-3 shrink-0 text-state-warn" />
        <Terminal v-else class="h-3 w-3 shrink-0 text-aurora-teal" />
        <span class="font-mono text-[12.6px] text-mist-300">{{ call.name }}</span>
        <span class="truncate text-[12.6px] text-mist-500">{{ call.summary }}</span>
        <span
          class="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10.8px]"
          :class="call.risk === 'destructive'
            ? 'bg-state-warn/12 text-state-warn'
            : 'bg-aurora-teal/10 text-aurora-teal'"
        >
          {{ call.risk === 'destructive' ? '需确认' : '只读' }}
        </span>
        <ChevronDown v-if="expanded[call.id]" class="h-3 w-3 shrink-0 text-mist-500" />
        <ChevronRight v-else class="h-3 w-3 shrink-0 text-mist-500" />
      </button>
      <div v-if="expanded[call.id]" class="mt-2 space-y-1.5 border-t border-white/[0.05] pt-2">
        <div v-if="call.args && Object.keys(call.args).length">
          <div class="label-caps mb-1">参数</div>
          <pre class="overflow-auto rounded bg-ink-950/60 p-2 font-mono text-[12px] text-mist-300">{{ JSON.stringify(call.args, null, 2) }}</pre>
        </div>
        <div v-if="call.data">
          <div class="label-caps mb-1">返回</div>
          <pre class="max-h-40 overflow-auto rounded bg-ink-950/60 p-2 font-mono text-[12px] text-mist-300">{{ JSON.stringify(call.data, null, 2) }}</pre>
        </div>
        <div v-if="call.isError" class="text-[12.6px] text-state-bad">{{ call.summary }}</div>
      </div>
    </div>
  </div>
</template>
