import { useEffect, useMemo, useState } from 'react'
import { FeedbackState } from '../../../shared/components'
import { ApiError } from '../../../shared/api/client'
import { usePersistentState } from '../../../shared/hooks/usePersistentState'
import { cancelScan, createScan, getScan } from '../api/scanApi'
import { ScanInspector } from '../components/ScanInspector'
import { ScanCriteriaBar } from '../components/ScanCriteriaBar'
import { ScanResultTable } from '../components/ScanResultTable'
import { ScanSummary } from '../components/ScanSummary'
import { ScanToolbar } from '../components/ScanToolbar'
import { useScanEvents } from '../hooks/useScanEvents'
import { scanFailureMessage } from '../model/formatters'
import { modeRatio, resultIsReady, sourceDepth } from '../model/scanPresentation'
import type { ScanCriteria, ScanResult, ScanStatus } from '../model/types'

const DEFAULT_CRITERIA: ScanCriteria = { candidateLimit: 20, mode: 'listing', platforms: ['buff'], minPriceYuan: '', maxPriceYuan: '', minDailyVolume: 0 }

export function ScanPage() {
  const [criteria, setCriteria] = usePersistentState<ScanCriteria>('skinflow.scan.criteria', loadCriteria())
  const [jobId, setJobId] = useState<string | null>(() => window.sessionStorage.getItem('skinflow.scan.jobId'))
  const [status, setStatus] = useState<ScanStatus | null>(null)
  const [selectedName, setSelectedName] = useState<string | null>(null)
  const initialView = loadViewSettings()
  const [query, setQuery] = usePersistentState('skinflow.scan.query', initialView.query)
  const [sort, setSort] = usePersistentState<'ratio' | 'volume'>('skinflow.scan.sort', initialView.sort)
  const [resultFilter, setResultFilter] = usePersistentState<'all' | 'ready' | 'depth'>('skinflow.scan.resultFilter', initialView.resultFilter)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventState = useScanEvents(jobId)
  const events = eventState.events
  useEffect(() => {
    if (!jobId) return
    if (status && ['cancelled', 'succeeded', 'failed'].includes(status)) return
    const timer = window.setInterval(() => void getScan(jobId).then((job) => {
      setStatus(job.status)
      if (job.status === 'failed') setError(scanFailureMessage(job.failure_code))
    }).catch((reason) => setError(errorMessage(reason))), 1000)
    return () => window.clearInterval(timer)
  }, [jobId, status])
  const results = useMemo(() => events.filter((event) => event.type === 'result.created').map((event) => event.payload as unknown as ScanResult), [events])
  const discoveredCount = useMemo(() => new Set(events.filter((event) => event.type === 'candidate.discovered').map((event) => event.payload.market_hash_name)).size, [events])
  const visibleResults = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    const filtered = results.filter((result) => {
      const matchesQuery = !normalized || `${result.name} ${result.market_hash_name}`.toLocaleLowerCase().includes(normalized)
      const matchesFilter = resultFilter === 'all' || (resultFilter === 'ready' ? resultIsReady(result, criteria.mode) : sourceDepth(result) < 10 || (criteria.mode === 'listing' ? result.steam_ask_depth < 10 : result.steam_bid_depth < 10))
      return matchesQuery && matchesFilter
    })
    return [...filtered].sort((a, b) => {
      if (sort === 'volume') return (b.daily_volume ?? 0) - (a.daily_volume ?? 0)
      const left = modeRatio(a, criteria.mode)
      const right = modeRatio(b, criteria.mode)
      if (left === null) return 1
      if (right === null) return -1
      return left - right
    })
  }, [criteria.mode, query, resultFilter, results, sort])
  const selected = visibleResults.find((result) => result.market_hash_name === selectedName) ?? visibleResults[0] ?? null
  const youpinUnavailableCount = criteria.platforms.includes('youpin') ? events.filter((event) => (
    event.type === 'candidate.source_unavailable' && event.payload.platform === 'youpin'
  ) || (
    event.type === 'candidate.rejected' && event.payload.reason_code === 'UPSTREAM_UNAVAILABLE'
  )).length : 0
  const start = async () => {
    setStarting(true); setError(null); setSelectedName(null)
    try {
      const job = await createScan(criteria)
      if (!job.job_id) throw new Error('扫描任务创建失败：服务未返回任务编号。')
      setJobId(job.job_id)
      window.sessionStorage.setItem('skinflow.scan.jobId', job.job_id)
      setStatus(job.status as ScanStatus)
    } catch (reason) {
      setError(errorMessage(reason))
    } finally {
      setStarting(false)
    }
  }
  const cancel = async () => {
    if (!jobId) return
    setError(null)
    try {
      const job = await cancelScan(jobId)
      setStatus(job.status)
    } catch (reason) {
      setError(errorMessage(reason))
    }
  }
  return <div className="market-studio">
    <ScanToolbar limit={criteria.candidateLimit} onLimit={(candidateLimit) => setCriteria({ ...criteria, candidateLimit })} mode={criteria.mode} platforms={criteria.platforms} status={status} query={query} onQuery={setQuery} sort={sort} onSort={setSort} filter={resultFilter} onFilter={setResultFilter} starting={starting} onStart={() => void start()} onCancel={() => void cancel()} />
    <ScanCriteriaBar criteria={criteria} disabled={status === 'queued' || status === 'running' || status === 'cancelling'} onChange={setCriteria} />
    <ScanSummary status={status} resultCount={results.length} candidateLimit={criteria.candidateLimit} discoveredCount={discoveredCount} connection={eventState.connection} connectionError={eventState.lastError} rejectedCount={events.filter((event) => event.type === 'candidate.rejected').length} backoffCount={events.filter((event) => event.type === 'upstream.backoff_started').length} sourceUnavailableCount={youpinUnavailableCount} platforms={criteria.platforms} />
    <div className="market-workspace">
      <section className="market-results">
        {error ? <div className="scan-empty"><FeedbackState kind="error" title="扫描未完成" description={error} /></div> : starting ? <div className="scan-empty"><FeedbackState kind="empty" title="正在创建扫描任务" description="任务建立后，候选结果会逐件追加到表格。" /></div> : results.length ? <ScanResultTable results={visibleResults} mode={criteria.mode} selectedName={selected?.market_hash_name ?? null} onSelect={setSelectedName} filter={resultFilter} onFilter={setResultFilter} /> : <div className="scan-empty"><FeedbackState kind="empty" title={status === 'succeeded' ? '没有获取到候选' : '等待扫描结果'} description={status === 'succeeded' && youpinUnavailableCount ? '悠悠公开接口未返回数据，结果未使用虚假价格；请稍后重试或暂时选择 BUFF。' : status === 'succeeded' ? '当前筛选条件没有返回可分析的 CS2 物品，请调整价格或成交量。' : '开始扫描后，结果会在每件物品完成时追加到表格。'} /></div>}
      </section>
      <ScanInspector result={selected} mode={criteria.mode} />
    </div>
  </div>
}

