import { api } from './client'
import type { FileContent, FileListing, FileSearchResult } from '../types'

function encode(path: string): string {
  return encodeURIComponent(path)
}

export const filesApi = {
  list: (path = '/') => api.get<FileListing>(`/files/list?path=${encode(path)}`),
  search: (query: string, limit = 40) =>
    api.get<FileSearchResult>(`/files/search?q=${encode(query)}&limit=${limit}`),
  read: (path: string) => api.get<FileContent>(`/files/read?path=${encode(path)}`),
  write: (path: string, content: string) =>
    api.put<{ path: string; size: number; modified_at: string | null }>('/files/write', {
      path,
      content,
    }),
  mkdir: (path: string) => api.post<{ path: string; is_dir: boolean }>('/files/mkdir', { path }),
  rename: (path: string, target: string) =>
    api.post<{ path: string; from: string }>('/files/rename', { path, target }),
  remove: (path: string, recursive = false) =>
    api.delete<{ path: string; deleted: boolean }>(
      `/files?path=${encode(path)}&recursive=${recursive}`,
    ),
}
