import { Filter, Play, Search, SlidersHorizontal, Square } from 'lucide-react'
import { Button } from '../../../shared/components'
import type { ScanMode, ScanStatus } from '../model/types'
import { RatioCalculator } from './RatioCalculator'

export type ResultFilter = 'all' | 'ready' | 'depth'

type Props = { limit: number; onLimit: (value: number) => void; mode: ScanMode; platforms: string[]; status: ScanStatus | null; query: string; onQuery: (value: string) => void; sort: 'ratio' | 'volume'; onSort: (value: 'ratio' | 'volume') => void; filter: ResultFilter; onFilter: (value: ResultFilter) => void; starting: boolean; onStart: () => void; onCancel: () => void }

export function ScanToolbar({ limit, onLimit, mode, platforms, status, query, onQuery, sort, onSort, filter, onFilter, starting, onStart, onCancel }: Props) {
  const active = status === 'queued' || status === 'running' || status === 'cancelling'
  return <>
    <header className="studio-header">
      <div className="studio-title"><p className="eyebrow">SKINFLOW / CS2 MARKET</p><h1>市场扫描</h1><span>匿名行情 · CNY · 实时分析</span></div>
    <div className="studio-meta"><RatioCalculator /><span>VISUAL MARKET WORKSPACE</span><span>·</span><span>2026.08.14</span></div>
    </header>
    <div className="command-bar">
      <div className="command-label"><strong>市场扫描</strong><span>CS2 饰品机会</span></div>
      <label className="search-control"><Search size={16} aria-hidden="true" /><input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="搜索中文或市场名称" /></label>
      <label className="tool-control"><Filter size={16} aria-hidden="true" /><select aria-label="筛选扫描结果" value={filter} onChange={(event) => onFilter(event.target.value as ResultFilter)}><option value="all">全部结果</option><option value="ready">可推荐</option><option value="depth">深度不足</option></select></label>
      <label className="tool-control"><SlidersHorizontal size={14} aria-hidden="true" /><select aria-label="结果排序" value={sort} onChange={(event) => onSort(event.target.value as Props['sort'])}><option value="ratio">{mode === 'listing' ? '挂底价比例' : '丢求购比例'}（低优先）</option><option value="volume">成交量（高优先）</option></select></label>
      <label className="limit-control">候选<input type="number" min={1} max={200} value={limit} onChange={(event) => onLimit(Number(event.target.value))} disabled={active} /></label>
      <span className="command-spacer" />
      <span className="connection-state"><i />{platforms.map((value) => value === 'youpin' ? '悠悠' : 'BUFF').join(' · ')} · STEAM</span>
      {active ? <Button variant="danger" icon={<Square size={16} />} onClick={onCancel}>取消</Button> : <Button variant="primary" icon={<Play size={16} />} loading={starting} onClick={onStart}>扫描</Button>}
    </div>
  </>
}
