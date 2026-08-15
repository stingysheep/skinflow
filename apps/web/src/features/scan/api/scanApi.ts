import { getJson, postJson } from '../../../shared/api/client'
import type { ScanCharts, ScanCriteria, ScanEvent, ScanJob } from '../model/types'

const chartCache = new Map<string, ScanCharts>()

export function createScan(criteria: ScanCriteria) {
  return postJson<{ job_id: string; status: string }>('/api/scans', {
    source_mode: 'csqaq',
    candidate_limit: criteria.candidateLimit,
    manual_names: [],
    operation_mode: criteria.mode,
    acquisition_platforms: criteria.platforms,
    min_price: yuanToCents(criteria.minPriceYuan),
    max_price: yuanToCents(criteria.maxPriceYuan),
    min_daily_volume: criteria.minDailyVolume,
  })
}

export function getScan(jobId: string) { return getJson<ScanJob>(`/api/scans/${jobId}`) }
export function cancelScan(jobId: string) { return postJson<ScanJob>(`/api/scans/${jobId}/cancel`) }
export function getScanEvents(jobId: string, after: number) {
  return getJson<ScanEvent[]>(`/api/scans/${jobId}/events?after=${after}`)
}

export function scanEventStreamUrl(jobId: string, after: number) {
  return `/api/scans/${jobId}/stream?after=${after}`
}

export async function getScanCharts(jobId: string, marketHashName: string, platforms: string[]): Promise<ScanCharts> {
  const cacheKey = `${jobId}:${marketHashName}:${platforms.join(',')}`
  const cached = chartCache.get(cacheKey)
  if (cached) return cached
  const query = encodeURIComponent(platforms.join(','))
  const result = await getJson<ScanCharts>(`/api/scans/${jobId}/results/${encodeURIComponent(marketHashName)}/charts?platforms=${query}`)
  chartCache.set(cacheKey, result)
  return result
}

function yuanToCents(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const number = Number(trimmed)
  return Number.isFinite(number) && number > 0 ? Math.round(number * 100) : null
}
