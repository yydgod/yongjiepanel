import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type ThemeMode = 'dark' | 'light'

export interface AccentTheme {
  id: string
  label: string
  hint: string
  /** 夜间模式（深底）使用的三段强调色 */
  dark: [string, string, string]
  /** 白天模式（浅底）使用的三段强调色，整体更深以保证对比度 */
  light: [string, string, string]
}

/**
 * 6 套强调色 × 明暗两套色值。颜色顺序对应 --accent-1/2/3：
 * 主色（按钮、焦点、开关）→ 次色（渐变、光晕）→ 辅色（第三条渐变/图表线）。
 */
export const ACCENT_THEMES: AccentTheme[] = [
  {
    id: 'teal',
    label: '青绿极光',
    hint: '默认控制台',
    dark: ['#35E0C8', '#7C6CFF', '#3B82F6'],
    light: ['#0B7F73', '#5B4BD6', '#1D4ED8'],
  },
  {
    id: 'violet',
    label: '星云紫',
    hint: '夜间观测',
    dark: ['#A78BFA', '#8B5CF6', '#38BDF8'],
    light: ['#6D4AE0', '#5B21B6', '#0369A1'],
  },
  {
    id: 'blue',
    label: '深海蓝',
    hint: '冷静理性',
    dark: ['#60A5FA', '#3B82F6', '#22D3EE'],
    light: ['#1D4ED8', '#1E40AF', '#0E7490'],
  },
  {
    id: 'emerald',
    label: '翡翠绿',
    hint: '长时值守',
    dark: ['#34D399', '#10B981', '#22D3EE'],
    light: ['#047857', '#065F46', '#0E7490'],
  },
  {
    id: 'amber',
    label: '琥珀金',
    hint: '高可读',
    dark: ['#FBBF24', '#F59E0B', '#FB7185'],
    light: ['#B45309', '#92400E', '#BE123C'],
  },
  {
    id: 'rose',
    label: '霓虹玫瑰',
    hint: '展示模式',
    dark: ['#FB7185', '#F43F5E', '#C084FC'],
    light: ['#BE123C', '#9F1239', '#6D28D9'],
  },
]

const ACCENT_KEY = 'yongjie.accent'
const MODE_KEY = 'yongjie.mode'
const LEGACY_ACCENT_KEY = 'obsidian.accent'
const LEGACY_MODE_KEY = 'obsidian.mode'

function hexToRgb(hex: string): [number, number, number] {
  const value = hex.replace('#', '')
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ]
}

function mix(hex: string, target: string, ratio: number): string {
  const source = hexToRgb(hex)
  const dest = hexToRgb(target)
  const channel = (index: number) =>
    Math.round(source[index] + (dest[index] - source[index]) * ratio)
      .toString(16)
      .padStart(2, '0')
  return `#${channel(0)}${channel(1)}${channel(2)}`
}

function readStorage(key: string, legacyKey?: string): string | null {
  try {
    const value = localStorage.getItem(key) ?? (legacyKey ? localStorage.getItem(legacyKey) : null)
    // 兼容旧品牌标识下的偏好，首次读取后迁移到新键
    if (value && legacyKey && !localStorage.getItem(key)) localStorage.setItem(key, value)
    return value
  } catch (error) {
    console.error('读取外观偏好失败', error)
    return null
  }
}

export const useThemeStore = defineStore('theme', () => {
  const savedAccent = readStorage(ACCENT_KEY, LEGACY_ACCENT_KEY)
  const accent = ref<string>(
    ACCENT_THEMES.some((item) => item.id === savedAccent) ? (savedAccent as string) : 'teal',
  )
  const mode = ref<ThemeMode>(readStorage(MODE_KEY, LEGACY_MODE_KEY) === 'light' ? 'light' : 'dark')

  const current = computed(
    () => ACCENT_THEMES.find((item) => item.id === accent.value) ?? ACCENT_THEMES[0],
  )
  const isLight = computed(() => mode.value === 'light')
  const colors = computed(() => (isLight.value ? current.value.light : current.value.dark))

  /** 供切换面板展示当前模式对应的色板 */
  const themes = computed(() =>
    ACCENT_THEMES.map((item) => ({
      id: item.id,
      label: item.label,
      hint: item.hint,
      colors: isLight.value ? item.light : item.dark,
    })),
  )

  function apply(): void {
    const theme = current.value
    const palette = colors.value
    const root = document.documentElement

    root.dataset.accent = theme.id
    root.dataset.mode = mode.value
    root.classList.toggle('dark', mode.value === 'dark')

    // Element Plus 主色需要派生 light-3/5/7/8/9 与 dark-2，才能让 hover / 边框 / 开关一致
    const style = root.style
    style.setProperty('--el-color-primary', palette[0])
    style.setProperty('--el-color-primary-light-3', mix(palette[0], '#ffffff', 0.3))
    style.setProperty('--el-color-primary-light-5', mix(palette[0], '#ffffff', 0.5))
    style.setProperty('--el-color-primary-light-7', mix(palette[0], '#ffffff', 0.7))
    style.setProperty('--el-color-primary-light-8', mix(palette[0], '#ffffff', 0.8))
    style.setProperty('--el-color-primary-light-9', mix(palette[0], '#ffffff', 0.9))
    style.setProperty('--el-color-primary-dark-2', mix(palette[0], '#000000', 0.2))
  }

  function persist(key: string, value: string): void {
    try {
      localStorage.setItem(key, value)
    } catch (error) {
      console.error('保存外观偏好失败', error)
    }
  }

  function setAccent(id: string): void {
    if (!ACCENT_THEMES.some((item) => item.id === id)) return
    accent.value = id
    persist(ACCENT_KEY, id)
    apply()
  }

  function setMode(next: ThemeMode): void {
    if (next !== 'dark' && next !== 'light') return
    mode.value = next
    persist(MODE_KEY, next)
    apply()
  }

  function toggleMode(): void {
    setMode(mode.value === 'dark' ? 'light' : 'dark')
  }

  function init(): void {
    apply()
  }

  return {
    accent,
    mode,
    isLight,
    current,
    colors,
    themes,
    setAccent,
    setMode,
    toggleMode,
    init,
  }
})

export { hexToRgb }
