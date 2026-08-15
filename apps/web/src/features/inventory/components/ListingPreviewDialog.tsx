import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import { ArrowDownToLine, ArrowUpFromLine, CheckCircle2, TriangleAlert, WalletCards } from 'lucide-react'
import { Button, Dialog } from '../../../shared/components'
import { submitListing } from '../api/inventoryApi'
import { getListingRequest, type ListingRequest } from '../../listings/api/listingsApi'
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
  const [submittedRequest, setSubmittedRequest] = useState<ListingRequest | null>(null)
  const [trackingPhase, setTrackingPhase] = useState<'idle' | 'waiting' | 'success' | 'failed'>('idle')
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
    setSubmittedRequest(null)
    setTrackingPhase('idle')
  }, [groups, preview])

  useEffect(() => {
    const requestId = submittedRequest?.id
    if (!requestId || trackingPhase === 'success' || trackingPhase === 'failed') return
    const controller = new AbortController()
    const poll = async () => {
      try {
        const next = await getListingRequest(requestId, controller.signal)
        setSubmittedRequest(next)
        const statuses = next.items.map((item) => item.status)
        if (statuses.some((status) => status === 'failed')) setTrackingPhase('failed')
        else if (statuses.length > 0 && statuses.every((status) => status === 'active')) setTrackingPhase('success')
        else setTrackingPhase('waiting')
      } catch { /* keep polling while Steam is processing */ }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 1000)
    return () => { window.clearInterval(timer); controller.abort() }
  }, [submittedRequest?.id, trackingPhase])

  useEffect(() => {
    if (trackingPhase !== 'success') return
    const timer = window.setTimeout(() => onOpenChange(false), 5000)
    return () => window.clearTimeout(timer)
  }, [onOpenChange, trackingPhase])

  async function submit() {
    if (!preview) return
    const parsed = Object.fromEntries(groups.map((group) => {
      const value = Number(prices[group.name])
      return [group.name, Number.isFinite(value) && value > 0 ? Math.round(value * 100) : 0]
    }))
    if (Object.values(parsed).some((value) => value < 1)) {
      setSubmitError('请为每个物品组填写有效的买家支付价。')
      return
    }
    if (pricedGroups.some((group) => !group.priceReachable)) {
      setSubmitError('当前手续费规则无法精确产生该买家支付价，请调整到相邻可达金额。')
      return
    }
    setSubmitting(true)
    setSubmitError(null)
    try {
      const request = await submitListing(preview.id, parsed)
      setSubmittedRequest({ id: request.id, status: request.status, created_at: Date.now(), completed_at: null, items: request.items.map((item, index) => ({
        id: item.id ?? preview.items[index]?.id ?? String(index),
        assetid: item.assetid ?? preview.items[index]?.assetid ?? String(index),
        status: item.status,
        steam_listing_id: item.steam_listing_id,
        message: item.message,
        market_hash_name: item.market_hash_name ?? preview.items[index]?.market_hash_name ?? '',
        display_name: item.display_name ?? preview.items[index]?.display_name ?? '',
        image_url: item.image_url ?? preview.items[index]?.image_url ?? '',
        wear_text: item.wear_text ?? null,
        cost_each: item.cost_each ?? preview.items[index]?.cost_each ?? null,
        buyer_pays: item.buyer_pays ?? preview.items[index]?.buyer_pays ?? 0,
        seller_proceeds: item.seller_proceeds ?? preview.items[index]?.seller_proceeds ?? 0,
      })) })
      setTrackingPhase('waiting')
      onSubmitted()
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : '提交挂单失败，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return <Dialog open={open} onOpenChange={onOpenChange} trigger={<span />} contentClassName="listing-preview-dialog" title="确认 Steam 挂单" description="按同类物品核对盘口、买家支付价和预计实收；提交后仍需在 Steam 手机端确认。">
    {preview ? <div className="listing-preview">
      <div className="listing-preview-summary"><span>{groups.length} 个物品组</span><span>{preview.items.length} 件资产</span><span>预览有效至 {new Date(preview.expires_at).toLocaleTimeString()}</span></div>
      <div className="listing-preview-intro"><div><strong>本次挂单价格核对</strong><small>输入的是买家支付价（实际提交总价）；Steam 请求会按规则换算卖家实收，避免把两种价格混用。</small></div><div className="listing-preview-total"><span>{money(totals.buyerPays)}</span><small>买家支付合计 · 实收 {money(totals.proceeds)}</small></div></div>
      <div className="listing-preview-head"><span>物品组</span><span>数量</span><span>买家支付价（实际提交）</span><span>卖家实收</span><span>成本比例</span></div>
      {pricedGroups.map((group) => <div className="listing-preview-group" key={group.name}>
        <div className="listing-preview-row">
          <span className="listing-preview-name"><span className="preview-thumb">{group.imageUrl ? <img src={group.imageUrl} alt="" /> : null}</span><strong>{group.displayName}<small>{group.name}</small></strong></span>
          <span className="mono">{group.quantity}</span>
          <label className={group.priceReachable ? 'price-input' : 'price-input is-invalid'}><span>¥</span><input aria-label={`${group.displayName} 买家支付价（实际提交）`} value={prices[group.name] ?? ''} onChange={(event) => setPrices((current) => ({ ...current, [group.name]: event.target.value }))} inputMode="decimal" /></label>
          <span className="mono">{money(group.proceeds)}</span>
          <span className="mono">{group.ratioPpm === null ? '--' : (group.ratioPpm / 1_000_000).toFixed(3)}</span>
        </div>
        <div className="listing-trend-strip"><TrendPanel points={group.trend} /></div>
        <div className="listing-analysis-grid">
          <OrderBookPanel title="当前在售" subtitle="卖单深度 · 价格从低到高" icon={<ArrowDownToLine size={15} aria-hidden="true" />} levels={group.asks} tone="ask" />
          <OrderBookPanel title="当前求购" subtitle="买单深度 · 价格从高到低" icon={<ArrowUpFromLine size={15} aria-hidden="true" />} levels={group.bids} tone="bid" />
          <SettlementPanel group={group} />
        </div>
      </div>)}
      <div className="listing-caution"><TriangleAlert size={15} aria-hidden="true" /><span>此操作会向 Steam 提交真实挂单，不会自动执行手机确认，也不会提前记为成交。</span></div>
      {submitError ? <div className="listing-action-error" role="alert">{submitError}</div> : null}
      {trackingPhase === 'waiting' ? <div className="listing-tracking is-waiting"><span className="tracking-spinner" />正在读取 Steam 上架状态…<small>手机确认完成后会自动更新。</small></div> : null}
      {trackingPhase === 'success' ? <div className="listing-tracking is-success"><CheckCircle2 size={17} />已确认全部挂单成功，5 秒后自动关闭。</div> : null}
      {trackingPhase === 'failed' ? <div className="listing-tracking is-failed" role="alert"><TriangleAlert size={17} />部分挂单失败，请返回调整后重试。</div> : null}
      <div className="dialog-actions"><Button variant="ghost" onClick={() => onOpenChange(false)}>{trackingPhase === 'failed' ? '返回修改' : '手动关闭'}</Button>{trackingPhase === 'idle' ? <Button variant="primary" loading={submitting} onClick={() => void submit()}>确认并提交</Button> : null}</div>
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
  const receive = receiveFromBuyerPays(buyerPays)
  if (receive === null) return { ...group, buyerPays, steamFee: 0, publisherFee: 0, proceeds: 0, ratioPpm: null, priceReachable: false }
  const steamFee = receive > 0 ? Math.max(5, Math.floor(receive * 0.05)) : 0
  const publisherFee = receive > 0 ? Math.max(5, Math.floor(receive * 0.10)) : 0
  const ratio = group.costEach !== null && receive > 0 ? Math.floor(group.costEach * 1_000_000 / receive) : null
  return { ...group, buyerPays, steamFee: steamFee * group.quantity, publisherFee: publisherFee * group.quantity, proceeds: receive * group.quantity, ratioPpm: ratio }
}

function receiveFromBuyerPays(buyerPays: number): number | null {
  let low = 1
  let high = buyerPays
  while (low <= high) {
    const receive = Math.floor((low + high) / 2)
    const steam = Math.max(5, Math.floor(receive * 0.05))
    const publisher = Math.max(5, Math.floor(receive * 0.10))
    const total = receive + steam + publisher
    if (total === buyerPays) return receive
    if (total < buyerPays) low = receive + 1
    else high = receive - 1
  }
  return null
}

const money = (value: number | null | undefined) => value == null ? '--' : `¥${(value / 100).toFixed(2)}`
