<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Bot,
  ExternalLink,
  History,
  Loader2,
  Plus,
  RefreshCw,
  SquareTerminal,
  Trash2,
  X,
} from 'lucide-vue-next'
import { terminalApi } from '../api/terminal'
import { cardsApi } from '../api/cards'
import { errorMessage } from '../api/client'
import { relativeTime } from '../utils/format'
import type { DshEntry, TerminalHistoryItem, TerminalSession } from '../types'

interface TerminalEntry {
  id: number
  command: string
  output: string
  exit_code: number
  cwd: string
  duration_ms: number
}

const sessions = ref<TerminalSession[]>([])
const activeId = ref('')
const outputs = reactive<Record<string, TerminalEntry[]>>({})
const runningIds = reactive<Record<string, boolean>>({})
const draft = ref('')
const cursor = ref(0)
const loading = ref(true)
const historyOpen = ref(false)
const historyItems = ref<TerminalHistoryItem[]>([])
const historyIndex = ref(-1)
const scrollEl = ref<HTMLElement | null>(null)
const terminalEl = ref<HTMLElement | null>(null)
const dsh = ref<DshEntry | null>(null)
const frameKey = ref(0)
let entrySeq = 0

const activeSession = computed(
  () => sessions.value.find((item) => item.id === activeId.value) ?? null,
)
const activeEntries = computed(() => (activeId.value ? outputs[activeId.value] ?? [] : []))
const activeRunning = computed(() => Boolean(runningIds[activeId.value]))

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const el = scrollEl.value
  if (el) el.scrollTop = el.scrollHeight
}

async function loadSessions(): Promise<void> {
  loading.value = true
  try {
    const result = await terminalApi.sessions()
    sessions.value = result.items
    if (!sessions.value.length) {
      await createSession(false)
    } else if (!sessions.value.some((item) => item.id === activeId.value)) {
      activeId.value = sessions.value[0].id
    }
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    loading.value = false
  }
  await scrollToBottom()
}

async function createSession(notify = true): Promise<void> {
  try {
    const title = `终端 ${sessions.value.length + 1}`
    const session = await terminalApi.createSession(title)
    sessions.value.push(session)
    outputs[session.id] = []
    activeId.value = session.id
    historyIndex.value = -1
    if (notify) ElMessage.success('已新建终端')
    await nextTick()
    focusTerminal()
  } catch (err) {
    ElMessage.error(errorMessage(err))
  }
}

async function closeSession(id: string): Promise<void> {
  try {
    await terminalApi.closeSession(id)
  } catch (err) {
    ElMessage.error(errorMessage(err))
    return
  }
  sessions.value = sessions.value.filter((item) => item.id !== id)
  delete outputs[id]
  delete runningIds[id]
  if (activeId.value === id) activeId.value = sessions.value[0]?.id ?? ''
  if (!sessions.value.length) await createSession(false)
}

function focusTerminal(): void {
  terminalEl.value?.focus()
}

function promptFor(cwd: string | null | undefined): string {
  return `${cwd || '/'} $ `
}

function insertText(text: string): void {
  if (!text) return
  const value = draft.value
  draft.value = value.slice(0, cursor.value) + text + value.slice(cursor.value)
  cursor.value += text.length
  historyIndex.value = -1
}

function onPaste(event: ClipboardEvent): void {
  const text = event.clipboardData?.getData('text') ?? ''
  insertText(text.replace(/[\r\n]+/g, ' '))
}

