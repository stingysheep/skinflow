import { recoverLocalSession } from './localSession'

export class ApiError extends Error {
  readonly status: number
  readonly code: string | null

  constructor(message: string, status: number, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

type ErrorEnvelope = { error?: { code?: string; message?: string } }

async function responseError(response: Response): Promise<ApiError> {
  try {
    const payload = await response.json() as ErrorEnvelope
    const message = payload.error?.message?.trim()
    return new ApiError(message || `请求失败 (${response.status})`, response.status, payload.error?.code ?? null)
  } catch {
    return new ApiError(`请求失败 (${response.status})`, response.status)
  }
}

async function fetchWithLocalRecovery(
  path: string,
  init: RequestInit,
): Promise<Response> {
  const response = await fetch(path, init)
  if (response.status !== 401) return response
  const error = await responseError(response)
  if (error.code !== 'AUTH_REQUIRED' || !await recoverLocalSession()) throw error
  return fetch(path, init)
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetchWithLocalRecovery(path, {
    method: 'GET',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    throw await responseError(response)
  }

  return response.json() as Promise<T>
}

export async function postJson<T>(path: string, body?: unknown, timeoutMs = 15_000): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetchWithLocalRecovery(path, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
    if (!response.ok) throw await responseError(response)
    return response.json() as Promise<T>
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === 'AbortError') {
      throw new ApiError('本地服务响应超时，请检查 Skinflow 服务是否仍在运行。', 0, 'REQUEST_TIMEOUT')
    }
    throw reason
  } finally {
    window.clearTimeout(timer)
  }
}

export async function putJson<T>(path: string, body: unknown, timeoutMs = 15_000): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetchWithLocalRecovery(path, {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      keepalive: true,
      signal: controller.signal,
    })
    if (!response.ok) throw await responseError(response)
    return response.json() as Promise<T>
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === 'AbortError') {
      throw new ApiError('本地服务响应超时，请检查 Skinflow 服务是否仍在运行。', 0, 'REQUEST_TIMEOUT')
    }
    throw reason
  } finally {
    window.clearTimeout(timer)
  }
}

export async function deleteJson<T>(path: string): Promise<T> {
  const response = await fetchWithLocalRecovery(path, {
    method: 'DELETE',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  })
  if (!response.ok) throw await responseError(response)
  return response.json() as Promise<T>
}
