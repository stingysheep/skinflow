import { CircleAlert, ExternalLink, Gamepad2, LineChart, Store } from 'lucide-react'
import { buffMarketUrl, steamMarketUrl, youpinMarketUrl } from '../model/marketLinks'
import {
  modeLabel,
  modeRatio,
  modeRatioLabel,
  modeSteamPrice,
  actualProceeds,
  sourceDepth,
  sourceLabel,
} from '../model/scanPresentation'
import type { ScanMode, ScanResult } from '../model/types'
import { formatMoney, formatRatio } from '../model/formatters'

export function ScanInspector({ result, mode }: { result: ScanResult | null; mode: ScanMode }) {
  if (!result) return <aside className="market-inspector is-empty"><LineChart size={22} /><strong>选择一件物品</strong><span>从行情表格选择物品，查看盘口与结算分析。</span></aside>
  const last = result.curves.at(-1)
  const depth = sourceDepth(result)
  const ratio = modeRatio(result, mode)
  return <aside className="market-inspector">
    <div className="inspector-header"><span>选中物品</span><span>实时快照</span></div>
    <div className="inspector-item"><div className="hero-thumb"><img src={result.image_url} alt={`${result.name} 缩略图`} /></div><div><span className="asset-label">CS2 / {sourceLabel(result)} 进货</span><h2>{result.name}</h2><p>{result.market_hash_name}</p><small>STEAM / BUFF / 悠悠</small></div></div>
    <section className="inspector-callout"><div><span>当前方式</span><strong>{modeLabel(mode)}</strong><small>{ratio === null ? '当前深度不足，保留已获取行情。' : `按 ${sourceLabel(result)} 成本计算，比例越低越优。`}</small></div><b>{formatRatio(ratio)}</b></section>
    <section className="inspector-section"><div className="inspector-section-title"><span>当前报价</span><small>{result.fee_policy_version}</small></div><div className="quote-grid quote-grid-mode"><div><small>{sourceLabel(result)} 最低</small><strong>{formatMoney(result.acquisition_lowest_ask)}</strong><span>{depth} 件深度</span></div><div><small>Steam {modeLabel(mode)}</small><strong>{formatMoney(modeSteamPrice(result, mode))}</strong><span>{mode === 'listing' ? `${result.queue_ahead ?? '--'} 件排队` : `${result.steam_bid_depth} 件深度`}</span></div><div><small>实际到手</small><strong>{formatMoney(actualProceeds(result, mode))}</strong><span>按手续费规则估算</span></div><div><small>Steam 成交参考</small><strong>{formatMoney(result.steam_transaction_price)}</strong><span>csqaq 汇总</span></div></div></section>
    <section className="inspector-section"><div className="inspector-section-title"><span>1–10 件累计{modeRatioLabel(mode)}</span><small>小数口径</small></div><div className="ratio-sequence">{result.curves.map((point) => <span key={point.quantity}><i>{String(point.quantity).padStart(2, '0')}</i><b>{formatRatio(mode === 'listing' ? point.recommended_ratio_ppm : point.immediate_ratio_ppm)}</b><small>成本 {formatMoney(point.cost_total)}</small></span>)}</div></section>
    <section className="inspector-section"><div className="inspector-section-title"><span>盘口深度</span><small>不外推</small></div><div className="depth-list"><DepthRow label={sourceLabel(result)} value={`${Math.min(10, depth)} / 10`} tone={depth >= 10 ? 'normal' : 'warning'} /><DepthRow label={mode === 'listing' ? '在售' : '求购'} value={`${Math.min(10, mode === 'listing' ? result.steam_ask_depth : result.steam_bid_depth)} / 10`} tone={(mode === 'listing' ? result.steam_ask_depth : result.steam_bid_depth) >= 10 ? 'normal' : 'warning'} /></div></section>
    <section className="inspector-section settlement"><div className="inspector-section-title"><span>累计结算预览</span><small>{result.curves.length} 件</small></div><SettleRow label={`${sourceLabel(result)} 累计成本`} value={formatMoney(last?.cost_total ?? null)} /><SettleRow label={`Steam ${modeLabel(mode)}价格`} value={formatMoney(modeSteamPrice(result, mode))} /><SettleRow label="预计平台手续费" value={formatMoney(mode === 'listing' ? result.recommendation_fees : null)} /><SettleRow label="预计实收 / 成本比例" value={formatRatio(mode === 'listing' ? last?.recommended_ratio_ppm ?? null : last?.immediate_ratio_ppm ?? null)} total /><div className="inspector-warning"><CircleAlert size={14} /><span>{depth < 10 ? `${sourceLabel(result)} 前十件深度不足，缺少部分不补零。` : ratio === null ? `${modeLabel(mode)}行情不足，结果不外推。` : `已按${modeLabel(mode)}口径完成计算。`}</span></div></section>
    <MarketButtons result={result} />
  </aside>
}

function MarketButtons({ result }: { result: ScanResult }) {
  const links = [
    ...(result.acquisition_platform === 'buff' ? [['网易 BUFF', buffMarketUrl(result), <Store size={13} aria-hidden="true" />] as const] : [['悠悠有品', youpinMarketUrl(result), <Gamepad2 size={13} aria-hidden="true" />] as const]),
    ['Steam 行情', steamMarketUrl(result), <Gamepad2 size={13} aria-hidden="true" />] as const,
  ] as const
  return <nav className="inspector-market-links" aria-label="打开市场页面">{links.map(([label, href, icon]) => href ? <a key={label} href={href} target="_blank" rel="noreferrer">{icon}<span>{label}</span><ExternalLink size={12} aria-hidden="true" /></a> : null)}</nav>
}

function DepthRow({ label, value, tone }: { label: string; value: string; tone: 'normal' | 'warning' }) { return <div className="depth-line"><span>{label}</span><i><b className={tone} /></i><strong>{value}</strong></div> }
function SettleRow({ label, value, total = false }: { label: string; value: string; total?: boolean }) { return <div className={total ? 'settle-line total' : 'settle-line'}><span>{label}</span><strong>{value}</strong></div> }
