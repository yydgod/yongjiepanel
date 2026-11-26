<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Activity, Clock3, Play, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-vue-next'
import { cardsApi } from '../api/cards'
import { errorMessage } from '../api/client'
import { useBoardStore } from '../stores/board'
import { relativeTime } from '../utils/format'
import type { AuditEntry } from '../types'

const board = useBoardStore()
const audit = ref<AuditEntry[]>([])
const loadingAudit = ref(false)
const collecting = ref(false)

const scheduler = computed(() => board.system?.scheduler)
const openclaw = computed(() => board.system?.openclaw)

const tiles = computed(() => [
  {
    label: '运行中服务',
    value: board.stats.running,
    hint: `告警 ${board.stats.warning} · 不可用 ${board.stats.unavailable + board.stats.stopped + board.stats.unknown}`,
    ok: board.stats.warning === 0 && board.stats.unavailable + board.stats.stopped + board.stats.unknown === 0,
  },
  {
    label: '最近采集耗时',
    value: scheduler.value?.duration_ms ? `${scheduler.value.duration_ms} ms` : '—',
    hint: scheduler.value?.last_run ? relativeTime(scheduler.value.last_run) : '等待首轮采集',
    ok: (scheduler.value?.duration_ms ?? 0) < 8000,
  },
  {
    label: '已配置 Key',
    value: `${board.system?.ai.providers_ready ?? 0}/${board.system?.ai.providers_total ?? 0}`,
    hint: board.system?.ai.mock_enabled ? '演示通道已启用' : '无 Key 时不会降级到演示',
    ok: (board.system?.ai.providers_ready ?? 0) > 0,
  },
  {
    label: 'AI 网关',
    value: openclaw.value?.healthy ? 'OpenClaw' : openclaw.value?.configured ? 'FALLBACK' : 'DIRECT',
    hint: openclaw.value?.reason || openclaw.value?.base_url || '未配置网关地址',
    ok: Boolean(openclaw.value?.healthy),
  },
])

async function loadAudit(): Promise<void> {
  loadingAudit.value = true
  try {
    audit.value = (await cardsApi.audit(40)).items
  } catch (err) {
    console.error('审计日志加载失败', err)
  } finally {
    loadingAudit.value = false
  }
}

async function collectNow(): Promise<void> {
  collecting.value = true
  try {
    const result = await cardsApi.collect()
    ElMessage.success(`已采集 ${result.cards} 张卡片，耗时 ${result.duration_ms}ms`)
    await board.refresh()
    await board.refreshSystem()
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    collecting.value = false
  }
}

onMounted(async () => {
  await Promise.all([board.refreshSystem(), board.refresh(), loadAudit()])
})
</script>

