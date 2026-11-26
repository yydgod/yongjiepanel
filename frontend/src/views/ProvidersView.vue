<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CheckCircle2,
  KeyRound,
  PlugZap,
  Plus,
  Radio,
  RefreshCw,
  ServerCog,
  Star,
  Trash2,
  TriangleAlert,
} from 'lucide-vue-next'
import { errorMessage } from '../api/client'
import { providersApi } from '../api/providers'
import { useBoardStore } from '../stores/board'
import type { OpenClawStatus, Provider, ProviderPreset } from '../types'
import ProviderForm from '../components/providers/ProviderForm.vue'

const board = useBoardStore()
const providers = ref<Provider[]>([])
const presets = ref<ProviderPreset[]>([])
const openclaw = ref<(OpenClawStatus & { healthy: boolean }) | null>(null)
const loading = ref(false)
const probing = ref(false)
const testingId = ref('')
const formOpen = ref(false)
const editing = ref<Provider | null>(null)
const initialKind = ref<string | null>(null)

const readyCount = computed(() => providers.value.filter((item) => item.has_key).length)

async function load(): Promise<void> {
  loading.value = true
  try {
    const [providerList, presetList, gateway] = await Promise.all([
      providersApi.list(),
      providersApi.presets(),
      providersApi.openclaw(),
    ])
    providers.value = providerList
    presets.value = presetList
    openclaw.value = gateway
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    loading.value = false
  }
}

async function probe(force = false): Promise<void> {
  probing.value = true
  try {
    openclaw.value = await providersApi.openclaw(force)
    await board.refreshSystem()
    ElMessage[openclaw.value.healthy ? 'success' : 'warning'](
      openclaw.value.healthy ? 'OpenClaw 网关健康' : `网关不可用，已启用降级：${openclaw.value.reason}`,
    )
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    probing.value = false
  }
}

async function test(provider: Provider): Promise<void> {
  testingId.value = provider.id
  try {
    const result = await providersApi.test(provider.id)
    ElMessage.success(`${result.message} · ${result.latency_ms}ms`)
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    testingId.value = ''
  }
}

async function toggle(provider: Provider): Promise<void> {
  try {
    await providersApi.update(provider.id, {
      name: provider.name,
      kind: provider.kind,
      base_url: provider.base_url,
      default_model: provider.default_model,
      models: provider.models,
      extra: provider.extra,
      temperature: provider.temperature,
      timeout: provider.timeout,
      is_default: provider.is_default,
      enabled: provider.enabled,
    })
    await load()
  } catch (err) {
    provider.enabled = !provider.enabled
    ElMessage.error(errorMessage(err))
  }
}

async function makeDefault(provider: Provider): Promise<void> {
  await providersApi.update(provider.id, {
    name: provider.name,
    kind: provider.kind,
    base_url: provider.base_url,
    default_model: provider.default_model,
    models: provider.models,
    extra: provider.extra,
    temperature: provider.temperature,
    timeout: provider.timeout,
    is_default: true,
    enabled: provider.enabled,
  })
  await load()
  ElMessage.success(`已将 ${provider.name} 设为默认供应商`)
}

