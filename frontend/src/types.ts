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

export interface MetricPoint {
  ts: string | null
  cpu: number | null
  mem: number | null
}

export interface ServiceCard {
  id: string
  host_id: string
  title: string
  subtitle: string | null
  card_type: string
  target_ref: string
  group_name: string
  workspace_path: string | null
  icon: string
  accent: string
  sort_order: number
  display_config: Record<string, unknown>
  enabled: boolean
  status: CardStatus
  created_at: string
  updated_at: string
  history?: MetricPoint[]
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
  metrics: string[]
  display_defaults: Record<string, unknown>
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

export interface DshWorkspaceInfo {
  configured: boolean
  workspace_id?: string
  title?: string
  path?: string
  url?: string
  reason?: string
}

export interface DshEntry {
  configured: boolean
  url?: string
  reason?: string
}

export interface FileEntry {
  name: string
  path: string
  is_dir: boolean
  is_symlink: boolean
  size: number | null
  mode: string
  modified_at: string | null
  hidden: boolean
  leaf?: boolean
}

export interface FileListing {
  root: string
  absolute_root: string
  path: string
  parent: string | null
  items: FileEntry[]
  truncated: boolean
}

export interface FileContent {
  path: string
  name: string
  size: number
  content: string
  binary: boolean
  truncated: boolean
  editable: boolean
  mime: string
  modified_at: string | null
}

export interface FileSearchResult {
  query: string
  items: FileEntry[]
  truncated: boolean
  scanned: number
}

export interface DshWorkspaceCreate {
  workspace_id: string
  path: string
  title: string | null
  created: boolean
  configured: boolean
  url?: string
  reason?: string
}

export interface DshWorkspaceBootstrap extends DshWorkspaceCreate {
  directory: string
  absolute_path: string
}

export interface TerminalSession {
  id: string
  title: string
  cwd: string
  created_at: string | null
  last_active: string | null
}

export interface TerminalExecResult {
  session_id: string
  cwd: string
  output: string
  exit_code: number
  duration_ms: number
  truncated: boolean
}

export interface TerminalHistoryItem {
  command: string
  session_id: string
  cwd: string
  exit_code: number
  created_at: string | null
}