function onTerminalKeydown(event: KeyboardEvent): void {
  if (event.ctrlKey && event.key.toLowerCase() === 'l') {
    event.preventDefault()
    clearOutput()
    return
  }
  if (event.ctrlKey && event.key.toLowerCase() === 'c') {
    event.preventDefault()
    draft.value = ''
    cursor.value = 0
    return
  }
  if (event.ctrlKey && event.key.toLowerCase() === 'v') return
  if (activeRunning.value && !event.ctrlKey) return

  const value = draft.value
  switch (event.key) {
    case 'Enter':
      event.preventDefault()
      void run()
      return
    case 'Backspace':
      event.preventDefault()
      if (cursor.value > 0) {
        draft.value = value.slice(0, cursor.value - 1) + value.slice(cursor.value)
        cursor.value -= 1
        historyIndex.value = -1
      }
      return
    case 'Delete':
      event.preventDefault()
      if (cursor.value < value.length) {
        draft.value = value.slice(0, cursor.value) + value.slice(cursor.value + 1)
      }
      return
    case 'ArrowLeft':
      event.preventDefault()
      cursor.value = Math.max(0, cursor.value - 1)
      return
    case 'ArrowRight':
      event.preventDefault()
      cursor.value = Math.min(value.length, cursor.value + 1)
      return
    case 'Home':
      event.preventDefault()
      cursor.value = 0
      return
    case 'End':
      event.preventDefault()
      cursor.value = value.length
      return
    case 'ArrowUp':
      event.preventDefault()
      navigateHistory(-1)
      return
    case 'ArrowDown':
      event.preventDefault()
      navigateHistory(1)
      return
    case 'Tab':
      event.preventDefault()
      return
    default:
      break
  }
  if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault()
    insertText(event.key)
  }
}

async function run(): Promise<void> {
  const session = activeSession.value
  const text = draft.value.trim()
  if (!session || !text || runningIds[session.id]) return

  const target = session.id
  const entry: TerminalEntry = {
    id: ++entrySeq,
    command: text,
    output: '',
    exit_code: 0,
    cwd: session.cwd,
    duration_ms: 0,
  }
  if (!outputs[target]) outputs[target] = []
  outputs[target].push(entry)
  draft.value = ''
  cursor.value = 0
  historyIndex.value = -1
  runningIds[target] = true
  await scrollToBottom()

  try {
    const result = await terminalApi.exec(target, text)
    entry.output = result.output
    entry.exit_code = result.exit_code
    entry.cwd = result.cwd
    entry.duration_ms = result.duration_ms
    const current = sessions.value.find((item) => item.id === target)
    if (current) current.cwd = result.cwd
    rememberCommand(text, target, result.cwd, result.exit_code)
  } catch (err) {
    entry.output = errorMessage(err)
    entry.exit_code = -1
    rememberCommand(text, target, session.cwd, -1)
  } finally {
    delete runningIds[target]
    await scrollToBottom()
  }
}

function rememberCommand(
  text: string,
  sessionId: string,
  cwd: string,
  exitCode: number,
): void {
  if (historyItems.value[0]?.command === text) return
  historyItems.value.unshift({
    command: text,
    session_id: sessionId,
    cwd,
    exit_code: exitCode,
    created_at: new Date().toISOString(),
  })
  if (historyItems.value.length > 200) historyItems.value.pop()
}

function navigateHistory(direction: -1 | 1): void {
  const commands = historyItems.value.map((item) => item.command)
  if (!commands.length) return
  if (direction === -1) {
    if (historyIndex.value < commands.length - 1) historyIndex.value += 1
    draft.value = commands[historyIndex.value] ?? ''
  } else if (historyIndex.value > 0) {
    historyIndex.value -= 1
    draft.value = commands[historyIndex.value] ?? ''
  } else {
    historyIndex.value = -1
    draft.value = ''
  }
  cursor.value = draft.value.length
}

function clearOutput(): void {
  if (!activeId.value) return
  outputs[activeId.value] = []
  ElMessage.success('已清屏')
}

async function loadHistory(): Promise<void> {
  try {
    historyItems.value = (await terminalApi.history(200)).items
  } catch {
    // 历史读取失败不影响终端使用
  }
}

function useHistory(item: TerminalHistoryItem): void {
  draft.value = item.command
  cursor.value = item.command.length
  historyOpen.value = false
  void nextTick(() => focusTerminal())
}

