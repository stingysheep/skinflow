import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { ArrowDownToLine, ArrowUpFromLine, TriangleAlert, WalletCards } from 'lucide-react'
import { Button, Dialog } from '../../../shared/components'
import { useListingNotifications } from '../../../shared/hooks/useListingNotifications'
import { submitListing } from '../api/inventoryApi'
import type { ListingPreview } from '../model/types'

type Props = {
  preview: ListingPreview | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmitted: () => void
}

type Level = { price: number; quantity: number }
type PreviewGroup = {
  name: string
  displayName: string
  imageUrl: string
  quantity: number
  buyerPays: number
  steamFee: number
  publisherFee: number
  proceeds: number
  costEach: number | null
  ratioPpm: number | null
  asks: Level[]
  bids: Level[]
  trend: Array<{ observed_at: number | null; median_price: number | null; lowest_ask: number | null; highest_bid: number | null; source?: 'csqaq' | 'legacy_snapshot' }>
  priceReachable: boolean
}

export function ListingPreviewDialog({ preview, open, onOpenChange, onSubmitted }: Props) {
  const [prices, setPrices] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const { trackListingRequest } = useListingNotifications()
  const groups = useMemo(() => groupPreviewItems(preview?.items ?? []), [preview])
  const pricedGroups = useMemo(() => groups.map((group) => applyBuyerPrice(group, prices[group.name])), [groups, prices])
  const totals = useMemo(() => pricedGroups.reduce((sum, group) => ({
    buyerPays: sum.buyerPays + group.buyerPays * group.quantity,
    proceeds: sum.proceeds + group.proceeds,
  }), { buyerPays: 0, proceeds: 0 }), [pricedGroups])

  useEffect(() => {
    if (!preview) return
    setPrices(Object.fromEntries(groups.map((group) => [group.name, (group.buyerPays / 100).toFixed(2)])))
    setSubmitError(null)
  }, [groups, preview])

  async function submit() {
    if (!preview) return
    const hasInvalidPrice = groups.some((group) => {
      const value = Number(prices[group.name])
      return !Number.isFinite(value) || value <= 0
    })
    if (hasInvalidPrice) {
      setSubmitError('请为每个物品组填写有效的买家支付价。')
      return
    }
    const parsed = Object.fromEntries(pricedGroups.map((group) => [group.name, group.buyerPays]))
    setSubmitting(true)
    setSubmitError(null)
    try {
      const request = await submitListing(preview.id, parsed)
      if (request.items.some((item) => item.status === 'failed')) {
        setSubmitError('Steam 拒绝了部分挂单，请查看挂单记录中的失败原因。')
        return
      }
      trackListingRequest(request.id)
      onSubmitted()
      onOpenChange(false)
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : '提交挂单失败，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (submitting && !nextOpen) return
    onOpenChange(nextOpen)
  }

  return <Dialog open={open} onOpenChange={handleOpenChange} trigger={<span />} contentClassName="listing-preview-dialog" title="确认 Steam 挂单" description="按同类物品核对盘口、买家支付价和预计实收；提交后仍需在 Steam 手机端确认。">
    {preview ? <div className="listing-preview">
      <div className="listing-preview-summary"><span>{groups.length} 个物品组</span><span>{preview.items.length} 件资产</span><span>预览有效至 {new Date(preview.expires_at).toLocaleTimeString()}</span></div>
      <div className="listing-preview-intro"><div><strong>本次挂单价格核对</strong><small>盘口在创建预览时从 Steam 实时刷新，默认采用最高求购价；输入价格仍按买家支付总价换算卖家实收。</small></div><div className="listing-preview-total"><span>{money(totals.buyerPays)}</span><small>买家支付合计 · 实收 {money(totals.proceeds)}</small></div></div>
      <div className="listing-preview-head"><span>物品组</span><span>数量</span><span>买家支付价（实际提交）</span><span>卖家实收</span><span>成本比例</span></div>
      {pricedGroups.map((group) => <div className="listing-preview-group" key={group.name}>
        <div className="listing-preview-row">
          <span className="listing-preview-name"><span className="preview-thumb">{group.imageUrl ? <img src={group.imageUrl} alt="" /> : null}</span><strong>{group.displayName}<small>{group.name}</small></strong></span>
          <span className="mono">{group.quantity}</span>
          <label className={group.priceReachable ? 'price-input' : 'price-input is-invalid'}><span>¥</span><input aria-label={`${group.displayName} 买家支付价（实际提交）`} value={prices[group.name] ?? ''} onChange={(event) => setPrices((current) => ({ ...current, [group.name]: event.target.value }))} onBlur={() => { const value = Number(prices[group.name]); if (Number.isFinite(value) && value > 0) setPrices((current) => ({ ...current, [group.name]: (group.buyerPays / 100).toFixed(2) })) }} inputMode="decimal" /></label>
          <span className="mono">{money(group.proceeds)}</span>
          <span className="mono">{group.ratioPpm === null ? '--' : (group.ratioPpm / 1_000_000).toFixed(3)}</span>
        </div>
        <div className="listing-trend-strip"><TrendPanel points={group.trend} /></div>
        <div className="listing-analysis-grid">
          <OrderBookPanel title="当前在售" subtitle="Steam 实时卖单 · 价格从低到高" icon={<ArrowDownToLine size={15} aria-hidden="true" />} levels={group.asks} tone="ask" />
          <OrderBookPanel title="当前求购" subtitle="Steam 实时买单 · 价格从高到低" icon={<ArrowUpFromLine size={15} aria-hidden="true" />} levels={group.bids} tone="bid" />
          <SettlementPanel group={group} />
        </div>
      </div>)}
      <div className="listing-caution"><TriangleAlert size={15} aria-hidden="true" /><span>此操作会向 Steam 提交真实挂单，不会自动执行手机确认，也不会提前记为成交。</span></div>
      {submitError ? <div className="listing-action-error" role="alert">{submitError}</div> : null}
      <div className="dialog-actions"><Button variant="ghost" disabled={submitting} onClick={() => handleOpenChange(false)}>手动关闭</Button><Button variant="primary" loading={submitting} disabled={submitting} onClick={() => void submit()}>确认并提交</Button></div>
    </div> : null}
  </Dialog>
}

function OrderBookPanel({ title, subtitle, icon, levels, tone }: { title: string; subtitle: string; icon: ReactNode; levels: Level[]; tone: 'ask' | 'bid' }) {
  const maxQuantity = Math.max(...levels.map((level) => level.quantity), 1)
  return <section className={`orderbook-panel is-${tone}`}>
    <div className="orderbook-panel-title"><div><h4>{title}</h4><small>{subtitle}</small></div>{icon}</div>
    <div className="orderbook-columns"><span>价格</span><span>数量</span></div>
    {levels.length ? <div className="orderbook-levels">{levels.map((level, index) => <div className={index === 0 ? 'orderbook-level is-best' : 'orderbook-level'} key={`${tone}-${level.price}`}><span className="orderbook-depth" style={{ '--depth-width': `${(level.quantity / maxQuantity) * 100}%` } as CSSProperties} /><code>{money(level.price)}</code><b>{level.quantity}</b></div>)}</div> : <div className="orderbook-empty">盘口不可用</div>}
  </section>
}

function SettlementPanel({ group }: { group: PreviewGroup }) {
  return <section className="settlement-panel">
    <div className="orderbook-panel-title"><div><h4>成本与结算</h4><small>按本组 {group.quantity} 件计算</small></div><WalletCards size={15} aria-hidden="true" /></div>
    <div className="settlement-rows"><div><span>成本均价</span><b>{money(group.costEach)}</b></div><div><span>Steam 手续费</span><b>{money(group.steamFee)}</b></div><div><span>发布方手续费</span><b>{money(group.publisherFee)}</b></div></div>
    <div className="settlement-total"><span>卖家实收</span><strong>{money(group.proceeds)}</strong></div>
    <div className="settlement-ratio"><span>成本比例</span><b>{group.ratioPpm === null ? '--' : (group.ratioPpm / 1_000_000).toFixed(3)}</b></div>
  </section>
}

function TrendPanel({ points }: { points: PreviewGroup['trend'] }) {
  const csqaqPoints = points.filter((point) => point.source !== 'legacy_snapshot')
  const values = csqaqPoints.map((point) => point.median_price ?? point.lowest_ask).filter((value): value is number => value != null)
  if (!values.length) return <section className="settlement-panel"><div className="orderbook-panel-title"><h4>Steam 价格走势</h4></div><div className="orderbook-empty">暂无 CSQAQ 图表数据</div></section>
  const min = Math.min(...values); const max = Math.max(...values); const range = Math.max(1, max - min)
  const pointsValue = values.map((value, index) => `${index / (values.length - 1) * 100},${90 - (value - min) / range * 70}`).join(' ')
  return <section className="settlement-panel trend-panel"><div className="orderbook-panel-title"><div><h4>Steam 价格走势</h4><small>CSQAQ 官方图表 · {csqaqPoints.length} 个数据点</small></div></div><div className="trend-chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Steam 价格走势"><polyline points={pointsValue} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" /></svg><div className="trend-axis"><span>{money(min)}</span><span>{money(max)}</span></div></div></section>
}

function groupPreviewItems(items: ListingPreview['items']): PreviewGroup[] {
  const groups = new Map<string, PreviewGroup>()
  for (const item of items) {
    const current = groups.get(item.market_hash_name)
    if (current) {
      current.quantity += 1
      current.steamFee += item.steam_fee
      current.publisherFee += item.publisher_fee
      current.proceeds += item.seller_proceeds
      continue
    }
    groups.set(item.market_hash_name, {
      name: item.market_hash_name,
      displayName: item.display_name,
      imageUrl: item.image_url,
      quantity: 1,
      buyerPays: item.buyer_pays,
      steamFee: item.steam_fee,
      publisherFee: item.publisher_fee,
      proceeds: item.seller_proceeds,
      costEach: item.cost_each,
      ratioPpm: item.ratio_ppm,
      asks: item.ask_levels ?? [],
      bids: item.bid_levels ?? [],
      trend: item.trend ?? [],
      priceReachable: true,
    })
  }
  return [...groups.values()]
}

function applyBuyerPrice(group: PreviewGroup, rawPrice: string | undefined): PreviewGroup {
  const value = Number(rawPrice)
  if (!Number.isFinite(value) || value <= 0) return group
  const buyerPays = Math.round(value * 100)
  const breakdown = feeBreakdownFromBuyerPays(buyerPays)
  if (breakdown === null) return { ...group, buyerPays, steamFee: 0, publisherFee: 0, proceeds: 0, ratioPpm: null, priceReachable: false }
  const ratio = group.costEach !== null && breakdown.sellerProceeds > 0 ? Math.floor(group.costEach * 1_000_000 / breakdown.sellerProceeds) : null
  return { ...group, buyerPays: breakdown.buyerPays, steamFee: breakdown.steamFee * group.quantity, publisherFee: breakdown.publisherFee * group.quantity, proceeds: breakdown.sellerProceeds * group.quantity, ratioPpm: ratio }
}

function feeBreakdownFromBuyerPays(buyerPays: number): { buyerPays: number; steamFee: number; publisherFee: number; sellerProceeds: number } | null {
  let low = 1
  let high = buyerPays
  let lower: ReturnType<typeof feeBreakdownFromBuyerPays> = null
  while (low <= high) {
    const receive = Math.floor((low + high) / 2)
    const steam = Math.max(7, Math.floor(receive * 0.05))
    const publisher = Math.max(7, Math.floor(receive * 0.10))
    const total = receive + steam + publisher
    if (total === buyerPays) return { buyerPays: total, steamFee: steam, publisherFee: publisher, sellerProceeds: receive }
    if (total < buyerPays) {
      lower = { buyerPays: total, steamFee: steam, publisherFee: publisher, sellerProceeds: receive }
      low = receive + 1
    }
    else high = receive - 1
  }
  return lower
}

const money = (value: number | null | undefined) => value == null ? '--' : `¥${(value / 100).toFixed(2)}`
