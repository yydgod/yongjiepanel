<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { Check, Moon, Palette, Sun, Terminal } from 'lucide-vue-next'
import { useBoardStore } from './stores/board'
import { useThemeStore, type ThemeMode } from './stores/theme'

const store = useBoardStore()
const theme = useThemeStore()
const route = useRoute()

const modeOptions: { id: ThemeMode; label: string; icon: typeof Moon }[] = [
  { id: 'dark', label: '夜间', icon: Moon },
  { id: 'light', label: '白天', icon: Sun },
]


let disposePolling: (() => void) | null = null

onMounted(() => {
  void store.refresh()
  void store.refreshSystem()
  void store.loadMeta()
  disposePolling = store.startPolling()
})

onUnmounted(() => {
  disposePolling?.()
  store.stopPolling()
})
</script>

<template>
  <div class="relative min-h-screen">
    <!-- ambient layers -->
    <div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div class="absolute -left-40 -top-52 h-[520px] w-[520px] rounded-full ambient-glow-a blur-[120px] animate-drift transition-colors duration-500" />
      <div class="absolute -right-32 top-10 h-[460px] w-[460px] rounded-full ambient-glow-b blur-[130px] animate-drift [animation-delay:-8s] transition-colors duration-500" />
      <div class="absolute inset-0 grid-grid-bg opacity-60" />
      <div class="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-aurora-teal/40 to-transparent" />
    </div>

    <header class="fixed inset-x-0 top-0 z-40 border-b border-white/[0.06] bg-ink-900/80 backdrop-blur-2xl">
      <div class="mx-auto flex h-16 max-w-[1600px] items-center gap-5 px-4 sm:px-6">
        <RouterLink to="/" class="flex items-center gap-3">
          <div class="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-aurora-teal/25 to-aurora-violet/25 ring-1 ring-white/10">
            <Terminal class="h-4 w-4 text-aurora-teal" />
            <span class="absolute -inset-px rounded-xl bg-gradient-to-br from-aurora-teal/10 to-transparent" />
          </div>
          <div class="leading-tight">
            <div class="whitespace-nowrap text-[16.8px] font-semibold tracking-[0.04em] text-mist-100">永杰面板</div>
            <div class="font-mono text-[12px] uppercase tracking-[0.18em] text-mist-500">yongjie panel</div>
          </div>
        </RouterLink>

        <nav class="ml-2 hidden items-center gap-1 lg:flex">
          <RouterLink to="/" class="nav-link">服务器总览</RouterLink>
          <RouterLink
            to="/board"
            class="nav-link"
            :class="{ 'router-link-active': route.path.startsWith('/cards') }"
          >
            应用面板
          </RouterLink>
          <RouterLink to="/dsh" class="nav-link">dsh 工作区</RouterLink>
          <RouterLink to="/system" class="nav-link">系统与审计</RouterLink>
        </nav>

        <div class="ml-auto flex items-center gap-2">


          <button
            type="button"
            class="btn-ghost h-9 w-9 justify-center p-0"
            :title="theme.isLight ? '切换到夜间模式' : '切换到白天模式'"
            @click="theme.toggleMode()"
          >
            <Sun v-if="theme.isLight" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </button>

          <el-popover placement="bottom-end" :width="296" trigger="click" popper-class="theme-popper">
            <template #reference>
              <button
                type="button"
                class="btn-ghost h-9 w-9 justify-center p-0"
                :title="`外观：${theme.isLight ? '白天' : '夜间'} · ${theme.current.label}`"
              >
                <Palette class="h-4 w-4" />
              </button>
            </template>
            <div>
              <div class="label-caps mb-1.5">外观模式</div>
              <div class="mb-3 grid grid-cols-2 gap-1 rounded-lg border border-white/[0.07] bg-white/[0.02] p-1">
                <button
                  v-for="item in modeOptions"
                  :key="item.id"
                  type="button"
                  class="flex h-7 cursor-pointer items-center justify-center gap-1.5 rounded-md text-[13.2px] transition-colors"
                  :class="theme.mode === item.id
                    ? 'bg-white/[0.08] text-mist-100'
                    : 'text-mist-500 hover:text-mist-300'"
                  @click="theme.setMode(item.id)"
                >
                  <component :is="item.icon" class="h-3 w-3" />
                  {{ item.label }}
                </button>
              </div>

              <div class="mb-2 flex items-center justify-between">
                <span class="label-caps">主题色</span>
                <span class="font-mono text-[11.4px] text-mist-500">{{ theme.current.id }}</span>
              </div>
              <div class="grid grid-cols-2 gap-1.5">
                <button
                  v-for="item in theme.themes"
                  :key="item.id"
                  type="button"
                  class="group flex cursor-pointer items-center gap-2 rounded-lg border px-2 py-1.5 text-left transition-colors"
                  :class="theme.accent === item.id
                    ? 'border-white/20 bg-white/[0.07]'
                    : 'border-white/[0.06] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.05]'"
                  :title="item.hint"
                  @click="theme.setAccent(item.id)"
                >
                  <span class="flex shrink-0 items-center -space-x-1">
                    <i
                      v-for="color in item.colors"
                      :key="color"
                      class="theme-swatch"
                      :style="{ backgroundColor: color }"
                    />
                  </span>
                  <span class="min-w-0 flex-1 truncate text-[13.2px]" :class="theme.accent === item.id ? 'text-mist-100' : 'text-mist-300'">
                    {{ item.label }}
                  </span>
                  <Check v-if="theme.accent === item.id" class="h-3 w-3 shrink-0 text-aurora-teal" />
                </button>
              </div>
              <p class="mt-2 text-[12px] leading-relaxed text-mist-500">
                明暗模式与主题色会同步到按钮渐变、光晕、图表曲线与 Element Plus 主色，偏好保存在本机。
              </p>
            </div>
          </el-popover>

        </div>
      </div>
    </header>

    <main class="mx-auto max-w-[1600px] px-4 pb-16 pt-[84px] sm:px-6">
      <RouterView />
    </main>
  </div>
</template>
