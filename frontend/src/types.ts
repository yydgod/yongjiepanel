export type ServiceStatus = 'running' | 'stopped' | 'warning' | 'unavailable' | 'unknown'

export interface CardStatus {
  status: ServiceStatus
  cpu_percent: number | null
  memory_mb: number | null
  memory_limit_mb: number | null
  uptime_seconds: number | null
  ports: number[]
  detail: string
  collector?: string
  collected_at?: string
  extra?: Record<string, unknown>
  error?: { code: string; message: string } | null
}

export interface Agent {
  id: string
  card_id: string
  name: string
  provider_id: string | null
  model: string
  system_prompt: string
  tools: string[]
  temperature: number
  max_tokens: number
  gateway: 'auto' | 'openclaw' | 'direct'
  enabled: boolean
}

export interface MetricPoint {
  ts: string | null
  cpu: number | null
  mem: number | null
}

export interface ToolMeta {
  name: string
  label: string
  risk: 'read' | 'destructive'
  description: string
}

export interface ServiceCard {
  id: string
  host_id: string
  title: string
  subtitle: string | null
  card_type: string
  target_ref: string
  group_name: string
  icon: string
  accent: string
  sort_order: number
  display_config: Record<string, unknown>
  enabled: boolean
  agent: Agent | null
  status: CardStatus
  created_at: string
  updated_at: string
  history?: MetricPoint[]
  available_tools?: ToolMeta[]
}

export interface CardGroup {
  name: string
  count: number
}

export interface CardTypeSpec {
  kind: string
  label: string
  icon: string
  accent: string
  description: string
  target_label: string
  target_placeholder: string
  target_pattern: string
  tools: string[]
  metrics: string[]
  display_defaults: Record<string, unknown>
}

export interface Provider {
  id: string
  name: string
  kind: string
  base_url: string
  default_model: string
  models: string[]
  extra: Record<string, unknown>
  temperature: number
  timeout: number
  is_default: boolean
  enabled: boolean
  has_key: boolean
  api_key_masked: string
  created_at: string
}

export interface ProviderPreset {
  kind: string
  label: string
  base_url: string
  models: string[]
  docs: string
  extra?: Record<string, unknown>
}

export interface OpenClawStatus {
  configured: boolean
  base_url: string | null
  mode: string
  healthy: boolean
  reason: string
  checked_at: number | null
}

export interface CollectDiagnostic {
  kind: string
  label: string
  available: boolean
  reason: string | null
}

export interface SystemStatus {
  overview: {
    counts: Record<string, number>
    total: number
    avg_cpu: number | null
    avg_mem_ratio: number | null
  }
  scheduler: {
    last_run: string | null
    duration_ms: number | null
    tracked_cards: number
    collectors: CollectDiagnostic[]
  }
  collectors: CollectDiagnostic[]
  openclaw: OpenClawStatus
  ai: { providers_total: number; providers_ready: number; mock_enabled: boolean }
  cards_total: number
  interval: number
}

export interface AuditEntry {
  id: string
  actor: string
  action: string
  target_type: string
  target_id: string | null
  params: Record<string, unknown> | null
  result: Record<string, unknown> | null
  error: string | null
  created_at: string | null
}

export interface CardDraft {
  title: string
  subtitle: string | null
  card_type: string
  target_ref: string
  group_name: string
  icon: string
  accent: string
  display_config: Record<string, unknown>
  system_prompt: string
  tools: string[]
  model_hint: string | null
  rationale: string
  channel: string
}

export interface ToolCallEvent {
  id: string
  name: string
  label?: string
  risk?: 'read' | 'destructive'
  args?: Record<string, unknown>
  ok?: boolean
  summary?: string
  data?: unknown
}

export interface PendingAction {
  token: string
  tool_name: string
  label?: string
  params: Record<string, unknown>
  expires_at: string
}

export interface ChatMessageView {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  channel?: string | null
  toolCalls?: ToolCallEvent[]
  pending?: PendingAction[]
  streaming?: boolean
}

export interface ChatStreamEvent {
  type: string
  [key: string]: unknown
}

export interface HostHistoryPoint {
  ts: string
  cpu: number
  mem: number
  net_up: number
  net_down: number
  disk_read: number
  disk_write: number
}

export interface HostPartition {
  device: string
  mountpoint: string
  fstype: string
  total_gb: number
  used_gb: number
  percent: number
}

export interface HostInterface {
  name: string
  ip: string
  up_kbps: number
  down_kbps: number
  sent_gb: number
  recv_gb: number
}

export interface HostProcess {
  pid: number
  name: string
  memory_mb: number
  cpu_percent: number
}

export interface HostOverview {
  available: boolean
  error: { code: string; message: string } | null
  collected_at: string | null
  interval: number
  system: {
    hostname: string
    os: string
    kernel: string
    arch: string
    cpu_model: string
    cores: number
    physical_cores: number
    python: string
    boot_time: string
    uptime_seconds: number
    process_count: number
    user_count: number
    load: number[]
  }
  cpu: { percent: number; per_core: number[]; freq_mhz: number | null }
  memory: {
    total_mb: number
    used_mb: number
    available_mb: number
    percent: number
    swap_total_mb: number
    swap_used_mb: number
    swap_percent: number
  }
  disk: {
    total_gb: number
    used_gb: number
    percent: number
    read_kbps: number
    write_kbps: number
    partitions: HostPartition[]
  }
  network: {
    up_kbps: number
    down_kbps: number
    total_sent_gb: number
    total_recv_gb: number
    interfaces: HostInterface[]
  }
  processes: HostProcess[]
  health: { status: 'ok' | 'warning' | 'critical' | 'unknown'; reasons: string[] }
  history: HostHistoryPoint[]
}
