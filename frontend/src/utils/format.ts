import type { ServiceStatus } from '../types'

export function formatUptime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${Math.floor(seconds)}s`
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

export function formatMemory(mb: number | null | undefined): string {
  if (mb === null || mb === undefined) return '—'
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`
  return `${mb.toFixed(mb < 10 ? 2 : 0)} MB`
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(value < 10 ? 1 : 0)}%`
}

export interface StatusVisual {
  label: string
  dot: string
  text: string
  ring: string
  aura: string
}

const STATUS_MAP: Record<ServiceStatus, StatusVisual> = {
  running: {
    label: '运行中',
    dot: 'bg-state-ok',
    text: 'text-state-ok',
    ring: 'ring-state-ok/30',
    aura: 'from-state-ok/25',
  },
  warning: {
    label: '告警',
    dot: 'bg-state-warn',
    text: 'text-state-warn',
    ring: 'ring-state-warn/30',
    aura: 'from-state-warn/25',
  },
  stopped: {
    label: '已停止',
    dot: 'bg-mist-500',
    text: 'text-mist-300',
    ring: 'ring-white/10',
    aura: 'from-mist-500/20',
  },
  unavailable: {
    label: '不可用',
    dot: 'bg-state-bad',
    text: 'text-state-bad',
    ring: 'ring-state-bad/30',
    aura: 'from-state-bad/25',
  },
  unknown: {
    label: '未知',
    dot: 'bg-aurora-blue',
    text: 'text-aurora-blue',
    ring: 'ring-aurora-blue/25',
    aura: 'from-aurora-blue/20',
  },
}

export function statusVisual(status: ServiceStatus | string | undefined): StatusVisual {
  return STATUS_MAP[(status as ServiceStatus) ?? 'unknown'] ?? STATUS_MAP.unknown
}

/** 卡片自身的强调色使用固定的 hue-* 色板，与全局主题色解耦，保证每张卡片可独立辨识。 */
export function accentGradient(accent: string): string {
  switch (accent) {
    case 'violet':
      return 'from-hue-violet/70 to-hue-blue/40'
    case 'blue':
      return 'from-hue-blue/70 to-hue-teal/30'
    case 'amber':
      return 'from-hue-amber/70 to-hue-violet/30'
    case 'rose':
      return 'from-hue-rose/70 to-hue-violet/30'
    default:
      return 'from-hue-teal/70 to-hue-blue/30'
  }
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return '—'
  const diff = Math.max(0, Date.now() - then)
  if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${Math.floor(diff / 86_400_000)} 天前`
}

export function formatRate(kbps: number | null | undefined): string {
  if (kbps === null || kbps === undefined) return '—'
  if (kbps < 1024) return `${kbps < 10 ? kbps.toFixed(1) : Math.round(kbps)} KB/s`
  return `${(kbps / 1024).toFixed(1)} MB/s`
}

export function formatGb(gb: number | null | undefined): string {
  if (gb === null || gb === undefined) return '—'
  if (gb >= 1024) return `${(gb / 1024).toFixed(2)} TB`
  return `${gb < 10 ? gb.toFixed(1) : Math.round(gb)} GB`
}

export function formatMbAsGb(mb: number | null | undefined): string {
  if (mb === null || mb === undefined) return '—'
  return `${(mb / 1024).toFixed(1)} GB`
}

export function usageTone(percent: number | null | undefined): {
  text: string
  bar: string
  chip: string
} {
  const value = percent ?? 0
  if (value >= 90) {
    return { text: 'text-state-bad', bar: 'from-state-bad to-state-bad/40', chip: 'bg-state-bad/12 text-state-bad' }
  }
  if (value >= 75) {
    return { text: 'text-state-warn', bar: 'from-state-warn to-state-warn/40', chip: 'bg-state-warn/12 text-state-warn' }
  }
  return { text: 'text-aurora-teal', bar: 'from-aurora-teal to-aurora-blue/60', chip: 'bg-aurora-teal/10 text-aurora-teal' }
}
