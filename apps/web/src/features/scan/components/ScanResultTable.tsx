import { Fragment, useState } from 'react'
import { ChevronDown, ChevronRight, ExternalLink, Gamepad2, Store } from 'lucide-react'
import { Button, DataTableFrame } from '../../../shared/components'
import { buffMarketUrl, steamMarketUrl, youpinMarketUrl } from '../model/marketLinks'
import { actualProceeds, modeLabel, modeRatio, modeRatioLabel, modeSteamPrice, sourceLabel } from '../model/scanPresentation'
import type { ScanMode, ScanResult } from '../model/types'
import { formatMoney, formatRatio } from '../model/formatters'
import { ScanResultDetails } from './ScanResultDetails'

type Props = { results: ScanResult[]; mode: ScanMode; selectedName: string | null; onSelect: (name: string) => void; filter: 'all' | 'ready' | 'depth'; onFilter: (filter: 'all' | 'ready' | 'depth') => void }

export function ScanResultTable({ results, mode, selectedName, onSelect, filter, onFilter }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  return <DataTableFrame className="market-table-frame"><div className="result-filter-bar"><strong>实时机会 · {modeLabel(mode)}</strong><button className={filter === 'all' ? 'is-active' : ''} type="button" onClick={() => onFilter('all')}>全部</button><button className={filter === 'ready' ? 'is-active' : ''} type="button" onClick={() => onFilter('ready')}>可执行</button><button className={filter === 'depth' ? 'is-active' : ''} type="button" onClick={() => onFilter('depth')}>深度不足</button><span>{results.length} 条结果</span></div><table className="scan-table"><thead><tr><th className="index-col">#</th><th>物品</th><th>进货最低</th><th>Steam {modeLabel(mode)}</th><th>实际到手</th><th>{modeRatioLabel(mode)}</th><th>日成交量</th><th>市场</th><th /></tr></thead><tbody>
    {results.map((result) => {
      const open = expanded.has(result.market_hash_name)
      const selected = selectedName === result.market_hash_name
      return <Fragment key={result.market_hash_name}>
        <tr className={selected ? 'result-row is-selected' : 'result-row'} onClick={() => { onSelect(result.market_hash_name); setExpanded((current) => { const next = new Set(current); if (open) next.delete(result.market_hash_name); else next.add(result.market_hash_name); return next }) }}>
          <td className="index-col">{String(results.indexOf(result) + 1).padStart(2, '0')}</td>
          <td className="item-cell">{result.image_url ? <img src={result.image_url} alt={`${result.name} 缩略图`} /> : <span className="item-placeholder" />}<span><strong>{result.name}</strong><small>{result.market_hash_name}</small></span></td>
          <td>{formatMoney(result.acquisition_lowest_ask)} <small className="source-hint">{sourceLabel(result)}</small></td><td>{formatMoney(modeSteamPrice(result, mode))}</td><td className="proceeds-value">{formatMoney(actualProceeds(result, mode))}</td>
          <td className="positive-value">{formatRatio(modeRatio(result, mode))}</td>
          <td>{result.daily_volume === null ? '--' : <VolumeMeter value={result.daily_volume} max={Math.max(...results.map((item) => item.daily_volume ?? 0), 1)} />}</td>
          <td><MarketLinks result={result} /></td>
          <td><Button variant="ghost" aria-label={`${open ? '收起' : '展开'} ${result.name}`} icon={open ? <ChevronDown size={15} /> : <ChevronRight size={15} />} onClick={(event) => { event.stopPropagation(); setExpanded((current) => { const next = new Set(current); if (open) next.delete(result.market_hash_name); else next.add(result.market_hash_name); return next }) }} /></td>
        </tr>
        {open ? <tr key={`${result.market_hash_name}-details`}><td colSpan={9}><ScanResultDetails result={result} mode={mode} /></td></tr> : null}
      </Fragment>
    })}
  </tbody></table></DataTableFrame>
}

function MarketLinks({ result }: { result: ScanResult }) {
  const links = [
    ...(result.acquisition_platform === 'buff' ? [['BUFF', buffMarketUrl(result), <Store size={12} aria-hidden="true" />] as const] : [['UU有品', youpinMarketUrl(result), <Gamepad2 size={12} aria-hidden="true" />] as const]),
    ['Steam 行情', steamMarketUrl(result), <Gamepad2 size={12} aria-hidden="true" />] as const,
  ] as const
  return <span className="market-links">{links.map(([label, href, icon]) => href ? <a className="market-link-button" key={label} href={href} target="_blank" rel="noreferrer" title={`打开 ${label}`} aria-label={`在 ${label} 打开 ${result.name}`} onClick={(event) => event.stopPropagation()}>{icon}<span>{label}</span><ExternalLink size={11} aria-hidden="true" /></a> : null)}</span>
}

function VolumeMeter({ value, max }: { value: number; max: number }) {
  return <span className="volume-meter"><i style={{ width: `${Math.max(4, Math.round(value / max * 100))}%` }} /><b>{value.toLocaleString()}</b></span>
}
