import { api } from './client'
import type { DshWorkspaceBootstrap, DshWorkspaceCreate } from '../types'

export const dshApi = {
  createWorkspace: (path: string, title?: string) =>
    api.post<DshWorkspaceCreate>('/dsh/workspaces', { path, title: title || null }),
  bootstrapWorkspace: (title: string, directory?: string) =>
    api.post<DshWorkspaceBootstrap>('/dsh/workspaces/bootstrap', {
      title,
      directory: directory || null,
    }),
}
