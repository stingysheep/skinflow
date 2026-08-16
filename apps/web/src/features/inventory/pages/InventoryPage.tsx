import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Boxes, ExternalLink, ListPlus, RefreshCw, Search } from 'lucide-react'
import { Button, FeedbackState } from '../../../shared/components'
import { ApiError } from '../../../shared/api/client'
import { createListingPreview, getInventory, getInventoryGroupDetails, refreshInventory } from '../api/inventoryApi'
import { InventoryGroupDetails } from '../components/InventoryGroupDetails'
import { ListingPreviewDialog } from '../components/ListingPreviewDialog'
import { TradeAvailability } from '../components/TradeAvailability'
import { usePersistentState } from '../../../shared/hooks/usePersistentState'
import {
  type InventoryGroup,
  type InventoryGroupDetails as InventoryGroupDetailsModel,
  type InventoryResponse,
  type ListingPreview,
} from '../model/types'
import '../inventory.css'

type InventoryScope = 'all' | 'held'
type InventoryTradeFilter = 'all' | 'tradable' | 'cooldown' | 'listed'
const INVENTORY_REFRESH_INTERVAL_MS = 60_000

export function InventoryPage() {
  const [data, setData] = useState<InventoryResponse | null>(null)
  const [quantities, setQuantities] = useState<Map<string, number>>(new Map())
  const [query, setQuery] = usePersistentState('skinflow.inventory.query', '')
  const [scope, setScope] = usePersistentState<InventoryScope>('skinflow.inventory.scope', 'all')
  const [tradeFilter, setTradeFilter] = usePersistentState<InventoryTradeFilter>('skinflow.inventory.trade', 'tradable')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<ListingPreview | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [expandedName, setExpandedName] = useState<string | null>(null)
  const [groupDetails, setGroupDetails] = useState<Record<string, InventoryGroupDetailsModel | null>>({})
  const [detailLoading, setDetailLoading] = useState<string | null>(null)
  const [detailErrors, setDetailErrors] = useState<Record<string, string>>({})
  const refreshInFlight = useRef(false)

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)
    try {
      setData(await getInventory())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法读取 Steam 库存')
    } finally {
      setLoading(false)
    }
  }, [])

  const groups = useMemo(() => normalizeGroups(data), [data])
  useEffect(() => {
    const names = new Set(groups.map((group) => group.market_hash_name))
    setQuantities((current) => {
      const next = new Map([...current].filter(([name]) => names.has(name)))
      return next.size === current.size ? current : next
    })
  }, [groups])
  const visibleGroups = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    return groups.filter((group) => {
      const matchesScope = scope === 'all' || (group.held_quantity ?? 0) > 0
      const matchesFilter = tradeFilter === 'all'
        || (tradeFilter === 'tradable' && group.tradable_quantity > 0)
        || (tradeFilter === 'cooldown' && Math.max(0, group.available_quantity - group.tradable_quantity) > 0)
        || (tradeFilter === 'listed' && (group.listed_quantity ?? 0) > 0)
      const matchesQuery = !normalizedQuery || `${group.display_name} ${group.market_hash_name}`
        .toLocaleLowerCase()
        .includes(normalizedQuery)
      return matchesScope && matchesFilter && matchesQuery
    })
  }, [scope, tradeFilter, groups, query])

  function setQuantity(name: string, quantity: number) {
    setQuantities((current) => {
      const next = new Map(current)
      if (quantity < 1) next.delete(name)
      else next.set(name, quantity)
      return next
    })
  }

  const refresh = useCallback(async (silent = false) => {
    if (refreshInFlight.current) return
    refreshInFlight.current = true
    if (!silent) setRefreshing(true)
    if (!silent) setError(null)
    try {
      await refreshInventory()
      await load(silent)
    } catch (reason) {
      if (!silent) setError(reason instanceof Error ? reason.message : 'Steam 库存刷新失败')
    } finally {
      refreshInFlight.current = false
      if (!silent) setRefreshing(false)
    }
  }, [load])

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void refresh(true), INVENTORY_REFRESH_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [load, refresh])

  async function buildPreview() {
    const selectedGroups = visibleGroups
      .map((group) => ({
        market_hash_name: group.market_hash_name,
        quantity: quantities.get(group.market_hash_name) ?? 0,
      }))
      .filter((group) => group.quantity > 0)
    if (!selectedGroups.length) {
      setPreviewError('请先选择物品并设置出售数量。')
      return
    }
    setPreviewLoading(true)
    setPreviewError(null)
    try {
      const next = await createListingPreview(selectedGroups)
      setPreview(next)
      setPreviewOpen(true)
    } catch (reason) {
      setPreviewError(previewErrorMessage(reason))
    } finally {
      setPreviewLoading(false)
    }
  }

  async function toggleDetails(name: string) {
    if (expandedName === name) {
      setExpandedName(null)
      return
    }
    setExpandedName(name)
    setDetailLoading(name)
    setDetailErrors((current) => ({ ...current, [name]: '' }))
    try {
      const details = await getInventoryGroupDetails(name)
      setGroupDetails((current) => ({ ...current, [name]: details }))
      if (!details.trend?.some((point) => point.source === 'csqaq')) {
        // The API starts a background CSQAQ refresh so opening a row stays instant.
        // Pick up the persisted chart shortly after it becomes available.
        for (const delay of [1500, 5000, 15000, 30000]) {
          window.setTimeout(() => {
            void getInventoryGroupDetails(name).then((next) => {
              if (next.trend?.some((point) => point.source === 'csqaq')) setGroupDetails((current) => ({ ...current, [name]: next }))
            }).catch(() => undefined)
          }, delay)
        }
      }
    } catch (reason) {
      setDetailErrors((current) => ({ ...current, [name]: reason instanceof Error ? reason.message : '行情详情读取失败' }))
      setGroupDetails((current) => ({ ...current, [name]: null }))
    } finally {
      setDetailLoading(null)
    }
  }

  const selectedCount = [...quantities.values()].reduce((sum, quantity) => sum + quantity, 0)
  return (
    <div className="inventory-studio">
      <header className="module-header">
        <div>
          <span className="eyebrow">SKINFLOW / INVENTORY</span>
          <h1>Steam 库存</h1>
          <p>按同类物品合并，选择数量后统一预览挂单</p>
        </div>
        <Boxes size={22} aria-hidden="true" />
      </header>
      <div className="inventory-command">
        <label className="search-control">
          <Search size={16} aria-hidden="true" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索中文或市场名称" />
        </label>
        <select aria-label="库存范围" value={scope} onChange={(event) => setScope(event.target.value as InventoryScope)}>
          <option value="all">全部</option>
          <option value="held">已记录持仓</option>
        </select>
        <select aria-label="交易状态" value={tradeFilter} onChange={(event) => setTradeFilter(event.target.value as InventoryTradeFilter)}>
          <option value="all">全部状态</option>
          <option value="tradable">可交易</option>
          <option value="cooldown">冷却中</option>
          <option value="listed">在售</option>
        </select>
        <span>{visibleGroups.length} 组 · 已选 {selectedCount} 件</span>
        <div className="command-spacer" />
        {previewError ? <span className="inventory-action-error" role="alert">{previewError}</span> : null}
        <Button icon={<RefreshCw size={16} />} loading={refreshing} onClick={() => void refresh()}>刷新库存</Button>
        <Button variant="primary" icon={<ListPlus size={16} />} loading={previewLoading} disabled={!selectedCount} onClick={() => void buildPreview()}>预览挂单</Button>
      </div>
      {error ? <FeedbackState kind="error" title="库存读取失败" description={error} /> : null}
      {!error && loading ? <div className="module-empty">正在读取库存…</div> : null}
      {!error && !loading && data?.status === 'session_required' ? <FeedbackState kind="empty" title="Steam 会话未连接" description="请从设置页连接 Steam。行情扫描仍然可以匿名使用。" /> : null}
      {!error && !loading && data?.status === 'ready' && visibleGroups.length ? <InventoryGrid groups={visibleGroups} quantities={quantities} expandedName={expandedName} details={groupDetails} detailLoading={detailLoading} detailErrors={detailErrors} onExpand={toggleDetails} onQuantityChange={setQuantity} /> : null}
      {!error && !loading && data?.status === 'ready' && !visibleGroups.length ? <FeedbackState kind="empty" title="没有匹配的物品" description="尝试切换筛选或清空搜索条件。" /> : null}
      <ListingPreviewDialog preview={preview} open={previewOpen} onOpenChange={setPreviewOpen} onSubmitted={load} />
    </div>
  )
}

