import { api } from './client'

export interface LogEntry {
  card_id: string
  card_title: string
  card_type: string
  level: 'error' | 'warn' | 'info' | 'debug'
  ts: string | null
  message: string
}

export interface LogCard {
  id: string
  title: string
  card_type: string
}

export interface LogFeedResponse {
  items: LogEntry[]
  cards: LogCard[]
  errors: { card_id: string; card_title: string; message: string }[]
  lines: number
}

export const logsApi = {
  feed: (lines = 60, cardId?: string) => {
    const query = new URLSearchParams({ lines: String(lines) })
    if (cardId) query.set('card_id', cardId)
    return api.get<LogFeedResponse>(`/logs?${query.toString()}`)
  },
}
