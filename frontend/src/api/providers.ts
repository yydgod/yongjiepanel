import { api } from './client'
import type { OpenClawStatus, Provider, ProviderPreset } from '../types'

export interface ProviderPayload {
  name: string
  kind: string
  base_url: string
  default_model: string
  models: string[]
  api_key?: string
  extra?: Record<string, unknown>
  temperature?: number
  timeout?: number
  is_default?: boolean
  enabled?: boolean
}

export const providersApi = {
  list: () => api.get<Provider[]>('/providers'),
  presets: () => api.get<ProviderPreset[]>('/providers/presets'),
  create: (payload: ProviderPayload) => api.post<Provider>('/providers', payload),
  update: (id: string, payload: ProviderPayload) => api.put<Provider>(`/providers/${id}`, payload),
  remove: (id: string) => api.delete<void>(`/providers/${id}`),
  test: (id: string) =>
    api.post<{
      ok: boolean
      latency_ms: number | null
      model: string | null
      channel: string | null
      message: string
      sample: string | null
    }>(`/providers/${id}/test`),
  openclaw: (force = false) =>
    api.get<OpenClawStatus & { healthy: boolean }>(`/providers/openclaw?force=${force}`),
}

export const generatorApi = {
  generate: (description: string, providerId?: string | null) =>
    api.post<{
      draft: Record<string, unknown>
      channel: string
      warnings: string[]
    }>('/generate/card', { description, provider_id: providerId ?? null }),
}
