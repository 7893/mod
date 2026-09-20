const configuredOrigin = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '')
const apiRoot = configuredOrigin
  ? `${configuredOrigin}/api`
  : `${import.meta.env.BASE_URL}api`

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function apiUrl(path: string): string {
  return `${apiRoot}/${path.replace(/^\/+/, '')}`
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init)
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new ApiError(payload?.detail || `请求失败（HTTP ${response.status}）`, response.status)
  }
  return response.json() as Promise<T>
}
