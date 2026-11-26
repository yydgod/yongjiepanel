export class ApiError extends Error {
  code: string
  status: number
  detail?: unknown

  constructor(code: string, message: string, status: number, detail?: unknown) {
    super(message)
    this.code = code
    this.status = status
    this.detail = detail
  }
}

const TOKEN_KEY = 'yongjie_admin_token'
const LEGACY_TOKEN_KEY = 'obsidian_admin_token'

export function setAdminToken(token: string): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export function hasAdminToken(): boolean {
  return Boolean(localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY))
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(LEGACY_TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers as Record<string, string> | undefined),
    },
  })
  if (response.status === 204) return undefined as T
  const text = await response.text()
  let payload: unknown = null
  try {
    payload = text ? JSON.parse(text) : null
  } catch {
    payload = text
  }
  if (!response.ok) {
    const envelope = (payload as { error?: { code?: string; message?: string; detail?: unknown } })?.error
    throw new ApiError(
      envelope?.code ?? 'http_error',
      envelope?.message ?? `请求失败 (${response.status})`,
      response.status,
      envelope?.detail,
    )
  }
  return payload as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return '未知错误'
}
