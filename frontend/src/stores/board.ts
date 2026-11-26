import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { cardsApi, type CardListResponse, type CardMetaResponse } from '../api/cards'
import { errorMessage } from '../api/client'
import type { CardGroup, ServiceCard, SystemStatus } from '../types'

const POLL_MS = 5000
const SYSTEM_POLL_MS = 15000

export const useBoardStore = defineStore('board', () => {
  const cards = ref<ServiceCard[]>([])
  const groups = ref<CardGroup[]>([])
  const system = ref<SystemStatus | null>(null)
  const meta = ref<CardMetaResponse>({ items: [], tools: [] })
  const loading = ref(false)
  const error = ref('')
  const lastSynced = ref<string>('')
  const viewMode = ref<'grid' | 'compact'>('grid')
  const filters = reactive({ q: '', group: '', type: '', status: '' })

  const filteredCards = computed(() => {
    const keyword = filters.q.trim().toLowerCase()
    return cards.value.filter((card) => {
      if (filters.group && card.group_name !== filters.group) return false
      if (filters.type && card.card_type !== filters.type) return false
      if (filters.status && card.status?.status !== filters.status) return false
      if (!keyword) return true
      return (
        card.title.toLowerCase().includes(keyword) ||
        card.target_ref.toLowerCase().includes(keyword) ||
        (card.subtitle ?? '').toLowerCase().includes(keyword)
      )
    })
  })

  const stats = computed(() => {
    const counts = { running: 0, warning: 0, stopped: 0, unavailable: 0, unknown: 0 }
    cards.value.forEach((card) => {
      const key = (card.status?.status ?? 'unknown') as keyof typeof counts
      counts[key] = (counts[key] ?? 0) + 1
    })
    const cpuValues = cards.value
      .map((card) => card.status?.cpu_percent)
      .filter((value): value is number => value !== null && value !== undefined)
    return {
      ...counts,
      total: cards.value.length,
      avgCpu: cpuValues.length ? cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length : null,
    }
  })

  async function refresh(silent = false): Promise<void> {
    if (!silent) loading.value = true
    try {
      const response: CardListResponse = await cardsApi.list()
      cards.value = response.items
      groups.value = response.groups
      error.value = ''
      lastSynced.value = new Date().toISOString()
    } catch (err) {
      error.value = errorMessage(err)
      console.error('看板数据加载失败', err)
    } finally {
      if (!silent) loading.value = false
    }
  }

  async function refreshSystem(): Promise<void> {
    try {
      system.value = await cardsApi.system()
    } catch (err) {
      console.error('系统状态加载失败', err)
    }
  }

  async function loadMeta(): Promise<void> {
    if (meta.value.items.length) return
    try {
      meta.value = await cardsApi.meta()
    } catch (err) {
      console.error('卡片类型加载失败', err)
    }
  }

  async function reorder(orderedIds: string[]): Promise<void> {
    const items = orderedIds.map((id, index) => ({ id, sort_order: index * 10 }))
    const local = new Map(cards.value.map((card) => [card.id, card]))
    cards.value = orderedIds
      .map((id) => local.get(id))
      .filter((card): card is ServiceCard => Boolean(card))
    try {
      await cardsApi.reorder(items)
    } catch (err) {
      console.error('排序保存失败', err)
      await refresh(true)
    }
  }

  async function quickAction(cardId: string, action: 'start' | 'stop' | 'restart'): Promise<string> {
    const result = await cardsApi.action(cardId, action)
    await refresh(true)
    return result.summary
  }

  let timer: number | null = null
  let systemTimer: number | null = null

  function startPolling(): () => void {
    stopPolling()
    timer = window.setInterval(() => {
      if (document.hidden) return
      void refresh(true)
    }, POLL_MS)
    systemTimer = window.setInterval(() => {
      if (document.hidden) return
      void refreshSystem()
    }, SYSTEM_POLL_MS)
    return stopPolling
  }

  function stopPolling(): void {
    if (timer) window.clearInterval(timer)
    if (systemTimer) window.clearInterval(systemTimer)
    timer = null
    systemTimer = null
  }

  return {
    cards,
    groups,
    system,
    meta,
    loading,
    error,
    lastSynced,
    viewMode,
    filters,
    filteredCards,
    stats,
    refresh,
    refreshSystem,
    loadMeta,
    reorder,
    quickAction,
    startPolling,
    stopPolling,
  }
})
