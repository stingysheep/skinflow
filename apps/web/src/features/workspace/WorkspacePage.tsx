import { useEffect, useState } from 'react'
import { Boxes, Clock3, PackageSearch, Settings2, WalletCards } from 'lucide-react'
import { getJson } from '../../shared/api/client'
import { FeedbackState } from '../../shared/components'

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
  useEffect(() => {
    const path = mode === 'holdings' ? '/api/holdings' : mode === 'history' ? '/api/history' : '/api/inventory'
    if (mode === 'settings') return
    void getJson<{ items: Item[] }>(path).then((data) => setItems(data.items)).finally(() => setLoading(false))
  }, [mode])
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
  const totals = items.reduce<{ cost: number; receive: number }>((summary, item) => {
    summary.cost += numberValue(item.cost_total) ?? 0
    summary.receive += numberValue(item.receive_total) ?? 0
    return summary
  }, { cost: 0, receive: 0 })
  const totalRatio = totals.receive > 0 ? (totals.cost / totals.receive).toFixed(3) : '--'
  return <div className="history-view">
    <div className="history-summary" aria-label="成交汇总">
      <span><small>总成本</small><strong>{money(totals.cost)}</strong></span>
      <span><small>总到账</small><strong>{money(totals.receive)}</strong></span>
      <span><small>总比例</small><strong>{totalRatio}</strong></span>
      <span className="history-summary-count">{items.length} 笔成交</span>
    </div>
    <div className="module-table"><table><thead><tr><th>物品</th><th>数量</th><th>总成本</th><th>实收</th><th>比例</th><th>记录方式</th><th>成交时间</th></tr></thead><tbody>{items.map((item, index) => <tr key={String(item.id ?? `${item.market_hash_name}-${index}`)}><td><span className="ledger-item-name history-item"><span className="history-thumb">{item.image_url ? <img src={String(item.image_url)} alt="" /> : null}</span><strong>{item.display_name ?? '中文名称待同步'}{item.wear_text ? ` · ${item.wear_text}` : ''}</strong><small>{item.market_hash_name}</small></span></td><td>{item.quantity ?? '--'}</td><td>{money(item.cost_total)}</td><td className="history-receive">{money(item.receive_total)}</td><td>{ratio(item.cost_total, item.receive_total)}</td><td>{item.source === 'automatic' ? 'Steam 自动同步' : '手动记录'}</td><td>{formatDate(item.sold_at)}</td></tr>)}</tbody></table></div>
  </div>
}
function SettingsPanel() { return <div className="settings-list"><div><strong>行情平台</strong><span>csqaq 候选 · BUFF 匿名 · Steam 匿名行情</span></div><div><strong>数据库</strong><span>SQLite WAL · 单机本地存储</span></div><div><strong>Steam 库存</strong><span>需要本机 Steam 会话，当前未连接</span></div><div><strong>迁移</strong><span>旧账本迁移由一次性命令执行，不在启动时重复导入</span></div></div> }
