<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bot, Loader2, MessagesSquare, Send, ShieldCheck, Sparkles, SquarePen } from 'lucide-vue-next'
import { chatApi, streamChat } from '../../api/chat'
import { errorMessage } from '../../api/client'
import type { ChatMessageView, PendingAction, ServiceCard, ToolCallEvent } from '../../types'
import ToolCallTimeline from './ToolCallTimeline.vue'

const props = defineProps<{ card: ServiceCard; active?: boolean }>()

const messages = ref<ChatMessageView[]>([])
const draft = ref('')
const streaming = ref(false)
const sessionId = ref<string | null>(null)
const channel = ref('direct')
const scroller = ref<HTMLElement | null>(null)
const loadedHistory = ref(false)
let controller: AbortController | null = null

const quickPrompts = computed(() => {
  const prompts = ['当前状态是否正常？', '帮我读取最近日志并分析异常']
  if (['container', 'systemd'].includes(props.card.card_type)) {
    prompts.push(`诊断 ${props.card.target_ref} 可能存在的问题`)
  }
  return prompts
})

function scrollToBottom(): void {
  void nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}

function pushAssistant(): ChatMessageView {
  const message: ChatMessageView = {
    id: `local-${crypto.randomUUID()}`,
    role: 'assistant',
    content: '',
    streaming: true,
    toolCalls: [],
    pending: [],
  }
  messages.value.push(message)
  return messages.value[messages.value.length - 1]
}

function applyEvent(event: Record<string, unknown>, assistant: ChatMessageView): void {
  switch (event.type) {
    case 'session':
      sessionId.value = String(event.session_id ?? '') || null
      break
    case 'route':
      channel.value = String(event.channel ?? 'direct')
      break
    case 'delta':
      assistant.content += String(event.text ?? '')
      scrollToBottom()
      break
    case 'tool_call': {
      assistant.toolCalls = assistant.toolCalls ?? []
      assistant.toolCalls.push({
        id: String(event.id ?? crypto.randomUUID()),
        name: String(event.name ?? ''),
        label: String(event.label ?? ''),
        risk: (event.risk as 'read' | 'destructive') ?? 'read',
        args: (event.args as Record<string, unknown>) ?? {},
        summary: '执行中…',
      })
      scrollToBottom()
      break
    }
    case 'tool_result': {
      const target = assistant.toolCalls?.find((call) => call.id === String(event.id))
      if (target) {
        target.ok = Boolean(event.ok)
        target.summary = String(event.summary ?? '')
        target.data = event.data
      }
      scrollToBottom()
      break
    }
    case 'pending': {
      assistant.pending = assistant.pending ?? []
      assistant.pending.push({
        token: String(event.token ?? ''),
        tool_name: String(event.tool_name ?? ''),
        label: String(event.label ?? ''),
        params: (event.params as Record<string, unknown>) ?? {},
        expires_at: String(event.expires_at ?? ''),
      })
      scrollToBottom()
      break
    }
    case 'done':
      assistant.streaming = false
      if (!assistant.content && event.content) assistant.content = String(event.content)
      if (Array.isArray(event.pending) && event.pending.length) {
        assistant.pending = (event.pending as PendingAction[]).map((item) => ({
          ...item,
          label: item.label ?? '',
        }))
      }
      break
    case 'error':
      assistant.streaming = false
      assistant.content += `\n\n⚠️ ${String(event.message ?? '对话失败')}`
      break
    default:
      break
  }
}

async function send(text?: string): Promise<void> {
  const content = (text ?? draft.value).trim()
  if (!content || streaming.value) return
  draft.value = ''
  messages.value.push({
    id: `user-${crypto.randomUUID()}`,
    role: 'user',
    content,
  })
  const assistant = pushAssistant()
  streaming.value = true
  controller = new AbortController()
  const onEvent = (event: Record<string, unknown>) => applyEvent(event, assistant)
  try {
    await streamChat(props.card.id, content, sessionId.value, {
      onEvent: onEvent as never,
      signal: controller.signal,
    })
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      assistant.content = assistant.content || `请求失败：${errorMessage(err)}`
      ElMessage.error(errorMessage(err))
    }
  } finally {
    streaming.value = false
    assistant.streaming = false
    controller = null
    scrollToBottom()
  }
}

function stop(): void {
  controller?.abort()
  streaming.value = false
}

async function confirmAction(action: PendingAction): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `即将执行 ${action.label || action.tool_name}，目标 ${props.card.target_ref}。该操作会被记入审计日志。`,
      '确认破坏性操作',
      { confirmButtonText: '确认执行', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    const result = await chatApi.confirm(action.token)
    ElMessage[result.ok ? 'success' : 'error'](result.message)
    messages.value.push({
      id: `tool-${crypto.randomUUID()}`,
      role: 'system',
      content: `已执行 ${result.tool_name}：${result.message}`,
    })
  } catch (err) {
    ElMessage.error(errorMessage(err))
  }
}

function resetSession(): void {
  messages.value = []
  sessionId.value = null
  loadedHistory.value = true
}

async function loadLatestSession(): Promise<void> {
  if (loadedHistory.value) return
  loadedHistory.value = true
  try {
    const sessions = await chatApi.sessions(props.card.id)
    if (!sessions.items.length) return
    const latest = sessions.items[0]
    const detail = await chatApi.session(latest.id)
    sessionId.value = latest.id
    channel.value = detail.channel
    messages.value = detail.messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map((message) => ({
        id: message.id,
        role: message.role as 'user' | 'assistant',
        content: message.content,
        channel: message.channel,
        toolCalls: (message.tool_calls ?? []).map((raw) => {
          const call = raw as { id?: string; function?: { name?: string } }
          return {
            id: call.id ?? crypto.randomUUID(),
            name: call.function?.name ?? 'tool',
            label: call.function?.name ?? 'tool',
            risk: 'read' as const,
            summary: '历史调用',
          }
        }),
      }))
    scrollToBottom()
  } catch (err) {
    console.error('历史会话加载失败', err)
  }
}