function normalizeGroups(data: InventoryResponse | null): InventoryGroup[] {
  if (data?.groups?.length) return data.groups
  const grouped = new Map<string, InventoryGroup>()
  for (const item of data?.items ?? []) {
    const current = grouped.get(item.market_hash_name) ?? {
      market_hash_name: item.market_hash_name,
      display_name: item.display_name,
      image_url: item.image_url,
      total_quantity: 0,
      available_quantity: 0,
      listed_quantity: 0,
      marketable_quantity: 0,
      tradable_quantity: 0,
    }
    current.total_quantity += 1
    if (item.status === 'available') current.available_quantity += 1
    if (item.status === 'listed') current.listed_quantity += 1
    if (item.status === 'available' && item.marketable) current.marketable_quantity += 1
    if (item.status === 'available' && item.marketable && item.tradable) current.tradable_quantity += 1
    grouped.set(item.market_hash_name, current)
  }
  return [...grouped.values()]
}

function InventoryGrid({ groups, quantities, expandedName, details, detailLoading, detailErrors, onExpand, onQuantityChange }: {
  groups: InventoryGroup[]
  quantities: Map<string, number>
  expandedName: string | null
  details: Record<string, InventoryGroupDetailsModel | null>
  detailLoading: string | null
  detailErrors: Record<string, string>
  onExpand: (name: string) => void
  onQuantityChange: (name: string, quantity: number) => void
}) {
  const hasCooldown = groups.some((group) => group.available_quantity > group.tradable_quantity)
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!hasCooldown) return
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [hasCooldown])

  return (
      <div className="inventory-grid inventory-group-grid">
      <div className="inventory-grid-head"><span>选择</span><span>物品组</span><span>交易状态</span><span>移动均价</span><span>出售数量</span><span>市场</span></div>
      {groups.map((group) => {
        const quantity = quantities.get(group.market_hash_name) ?? 0
        const max = group.tradable_quantity
        return <Fragment key={group.market_hash_name}><div className={quantity ? 'inventory-row is-selected' : 'inventory-row'} role="button" tabIndex={0} aria-expanded={expandedName === group.market_hash_name} onClick={() => onExpand(group.market_hash_name)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onExpand(group.market_hash_name) } }}>
          <input type="checkbox" checked={quantity > 0} disabled={!max} aria-label={`选择 ${group.display_name}`} onClick={(event) => event.stopPropagation()} onChange={() => onQuantityChange(group.market_hash_name, quantity ? 0 : 1)} />
          <span className="inventory-item"><span className="inventory-thumb">{group.image_url ? <img src={group.image_url} alt="" /> : null}</span><strong>{group.display_name}{group.wear_text ? ` · ${group.wear_text}` : ''}<small>{group.market_hash_name}</small></strong></span>
          <TradeAvailability group={group} now={now} />
          <code>{money(group.average_cost)}</code>
          <span className="quantity-stepper" onClick={(event) => event.stopPropagation()}><button type="button" onClick={() => onQuantityChange(group.market_hash_name, Math.max(0, quantity - 1))} aria-label={`减少 ${group.display_name}`}>−</button><QuantityInput value={quantity} max={max} label={group.display_name} onChange={(next) => onQuantityChange(group.market_hash_name, next)} /><button type="button" onClick={() => onQuantityChange(group.market_hash_name, Math.min(max, quantity + 1))} aria-label={`增加 ${group.display_name}`}>+</button></span>
          <a className="market-link-icon" href={steamMarketUrl(group.market_hash_name)} target="_blank" rel="noreferrer" title="在 Steam 市场查看" aria-label={`在 Steam 市场查看 ${group.display_name}`} onClick={(event) => event.stopPropagation()}><ExternalLink size={15} aria-hidden="true" /></a>
        </div>{expandedName === group.market_hash_name ? <div className="inventory-detail-row"><InventoryGroupDetails details={details[group.market_hash_name] ?? null} loading={detailLoading === group.market_hash_name} error={detailErrors[group.market_hash_name] || null} /></div> : null}</Fragment>
      })}
    </div>
  )
}

