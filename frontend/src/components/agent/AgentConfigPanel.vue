<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Save, ShieldAlert, Terminal } from 'lucide-vue-next'
import { cardsApi } from '../../api/cards'
import { errorMessage } from '../../api/client'
import type { Provider, ServiceCard, ToolMeta } from '../../types'

const props = defineProps<{
  card: ServiceCard
  providers: Provider[]
  tools: ToolMeta[]
}>()

const emit = defineEmits<{ (event: 'saved'): void }>()

const saving = ref(false)

const form = reactive({
  name: '',
  provider_id: undefined as string | undefined,
  model: '',
  system_prompt: '',
  tools: [] as string[],
  temperature: 0.3,
  max_tokens: 1024,
  gateway: 'auto' as 'auto' | 'openclaw' | 'direct',
  enabled: true,
})

function hydrate(): void {
  const agent = props.card.agent
  form.name = agent?.name ?? '卡片助手'
  form.provider_id = agent?.provider_id ?? undefined
  form.model = agent?.model ?? ''
  form.system_prompt = agent?.system_prompt ?? ''
  form.tools = [...(agent?.tools ?? [])]
  form.temperature = agent?.temperature ?? 0.3
  form.max_tokens = agent?.max_tokens ?? 1024
  form.gateway = agent?.gateway ?? 'auto'
  form.enabled = agent?.enabled ?? true
}

watch(() => props.card.id, hydrate, { immediate: true })

const selectedProvider = computed(() => props.providers.find((item) => item.id === form.provider_id))
const modelOptions = computed(() => selectedProvider.value?.models ?? [])
const readyProviders = computed(() => props.providers.filter((item) => item.has_key && item.enabled))

function toggleTool(name: string): void {
  form.tools = form.tools.includes(name)
    ? form.tools.filter((item) => item !== name)
    : [...form.tools, name]
}

async function save(): Promise<void> {
  saving.value = true
  try {
    await cardsApi.updateAgent(props.card.id, {
      name: form.name,
      provider_id: form.provider_id ?? null,
      model: form.model,
      system_prompt: form.system_prompt,
      tools: form.tools,
      temperature: form.temperature,
      max_tokens: form.max_tokens,
      gateway: form.gateway,
      enabled: form.enabled,
    })
    ElMessage.success('Agent 配置已保存')
    emit('saved')
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label class="label-caps mb-1 block">Agent 名称</label>
        <input
          v-model="form.name"
          type="text"
          class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50"
        />
      </div>
      <div>
        <label class="label-caps mb-1 block">模型供应商</label>
        <el-select v-model="form.provider_id" placeholder="使用默认供应商" clearable class="w-full">
          <el-option
            v-for="provider in providers"
            :key="provider.id"
            :value="provider.id"
            :label="`${provider.name}${provider.has_key ? '' : '（未配置 Key）'}`"
          />
        </el-select>
      </div>
      <div>
        <label class="label-caps mb-1 block">模型</label>
        <el-select
          v-model="form.model"
          filterable
          allow-create
          default-first-option
          placeholder="选择或输入模型名"
          class="w-full"
        >
          <el-option v-for="model in modelOptions" :key="model" :value="model" :label="model" />
        </el-select>
      </div>
      <div>
        <label class="label-caps mb-1 block">推理通道</label>
        <div class="flex h-9 items-center gap-1 rounded-lg border border-white/[0.07] bg-white/[0.02] p-1">
          <button
            v-for="option in [
              { value: 'auto', label: '自动' },
              { value: 'openclaw', label: 'OpenClaw' },
              { value: 'direct', label: '直连' },
            ]"
            :key="option.value"
            type="button"
            class="h-7 flex-1 cursor-pointer rounded-md text-[13.2px] transition-colors"
            :class="form.gateway === option.value
              ? 'bg-white/[0.08] text-mist-100'
              : 'text-mist-500 hover:text-mist-300'"
            @click="form.gateway = option.value as typeof form.gateway"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
    </div>

    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label class="label-caps mb-1 flex items-center justify-between">
          <span>温度</span>
          <span class="font-mono text-mist-300">{{ form.temperature.toFixed(2) }}</span>
        </label>
        <el-slider v-model="form.temperature" :min="0" :max="1.5" :step="0.05" size="small" />
      </div>
      <div>
        <label class="label-caps mb-1 block">最大输出 tokens</label>
        <el-input-number v-model="form.max_tokens" :min="128" :max="8192" :step="128" class="w-full" />
      </div>
    </div>

    <div>
      <label class="label-caps mb-1 block">系统提示词</label>
      <textarea
        v-model="form.system_prompt"
        rows="5"
        placeholder="描述该卡片的职责、诊断偏好与安全约束…"
        class="w-full resize-y rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 py-2 font-sans text-[13.2px] leading-relaxed text-mist-200 outline-none focus:border-aurora-teal/50"
      />
    </div>

    <div>
      <div class="mb-1.5 flex items-center justify-between">
        <label class="label-caps">可用工具（白名单）</label>
        <span class="text-[12px] text-mist-500">破坏性工具执行前需二次确认</span>
      </div>
      <div class="grid gap-1.5 sm:grid-cols-2">
        <button
          v-for="tool in tools"
          :key="tool.name"
          type="button"
          class="flex cursor-pointer items-start gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors"
          :class="form.tools.includes(tool.name)
            ? 'border-aurora-teal/25 bg-aurora-teal/6'
            : 'border-white/[0.06] bg-white/[0.02] hover:border-white/12'"
          @click="toggleTool(tool.name)"
        >
          <ShieldAlert v-if="tool.risk === 'destructive'" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-state-warn" />
          <Terminal v-else class="mt-0.5 h-3.5 w-3.5 shrink-0 text-aurora-teal" />
          <span class="min-w-0">
            <span class="flex items-center gap-1.5">
              <span class="font-mono text-[13.2px] text-mist-200">{{ tool.name }}</span>
              <span
                class="rounded px-1 py-px text-[10.2px]"
                :class="tool.risk === 'destructive' ? 'bg-state-warn/12 text-state-warn' : 'bg-white/[0.06] text-mist-500'"
              >
                {{ tool.risk === 'destructive' ? '破坏性' : '只读' }}
              </span>
            </span>
            <span class="mt-0.5 block text-[12px] leading-snug text-mist-500">{{ tool.description }}</span>
          </span>
        </button>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3 border-t border-white/[0.06] pt-3">
      <div class="text-[12.6px] text-mist-500">
        可用供应商：{{ readyProviders.length }}/{{ providers.length }}
        <span class="mx-1 text-mist-500">·</span>
        未配置 Key 时自动回落演示通道
      </div>
      <button type="button" class="btn-primary" :disabled="saving" @click="save">
        <Save class="h-3.5 w-3.5" />
        {{ saving ? '保存中…' : '保存配置' }}
      </button>
    </div>
  </div>
</template>
