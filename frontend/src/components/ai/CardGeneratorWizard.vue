<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Check, Loader2, Sparkles, Wand2 } from 'lucide-vue-next'
import { cardsApi } from '../../api/cards'
import { errorMessage } from '../../api/client'
import { generatorApi } from '../../api/providers'
import { useBoardStore } from '../../stores/board'
import { ACCENT_CHOICES, ICON_CHOICES, cardIcon } from '../../utils/icons'
import type { CardDraft, Provider } from '../../types'

const props = defineProps<{
  modelValue: boolean
  providers: Provider[]
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created'): void
}>()

const store = useBoardStore()
const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const step = ref(0)
const description = ref('')
const providerId = ref<string | undefined>(undefined)
const generating = ref(false)
const creating = ref(false)
const channel = ref('')
const warnings = ref<string[]>([])
const error = ref('')

const draft = reactive<CardDraft>({
  title: '',
  subtitle: '',
  card_type: 'container',
  target_ref: '',
  group_name: 'AI 生成',
  icon: 'sparkles',
  accent: 'teal',
  display_config: {},
  system_prompt: '',
  tools: [],
  model_hint: null,
  rationale: '',
  channel: 'mock',
})

const examples = [
  '监控名为 redis-cache 的 Docker 容器，关注内存与 6379 端口',
  '盯住 nginx.service 这个 systemd 服务，异常时读取日志定位',
  '监控 5432 端口上的 PostgreSQL，关注连接进程内存',
]

const PreviewIcon = computed(() => cardIcon(draft.icon))
const typeLabel = computed(() => store.meta.items.find((item) => item.kind === draft.card_type)?.label ?? draft.card_type)
const typeTools = computed(() => store.meta.tools.filter((tool) => {
  const spec = store.meta.items.find((item) => item.kind === draft.card_type)
  return spec?.tools.includes(tool.name)
}))

watch(() => props.modelValue, (open) => {
  if (open) {
    void store.loadMeta()
    error.value = ''
    if (!description.value) step.value = 0
  }
})

function fill(next: CardDraft): void {
  Object.assign(draft, next)
  warnings.value = Array.isArray((next as CardDraft).channel) ? [] : warnings.value
}

async function generate(): Promise<void> {
  if (description.value.trim().length < 4) {
    error.value = '请用一句完整的话描述要监控的服务'
    return
  }
  generating.value = true
  error.value = ''
  try {
    const response = await generatorApi.generate(description.value.trim(), providerId.value ?? null)
    fill(response.draft as unknown as CardDraft)
    channel.value = response.channel
    warnings.value = response.warnings ?? []
    step.value = 1
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    generating.value = false
  }
}

function toggleTool(name: string): void {
  draft.tools = draft.tools.includes(name)
    ? draft.tools.filter((item) => item !== name)
    : [...draft.tools, name]
}

async function create(): Promise<void> {
  if (!draft.title.trim() || !draft.target_ref.trim()) {
    error.value = '卡片标题与目标对象不能为空，请补全后再创建'
    return
  }
  creating.value = true
  error.value = ''
  try {
    await cardsApi.create({
      title: draft.title.trim(),
      subtitle: draft.subtitle || null,
      card_type: draft.card_type,
      target_ref: draft.target_ref.trim(),
      group_name: draft.group_name || 'AI 生成',
      icon: draft.icon,
      accent: draft.accent,
      display_config: draft.display_config,
      agent: {
        name: `${draft.title.trim()} 助手`,
        provider_id: providerId.value ?? null,
        model: draft.model_hint ?? '',
        system_prompt: draft.system_prompt,
        tools: draft.tools,
        gateway: 'auto',
      },
    })
    ElMessage.success('AI 卡片已创建并加入看板')
    await store.refresh()
    step.value = 2
    emit('created')
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    creating.value = false
  }
}

function restart(): void {
  step.value = 0
  error.value = ''
}
</script>

