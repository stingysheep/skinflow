import { Fragment, useEffect, useState } from 'react'
import { Boxes, Clock3, PackageSearch, Settings2, WalletCards } from 'lucide-react'
import { getJson } from '../../shared/api/client'
import { FeedbackState } from '../../shared/components'
import { useListingNotifications } from '../../shared/hooks/useListingNotifications'

type Mode = 'inventory' | 'holdings' | 'history' | 'settings'
type Item = Record<string, string | number | null>

const numberValue = (value: Item[string]): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

const money = (value: Item[string]) => {
  const fen = numberValue(value)
  return fen == null ? '--' : `¥${(fen / 100).toFixed(2)}`
}

const formatDate = (value: Item[string]) => {
  const stamp = numberValue(value)
  if (!stamp) return '--'
  const milliseconds = stamp < 10_000_000_000 ? stamp * 1000 : stamp
  const date = new Date(milliseconds)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}

const ratio = (cost: Item[string], receive: Item[string]) => {
  const costValue = numberValue(cost)
  const receiveValue = numberValue(receive)
  return costValue == null || receiveValue == null || receiveValue <= 0 ? '--' : (costValue / receiveValue).toFixed(3)
}

export function WorkspacePage({ mode }: { mode: Mode }) {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(mode !== 'settings')
  const { revision } = useListingNotifications()
  useEffect(() => {
    const path = mode === 'holdings' ? '/api/holdings' : mode === 'history' ? '/api/history' : '/api/inventory'
    if (mode === 'settings') return
    let disposed = false
    const load = () => void getJson<{ items: Item[] }>(path).then((data) => { if (!disposed) setItems(data.items) }).finally(() => { if (!disposed) setLoading(false) })
    load()
    const timer = mode === 'history' ? window.setInterval(load, 30_000) : undefined
    return () => { disposed = true; if (timer) window.clearInterval(timer) }
  }, [mode, revision])
  const meta = {
    inventory: { icon: Boxes, title: '库存资产', desc: 'Steam 单件资产与挂单状态' },
    holdings: { icon: WalletCards, title: '持仓账本', desc: '买入批次、剩余数量与成本' },
    history: { icon: Clock3, title: '成交历史', desc: '已确认的卖出回报与成本' },
    settings: { icon: Settings2, title: '系统设置', desc: '本地服务、平台连接与数据迁移' },
  }[mode]
  const Icon = meta.icon
  return <div className="workspace-page"><header className="module-header"><div><span className="eyebrow">SKINFLOW / {mode.toUpperCase()}</span><h1>{meta.title}</h1><p>{meta.desc}</p></div><Icon size={22} aria-hidden="true" /></header>{mode === 'settings' ? <SettingsPanel /> : loading ? <div className="module-empty">正在读取本地数据…</div> : mode === 'inventory' ? <InventoryEmpty /> : items.length ? <LedgerTable mode={mode} items={items} /> : <FeedbackState kind="empty" title={mode === 'history' ? '暂无成交记录' : '暂无持仓'} description="迁移旧账本或完成第一笔记录后，这里会显示真实数据。" />}</div>
}

function InventoryEmpty() { return <div className="inventory-gate"><PackageSearch size={24} /><strong>Steam 会话未连接</strong><p>行情扫描不需要账号；读取单件库存和提交挂单时，才需要在本机连接 Steam 会话。</p></div> }
function LedgerTable({ mode, items }: { mode: Mode; items: Item[] }) {
  if (mode === 'history') return <HistoryTable items={items} />
  const columns = ['market_hash_name', 'open_quantity', 'cost_each', 'lots']
  const labels: Record<string, string> = { market_hash_name: '物品', open_quantity: '持有', cost_each: '单件成本', lots: '批次' }
  return <div className="module-table"><table><thead><tr>{columns.map((column) => <th key={column}>{labels[column]}</th>)}</tr></thead><tbody>{items.map((item, index) => <tr key={String(item.market_hash_name ?? item.id ?? index)}>{columns.map((column) => <td key={column}>{column === 'market_hash_name' ? <span className="ledger-item-name"><strong>{item.display_name ?? '中文名称待同步'}{item.wear_text ? ` · ${item.wear_text}` : ''}</strong><small>{item.market_hash_name}</small></span> : column === 'cost_each' ? money(item[column]) : item[column] ?? '--'}</td>)}</tr>)}</tbody></table></div>
}