function steamMarketUrl(marketHashName: string) {
  return `https://steamcommunity.com/market/listings/730/${encodeURIComponent(marketHashName)}`
}

function QuantityInput({ value, max, label, onChange }: { value: number; max: number; label: string; onChange: (value: number) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  return <input
    className="quantity-input"
    type="text"
    inputMode="numeric"
    value={editing ? draft : value > 0 ? String(value) : ''}
    maxLength={4}
    aria-label={`挂单数量 ${label}`}
    onFocus={() => { setEditing(true); setDraft(value > 0 ? String(value) : '') }}
    onBlur={() => {
      setEditing(false)
    }}
    onChange={(event) => {
      const nextDraft = event.target.value.replace(/\D/g, '').slice(0, 4)
      const nextValue = nextDraft ? Math.min(max, Number(nextDraft)) : 0
      setDraft(nextDraft)
      onChange(nextValue)
    }}
  />
}

const money = (value: number | null | undefined) => value == null ? '--' : `¥${(value / 100).toFixed(2)}`

function previewErrorMessage(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.code === 'SESSION_REQUIRED') return 'Steam 会话已过期，请重新登录后再预览挂单。'
    if (reason.code === 'CONFLICT' && reason.message.includes('insufficient')) return '所选数量超过当前可交易库存，请刷新后重试。'
    if (reason.code === 'CONFLICT' && reason.message.includes('STEAM_SNAPSHOT_REQUIRED')) return '该资产暂无可用 Steam 行情，请先扫描该物品后再预览挂单。'
    if (reason.code === 'CONFLICT' && reason.message.includes('STEAM_SNAPSHOT_UNAVAILABLE')) return '暂时无法获取该资产的 Steam 行情，请确认网络后重试。'
    if (reason.code === 'CONFLICT') return `无法预览挂单：${reason.message}`
    return reason.message
  }
  return reason instanceof Error ? reason.message : '预览挂单失败，请稍后重试。'
}
