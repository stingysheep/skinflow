import { useEffect, useState } from 'react'
import { ClipboardList, RefreshCw, XCircle } from 'lucide-react'
import { Button, FeedbackState } from '../../../shared/components'
import { cancelListingItems, getListingRequests, reconcileListingRequests, type ListingRequest } from '../api/listingsApi'
import '../listings.css'

const date = (stamp: number) => new Date(stamp).toLocaleString('zh-CN', { hour12: false })
const money = (value: number | null) => value == null ? '--' : `¥${(value / 100).toFixed(2)}`

export function ListingsPage() {
  const [items, setItems] = useState<ListingRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [cancelling, setCancelling] = useState(false)
  const load = () => getListingRequests().then((data) => setItems(data.items)).finally(() => setLoading(false))
  useEffect(() => { void load() }, [])
  async function sync() { setSyncing(true); try { await reconcileListingRequests(); await load() } finally { setSyncing(false) } }
  async function cancelSelected() {
    if (!selected.size || !window.confirm(`确认取消选中的 ${selected.size} 个挂单？`)) return
    setCancelling(true)
    try { await cancelListingItems([...selected]); setSelected(new Set()); await load() } finally { setCancelling(false) }
  }
  const statusLabel: Record<string, string> = { pending_confirmation: '待手机确认', active: '在售', sold: '已售出', cancelled: '已取消', pending_reconciliation: '待同步', submitted: '已提交', partially_sold: '部分售出', completed: '已完成' }
  return <div className="workspace-page"><header className="module-header"><div><span className="eyebrow">SKINFLOW / LISTINGS</span><h1>挂单记录</h1><p>Steam 挂单状态与真实成交同步</p></div><ClipboardList size={22} aria-hidden="true" /></header><div className="ledger-command"><span>自动同步每 60 秒运行</span><div className="command-spacer" /><Button variant="danger" icon={<XCircle size={16} />} disabled={!selected.size || cancelling} loading={cancelling} onClick={() => void cancelSelected()}>取消所选挂单</Button><Button icon={<RefreshCw size={16} />} loading={syncing} onClick={() => void sync()}>立即同步</Button></div>{loading ? <div className="module-empty">正在读取挂单记录…</div> : items.length ? <div className="listing-history">{items.map((request) => <article key={request.id}><header><strong>{statusLabel[request.status] ?? request.status}</strong><span>{date(request.created_at)}</span><code>{request.id.slice(0, 8)}</code></header><div className="listing-history-columns"><span>物品</span><span>成本</span><span>挂出价格</span><span>状态</span><span>Steam listing</span></div>{request.items.map((item) => { const canCancel = ['pending_confirmation', 'active'].includes(item.status) && Boolean(item.steam_listing_id); return <div className="listing-history-row" key={item.id}><span className="listing-item-asset"><input type="checkbox" checked={selected.has(item.id)} disabled={!canCancel} aria-label={`选择取消 ${item.display_name}`} onChange={(event) => setSelected((current) => { const next = new Set(current); if (event.target.checked) next.add(item.id); else next.delete(item.id); return next })} /><span className="listing-history-thumb">{item.image_url ? <img src={item.image_url} alt="" /> : null}</span><span><strong>{item.display_name}{item.wear_text ? ` · ${item.wear_text}` : ''}</strong><small>{item.market_hash_name}</small></span></span><span>{money(item.cost_each)}</span><span>{money(item.buyer_pays)}</span><span className={item.status === 'sold' ? 'is-sold' : ''}>{statusLabel[item.status] ?? item.status}</span><code>{item.steam_listing_id ?? item.message ?? '--'}</code></div> })}</article>)}</div> : <FeedbackState kind="empty" title="暂无挂单记录" description="从库存选择资产并完成一次挂单预览后，结果会显示在这里。" />}</div>
}