async function remove(provider: Provider): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除供应商「${provider.name}」？引用它的 agent 会回落到默认供应商。`, '删除供应商', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await providersApi.remove(provider.id)
    ElMessage.success('已删除')
    await load()
  } catch (err) {
    ElMessage.error(errorMessage(err))
  }
}

function addProvider(preset?: ProviderPreset): void {
  editing.value = null
  initialKind.value = preset?.kind ?? null
  formOpen.value = true
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-[26.4px] font-semibold text-mist-100">模型与通道</h1>
        <p class="mt-1 text-[14.4px] text-mist-300">
          所有卡片 agent 统一经由 AI Gateway 调度：优先 OpenClaw 网关，不可用时自动降级直连供应商。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button type="button" class="btn-ghost" :disabled="probing" @click="probe(true)">
          <RefreshCw class="h-3.5 w-3.5" :class="probing ? 'animate-spin' : ''" />
          重新探测网关
        </button>
        <button type="button" class="btn-primary" @click="addProvider()">
          <Plus class="h-4 w-4" />
          新增供应商
        </button>
      </div>
    </header>

    <div class="grid gap-3 lg:grid-cols-[1.4fr_1fr]">
      <section class="glass-panel relative overflow-hidden p-4">
        <div class="absolute -right-16 -top-20 h-48 w-48 rounded-full bg-aurora-teal/10 blur-3xl" />
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-aurora-teal/25 to-aurora-blue/15 ring-1 ring-white/10">
              <ServerCog class="h-[18px] w-[18px] text-aurora-teal" />
            </div>
            <div>
              <div class="flex items-center gap-2">
                <h2 class="text-[16.8px] font-semibold text-mist-100">OpenClaw 能力网关</h2>
                <span
                  class="rounded-full px-2 py-0.5 text-[12px]"
                  :class="openclaw?.healthy
                    ? 'bg-state-ok/12 text-state-ok'
                    : openclaw?.configured
                      ? 'bg-state-warn/12 text-state-warn'
                      : 'bg-white/[0.05] text-mist-500'"
                >
                  {{ openclaw?.healthy ? 'ONLINE' : openclaw?.configured ? 'FALLBACK' : 'OFF' }}
                </span>
              </div>
              <p class="mt-0.5 font-mono text-[12.6px] text-mist-500">
                {{ openclaw?.base_url || '未配置 OPENCLAW_BASE_URL' }} · mode={{ openclaw?.mode }}
              </p>
            </div>
          </div>
          <button type="button" class="btn-ghost h-8" @click="probe(true)">探测</button>
        </div>
        <div class="mt-3 rounded-lg border border-white/[0.06] bg-ink-950/50 px-3 py-2 font-mono text-[12.6px] leading-relaxed text-mist-300">
          <div><span class="text-mist-500"># backend/.env</span></div>
          <div>OPENCLAW_BASE_URL=http://127.0.0.1:18789</div>
          <div>OPENCLAW_TOKEN=oc_xxx</div>
          <div>OPENCLAW_MODE=openai <span class="text-mist-500"># 或 channel</span></div>
        </div>
        <p class="mt-2 text-[12.6px] leading-relaxed text-mist-500">
          {{ openclaw?.healthy
            ? '网关健康：卡片 agent 的工具调用将透传 session / agent 元数据，由 OpenClaw 统一编排 skills。'
            : openclaw?.configured
              ? `网关异常（${openclaw?.reason}），请求已自动降级直连供应商，响应中的 channel 字段会标记 fallback。`
              : '未配置网关时系统直连供应商；未配置任何 Key 则使用离线演示通道，便于先体验交互。' }}
        </p>
      </section>

      <section class="glass-panel p-4">
        <div class="label-caps">供应商就绪度</div>
        <div class="mt-2 flex items-end gap-2">
          <span class="stat-mono text-[36px] font-semibold leading-none">{{ readyCount }}</span>
          <span class="pb-1 text-[13.2px] text-mist-500">/ {{ providers.length }} 家已配置 Key</span>
        </div>
        <div class="mt-3 space-y-1.5">
          <div
            v-for="provider in providers"
            :key="provider.id"
            class="flex items-center gap-2 text-[13.2px]"
          >
            <CheckCircle2 v-if="provider.has_key" class="h-3 w-3 text-state-ok" />
            <TriangleAlert v-else class="h-3 w-3 text-mist-500" />
            <span class="truncate text-mist-300">{{ provider.name }}</span>
            <span class="ml-auto font-mono text-[12px] text-mist-500">{{ provider.default_model }}</span>
          </div>
        </div>
      </section>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <span class="label-caps">快速添加</span>
      <button
        v-for="preset in presets"
        :key="preset.kind"
        type="button"
        class="btn-ghost h-8"
        @click="addProvider(preset)"
      >
        <Plus class="h-3 w-3" />{{ preset.label }}
      </button>
    </div>

    <div v-if="loading" class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      <div v-for="index in 3" :key="index" class="h-[168px] animate-pulse rounded-2xl border border-white/[0.05] bg-white/[0.02]" />
    </div>

    <div v-else class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="provider in providers"
        :key="provider.id"
        class="glass-panel group relative overflow-hidden p-4 transition-all hover:-translate-y-0.5 hover:border-white/[0.13]"
      >
        <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-aurora-teal/30 to-transparent" />
        <div class="flex items-start gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.05] font-mono text-[13.2px] uppercase text-aurora-teal ring-1 ring-white/10">
            {{ provider.kind.slice(0, 2) }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <h3 class="truncate text-[16.2px] font-semibold text-mist-100">{{ provider.name }}</h3>
              <Star v-if="provider.is_default" class="h-3 w-3 shrink-0 fill-state-warn text-state-warn" />
            </div>
            <p class="truncate font-mono text-[12px] text-mist-500">{{ provider.base_url }}</p>
          </div>
          <el-switch v-model="provider.enabled" size="small" @change="toggle(provider)" />
        </div>

        <div class="mt-3 flex flex-wrap items-center gap-1.5">
          <span class="rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[12px] text-mist-300">
            {{ provider.default_model }}
          </span>
          <span
            class="flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[12px]"
            :class="provider.has_key ? 'bg-state-ok/10 text-state-ok' : 'bg-white/[0.04] text-mist-500'"
          >
            <KeyRound class="h-2.5 w-2.5" />
            {{ provider.has_key ? provider.api_key_masked : '未配置 Key' }}
          </span>
        </div>

        <div class="mt-3 flex items-center gap-1 border-t border-white/[0.05] pt-2.5">
          <button
            type="button"
            class="btn-ghost h-7 px-2 text-[13.2px]"
            :disabled="testingId === provider.id || !provider.has_key"
            @click="test(provider)"
          >
            <PlugZap class="h-3 w-3" />
            {{ testingId === provider.id ? '测试中' : '测试' }}
          </button>
          <button type="button" class="btn-ghost h-7 px-2 text-[13.2px]" @click="editing = provider; formOpen = true">
            编辑
          </button>
          <button
            v-if="!provider.is_default"
            type="button"
            class="btn-ghost h-7 px-2 text-[13.2px]"
            @click="makeDefault(provider)"
          >
            设为默认
          </button>
          <button type="button" class="btn-ghost ml-auto h-7 px-2 text-state-bad" @click="remove(provider)">
            <Trash2 class="h-3 w-3" />
          </button>
        </div>
      </article>

      <button
        type="button"
        class="flex min-h-[168px] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-white/[0.09] bg-white/[0.015] text-mist-500 transition-colors hover:border-aurora-teal/30 hover:text-mist-300"
        @click="addProvider()"
      >
        <Plus class="h-5 w-5" />
        <span class="text-[14.4px]">接入新的 OpenAI 兼容端点</span>
        <span class="text-[12px]">DeepSeek / 混元 / Qwen / 自建 vLLM</span>
      </button>
    </div>

    <section class="glass-panel flex flex-wrap items-center gap-3 p-4 text-[13.2px] text-mist-500">
      <Radio class="h-3.5 w-3.5 text-aurora-teal" />
      <span>
        通道优先级：<span class="text-mist-300">OpenClaw（健康时）</span> →
        <span class="text-mist-300">直连供应商</span> →
        <span class="text-mist-300">离线演示通道</span>。降级会写入结构化日志，并可通过
        <code class="mx-1 rounded bg-white/[0.05] px-1 py-0.5 font-mono text-[12px]">/api/system/status</code>
        查看当前通道状态。
      </span>
    </section>

    <ProviderForm
      v-model="formOpen"
      :provider="editing"
      :presets="presets"
      :initial-kind="initialKind"
      @saved="load(); board.refreshSystem()"
    />
  </div>
</template>
