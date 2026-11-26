<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { KeyRound, PlugZap, Save } from 'lucide-vue-next'
import { errorMessage } from '../../api/client'
import { providersApi } from '../../api/providers'
import type { Provider, ProviderPreset } from '../../types'

const props = defineProps<{
  modelValue: boolean
  provider: Provider | null
  presets: ProviderPreset[]
  initialKind?: string | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'saved'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const saving = ref(false)
const testing = ref(false)
const testResult = ref('')
const error = ref('')

const form = reactive({
  kind: 'deepseek',
  name: '',
  base_url: '',
  default_model: '',
  modelsText: '',
  api_key: '',
  temperature: 0.3,
  timeout: 60,
  is_default: false,
  enabled: true,
})

function applyPreset(kind: string): void {
  const preset = props.presets.find((item) => item.kind === kind)
  if (!preset) return
  form.base_url = preset.base_url
  form.default_model = preset.models[0] ?? ''
  form.modelsText = preset.models.join(', ')
  if (!form.name) form.name = preset.label
}

function hydrate(): void {
  error.value = ''
  testResult.value = ''
  form.api_key = ''
  if (props.provider) {
    const provider = props.provider
    form.kind = provider.kind
    form.name = provider.name
    form.base_url = provider.base_url
    form.default_model = provider.default_model
    form.modelsText = provider.models.join(', ')
    form.temperature = provider.temperature
    form.timeout = provider.timeout
    form.is_default = provider.is_default
    form.enabled = provider.enabled
  } else {
    form.kind = props.initialKind || 'deepseek'
    form.name = ''
    form.temperature = 0.3
    form.timeout = 60
    form.is_default = false
    form.enabled = true
    applyPreset(form.kind)
  }
}

function choosePreset(kind: string): void {
  form.kind = kind
  if (!props.provider) applyPreset(kind)
}

watch(() => [props.modelValue, props.provider?.id], ([open]) => {
  if (open) hydrate()
})

function payload() {
  return {
    name: form.name.trim(),
    kind: form.kind,
    base_url: form.base_url.trim(),
    default_model: form.default_model.trim(),
    models: form.modelsText.split(',').map((item) => item.trim()).filter(Boolean),
    api_key: form.api_key.trim() || undefined,
    temperature: form.temperature,
    timeout: form.timeout,
    is_default: form.is_default,
    enabled: form.enabled,
  }
}

async function save(): Promise<void> {
  if (!form.name.trim() || !form.base_url.trim() || !form.default_model.trim()) {
    error.value = '名称、Base URL 与默认模型为必填项'
    return
  }
  saving.value = true
  error.value = ''
  try {
    if (props.provider) {
      await providersApi.update(props.provider.id, payload())
      ElMessage.success('供应商已更新')
    } else {
      await providersApi.create(payload())
      ElMessage.success('供应商已创建')
    }
    emit('saved')
    visible.value = false
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    saving.value = false
  }
}

async function test(): Promise<void> {
  if (!props.provider) {
    error.value = '请先保存供应商，再测试连通性'
    return
  }
  testing.value = true
  testResult.value = ''
  try {
    const result = await providersApi.test(props.provider.id)
    testResult.value = `${result.message} · ${result.latency_ms}ms · ${result.channel ?? ''} ${result.sample ?? ''}`
    ElMessage.success('连通性正常')
  } catch (err) {
    testResult.value = errorMessage(err)
    ElMessage.error(testResult.value)
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <el-drawer v-model="visible" :size="'min(560px, 100%)'" :title="provider ? '编辑供应商' : '新增模型供应商'">
    <div class="space-y-3.5">
      <div>
        <label class="label-caps mb-1 block">厂商预设</label>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="preset in presets"
            :key="preset.kind"
            type="button"
            class="cursor-pointer rounded-lg border px-2.5 py-1.5 text-[13.2px] transition-colors"
            :class="form.kind === preset.kind
              ? 'border-aurora-teal/40 bg-aurora-teal/8 text-aurora-teal'
              : 'border-white/[0.07] bg-white/[0.02] text-mist-300 hover:border-white/15'"
            @click="choosePreset(preset.kind)"
          >
            {{ preset.label }}
          </button>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label-caps mb-1 block">显示名称</label>
          <input v-model="form.name" type="text" class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50" />
        </div>
        <div>
          <label class="label-caps mb-1 block">默认模型</label>
          <input v-model="form.default_model" type="text" class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 font-mono text-[13.8px] text-mist-100 outline-none focus:border-aurora-teal/50" />
        </div>
      </div>

      <div>
        <label class="label-caps mb-1 block">Base URL（OpenAI 兼容）</label>
        <input v-model="form.base_url" type="text" class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 font-mono text-[13.2px] text-mist-100 outline-none focus:border-aurora-teal/50" />
      </div>

      <div>
        <label class="label-caps mb-1 block">模型列表（逗号分隔）</label>
        <input v-model="form.modelsText" type="text" class="h-9 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 font-mono text-[13.2px] text-mist-100 outline-none focus:border-aurora-teal/50" />
      </div>

      <div>
        <label class="label-caps mb-1 flex items-center gap-1">
          <KeyRound class="h-3 w-3" />API Key
        </label>
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          :placeholder="provider?.has_key ? `已保存 ${provider.api_key_masked}，留空保持不变` : 'sk-...（加密存储，不会回显）'"
        />
        <p class="mt-1 text-[12px] leading-relaxed text-mist-500">
          使用 Fernet 加密后写入数据库，接口只返回掩码。也可通过环境变量 DEEPSEEK_API_KEY / HUNYUAN_API_KEY / QWEN_API_KEY 注入。
        </p>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="label-caps mb-1 block">默认温度</label>
          <el-input-number v-model="form.temperature" :min="0" :max="1.5" :step="0.05" class="w-full" />
        </div>
        <div>
          <label class="label-caps mb-1 block">超时（秒）</label>
          <el-input-number v-model="form.timeout" :min="5" :max="300" :step="5" class="w-full" />
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-4 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
        <label class="flex cursor-pointer items-center gap-1.5 text-[13.8px] text-mist-300">
          <input v-model="form.enabled" type="checkbox" class="h-3 w-3 accent-aurora-teal" />启用
        </label>
        <label class="flex cursor-pointer items-center gap-1.5 text-[13.8px] text-mist-300">
          <input v-model="form.is_default" type="checkbox" class="h-3 w-3 accent-aurora-teal" />设为默认供应商
        </label>
      </div>

      <div v-if="testResult" class="rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2 text-[13.2px] text-mist-300">
        {{ testResult }}
      </div>
      <div v-if="error" class="rounded-lg border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.8px] text-state-bad">
        {{ error }}
      </div>

      <div class="flex items-center justify-between gap-2 border-t border-white/[0.06] pt-3">
        <button v-if="provider" type="button" class="btn-ghost" :disabled="testing" @click="test">
          <PlugZap class="h-3.5 w-3.5" />
          {{ testing ? '测试中…' : '测试连通性' }}
        </button>
        <div class="ml-auto flex gap-2">
          <button type="button" class="btn-ghost" @click="visible = false">取消</button>
          <button type="button" class="btn-primary" :disabled="saving" @click="save">
            <Save class="h-3.5 w-3.5" />
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>
