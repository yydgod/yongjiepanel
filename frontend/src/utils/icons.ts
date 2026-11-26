import {
  Activity,
  Box,
  Container,
  Database,
  Globe,
  LayoutGrid,
  Radio,
  Server,
  Shield,
  Sparkles,
  Terminal,
  type LucideIcon,
} from 'lucide-vue-next'

const ICONS: Record<string, LucideIcon> = {
  box: Box,
  container: Container,
  server: Server,
  radio: Radio,
  sparkles: Sparkles,
  database: Database,
  globe: Globe,
  shield: Shield,
  terminal: Terminal,
  grid: LayoutGrid,
  activity: Activity,
}

export function cardIcon(name: string | undefined): LucideIcon {
  return ICONS[name ?? ''] ?? Box
}

export const ICON_CHOICES = [
  { value: 'box', label: '容器' },
  { value: 'server', label: '服务' },
  { value: 'radio', label: '端口' },
  { value: 'sparkles', label: 'AI' },
  { value: 'database', label: '数据库' },
  { value: 'globe', label: '外部' },
  { value: 'shield', label: '安全' },
  { value: 'terminal', label: '命令行' },
]

export const ACCENT_CHOICES = [
  { value: 'teal', label: '青绿', className: 'from-hue-teal to-hue-blue' },
  { value: 'violet', label: '星紫', className: 'from-hue-violet to-hue-blue' },
  { value: 'blue', label: '电蓝', className: 'from-hue-blue to-hue-teal' },
  { value: 'amber', label: '琥珀', className: 'from-hue-amber to-hue-violet' },
  { value: 'rose', label: '玫瑰', className: 'from-hue-rose to-hue-violet' },
]