function HistoryTable({ items }: { items: Item[] }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const groups = groupHistory(items)
  const totals = groups.reduce<{ cost: number; receive: number }>((summary, group) => {
    summary.cost += group.cost
    summary.receive += group.receive
    return summary
  }, { cost: 0, receive: 0 })
  const totalRatio = totals.receive > 0 ? (totals.cost / totals.receive).toFixed(3) : '--'
  return <div className="history-view">
    <div className="history-summary" aria-label="成交汇总">
      <span><small>总成本</small><strong>{money(totals.cost)}</strong></span>
      <span><small>总到账</small><strong>{money(totals.receive)}</strong></span>
      <span><small>总比例</small><strong>{totalRatio}</strong></span>
      <span className="history-summary-count">{groups.length} 个物品组 · {items.length} 笔成交</span>
    </div>
    <div className="module-table"><table><thead><tr><th>物品</th><th>数量</th><th>总成本</th><th>实收</th><th>比例</th></tr></thead><tbody>{groups.map((group) => <Fragment key={group.name}>
      <tr className="history-group-row" role="button" tabIndex={0} aria-expanded={expanded.has(group.name)} onClick={() => setExpanded((current) => toggleSet(current, group.name))} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setExpanded((current) => toggleSet(current, group.name)) } }}>
        <td><span className="ledger-item-name history-item"><span className="history-thumb">{group.imageUrl ? <img src={group.imageUrl} alt="" /> : null}</span><strong>{group.displayName}{group.wearText ? ` · ${group.wearText}` : ''}</strong><small>{group.name} · {group.batches.length} 个成本批次</small></span></td>
        <td>{group.quantity}</td><td>{money(group.cost)}</td><td className="history-receive">{money(group.receive)}</td><td>{ratio(group.cost, group.receive)}</td>
      </tr>
      {expanded.has(group.name) ? <tr className="history-detail-row"><td colSpan={5}><div className="history-details">{group.batches.map((batch) => <section key={batch.id} className="history-batch"><header><strong>成本批次</strong><span>{batch.quantity} 件 · 成本 {money(batch.cost)} · 实收 {money(batch.receive)} · 比例 {ratio(batch.cost, batch.receive)}</span></header><div className="history-detail-list">{batch.items.map((item, index) => <div className="history-detail-line" key={String(item.id ?? `${batch.id}-${index}`)}><span>{item.quantity ?? '--'} 件 · {item.source === 'automatic' ? 'Steam 自动同步' : '手动记录'}</span><span>{money(item.receive_total)}</span><time>{formatDate(item.sold_at)}</time></div>)}</div></section>)}</div></td></tr> : null}
    </Fragment>)}</tbody></table></div>
  </div>
}

type HistoryGroup = {
  name: string
  displayName: string
  imageUrl: string
  wearText: string | null
  quantity: number
  cost: number
  receive: number
  batches: HistoryBatch[]
}

type HistoryBatch = { id: string; quantity: number; cost: number; receive: number; items: Item[] }

function groupHistory(items: Item[]): HistoryGroup[] {
  const groups = new Map<string, HistoryGroup>()
  for (const item of items) {
    const name = String(item.market_hash_name ?? item.id ?? '')
    let group = groups.get(name)
    if (!group) {
      group = { name, displayName: String(item.display_name ?? '中文名称待同步'), imageUrl: String(item.image_url ?? ''), wearText: item.wear_text ? String(item.wear_text) : null, quantity: 0, cost: 0, receive: 0, batches: [] }
      groups.set(name, group)
    }
    const quantity = numberValue(item.quantity) ?? 0
    const cost = numberValue(item.cost_total) ?? 0
    const receive = numberValue(item.receive_total) ?? 0
    const batchId = String(item.purchase_lot_id ?? item.id ?? `${name}:${group.batches.length}`)
    let batch = group.batches.find((candidate) => candidate.id === batchId)
    if (!batch) { batch = { id: batchId, quantity: 0, cost: 0, receive: 0, items: [] }; group.batches.push(batch) }
    group.quantity += quantity
    group.cost += cost
    group.receive += receive
    batch.quantity += quantity
    batch.cost += cost
    batch.receive += receive
    batch.items.push(item)
  }
  return [...groups.values()]
}

function toggleSet(current: Set<string>, name: string) {
  const next = new Set(current)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  return next
}
function SettingsPanel() { return <div className="settings-list"><div><strong>行情平台</strong><span>csqaq 候选 · BUFF 匿名 · Steam 匿名行情</span></div><div><strong>数据库</strong><span>SQLite WAL · 单机本地存储</span></div><div><strong>Steam 库存</strong><span>需要本机 Steam 会话，当前未连接</span></div><div><strong>迁移</strong><span>旧账本迁移由一次性命令执行，不在启动时重复导入</span></div></div> }
