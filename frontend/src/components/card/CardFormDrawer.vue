<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Boxes, Save } from 'lucide-vue-next'
import { cardsApi } from '../../api/cards'
import { errorMessage } from '../../api/client'
import { useBoardStore } from '../../stores/board'
import { ACCENT_CHOICES, ICON_CHOICES } from '../../utils/icons'
import type { Provider, ServiceCard } from '../../types'

const props = defineProps<{
  modelValue: boolean
  card: ServiceCard | null
  providers: Provider[]
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved'): void
}>()

const store = useBoardStore()
const saving = ref(false)
const error = ref('')

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive({
  title: '',
  subtitle: '',
  card_type: 'container',
  target_ref: '',
  group_name: '默认分组',
  icon: 'box',
  accent: 'teal',
  enabled: true,
  showMetrics: true,
  showPorts: true,
  showUptime: true,
  provider_id: undefined as string | undefined,
  model: '',
  system_prompt: '',
})

const editing = computed(() => Boolean(props.card))
const spec = computed(() => store.meta.items.find((item) => item.kind === form.card_type))
const agentTools = computed(() => spec.value?.tools ?? [])

function hydrate(): void {
  if (props.card) {
    const card = props.card
    form.title = card.title
    form.subtitle = card.subtitle ?? ''
    form.card_type = card.card_type
    form.target_ref = card.target_ref
    form.group_name = card.group_name
    form.icon = card.icon
    form.accent = card.accent
    form.enabled = card.enabled
    form.showMetrics = card.display_config?.showMetrics !== false
    form.showPorts = card.display_config?.showPorts !== false
    form.showUptime = card.display_config?.showUptime !== false
    form.provider_id = card.agent?.provider_id ?? undefined
    form.model = card.agent?.model ?? ''
    form.system_prompt = card.agent?.system_prompt ?? ''
  } else {
    form.title = ''
    form.subtitle = ''
    form.card_type = 'container'
    form.target_ref = ''
    form.group_name = '默认分组'
    form.icon = 'box'
    form.accent = 'teal'
    form.enabled = true
    form.showMetrics = true
    form.showPorts = true
    form.showUptime = true
    form.provider_id = props.providers.find((item) => item.is_default)?.id ?? undefined
    form.model = ''
    form.system_prompt = ''
  }
  error.value = ''
}

watch(() => [props.modelValue, props.card?.id], ([open]) => {
  if (open) {
    void store.loadMeta()
    hydrate()
  }
})

watch(() => form.card_type, (kind) => {
  const found = store.meta.items.find((item) => item.kind === kind)
  if (found && !editing.value) {
    form.icon = found.icon
    form.accent = found.accent
    form.showMetrics = found.display_defaults.showMetrics !== false
    form.showPorts = found.display_defaults.showPorts !== false
  }
})

