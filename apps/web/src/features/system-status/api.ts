import { getJson } from '../../shared/api/client'

export type HealthStatus = {
  status: 'ok'
  service: string
  api_version: string
  environment: string
}

export function fetchHealth(signal?: AbortSignal) {
  return getJson<HealthStatus>('/api/health', signal)
}

