import { useEffect, useState } from 'react'
import { PackageCheck } from 'lucide-react'
import { Button } from '../../../shared/components'
import { getJson, postJson } from '../../../shared/api/client'

type Pending = { id: string; market_hash_name: string; display_name: string; quantity: number; cost_each: number; venue: string | null }

export function PendingPurchases({ onChanged }: { onChanged: () => void }) {
  const [items, setItems] = useState<Pending[]>([])
  const load = async () => setItems((await getJson<{ items: Pending[] }>('/api/pending-purchases')).items)
  useEffect(() => {
    let active = true
    void getJson<{ items: Pending[] }>('/api/pending-purchases').then((data) => {
      if (active) setItems(data.items)
    })
    return () => { active = false }
  }, [])
  async function receive(item: Pending) {
    const value = window.prompt(`本次收到多少件？最多 ${item.quantity} 件`, String(item.quantity))
    if (!value) return
    await postJson(`/api/purchases/${item.id}/receive`, { quantity: Number(value) })
    await load(); onChanged()
  }
  if (!items.length) return null
  return <section className="pending-section"><div className="pending-heading"><span><PackageCheck size={16} aria-hidden="true" />待到货</span><small>到账后结算为正式买入批次</small></div>{items.map((item) => <div className="pending-row" key={item.id}><strong>{item.display_name}<small>{item.market_hash_name} · {item.venue ?? '未填写平台'} · {item.quantity} 件 · ¥{(item.cost_each / 100).toFixed(2)} / 件</small></strong><Button variant="secondary" onClick={() => receive(item)}>登记到货</Button></div>)}</section>
}