function errorMessage(reason: unknown) {
  if (reason instanceof ApiError && reason.code === 'CONFLICT') return '已有扫描任务正在运行，请等待完成或先取消当前任务。'
  return reason instanceof Error ? reason.message : '无法启动扫描任务'
}

function loadCriteria(): ScanCriteria {
  try {
    const stored = window.localStorage.getItem('skinflow.scan.criteria')
    if (!stored) return DEFAULT_CRITERIA
    const value = JSON.parse(stored) as Partial<ScanCriteria>
    if (value.mode !== 'listing' && value.mode !== 'buy_order') return DEFAULT_CRITERIA
    if (!Array.isArray(value.platforms) || value.platforms.length < 1) return DEFAULT_CRITERIA
    return { ...DEFAULT_CRITERIA, ...value } as ScanCriteria
  } catch {
    return DEFAULT_CRITERIA
  }
}

function loadViewSettings(): { query: string; sort: 'ratio' | 'volume'; resultFilter: 'all' | 'ready' | 'depth' } {
  try {
    const stored = window.localStorage.getItem('skinflow.scan.view')
    if (!stored) return { query: '', sort: 'ratio', resultFilter: 'all' }
    const value = JSON.parse(stored) as Partial<ReturnType<typeof loadViewSettings>>
    return {
      query: typeof value.query === 'string' ? value.query : '',
      sort: value.sort === 'volume' ? 'volume' : 'ratio',
      resultFilter: value.resultFilter === 'ready' || value.resultFilter === 'depth' ? value.resultFilter : 'all',
    }
  } catch {
    return { query: '', sort: 'ratio', resultFilter: 'all' }
  }
}
