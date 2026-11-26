import { api } from './client'
import type { HostOverview } from '../types'

export const hostApi = {
  overview: () => api.get<HostOverview>('/host/overview'),
  sample: () => api.post<HostOverview>('/host/sample'),
}