async function clearHistory(): Promise<void> {
  try {
    await ElMessageBox.confirm('清空服务器保存的命令历史？该操作不可恢复。', '清空历史', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await terminalApi.clearHistory()
    historyItems.value = []
    ElMessage.success('历史已清空')
  } catch (err) {
    ElMessage.error(errorMessage(err))
  }
}

async function loadDsh(): Promise<void> {
  try {
    dsh.value = await cardsApi.dshEntry()
  } catch {
    dsh.value = { configured: false, reason: 'dsh 未就绪' }
  }
}

function reloadDsh(): void {
  frameKey.value += 1
}

onMounted(() => {
  document.title = '终端 · 永杰面板'
  void Promise.all([loadSessions(), loadHistory(), loadDsh()])
})

onBeforeUnmount(() => {
  document.title = '永杰面板 · 服务器管理看板'
})
</script>

<template>
  <div class="space-y-4">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-[26.4px] font-semibold tracking-tight text-mist-100">终端</h1>
          <span class="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 font-mono text-[12px] text-mist-500">
            TERMINAL
          </span>
        </div>
        <p class="mt-1 max-w-2xl text-[13.2px] leading-relaxed text-mist-500">
          点击终端区域后直接输入，Enter 执行，↑/↓ 翻历史，Ctrl+L 清屏；vim/top 等交互式命令请使用右侧 dsh 终端。
        </p>
      </div>
      <div class="text-[13.2px] text-mist-500">最多 8 个终端 · 非交互式命令</div>
    </header>

    <div class="grid items-start gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(380px,42%)]">
      <section class="flex h-[calc(100vh-230px)] min-h-[520px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-[#ffffff] shadow-glass">
        <div class="flex items-center gap-1 overflow-x-auto border-b border-slate-200 bg-slate-50 px-2 py-1.5">
          <button
            v-for="(session, index) in sessions"
            :key="session.id"
            type="button"
            class="group flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13.5px] transition-colors"
            :class="session.id === activeId
              ? 'bg-slate-200 text-slate-900'
              : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'"
            @click="activeId = session.id"
          >
            <SquareTerminal
              class="h-4 w-4"
              :class="session.id === activeId ? 'text-teal-600' : ''"
            />
            <span class="max-w-[120px] truncate">终端 {{ index + 1 }}</span>
            <span class="max-w-[110px] truncate font-mono text-[11.5px] text-slate-400">{{ session.cwd }}</span>
            <X
              class="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity hover:text-red-600 group-hover:opacity-100"
              @click.stop="closeSession(session.id)"
            />
          </button>
          <button
            type="button"
            class="ml-1 flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
            title="新建终端"
            @click="createSession()"
          >
            <Plus class="h-4 w-4" />
          </button>
          <Loader2 v-if="loading" class="ml-auto h-4 w-4 shrink-0 animate-spin text-slate-400" />
        </div>

        <div
          ref="scrollEl"
          tabindex="0"
          class="min-h-0 flex-1 cursor-text overflow-auto px-4 py-3 font-mono text-[15px] leading-[1.75] text-slate-700 outline-none selection:bg-teal-200"
          @keydown="onTerminalKeydown"
          @paste.prevent="onPaste"
          @click="focusTerminal"
        >
          <div v-for="entry in activeEntries" :key="entry.id">
            <div class="whitespace-pre-wrap break-all">
              <span class="text-teal-700">{{ promptFor(entry.cwd) }}</span>
              <span class="text-slate-900">{{ entry.command }}</span>
              <span
                v-if="entry.exit_code !== 0"
                class="ml-2 rounded bg-red-50 px-1.5 py-0.5 text-[11px] text-red-600"
              >
                exit {{ entry.exit_code }}
              </span>
            </div>
            <pre
              v-if="entry.output"
              class="whitespace-pre-wrap break-all"
              :class="entry.exit_code !== 0 ? 'text-red-600' : 'text-slate-700'"
            >{{ entry.output }}</pre>
          </div>

          <div v-if="activeSession" class="whitespace-pre-wrap break-all">
            <span class="text-teal-700">{{ promptFor(activeSession.cwd) }}</span>
            <span class="text-slate-900">{{ draft.slice(0, cursor) }}</span><span
              class="inline-block h-[1.05em] w-[0.55em] translate-y-[0.18em] bg-slate-900 animate-pulse"
            /><span class="text-slate-900">{{ draft.slice(cursor) }}</span>
            <span v-if="activeRunning" class="ml-2 text-[11.5px] text-slate-400">执行中…</span>
          </div>
          <p v-else class="font-sans text-slate-400">未选择终端</p>
        </div>

        <div class="flex flex-wrap items-center gap-2 border-t border-slate-200 bg-slate-50 px-3 py-1.5 text-[12.5px] text-slate-500">
          <SquareTerminal class="h-3.5 w-3.5 text-teal-600" />
          <span class="truncate font-mono">{{ activeSession?.cwd || '—' }}</span>
          <div class="ml-auto flex items-center gap-1">
            <button
              type="button"
              class="flex h-7 cursor-pointer items-center gap-1 rounded-lg px-2 text-[12.5px] text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
              @click="historyOpen = true"
            >
              <History class="h-3.5 w-3.5" />
              历史
            </button>
            <button
              type="button"
              class="flex h-7 cursor-pointer items-center rounded-lg px-2 text-[12.5px] text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
              @click="clearOutput"
            >
              清屏
            </button>
            <button
              type="button"
              class="flex h-7 cursor-pointer items-center rounded-lg px-2 text-[12.5px] text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="!activeSession"
              @click="activeId && closeSession(activeId)"
            >
              关闭
            </button>
          </div>
        </div>
      </section>

      <section class="glass-panel flex h-[calc(100vh-230px)] min-h-[520px] flex-col overflow-hidden">
        <div class="flex items-center gap-2 border-b border-white/[0.06] px-3 py-2">
          <Bot class="h-4 w-4 text-aurora-violet" />
          <span class="text-[13.8px] font-medium text-mist-100">dsh · AI 辅助</span>
          <div class="ml-auto flex items-center gap-1.5">
            <button type="button" class="btn-ghost h-7 px-2 text-[11.4px]" title="刷新 dsh" @click="reloadDsh">
              <RefreshCw class="h-3 w-3" />
              刷新
            </button>
            <a
              v-if="dsh?.configured && dsh.url"
              :href="dsh.url"
              target="_blank"
              rel="noreferrer"
              class="btn-ghost h-7 px-2 text-[11.4px]"
            >
              <ExternalLink class="h-3 w-3" />
              新窗口
            </a>
          </div>
        </div>

        <iframe
          v-if="dsh?.configured && dsh.url"
          :key="frameKey"
          :src="dsh.url"
          title="dsh AI 辅助"
          class="min-h-0 w-full flex-1 border-0 bg-[#ffffff]"
          allow="clipboard-read; clipboard-write"
        />
        <div v-else class="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
          <p class="text-[15px] text-mist-100">dsh 尚未就绪</p>
          <p class="text-[12.6px] text-mist-500">{{ dsh?.reason || '请先完成 dsh 部署' }}</p>
          <RouterLink to="/dsh" class="btn-ghost mt-1 inline-flex">前往 dsh 工作区</RouterLink>
        </div>
      </section>
    </div>

    <el-drawer v-model="historyOpen" title="命令历史" size="min(560px, 92vw)" direction="rtl" destroy-on-close>
      <div v-if="historyItems.length" class="space-y-1">
        <button
          v-for="(item, index) in historyItems"
          :key="`${item.created_at}-${index}`"
          type="button"
          class="flex w-full cursor-pointer flex-col gap-0.5 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-white/[0.05]"
          @click="useHistory(item)"
        >
          <span class="break-all font-mono text-[12.6px] text-mist-100">{{ item.command }}</span>
          <span class="font-mono text-[10.8px] text-mist-500">
            {{ item.cwd }} · exit {{ item.exit_code }} · {{ relativeTime(item.created_at) }}
          </span>
        </button>
      </div>
      <p v-else class="text-[13.2px] text-mist-500">还没有命令历史。</p>
      <div class="mt-4 flex justify-end gap-2">
        <button
          type="button"
          class="btn-ghost text-state-bad"
          :disabled="!historyItems.length"
          @click="clearHistory"
        >
          <Trash2 class="h-3.5 w-3.5" />
          清空历史
        </button>
        <button type="button" class="btn-ghost" @click="historyOpen = false">关闭</button>
      </div>
    </el-drawer>
  </div>
</template>