<template>
  <div class="space-y-4">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-[26.4px] font-semibold text-mist-100">系统与审计</h1>
        <p class="mt-1 text-[14.4px] text-mist-300">
          调度耗时、服务运行状态与破坏性操作审计。单个服务读取失败只会降级为「不可用」，不会阻塞看板。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button type="button" class="btn-ghost" :disabled="collecting" @click="collectNow">
          <Play class="h-3.5 w-3.5" />
          立即采集
        </button>
        <button type="button" class="btn-ghost" @click="board.refreshSystem(); loadAudit()">
          <RefreshCw class="h-3.5 w-3.5" />
          刷新
        </button>
      </div>
    </header>

    <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div v-for="tile in tiles" :key="tile.label" class="glass-panel relative overflow-hidden p-4">
        <div
          class="absolute inset-x-0 top-0 h-px bg-gradient-to-r"
          :class="tile.ok ? 'from-state-ok/60 to-transparent' : 'from-state-warn/60 to-transparent'"
        />
        <div class="label-caps">{{ tile.label }}</div>
        <div class="stat-mono mt-1.5 text-[28.8px] font-semibold leading-none">{{ tile.value }}</div>
        <div class="mt-1.5 line-clamp-2 text-[12.6px] leading-snug text-mist-500">{{ tile.hint }}</div>
      </div>
    </div>

    <div class="grid gap-3 lg:grid-cols-[1.15fr_1fr]">
      <section class="glass-panel p-4">
        <div class="mb-3 flex items-center gap-2">
          <Clock3 class="h-4 w-4 text-aurora-teal" />
          <h2 class="text-[16.2px] font-semibold text-mist-100">调度信息</h2>
          <span class="ml-auto font-mono text-[12px] text-mist-500">
            interval={{ board.system?.interval ?? 5 }}s · tracked={{ scheduler?.tracked_cards ?? 0 }}
          </span>
        </div>

        <div class="rounded-xl border border-white/[0.05] bg-ink-950/40 p-3">
          <div class="label-caps mb-1.5 flex items-center gap-1"><Clock3 class="h-3 w-3" />调度信息</div>
          <div class="grid grid-cols-2 gap-2 text-[12.6px] text-mist-300">
            <div>last_run: {{ scheduler?.last_run ? relativeTime(scheduler.last_run) : '—' }}</div>
            <div>duration: {{ scheduler?.duration_ms ?? '—' }} ms</div>
            <div>history: 每卡 180 点环形缓冲</div>
            <div>storage: SQLite (WAL)</div>
          </div>
        </div>

        <div class="mt-3 grid grid-cols-3 gap-2">
          <div class="rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
            <div class="label-caps">运行中</div>
            <div class="stat-mono mt-1 text-[19.2px] text-state-ok">{{ board.stats.running }}</div>
          </div>
          <div class="rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
            <div class="label-caps">告警</div>
            <div class="stat-mono mt-1 text-[19.2px] text-state-warn">{{ board.stats.warning }}</div>
          </div>
          <div class="rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
            <div class="label-caps">不可用</div>
            <div class="stat-mono mt-1 text-[19.2px] text-state-bad">
              {{ board.stats.unavailable + board.stats.stopped + board.stats.unknown }}
            </div>
          </div>
        </div>

        <RouterLink
          to="/board"
          class="mt-3 flex items-center justify-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] py-2 text-[12.6px] text-mist-300 transition-colors hover:border-aurora-teal/30 hover:text-mist-100"
        >
          查看 {{ board.stats.total }} 张服务卡片
        </RouterLink>
      </section>

      <section class="glass-panel p-4">
        <div class="mb-3 flex items-center gap-2">
          <ShieldCheck class="h-4 w-4 text-aurora-violet" />
          <h2 class="text-[16.2px] font-semibold text-mist-100">通道与安全基线</h2>
        </div>
        <div class="space-y-2 text-[13.2px] leading-relaxed text-mist-300">
          <div class="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
            <Activity class="mt-0.5 h-3.5 w-3.5 shrink-0 text-aurora-teal" />
            <span>
              AI 通道：
              <span class="text-mist-100">{{ openclaw?.healthy ? 'openclaw' : openclaw?.configured ? 'openclaw→direct（降级）' : 'direct / mock' }}</span>
              ，降级原因：{{ openclaw?.reason || '无' }}
            </span>
          </div>
          <div class="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
            <ShieldCheck class="mt-0.5 h-3.5 w-3.5 shrink-0 text-state-ok" />
            <span>API Key 使用 Fernet 加密存储，接口仅返回掩码；破坏性工具需一次性确认令牌并写入审计。</span>
          </div>
          <div class="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 py-2">
            <TriangleAlert class="mt-0.5 h-3.5 w-3.5 shrink-0 text-state-warn" />
            <span>后端默认监听 127.0.0.1；如需暴露公网，请在 <code class="rounded bg-white/[0.05] px-1 font-mono text-[12px]">.env</code> 配置 ADMIN_TOKEN 并置于反向代理之后。</span>
          </div>
        </div>
        <div class="mt-3 rounded-xl border border-white/[0.06] bg-ink-950/50 p-3 font-mono text-[12px] leading-relaxed text-mist-500">
          <div># 运行参数</div>
          <div>COLLECT_INTERVAL=5</div>
          <div>DOCKER_ENABLED=true</div>
          <div>SYSTEMD_ENABLED=true</div>
          <div>PORT_ENABLED=true</div>
          <div>ALLOW_MOCK_AI=true</div>
        </div>
      </section>
    </div>

    <section class="glass-panel overflow-hidden">
      <div class="flex items-center gap-2 border-b border-white/[0.06] px-4 py-3">
        <ShieldCheck class="h-4 w-4 text-state-warn" />
        <h2 class="text-[16.2px] font-semibold text-mist-100">操作审计</h2>
        <span class="ml-auto text-[12.6px] text-mist-500">最近 40 条 · 破坏性操作与卡片变更</span>
        <button type="button" class="btn-ghost h-7 px-2" @click="loadAudit">
          <RefreshCw class="h-3 w-3" :class="loadingAudit ? 'animate-spin' : ''" />
        </button>
      </div>
      <div class="max-h-[360px] overflow-auto">
        <table class="w-full text-left text-[13.8px]">
          <thead class="sticky top-0 bg-ink-800/95 text-[12px] uppercase tracking-wider text-mist-500 backdrop-blur">
            <tr>
              <th class="w-[150px] whitespace-nowrap px-4 py-2 font-medium">时间</th>
              <th class="px-4 py-2 font-medium">动作</th>
              <th class="px-4 py-2 font-medium">目标</th>
              <th class="px-4 py-2 font-medium">结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in audit" :key="entry.id" class="border-t border-white/[0.04] hover:bg-white/[0.02]">
              <td class="w-[150px] whitespace-nowrap px-4 py-2 text-[12.6px] text-mist-500">{{ relativeTime(entry.created_at) }}</td>
              <td class="px-4 py-2">
                <span
                  class="rounded px-1.5 py-0.5 font-mono text-[12px]"
                  :class="entry.action.includes('tool.') || entry.action.includes('card.restart') || entry.action.includes('card.stop')
                    ? 'bg-state-warn/10 text-state-warn'
                    : 'bg-white/[0.05] text-mist-300'"
                >
                  {{ entry.action }}
                </span>
              </td>
              <td class="px-4 py-2 font-mono text-[12.6px] text-mist-300">
                {{ entry.target_type }}<span class="text-mist-500">/{{ entry.target_id ?? '—' }}</span>
              </td>
              <td class="px-4 py-2 text-[12.6px]" :class="entry.error ? 'text-state-bad' : 'text-state-ok'">
                {{ entry.error || 'success' }}
              </td>
            </tr>
            <tr v-if="!audit.length">
              <td colspan="4" class="px-4 py-8 text-center text-[13.8px] text-mist-500">
                暂无审计记录。执行一次重启或 agent 破坏性操作后会出现在这里。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
