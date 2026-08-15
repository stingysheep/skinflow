import { useMemo, type CSSProperties } from 'react'
import { BarChart3, Clock3 } from 'lucide-react'
import type { InventoryGroupDetails as GroupDetails } from '../model/types'

type Props = { details: GroupDetails | null; loading: boolean; error: string | null }

export function InventoryGroupDetails({ details, loading, error }: Props) {
  if (loading) return <div className="inventory-detail-state">正在读取 Steam 行情…</div>
  if (error) return <div className="inventory-detail-state is-error" role="alert">{error}</div>
  if (!details) return <div className="inventory-detail-state">展开后读取最近行情与盘口。</div>

  const observed = details.current.observed_at ? new Date(details.current.observed_at).toLocaleString() : '暂无时间'
  return <div className="inventory-group-details">
    <div className="inventory-detail-head">
      <div><span className="detail-kicker">STEAM / MARKET DETAIL</span><h3>{details.display_name}</h3><small>{details.market_hash_name}</small></div>
      <span className="detail-observed"><Clock3 size={14} aria-hidden="true" /> {observed}</span>
    </div>
    <div className="inventory-detail-grid">
      <section className="inventory-detail-panel trend-panel">
        <div className="detail-panel-title"><span>最近价格走势</span><BarChart3 size={15} aria-hidden="true" /></div>
        <PriceTrend points={details.trend} />
      </section>
      <OrderBook title="当前在售" levels={details.current.ask_levels} tone="ask" empty="暂无在售数据" />
      <OrderBook title="当前求购" levels={details.current.bid_levels} tone="bid" empty="暂无求购数据" />
    </div>
  </div>
}

function PriceTrend({ points }: { points: GroupDetails['trend'] }) {
  const values = useMemo(() => points.filter((point) => point.source !== 'legacy_snapshot').map((point) => point.median_price ?? point.lowest_ask).filter((value): value is number => value != null), [points])
  if (values.length === 0) return <div className="trend-empty">暂无 CSQAQ 图表数据</div>
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = Math.max(1, max - min)
  const source = 'CSQAQ 官方图表'
  const coordinates = values.length === 1
    ? `0,55 100,55`
    : values.map((value, index) => `${(index / (values.length - 1)) * 100},${90 - ((value - min) / range) * 70}`).join(' ')
  return <div className="trend-chart" aria-label={`${source}提供的 Steam 价格走势，共 ${values.length} 个数据点`}>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-hidden="true"><polyline points={coordinates} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg>
    <div className="trend-axis"><span>{money(min)}</span><span>{money(max)}</span></div>
  </div>
}

function OrderBook({ title, levels, tone, empty }: { title: string; levels: Array<{ price: number; quantity: number }>; tone: 'ask' | 'bid'; empty: string }) {
  const max = Math.max(...levels.map((level) => level.quantity), 1)
  return <section className={`inventory-detail-panel orderbook-panel is-${tone}`}>
    <div className="detail-panel-title"><span>{title}</span><small>{levels.length ? `${levels.reduce((sum, level) => sum + level.quantity, 0)} 件深度` : '不可用'}</small></div>
    {levels.length ? <div className="detail-levels">{levels.map((level, index) => <div className="detail-level" key={`${tone}-${level.price}-${index}`}><span className="detail-level-bar" style={{ '--level-width': `${(level.quantity / max) * 100}%` } as CSSProperties} /><code>{money(level.price)}</code><b>{level.quantity}</b></div>)}</div> : <div className="trend-empty">{empty}</div>}
  </section>
}

const money = (value: number) => `¥${(value / 100).toFixed(2)}`
