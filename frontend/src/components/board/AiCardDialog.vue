<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Sparkles } from 'lucide-vue-next'
import { dshApi } from '../../api/dsh'
import { errorMessage } from '../../api/client'

const props = defineProps<{ modelValue: boolean }>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'created', workspaceId: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const title = ref('')
const directory = ref('')
const directoryTouched = ref(false)
const submitting = ref(false)
const error = ref('')

const DIRECTORY_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
}

function defaultDirectory(value: string): string {
  const base = slugify(value)
  const stamp = Date.now().toString(36).slice(-5)
  return base ? `${base}-${stamp}` : `card-${stamp}`
}

watch(title, (value) => {
  if (!directoryTouched.value) directory.value = defaultDirectory(value)
})

watch(visible, (open) => {
  if (!open) return
  title.value = ''
  directory.value = defaultDirectory('')
  directoryTouched.value = false
  error.value = ''
})

function onDirectoryInput(): void {
  directoryTouched.value = true
}

async function submit(): Promise<void> {
  error.value = ''
  const name = title.value.trim()
  const dir = directory.value.trim()
  if (!name) {
    error.value = '请填写卡片名称'
    return
  }
  if (!DIRECTORY_PATTERN.test(dir)) {
    error.value = '目录名称只能包含字母、数字、点、下划线和连字符，且不能以符号开头'
    return
  }
  submitting.value = true
  try {
    const result = await dshApi.bootstrapWorkspace(name, dir)
    ElMessage.success('工作区已创建，正在进入 dsh')
    visible.value = false
    emit('created', result.workspace_id)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="用 AI 创建卡片" width="min(560px, 92vw)" destroy-on-close>
    <div class="space-y-3.5">
      <div class="rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[13px] leading-relaxed text-mist-500">
        <p>1. 填写卡片名称与目录名称</p>
        <p>2. 在工作区根目录下创建以该目录名命名的目录</p>
        <p>3. 注册同名 dsh 工作区，并直接进入该工作区</p>
        <p>4. 在 dsh 中让 AI 创建服务或容器，AI 通过 MCP 生成卡片</p>
      </div>

      <div>
        <label class="label-caps mb-1 block">卡片名称</label>
        <input
          v-model="title"
          type="text"
          maxlength="120"
          placeholder="例如 订单服务"
          class="h-10 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 text-[14.4px] text-mist-100 outline-none focus:border-aurora-teal/50"
        />
      </div>

      <div>
        <label class="label-caps mb-1 block">目录名称</label>
        <input
          v-model="directory"
          type="text"
          maxlength="64"
          placeholder="例如 order-service"
          class="h-10 w-full rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 font-mono text-[13.2px] text-mist-100 outline-none focus:border-aurora-teal/50"
          @input="onDirectoryInput"
        />
        <p class="mt-1 text-[11.4px] leading-relaxed text-mist-500">
          将在工作区根目录下创建该目录；目录已存在时直接复用。只能包含字母、数字、点、下划线和连字符。
        </p>
      </div>

      <div
        v-if="error"
        class="rounded-lg border border-state-bad/25 bg-state-bad/8 px-3 py-2 text-[13.2px] text-state-bad"
      >
        {{ error }}
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <button type="button" class="btn-ghost" @click="visible = false">取消</button>
        <button type="button" class="btn-primary" :disabled="submitting" @click="submit">
          <Sparkles class="h-3.5 w-3.5" />
          {{ submitting ? '创建中…' : '创建工作区并进入 dsh' }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>
