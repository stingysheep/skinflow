import { useEffect, useState, type ReactNode } from 'react'
import { ArrowDownToLine, ArrowUpFromLine, BarChart3 } from 'lucide-react'
import { getScanCharts } from '../api/scanApi'
import type { MarketLevel, ScanMode, ScanResult } from '../model/types'
import type { PlatformTrendPoint } from '../model/types'
import { formatMoney } from '../model/formatters'

export function ScanResultDetails({ result }: { result: ScanResult; mode: ScanMode }) {
  const [chartState, setChartState] = useState<{ key: string; trends: Record<string, PlatformTrendPoint[]>; error: boolean }>({ key: '', trends: {}, error: false })
  const asks = result.steam_ask_levels ?? []
  const bids = result.steam_bid_levels ?? []
  const platformQuery = result.acquisition_platform === 'buff' ? 'buff,steam' : 'youpin,steam'
  const platforms = platformQuery.split(',')
  const jobId = result.job_id
  const chartKey = `${jobId ?? 'missing'}:${result.market_hash_name}:${platformQuery}`
  const charts = chartState.key === chartKey ? chartState.trends : null
  const chartError = chartState.key === chartKey && chartState.error
  useEffect(() => {
    let cancelled = false
    // The job id is attached by the table through the result event payload.
    if (!jobId) {
      return () => { cancelled = true }
    }
    void getScanCharts(jobId, result.market_hash_name, platformQuery.split(','))
      .then((response) => { if (!cancelled) setChartState({ key: chartKey, trends: response.trends, error: false }) })
      .catch(() => { if (!cancelled) setChartState({ key: chartKey, trends: {}, error: true }) })
    return () => { cancelled = true }
  }, [jobId, result.market_hash_name, platformQuery, chartKey])
  const trend = charts?.steam ?? result.steam_trend ?? []
  return <div className="scan-details">
    <div className="scan-detail-trends">{platforms.map((platform) => <section className="scan-detail-chart" key={platform}><div className="scan-detail-title"><span><BarChart3 size={15} aria-hidden="true" /> {platform === 'steam' ? 'Steam' : platform === 'buff' ? 'BUFF' : '悠悠'} 价格走势</span><small>CSQAQ 官方图表 · {(charts?.[platform] ?? []).length} 个数据点</small></div>{charts === null && !chartError && jobId ? <div className="scan-detail-empty">正在读取 CSQAQ 走势…</div> : <PriceTrend points={charts?.[platform] ?? (platform === 'steam' ? trend : [])} />}</section>)}</div>
    <div className="scan-detail-books"><OrderBook title="Steam 在售" levels={asks} tone="ask" icon={<ArrowDownToLine size={14} aria-hidden="true" />} /><OrderBook title="Steam 求购" levels={bids} tone="bid" icon={<ArrowUpFromLine size={14} aria-hidden="true" />} /></div>
  </div>
}

function PriceTrend({ points }: { points: NonNullable<ScanResult['steam_trend']> }) {
  const values = points.map((point) => point.price).filter((value): value is number => value != null)
  if (!values.length) return <div className="scan-detail-empty">暂无 CSQAQ 图表数据</div>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = Math.max(1, max - min)
  const coordinates = values.length === 1
    ? '0,55 100,55'
    : values.map((value, index) => `${index / (values.length - 1) * 100},${90 - (value - min) / range * 70}`).join(' ')
  return <div className="scan-detail-trend"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Steam 价格走势"><polyline points={coordinates} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg><div><span>{formatMoney(min)}</span><span>{formatMoney(max)}</span></div></div>
}

function OrderBook({ title, levels, tone, icon }: { title: string; levels: MarketLevel[]; tone: 'ask' | 'bid'; icon: ReactNode }) {
  const max = Math.max(...levels.map((level) => level.quantity), 1)
  return <section className={`scan-detail-book is-${tone}`}><h4>{icon}{title}<small>{levels.length ? `${levels.reduce((sum, level) => sum + level.quantity, 0)} 件深度` : '不可用'}</small></h4>{levels.length ? levels.map((level, index) => <div className="scan-book-level" key={`${tone}-${level.price}-${index}`}><i style={{ width: `${Math.max(4, level.quantity / max * 100)}%` }} /><code>{formatMoney(level.price)}</code><b>{level.quantity}</b></div>) : <div className="scan-detail-empty">暂无盘口数据</div>}</section>
}
