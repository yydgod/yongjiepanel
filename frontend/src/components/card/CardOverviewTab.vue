<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Bot, Cpu, Gauge, MessageSquare, Settings2, Wand2, Waypoints } from 'lucide-vue-next'
import { cardsApi } from '../../api/cards'
import { errorMessage } from '../../api/client'
import type { Provider, ServiceCard } from '../../types'
import { formatMemory, formatPercent, formatUptime, relativeTime } from '../../utils/format'
import LogPanel from './LogPanel.vue'
import MetricsChart from './MetricsChart.vue'

const props = defineProps<{ card: ServiceCard; providers: Provider[] }>()

const emit = defineEmits<{
  (event: 'changed'): void
  (event: 'open-config'): void
  (event: 'open-chat'): void
}>()

const instruction = ref('')
const busy = ref(false)
const logPanel = ref<InstanceType<typeof LogPanel> | null>(null)

const showLogs = computed(() => ['container', 'systemd'].includes(props.card.card_type))
const agent = computed(() => props.card.agent)
const provider = computed(() =>
  props.providers.find((item) => item.id === agent.value?.provider_id) ?? null,
)
const tools = computed(() => props.card.available_tools ?? [])

async function applyCustomize(): Promise<void> {
  if (!instruction.value.trim()) return
  busy.value = true
  try {
    const patch = (await cardsApi.customize(props.card.id, instruction.value.trim())) as Record<string, unknown>
    await cardsApi.update(props.card.id, {
      title: patch.title,
      subtitle: patch.subtitle,
      group_name: patch.group_name,
      icon: patch.icon,
      accent: patch.accent,
      display_config: patch.display_config,
    })
    if (props.card.agent) {
      await cardsApi.updateAgent(props.card.id, {
        ...props.card.agent,
        system_prompt: patch.system_prompt,
        tools: patch.tools,
      })
    }
    instruction.value = ''
    ElMessage.success(String(patch.rationale ?? '已应用定制'))
    emit('changed')
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    busy.value = false
  }
}

defineExpose({ refreshLogs: () => logPanel.value?.load() })
</script>

<template>
  <div class="grid items-start gap-3 lg:grid-cols-3">
    <div class="space-y-3 lg:col-span-2">
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps flex items-center gap-1"><Cpu class="h-3 w-3" />CPU</div>
          <div class="stat-mono mt-1 text-[21.6px]">{{ formatPercent(card.status?.cpu_percent) }}</div>
        </div>
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps flex items-center gap-1"><Gauge class="h-3 w-3" />内存</div>
          <div class="stat-mono mt-1 text-[21.6px]">{{ formatMemory(card.status?.memory_mb) }}</div>
        </div>
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps">运行时长</div>
          <div class="stat-mono mt-1 text-[21.6px]">{{ formatUptime(card.status?.uptime_seconds) }}</div>
        </div>
        <div class="glass-panel-soft px-3 py-2.5">
          <div class="label-caps flex items-center gap-1"><Waypoints class="h-3 w-3" />端口</div>
          <div class="stat-mono mt-1 truncate text-[21.6px]">
            {{ card.status?.ports?.length ? card.status.ports.map((p) => `:${p}`).join(' ') : '—' }}
          </div>
        </div>
      </div>

      <div v-if="card.status?.error" class="rounded-xl border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.8px] text-state-bad">
        {{ card.status.error.code }} · {{ card.status.error.message }}
      </div>

      <section class="glass-panel p-4">
        <div class="mb-1 flex items-center justify-between">
          <span class="label-caps">资源趋势（近 15 分钟）</span>
          <span class="text-[12px] text-mist-500">{{ card.status?.detail }}</span>
        </div>
        <MetricsChart :points="card.history ?? []" height="220px" />
      </section>

      <section v-if="showLogs" class="glass-panel p-4">
        <LogPanel ref="logPanel" :card-id="card.id" :card-type="card.card_type" />
      </section>
    </div>

    <div class="space-y-3">
      <section class="glass-panel p-4">
        <div class="flex items-center gap-2">
          <Bot class="h-4 w-4 text-aurora-violet" />
          <h2 class="text-[15.6px] font-semibold text-mist-100">专属 Agent</h2>
          <span class="ml-auto rounded px-1.5 py-0.5 font-mono text-[10.2px] uppercase" :class="agent?.enabled === false ? 'bg-white/[0.05] text-mist-500' : 'bg-state-ok/12 text-state-ok'">
            {{ agent?.enabled === false ? 'off' : 'on' }}
          </span>
        </div>
        <div class="mt-2 space-y-1.5 text-[12.6px]">
          <div class="flex justify-between gap-3">
            <span class="text-mist-500">名称</span>
            <span class="truncate text-mist-100">{{ agent?.name || '未配置' }}</span>
          </div>
          <div class="flex justify-between gap-3">
            <span class="text-mist-500">供应商</span>
            <span class="truncate text-mist-100">{{ provider?.name || '默认供应商' }}</span>
          </div>
          <div class="flex justify-between gap-3">
            <span class="text-mist-500">模型</span>
            <span class="truncate font-mono text-[11.4px] text-mist-100">{{ agent?.model || '未指定' }}</span>
          </div>
          <div class="flex justify-between gap-3">
            <span class="text-mist-500">通道 / 工具</span>
            <span class="font-mono text-[11.4px] text-mist-100">
              {{ agent?.gateway || 'auto' }} · {{ agent?.tools?.length ?? 0 }}/{{ tools.length }}
            </span>
          </div>
        </div>
        <div class="mt-3 grid grid-cols-2 gap-2">
          <button type="button" class="btn-ghost justify-center" @click="emit('open-chat')">
            <MessageSquare class="h-3.5 w-3.5" />
            对话
          </button>
          <button type="button" class="btn-ghost justify-center" @click="emit('open-config')">
            <Settings2 class="h-3.5 w-3.5" />
            配置
          </button>
        </div>
      </section>

      <section class="glass-panel p-4">
        <div class="label-caps mb-2">卡片信息</div>
        <dl class="space-y-1.5 text-[12.6px]">
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">类型</dt>
            <dd class="font-mono text-mist-100">{{ card.card_type }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">目标对象</dt>
            <dd class="max-w-[62%] truncate font-mono text-mist-100" :title="card.target_ref">{{ card.target_ref }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">分组</dt>
            <dd class="truncate text-mist-100">{{ card.group_name }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">采集于</dt>
            <dd class="text-mist-100">{{ relativeTime(card.status?.collected_at) }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-mist-500">创建时间</dt>
            <dd class="text-mist-100">{{ relativeTime(card.created_at) }}</dd>
          </div>
        </dl>
      </section>

      <section class="glass-panel p-4">
        <div class="label-caps mb-2 flex items-center gap-1.5">
          <Wand2 class="h-3 w-3" />自然语言定制
        </div>
        <div class="flex gap-2">
          <input
            v-model="instruction"
            type="text"
            placeholder="例如：归类到核心链路，换成紫色，强调只读诊断"
            class="h-9 min-w-0 flex-1 rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[12.6px] text-mist-100 outline-none focus:border-aurora-violet/50"
            @keyup.enter="applyCustomize"
          />
          <button type="button" class="btn-primary h-9 shrink-0" :disabled="busy || !instruction.trim()" @click="applyCustomize">
            应用
          </button>
        </div>
      </section>
    </div>
  </div>
</template>