<template>
  <el-dialog v-model="visible" width="min(880px, 94vw)" :show-close="true" class="ai-wizard" destroy-on-close>
    <template #header>
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-aurora-violet/30 to-aurora-teal/20 ring-1 ring-white/10">
          <Wand2 class="h-4 w-4 text-aurora-violet" />
        </div>
        <div>
          <div class="text-[16.8px] font-semibold text-mist-100">AI 生成服务卡片</div>
          <div class="text-[12.6px] text-mist-500">描述需求 → 预览并微调 → 一键加入看板</div>
        </div>
      </div>
    </template>

    <div class="mb-5 flex items-center gap-2">
      <div
        v-for="(label, index) in ['描述需求', '预览与微调', '创建完成']"
        :key="label"
        class="flex flex-1 items-center gap-2"
      >
        <div
          class="flex h-6 w-6 items-center justify-center rounded-full border text-[12px] font-mono"
          :class="index < step
            ? 'border-state-ok/40 bg-state-ok/15 text-state-ok'
            : index === step
              ? 'border-aurora-teal/50 bg-aurora-teal/12 text-aurora-teal'
              : 'border-white/10 text-mist-500'"
        >
          <Check v-if="index < step" class="h-3 w-3" />
          <span v-else>{{ index + 1 }}</span>
        </div>
        <span class="text-[13.8px]" :class="index === step ? 'text-mist-100' : 'text-mist-500'">{{ label }}</span>
        <div v-if="index < 2" class="h-px flex-1 bg-white/[0.07]" />
      </div>
    </div>

    <div v-if="step === 0" class="space-y-3">
      <textarea
        v-model="description"
        rows="4"
        placeholder="用自然语言描述你想监控什么，例如：帮我盯住 redis-cache 这个容器，重点是内存占用和 6379 端口"
        class="w-full resize-none rounded-xl border border-white/10 bg-white/[0.05] px-3.5 py-3 text-[15px] leading-relaxed text-mist-100 placeholder:text-mist-500 outline-none transition-colors focus:border-aurora-teal/50 focus:bg-white/[0.07]"
      />
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="example in examples"
          :key="example"
          type="button"
          class="cursor-pointer rounded-full border border-white/[0.07] bg-white/[0.02] px-2.5 py-1 text-[12.6px] text-mist-300 transition-colors hover:border-aurora-violet/30 hover:text-mist-100"
          @click="description = example"
        >
          {{ example }}
        </button>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="label-caps">生成通道</span>
        <el-select v-model="providerId" placeholder="默认供应商 / OpenClaw" clearable size="small" class="w-[220px]">
          <el-option v-for="provider in providers" :key="provider.id" :value="provider.id" :label="provider.name" />
        </el-select>
        <span class="text-[12px] text-mist-500">未配置 Key 时后端会给出关键词草稿，仍可手动调整</span>
      </div>
      <div v-if="error" class="rounded-lg border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.8px] text-state-bad">{{ error }}</div>
      <div class="flex justify-end">
        <button type="button" class="btn-primary h-10 px-4" :disabled="generating" @click="generate">
          <Loader2 v-if="generating" class="h-4 w-4 animate-spin" />
          <Sparkles v-else class="h-4 w-4" />
          {{ generating ? '正在生成卡片…' : '生成卡片草稿' }}
        </button>
      </div>
    </div>

    <div v-else-if="step === 1" class="grid gap-4 md:grid-cols-[300px_1fr]">
      <div class="space-y-3">
        <div class="label-caps">卡片预览</div>
        <div class="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-ink-800/70 p-4 shadow-glass">
          <div class="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full bg-gradient-to-br from-aurora-violet/40 to-aurora-teal/20 opacity-40 blur-2xl" />
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-white/15 to-white/[0.04] ring-1 ring-white/10">
              <component :is="PreviewIcon" class="h-[18px] w-[18px] text-aurora-teal" />
            </div>
            <div class="min-w-0">
              <div class="truncate text-[15.6px] font-semibold text-mist-100">{{ draft.title || '未命名卡片' }}</div>
              <div class="truncate text-[12px] text-mist-500">{{ draft.target_ref || '待填写目标' }}</div>
            </div>
          </div>
          <div class="mt-3 flex items-center gap-2 text-[12px] text-mist-500">
            <span class="rounded border border-white/10 px-1.5 py-0.5">{{ typeLabel }}</span>
            <span class="rounded border border-aurora-teal/25 bg-aurora-teal/8 px-1.5 py-0.5 text-aurora-teal">{{ draft.group_name }}</span>
          </div>
          <div class="mt-3 flex items-center gap-1.5 text-[12px] text-mist-500">
            <span class="h-1.5 w-1.5 rounded-full bg-state-ok animate-breathe" />
            创建后 5 秒内会自动回填真实状态
          </div>
        </div>

        <div class="rounded-xl border border-white/[0.06] bg-white/[0.02] p-2.5 text-[12.6px] leading-relaxed text-mist-500">
          <div class="mb-1 flex items-center gap-1 text-mist-300">
            <Sparkles class="h-3 w-3 text-aurora-violet" />
            生成依据（{{ channel }} 通道）
          </div>
          {{ draft.rationale || '模型未提供说明' }}
        </div>
        <div v-if="warnings.length" class="space-y-1">
          <div v-for="warning in warnings" :key="warning" class="rounded-lg border border-state-warn/25 bg-state-warn/8 px-2.5 py-1.5 text-[12.6px] text-state-warn">
            {{ warning }}
          </div>
        </div>
      </div>

      <div class="space-y-3">
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="label-caps mb-1 block">标题</label>
            <input v-model="draft.title" class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50" />
          </div>
          <div>
            <label class="label-caps mb-1 block">目标对象</label>
            <input v-model="draft.target_ref" class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 font-mono text-[13.8px] text-mist-100 outline-none focus:border-aurora-teal/50" />
          </div>
          <div>
            <label class="label-caps mb-1 block">卡片类型</label>
            <el-select v-model="draft.card_type" class="w-full">
              <el-option v-for="item in store.meta.items" :key="item.kind" :value="item.kind" :label="item.label" />
            </el-select>
          </div>
          <div>
            <label class="label-caps mb-1 block">分组</label>
            <input v-model="draft.group_name" class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50" />
          </div>
        </div>

        <div class="flex items-center gap-3">
          <div>
            <label class="label-caps mb-1 block">图标</label>
            <el-select v-model="draft.icon" size="small" class="w-[120px]">
              <el-option v-for="icon in ICON_CHOICES" :key="icon.value" :value="icon.value" :label="icon.label" />
            </el-select>
          </div>
          <div>
            <label class="label-caps mb-1 block">配色</label>
            <div class="flex h-8 items-center gap-1.5">
              <button
                v-for="accent in ACCENT_CHOICES"
                :key="accent.value"
                type="button"
                class="h-5 w-5 cursor-pointer rounded-full bg-gradient-to-br ring-2 transition-all"
                :class="[accent.className, draft.accent === accent.value ? 'ring-white/70' : 'ring-transparent hover:ring-white/25']"
                @click="draft.accent = accent.value"
              />
            </div>
          </div>
        </div>

        <div>
          <label class="label-caps mb-1 block">Agent 系统提示词</label>
          <textarea
            v-model="draft.system_prompt"
            rows="4"
            class="w-full resize-y rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 py-2 font-sans text-[12.6px] leading-relaxed text-mist-200 outline-none focus:border-aurora-violet/50"
          />
        </div>

        <div>
          <label class="label-caps mb-1.5 block">Agent 工具白名单</label>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="tool in typeTools"
              :key="tool.name"
              type="button"
              class="cursor-pointer rounded-md border px-2 py-1 font-mono text-[12px] transition-colors"
              :class="draft.tools.includes(tool.name)
                ? 'border-aurora-teal/35 bg-aurora-teal/10 text-aurora-teal'
                : 'border-white/[0.07] text-mist-500 hover:text-mist-300'"
              @click="toggleTool(tool.name)"
            >
              {{ tool.name }}
              <span v-if="tool.risk === 'destructive'" class="ml-0.5 text-state-warn">!</span>
            </button>
          </div>
        </div>

        <div v-if="error" class="rounded-lg border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.8px] text-state-bad">{{ error }}</div>

        <div class="flex items-center justify-between gap-2 border-t border-white/[0.06] pt-3">
          <button type="button" class="btn-ghost h-9" @click="restart">
            <ArrowLeft class="h-3.5 w-3.5" />
            修改描述
          </button>
          <div class="flex gap-2">
            <button type="button" class="btn-ghost h-9" :disabled="generating" @click="generate">重新生成</button>
            <button type="button" class="btn-primary h-9 px-4" :disabled="creating" @click="create">
              <Loader2 v-if="creating" class="h-3.5 w-3.5 animate-spin" />
              <Check v-else class="h-3.5 w-3.5" />
              创建并加入看板
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="flex flex-col items-center gap-3 py-8 text-center">
      <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-state-ok/12 ring-1 ring-state-ok/30">
        <Check class="h-5 w-5 text-state-ok" />
      </div>
      <div>
        <p class="text-[16.8px] font-medium text-mist-100">卡片「{{ draft.title }}」已加入看板</p>
        <p class="mt-1 text-[13.8px] text-mist-500">状态将在 5 秒内自动回填，你可以打开卡片继续调教它的 agent。</p>
      </div>
      <div class="flex gap-2">
        <button type="button" class="btn-ghost" @click="restart">再生成一张</button>
        <button type="button" class="btn-primary" @click="visible = false">回到看板</button>
      </div>
    </div>
  </el-dialog>
</template>