async function submit(): Promise<void> {
  error.value = ''
  if (!form.title.trim() || !form.target_ref.trim()) {
    error.value = '卡片标题与目标对象不能为空'
    return
  }
  if (spec.value) {
    const pattern = new RegExp(spec.value.target_pattern)
    if (!pattern.test(form.target_ref.trim())) {
      error.value = `目标对象格式不符合 ${spec.value.label} 要求，例如：${spec.value.target_placeholder}`
      return
    }
  }
  saving.value = true
  const payload: Record<string, unknown> = {
    title: form.title.trim(),
    subtitle: form.subtitle.trim() || null,
    card_type: form.card_type,
    target_ref: form.target_ref.trim(),
    group_name: form.group_name.trim() || '默认分组',
    icon: form.icon,
    accent: form.accent,
    enabled: form.enabled,
    display_config: {
      showMetrics: form.showMetrics,
      showPorts: form.showPorts,
      showUptime: form.showUptime,
    },
  }
  if (!editing.value) {
    payload.agent = {
      name: `${form.title.trim()} 助手`,
      provider_id: form.provider_id ?? null,
      model: form.model,
      system_prompt: form.system_prompt,
      tools: agentTools.value,
      gateway: 'auto',
    }
  }
  try {
    if (editing.value && props.card) {
      await cardsApi.update(props.card.id, payload)
      ElMessage.success('卡片已更新')
    } else {
      await cardsApi.create(payload)
      ElMessage.success('卡片已创建，状态将在下一轮自动同步')
    }
    await store.refresh()
    visible.value = false
    emit('saved')
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-drawer v-model="visible" :size="'min(560px, 100%)'" :title="editing ? '编辑卡片' : '新建服务卡片'">
    <div class="space-y-3.5">
      <div class="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[13.2px] text-mist-500">
        <Boxes class="h-3.5 w-3.5 text-aurora-teal" />
        卡片类型决定监控方式、可用工具与详情页展示，新增类型由后端注册表驱动。
      </div>

      <div>
        <label class="label-caps mb-1 block">卡片类型</label>
        <div class="grid grid-cols-2 gap-1.5">
          <button
            v-for="item in store.meta.items"
            :key="item.kind"
            type="button"
            class="cursor-pointer rounded-lg border px-2.5 py-2 text-left transition-colors"
            :class="form.card_type === item.kind
              ? 'border-aurora-teal/35 bg-aurora-teal/8'
              : 'border-white/[0.06] bg-white/[0.02] hover:border-white/15'"
            @click="form.card_type = item.kind"
          >
            <div class="text-[14.4px] font-medium text-mist-100">{{ item.label }}</div>
            <div class="mt-0.5 line-clamp-2 text-[12px] leading-snug text-mist-500">{{ item.description }}</div>
          </button>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label-caps mb-1 block">卡片标题</label>
          <input
            v-model="form.title"
            type="text"
            placeholder="例如 redis-cache"
            class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50"
          />
        </div>
        <div>
          <label class="label-caps mb-1 block">分组</label>
          <el-select v-model="form.group_name" filterable allow-create default-first-option class="w-full">
            <el-option v-for="group in store.groups" :key="group.name" :value="group.name" :label="group.name" />
          </el-select>
        </div>
      </div>

      <div>
        <label class="label-caps mb-1 block">{{ spec?.target_label ?? '目标对象' }}</label>
        <input
          v-model="form.target_ref"
          type="text"
          :placeholder="spec?.target_placeholder ?? ''"
          class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 font-sans text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50"
        />
      </div>

      <div>
        <label class="label-caps mb-1 block">副标题 / 说明</label>
        <input
          v-model="form.subtitle"
          type="text"
          placeholder="一句话说明这张卡片的用途"
          class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50"
        />
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label-caps mb-1 block">图标</label>
          <el-select v-model="form.icon" class="w-full">
            <el-option v-for="icon in ICON_CHOICES" :key="icon.value" :value="icon.value" :label="icon.label" />
          </el-select>
        </div>
        <div>
          <label class="label-caps mb-1 block">配色</label>
          <div class="flex h-9 items-center gap-1.5">
            <button
              v-for="accent in ACCENT_CHOICES"
              :key="accent.value"
              type="button"
              class="h-6 w-6 cursor-pointer rounded-full bg-gradient-to-br ring-2 transition-all"
              :class="[accent.className, form.accent === accent.value ? 'ring-white/70' : 'ring-transparent hover:ring-white/25']"
              :title="accent.label"
              @click="form.accent = accent.value"
            />
          </div>
        </div>
      </div>

      <div class="flex flex-wrap gap-4 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
        <label class="flex cursor-pointer items-center gap-1.5 text-[13.8px] text-mist-300">
          <input v-model="form.showMetrics" type="checkbox" class="h-3 w-3 accent-aurora-teal" />指标
        </label>
        <label class="flex cursor-pointer items-center gap-1.5 text-[13.8px] text-mist-300">
          <input v-model="form.showPorts" type="checkbox" class="h-3 w-3 accent-aurora-teal" />端口
        </label>
        <label class="flex cursor-pointer items-center gap-1.5 text-[13.8px] text-mist-300">
          <input v-model="form.showUptime" type="checkbox" class="h-3 w-3 accent-aurora-teal" />运行时长
        </label>
        <label class="flex cursor-pointer items-center gap-1.5 text-[13.8px] text-mist-300">
          <input v-model="form.enabled" type="checkbox" class="h-3 w-3 accent-aurora-teal" />启用采集
        </label>
      </div>

      <template v-if="!editing">
        <div class="border-t border-white/[0.06] pt-3">
          <div class="label-caps mb-2">专属 Agent（创建后可继续细化）</div>
          <div class="grid gap-3 sm:grid-cols-2">
            <el-select v-model="form.provider_id" placeholder="选择模型供应商" clearable class="w-full">
              <el-option
                v-for="provider in providers"
                :key="provider.id"
                :value="provider.id"
                :label="`${provider.name}${provider.has_key ? '' : '（未配置 Key）'}`"
              />
            </el-select>
            <input
              v-model="form.model"
              type="text"
              placeholder="模型名，例如 deepseek-chat"
              class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 font-sans text-[13.8px] text-mist-100 outline-none focus:border-aurora-teal/50"
            />
          </div>
          <textarea
            v-model="form.system_prompt"
            rows="3"
            placeholder="留空则自动生成默认运维提示词"
            class="mt-2 w-full resize-y rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 py-2 text-[13.8px] text-mist-200 outline-none focus:border-aurora-teal/50"
          />
        </div>
      </template>

      <div v-if="error" class="rounded-lg border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.8px] text-state-bad">
        {{ error }}
      </div>

      <div class="flex items-center justify-end gap-2 border-t border-white/[0.06] pt-3">
        <button type="button" class="btn-ghost" @click="visible = false">取消</button>
        <button type="button" class="btn-primary" :disabled="saving" @click="submit">
          <Save class="h-3.5 w-3.5" />
          {{ saving ? '保存中…' : editing ? '保存修改' : '创建卡片' }}
        </button>
      </div>
    </div>
  </el-drawer>
</template>