watch(
  () => props.active,
  (active) => {
    if (active) void loadLatestSession()
  },
)

onMounted(() => {
  if (props.active !== false) void loadLatestSession()
})
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="mb-2 flex items-center gap-2">
      <div class="flex items-center gap-2">
        <Bot class="h-3.5 w-3.5 text-aurora-violet" />
        <span class="text-[14.4px] font-medium text-mist-100">{{ card.agent?.name || '卡片 agent' }}</span>
        <span class="rounded border border-white/10 bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10.8px] uppercase text-mist-500">
          {{ channel }}
        </span>
        <span class="text-[11.4px] text-mist-500">{{ card.agent?.model || '未指定模型' }}</span>
      </div>
      <button type="button" class="ml-auto btn-ghost h-7 px-2" @click="resetSession">
        <SquarePen class="h-3 w-3" />
        新会话
      </button>
    </div>

    <div
      ref="scroller"
      class="min-h-[220px] flex-1 space-y-3 overflow-y-auto rounded-xl border border-white/[0.05] bg-ink-950/40 p-3"
    >
      <div v-if="!messages.length" class="flex h-full flex-col items-center justify-center gap-2 py-8 text-center">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-aurora-violet/25 to-aurora-teal/20 ring-1 ring-white/10">
          <Sparkles class="h-4 w-4 text-aurora-violet" />
        </div>
        <p class="text-[15px] text-mist-200">向这张卡片的专属 agent 提问</p>
        <p class="max-w-[280px] text-[13.2px] leading-relaxed text-mist-500">
          它会读取实时采集数据、调用只读工具定位问题；重启等破坏性操作需要你二次确认。
        </p>
      </div>

      <div
        v-for="message in messages"
        :key="message.id"
        class="flex"
        :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-[92%] rounded-2xl px-3 py-2 text-[14.4px] leading-relaxed"
          :class="message.role === 'user'
            ? 'rounded-br-md bg-gradient-to-br from-aurora-teal/18 to-aurora-blue/12 text-mist-100 ring-1 ring-aurora-teal/15'
            : message.role === 'system'
              ? 'rounded-bl-md border border-white/[0.06] bg-white/[0.02] text-mist-300'
              : 'rounded-bl-md border border-white/[0.06] bg-white/[0.03] text-mist-200'"
        >
          <div v-if="message.role === 'system'" class="flex items-center gap-1.5">
            <ShieldCheck class="h-3 w-3 text-state-ok" />
            <span>{{ message.content }}</span>
          </div>
          <template v-else>
            <div class="whitespace-pre-wrap">{{ message.content }}</div>
            <div v-if="message.streaming && !message.content" class="flex items-center gap-1.5 text-mist-500">
              <Loader2 class="h-3 w-3 animate-spin" />
              思考中…
            </div>
            <ToolCallTimeline v-if="message.toolCalls?.length" class="mt-2" :calls="message.toolCalls" />
            <div v-for="action in message.pending" :key="action.token" class="mt-2 rounded-lg border border-state-warn/25 bg-state-warn/8 p-2">
              <div class="flex items-center gap-1.5 text-[13.2px] text-state-warn">
                <ShieldCheck class="h-3 w-3" />
                待确认：{{ action.label || action.tool_name }}
              </div>
              <div class="mt-1 font-mono text-[12px] text-mist-500">
                {{ JSON.stringify(action.params) }}
              </div>
              <button type="button" class="btn-primary mt-2 h-7 px-2.5 text-[13.2px]" @click="confirmAction(action)">
                确认执行
              </button>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div class="mt-2 flex flex-wrap gap-1.5">
      <button
        v-for="prompt in quickPrompts"
        :key="prompt"
        type="button"
        class="cursor-pointer rounded-full border border-white/[0.07] bg-white/[0.02] px-2.5 py-1 text-[12.6px] text-mist-300 transition-colors hover:border-aurora-teal/30 hover:text-mist-100"
        @click="send(prompt)"
      >
        {{ prompt }}
      </button>
    </div>

    <div class="mt-2 flex items-end gap-2">
      <textarea
        v-model="draft"
        rows="2"
        placeholder="向 agent 提问，例如：内存占用为什么升高？"
        class="max-h-24 min-h-[46px] flex-1 resize-none rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2 text-[14.4px] text-mist-100 placeholder:text-mist-500 outline-none transition-colors focus:border-aurora-teal/50"
        @keydown.enter.exact.prevent="send()"
      />
      <button v-if="!streaming" type="button" class="btn-primary h-[46px] px-3" :disabled="!draft.trim()" @click="send()">
        <Send class="h-4 w-4" />
      </button>
      <button v-else type="button" class="btn-ghost h-[46px] px-3 text-state-warn" @click="stop">
        <Loader2 class="h-4 w-4 animate-spin" />
      </button>
    </div>
    <div class="mt-1 flex items-center gap-1 text-[12px] text-mist-500">
      <MessagesSquare class="h-3 w-3" />
      Enter 发送 · Shift+Enter 换行 · 破坏性操作需确认
    </div>
  </div>
</template>
