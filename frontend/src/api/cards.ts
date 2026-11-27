import { api } from './client'
import type {
  DshEntry,
  AuditEntry,
  CardGroup,
  CardTypeSpec,
  DshWorkspaceInfo,
  MetricPoint,
  ServiceCard,
  SystemStatus,
} from '../types'

export interface CardListResponse {
  items: ServiceCard[]
  groups: CardGroup[]
}

export interface CardMetaResponse {
  items: CardTypeSpec[]
}

export const cardsApi = {
  list: (params: Record<string, string> = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => Boolean(value)) as [string, string][],
    ).toString()
    return api.get<CardListResponse>(`/cards${query ? `?${query}` : ''}`)
  },
  detail: (id: string) =>
    api.get<ServiceCard & { history: MetricPoint[] }>(`/cards/${id}`),
  create: (payload: Record<string, unknown>) => api.post<ServiceCard>('/cards', payload),
  update: (id: string, payload: Record<string, unknown>) =>
    api.patch<ServiceCard>(`/cards/${id}`, payload),
  remove: (id: string) => api.delete<void>(`/cards/${id}`),
  reorder: (items: { id: string; sort_order: number }[]) =>
    api.post<CardListResponse>('/cards/reorder', { items }),
  action: (id: string, action: 'start' | 'stop' | 'restart') =>
    api.post<{ ok: boolean; summary: string; data: unknown }>(`/cards/${id}/actions`, { action }),
  metrics: (id: string) =>
    api.get<{ points: MetricPoint[]; snapshot: unknown }>(`/cards/${id}/metrics`),
  logs: (id: string, lines = 120) =>
    api.get<{ lines: number; content: string }>(`/cards/${id}/logs?lines=${lines}`),
  meta: () => api.get<CardMetaResponse>('/card-types'),
  system: () => api.get<SystemStatus>('/system/status'),
  audit: (limit = 50) => api.get<{ items: AuditEntry[] }>(`/audit?limit=${limit}`),
  collect: () => api.post<{ cards: number; duration_ms: number }>('/system/collect'),
  dsh: (id: string) => api.get<DshWorkspaceInfo>(`/cards/${id}/dsh`),
  dshEntry: () => api.get<DshEntry>('/dsh'),
}
