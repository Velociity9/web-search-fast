const BASE = '/admin/api'

function getToken(): string {
  return localStorage.getItem('admin_token') || ''
}

export function setToken(token: string) {
  localStorage.setItem('admin_token', token)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  getStats: () => request<Stats>('/stats'),
  getSearchLogs: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return request<PaginatedLogs>(`/search-logs${qs}`)
  },
  getKeys: () => request<APIKey[]>('/keys'),
  createKey: (data: { name: string; call_limit: number }) =>
    request<APIKeyCreated>('/keys', { method: 'POST', body: JSON.stringify(data) }),
  deleteKey: (id: string) => request<{ ok: boolean }>(`/keys/${id}`, { method: 'DELETE' }),
  getBans: () => request<IPBan[]>('/ip-bans'),
  banIP: (data: { ip: string; reason: string }) =>
    request<IPBan>('/ip-bans', { method: 'POST', body: JSON.stringify(data) }),
  unbanIP: (ip: string) => request<{ ok: boolean }>(`/ip-bans/${ip}`, { method: 'DELETE' }),
}

export interface Stats {
  total_searches: number
  searches_today: number
  active_keys: number
  banned_ips: number
}

export interface SearchLog {
  id: number
  api_key_id: string | null
  query: string
  engine: string | null
  ip_address: string
  user_agent: string | null
  status_code: number | null
  elapsed_ms: number | null
  created_at: string
}

export interface PaginatedLogs {
  items: SearchLog[]
  total: number
  page: number
  page_size: number
}

export interface APIKey {
  id: string
  name: string
  key_prefix: string
  call_limit: number
  call_count: number
  is_active: boolean
  created_at: string
  expires_at: string | null
}

export interface APIKeyCreated extends APIKey {
  key: string
}

export interface IPBan {
  id: number
  ip_address: string
  reason: string
  created_at: string
}
