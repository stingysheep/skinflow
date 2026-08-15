import { Fragment, useEffect, useRef, useState } from 'react'
import { ArrowDownToLine, ArrowUpFromLine, WalletCards } from 'lucide-react'
import { Button, FeedbackState } from '../../../shared/components'
import { getHoldings, type Holding } from '../api/ledgerApi'
import { LedgerEntryDialog } from '../components/LedgerEntryDialog'
import { PendingPurchases } from '../components/PendingPurchases'
import { getInventoryGroupDetails } from '../../inventory/api/inventoryApi'
import { InventoryGroupDetails } from '../../inventory/components/InventoryGroupDetails'
import type { InventoryGroupDetails as InventoryGroupDetailsModel } from '../../inventory/model/types'
import '../holdings.css'
import '../../inventory/inventory.css'

const money = (value: number) => `¥${(value / 100).toFixed(2)}`

export function HoldingsPage() {
  const [items, setItems] = useState<Holding[]>([])
  const [loading, setLoading] = useState(true)
  const [dialog, setDialog] = useState<'purchase' | 'sale' | null>(null)
  const [expandedName, setExpandedName] = useState<string | null>(null)
  const [details, setDetails] = useState<Record<string, InventoryGroupDetailsModel | null>>({})
  const [detailLoading, setDetailLoading] = useState<string | null>(null)
  const purchaseButtonRef = useRef<HTMLButtonElement>(null)
  const saleButtonRef = useRef<HTMLButtonElement>(null)

  const load = async () => {
    setLoading(true)
    try { setItems((await getHoldings()).items) } finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])

  async function toggleDetails(name: string) {
    if (expandedName === name) { setExpandedName(null); return }
    setExpandedName(name)
    if (Object.prototype.hasOwnProperty.call(details, name)) return
    setDetailLoading(name)
    try {
      const next = await getInventoryGroupDetails(name)
      setDetails((current) => ({ ...current, [name]: next }))
      if (!next.trend?.some((point) => point.source === 'csqaq')) {
        for (const delay of [1500, 5000, 15000, 30000]) {
          window.setTimeout(() => {
            void getInventoryGroupDetails(name).then((refreshed) => {
              if (refreshed.trend?.some((point) => point.source === 'csqaq')) setDetails((current) => ({ ...current, [name]: refreshed }))
            }).catch(() => undefined)
          }, delay)
        }
      }
    } catch {
      setDetails((current) => ({ ...current, [name]: null }))
    } finally { setDetailLoading(null) }
  }

  const finalFocusRef = dialog === 'sale' ? saleButtonRef : purchaseButtonRef
  return <div className="workspace-page">
    <header className="module-header"><div><span className="eyebrow">SKINFLOW / HOLDINGS</span><h1>持仓账本</h1><p>买入批次、FIFO 成本与已确认的真实实收</p></div><WalletCards size={22} aria-hidden="true" /></header>
    <div className="ledger-command"><span>{items.length} 个品种 · {items.reduce((sum, item) => sum + item.open_quantity, 0)} 件未售</span><div className="command-spacer" /><Button ref={purchaseButtonRef} icon={<ArrowDownToLine size={16} />} onClick={() => setDialog('purchase')}>记录买入</Button><Button ref={saleButtonRef} variant="primary" icon={<ArrowUpFromLine size={16} />} onClick={() => setDialog('sale')}>记录卖出</Button></div>
    {loading ? <div className="module-empty">正在读取账本…</div> : items.length ? <div className="module-table holdings-table"><table><thead><tr><th>物品</th><th>持有</th><th>已售</th><th>未售成本</th><th>持仓均价</th><th>批次</th></tr></thead><tbody>{items.map((item) => <Fragment key={item.market_hash_name}><tr className="holding-row" role="button" tabIndex={0} aria-expanded={expandedName === item.market_hash_name} onClick={() => void toggleDetails(item.market_hash_name)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void toggleDetails(item.market_hash_name) } }}><td><span className="holding-item">{item.image_url ? <img src={item.image_url} alt="" /> : <i aria-hidden="true" />}<span><strong>{item.display_name}{item.wear_text ? ` · ${item.wear_text}` : ''}</strong><small>{item.market_hash_name}</small></span></span></td><td>{item.open_quantity}</td><td>{item.sold_quantity}</td><td>{money(item.open_cost)}</td><td>{money(Math.round(item.open_cost / item.open_quantity))}</td><td>{item.lots}</td></tr>{expandedName === item.market_hash_name ? <tr><td colSpan={6}><InventoryGroupDetails details={details[item.market_hash_name] ?? null} loading={detailLoading === item.market_hash_name} error={details[item.market_hash_name] === null ? '行情详情读取失败' : null} /></td></tr> : null}</Fragment>)}</tbody></table></div> : <FeedbackState kind="empty" title="暂无持仓" description="记录第一笔买入后，批次成本会出现在这里。" />}
    <PendingPurchases onChanged={load} />
    <LedgerEntryDialog mode={dialog ?? 'purchase'} open={dialog !== null} onOpenChange={(open) => { if (!open) setDialog(null) }} onSaved={load} finalFocusRef={finalFocusRef} holdings={items} />
  </div>
}
