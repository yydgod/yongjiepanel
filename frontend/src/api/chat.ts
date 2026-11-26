import { ApiError, api } from './client'
import type { ChatStreamEvent, ChatMessageView } from '../types'

const TOKEN_KEY = 'yongjie_admin_token'
const LEGACY_TOKEN_KEY = 'obsidian_admin_token'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface StreamHandlers {
  onEvent: (event: ChatStreamEvent) => void
  signal?: AbortSignal
}

/** POST + ReadableStream SSE parsing (EventSource cannot send a body). */
export async function streamChat(
  cardId: string,
  message: string,
  sessionId: string | null,
  handlers: StreamHandlers,
): Promise<void> {
  const response = await fetch(`/api/cards/${cardId}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal: handlers.signal,
  })

  if (!response.ok) {
    const text = await response.text()
    let payload: { error?: { code?: string; message?: string } } = {}
    try {
      payload = JSON.parse(text)
    } catch {
      payload = {}
    }
    throw new ApiError(
      payload.error?.code ?? 'http_error',
      payload.error?.message ?? `对话请求失败 (${response.status})`,
      response.status,
    )
  }
  if (!response.body) throw new ApiError('stream_error', '浏览器不支持流式响应', 500)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'))
      if (dataLine) {
        const payload = dataLine.slice(5).trim()
        if (payload === '[DONE]') return
        try {
          handlers.onEvent(JSON.parse(payload) as ChatStreamEvent)
        } catch (error) {
          console.error('SSE 解析失败', error)
        }
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}

export const chatApi = {
  confirm: (token: string) =>
    api.post<{ ok: boolean; tool_name: string; status: string; message: string; result: unknown }>(
      '/chat/confirm',
      { token },
    ),
  sessions: (cardId: string) =>
    api.get<{ items: { id: string; title: string; channel: string; updated_at: string }[] }>(
      `/cards/${cardId}/sessions`,
    ),
  session: (sessionId: string) =>
    api.get<{
      id: string
      card_id: string
      title: string
      channel: string
      messages: {
        id: string
        role: string
        content: string
        tool_calls: unknown[] | null
        tool_name: string | null
        channel: string | null
        created_at: string
      }[]
    }>(`/chat/sessions/${sessionId}`),
  pending: (cardId: string) =>
    api.get<{ items: { token: string; tool_name: string; params: Record<string, unknown>; expires_at: string }[] }>(
      `/cards/${cardId}/pending`,
    ),
}

export type { ChatMessageView }
