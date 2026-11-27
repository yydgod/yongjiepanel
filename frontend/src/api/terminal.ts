import { api } from './client'
import type { TerminalExecResult, TerminalHistoryItem, TerminalSession } from '../types'

export const terminalApi = {
  sessions: () => api.get<{ items: TerminalSession[] }>('/terminal/sessions'),
  createSession: (title?: string) =>
    api.post<TerminalSession>('/terminal/sessions', { title: title || null }),
  closeSession: (id: string) => api.delete<void>(`/terminal/sessions/${id}`),
  exec: (sessionId: string, command: string, timeout?: number) =>
    api.post<TerminalExecResult>('/terminal/exec', {
      session_id: sessionId,
      command,
      timeout: timeout ?? null,
    }),
  history: (limit = 200) =>
    api.get<{ items: TerminalHistoryItem[] }>(`/terminal/history?limit=${limit}`),
  clearHistory: () => api.delete<void>('/terminal/history'),
}
