import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, ChevronRight, ClipboardList, RefreshCw, XCircle } from 'lucide-react'

import { Button, FeedbackState } from '../../../shared/components'
import { useListingNotifications } from '../../../shared/hooks/useListingNotifications'
import {
  cancelListingItems,
  getListingRequests,
  reconcileListingRequests,
  type ListingRequest,
} from '../api/listingsApi'
import '../listings.css'

type ListingItem = ListingRequest['items'][number] & {
  requestId: string
  requestCreatedAt: number
}
type SectionKey = 'pending' | 'active' | 'sold' | 'closed'
type ListingGroup = {
  name: string
  displayName: string
  imageUrl: string
  wearText: string | null
  items: ListingItem[]
}

const REFRESH_INTERVAL_MS = 60_000
const sectionOrder: SectionKey[] = ['pending', 'active', 'sold', 'closed']
const sectionLabels: Record<SectionKey, string> = {
  pending: '等待提交/待确认',
  active: '在售',
  sold: '已售出',
  closed: '已取消/失败',
}
const statusLabels: Record<string, string> = {
  queued: '等待提交',
  pending_confirmation: '待手机确认',
  active: '在售',
  sold: '已售出',
  cancelled: '已取消',
  failed: '失败',
  pending_reconciliation: '待同步',
  submitted: '已提交',
  submitting: '提交中',
}

const money = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? '--' : `¥${(value / 100).toFixed(2)}`
const date = (stamp: number | null | undefined) => stamp ? new Date(stamp).toLocaleString('zh-CN', { hour12: false }) : '--'

export function ListingsPage() {
  const [requests, setRequests] = useState<ListingRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [expandedSections, setExpandedSections] = useState<Set<SectionKey>>(new Set(['pending', 'active']))
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [cancelling, setCancelling] = useState(false)
  const { revision } = useListingNotifications()
  const requestInFlight = useRef(false)
  const syncInFlight = useRef(false)

  const items = useMemo(() => requests.flatMap((request) => request.items.map((item) => ({
    ...item,
    requestId: request.id,
    requestCreatedAt: request.created_at,
  }))), [requests])
  const sections = useMemo(() => groupSections(items), [items])
  const allItemsByName = useMemo(() => groupItems(items), [items])
  const cancellableIds = useMemo(() => new Set(items.filter(canCancel).map((item) => item.id)), [items])

  const load = useCallback(async (initial = false) => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    if (initial) setLoading(true)
    setError(null)
    try {
      const data = await getListingRequests()
      setRequests(data.items)
      const available = new Set(data.items.flatMap((request) => request.items.filter(canCancel).map((item) => item.id)))
      setSelected((current) => new Set([...current].filter((id) => available.has(id))))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法读取挂单记录')
    } finally {
      requestInFlight.current = false
      if (initial) setLoading(false)
    }
  }, [])

  const sync = useCallback(async (showActivity = true) => {
    if (syncInFlight.current) return
    syncInFlight.current = true
    if (showActivity) setSyncing(true)
    setError(null)
    try {
      await reconcileListingRequests()
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '挂单状态同步失败')
    } finally {
      syncInFlight.current = false
      if (showActivity) setSyncing(false)
    }
  }, [load])

  useEffect(() => {
    void load(true)
    const timer = window.setInterval(() => void sync(false), REFRESH_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [load, revision, sync])

  async function cancelSelected() {
    if (!selected.size || !window.confirm(`确认取消选中的 ${selected.size} 个 Steam 挂单？`)) return
    setCancelling(true)
    setError(null)
    try {
      const result = await cancelListingItems([...selected])
      const failed = result.items.filter((item) => item.status === 'failed')
      setSelected(new Set())
      await load()
      if (failed.length) setError(`${failed.length} 个挂单取消失败，请同步后重试。`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '取消挂单失败')
    } finally {
      setCancelling(false)
    }
  }

  function toggleSelection(ids: string[], checked: boolean) {
    setSelected((current) => {
      const next = new Set(current)
      for (const id of ids) {
        if (checked) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }

  return <div className="workspace-page">
    <header className="module-header"><div><span className="eyebrow">SKINFLOW / LISTINGS</span><h1>挂单记录</h1><p>Steam 挂单状态与真实成交同步</p></div><ClipboardList size={22} aria-hidden="true" /></header>
    <div className={selected.size ? 'ledger-command listing-command is-selecting' : 'ledger-command listing-command'}>
      <span>{selected.size ? `已选 ${selected.size} / 可取消 ${cancellableIds.size}` : `自动同步每 ${REFRESH_INTERVAL_MS / 1000} 秒运行`}</span>
      <div className="command-spacer" />
      {selected.size ? <Button variant="ghost" onClick={() => setSelected(new Set())}>清除选择</Button> : null}
      <Button variant="danger" icon={<XCircle size={16} />} disabled={!selected.size || cancelling} loading={cancelling} onClick={() => void cancelSelected()}>取消所选挂单</Button>
      <Button icon={<RefreshCw size={16} />} loading={syncing} onClick={() => void sync()}>立即同步</Button>
    </div>
    {error && items.length ? <div className="listing-page-error" role="alert">{error}</div> : null}
    {loading ? <div className="module-empty">正在读取挂单记录…</div> : items.length ? <div className="listing-status-tree">
      <div className="listing-tree-columns"><span>状态 / 物品 / 资产</span><span>数量</span><span>成本</span><span>挂出价格</span><span>到手价格</span><span>比例</span><span>在售 / 已售出</span></div>
      {sectionOrder.map((sectionKey) => {
        const sectionItems = sections.get(sectionKey) ?? []
        const groups = groupItems(sectionItems)
        const eligible = sectionItems.filter(canCancel).map((item) => item.id)
        const open = expandedSections.has(sectionKey)
        return <section className={`listing-status-section is-${sectionKey}`} key={sectionKey}>
          <SummaryRow
            level="section"
            label={sectionLabels[sectionKey]}
            detail={`${groups.size} 个物品大类`}
            items={sectionItems}
            selected={selected}
            eligible={eligible}
            open={open}
            onToggleOpen={() => setExpandedSections((current) => toggleSet(current, sectionKey))}
            onToggleSelection={toggleSelection}
          />
          {open ? <div className="listing-section-groups">{[...groups.values()].map((group) => {
            const groupKey = `${sectionKey}:${group.name}`
            const groupOpen = expandedGroups.has(groupKey)
            const groupEligible = group.items.filter(canCancel).map((item) => item.id)
            return <div className="listing-item-group" key={groupKey}>
              <SummaryRow
                level="group"
                label={group.displayName}
                detail={`${group.name}${group.wearText ? ` · ${group.wearText}` : ''}`}
                imageUrl={group.imageUrl}
                items={group.items}
                relationshipItems={allItemsByName.get(group.name)?.items ?? group.items}
                selected={selected}
                eligible={groupEligible}
                open={groupOpen}
                onToggleOpen={() => setExpandedGroups((current) => toggleSet(current, groupKey))}
                onToggleSelection={toggleSelection}
              />
              {groupOpen ? <div className="listing-assets">{group.items.map((item) => <AssetRow
                key={item.id}
                item={item}
                selected={selected.has(item.id)}
                onToggle={(checked) => toggleSelection([item.id], checked)}
              />)}</div> : null}
            </div>
          })}</div> : null}
        </section>
      })}
    </div> : error ? <FeedbackState kind="error" title="挂单记录读取失败" description={error} actionLabel="重试" onAction={() => void load(true)} /> : <FeedbackState kind="empty" title="暂无挂单记录" description="从库存选择资产并完成一次挂单预览后，结果会显示在这里。" />}
  </div>
}

function SummaryRow({ level, label, detail, imageUrl, items, relationshipItems = items, selected, eligible, open, onToggleOpen, onToggleSelection }: {
  level: 'section' | 'group'
  label: string
  detail: string
  imageUrl?: string
  items: ListingItem[]
  relationshipItems?: ListingItem[]
  selected: Set<string>
  eligible: string[]
  open: boolean
  onToggleOpen: () => void
  onToggleSelection: (ids: string[], checked: boolean) => void
}) {
  const totals = summarize(items)
  const selectedCount = eligible.filter((id) => selected.has(id)).length
  return <div className={`listing-summary-row is-${level}`}>
    <span className="listing-summary-name">
      <SelectionCheckbox label={`选择${label}下所有可取消挂单`} selectedCount={selectedCount} eligibleCount={eligible.length} onChange={(checked) => onToggleSelection(eligible, checked)} />
      <button type="button" className="listing-disclosure" aria-label={`${open ? '收起' : '展开'} ${label}`} aria-expanded={open} onClick={onToggleOpen}>{open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</button>
      {imageUrl ? <span className="listing-history-thumb"><img src={imageUrl} alt="" loading="lazy" /></span> : null}
      <span><strong>{label}</strong><small>{detail}{eligible.length ? ` · 可取消 ${eligible.length}` : ''}</small></span>
    </span>
    <span>{items.length}</span><span>{money(totals.cost)}</span><span>{money(totals.buyerPays)}</span><span className="listing-proceeds">{money(totals.proceeds)}</span><span>{formatRatio(totals.cost, totals.proceeds)}</span><ListingStatusProgress items={relationshipItems} />
  </div>
}

function AssetRow({ item, selected, onToggle }: { item: ListingItem; selected: boolean; onToggle: (checked: boolean) => void }) {
  const proceeds = item.sold_receive_total ?? item.seller_proceeds ?? null
  return <div className="listing-asset-row">
    <span className="listing-asset-name"><SelectionCheckbox label={`选择取消资产 ${item.assetid}`} selectedCount={selected ? 1 : 0} eligibleCount={canCancel(item) ? 1 : 0} onChange={onToggle} /><span><strong>资产 {item.assetid}</strong><small>{item.steam_listing_id ? `Steam listing ${item.steam_listing_id}` : item.message ?? `请求 ${item.requestId.slice(0, 8)}`} · {date(item.sold_at ?? item.last_checked_at ?? item.requestCreatedAt)}</small></span></span>
    <span>1</span><span>{money(item.cost_each)}</span><span>{money(item.buyer_pays)}</span><span className="listing-proceeds">{money(proceeds)}</span><span>{formatRatio(item.cost_each ?? 0, proceeds)}</span><span className={`listing-status-label is-${sectionFor(item)}`}>{statusLabels[item.status] ?? item.status}</span>
  </div>
}

function SelectionCheckbox({ label, selectedCount, eligibleCount, onChange }: { label: string; selectedCount: number; eligibleCount: number; onChange: (checked: boolean) => void }) {
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = selectedCount > 0 && selectedCount < eligibleCount
  }, [eligibleCount, selectedCount])
  return <input ref={ref} type="checkbox" aria-label={label} checked={eligibleCount > 0 && selectedCount === eligibleCount} disabled={!eligibleCount} onClick={(event) => event.stopPropagation()} onChange={(event) => onChange(event.target.checked)} />
}

function ListingStatusProgress({ items }: { items: ListingItem[] }) {
  const active = items.filter((item) => sectionFor(item) === 'active').length
  const sold = items.filter((item) => sectionFor(item) === 'sold').length
  const total = active + sold
  const activeShare = total ? active / total * 100 : 0
  const soldShare = total ? sold / total * 100 : 0
  return <span className="listing-status-progress" aria-label={`在售 ${active} 件，已售出 ${sold} 件`}>
    <span className="listing-progress-bar" role="img" aria-hidden="true"><i className="is-active" style={{ width: `${activeShare}%` }} /><i className="is-sold" style={{ width: `${soldShare}%` }} /></span>
    <small><b>在售 {active}</b><b>已售 {sold}</b></small>
  </span>
}

function groupSections(items: ListingItem[]) {
  const sections = new Map<SectionKey, ListingItem[]>()
  for (const item of items) sections.set(sectionFor(item), [...(sections.get(sectionFor(item)) ?? []), item])
  return sections
}

function groupItems(items: ListingItem[]) {
  const groups = new Map<string, ListingGroup>()
  for (const item of items) {
    const current = groups.get(item.market_hash_name)
    if (current) current.items.push(item)
    else groups.set(item.market_hash_name, {
      name: item.market_hash_name,
      displayName: item.display_name,
      imageUrl: item.image_url,
      wearText: item.wear_text ?? null,
      items: [item],
    })
  }
  return groups
}

function summarize(items: ListingItem[]) {
  return items.reduce((total, item) => ({
    cost: total.cost + finiteOrZero(item.cost_each),
    buyerPays: total.buyerPays + finiteOrZero(item.buyer_pays),
    proceeds: total.proceeds + finiteOrZero(item.sold_receive_total ?? item.seller_proceeds),
  }), { cost: 0, buyerPays: 0, proceeds: 0 })
}

function finiteOrZero(value: number | null | undefined) {
  return value != null && Number.isFinite(value) ? value : 0
}

function sectionFor(item: Pick<ListingItem, 'status'>): SectionKey {
  if (item.status === 'sold') return 'sold'
  if (['cancelled', 'failed'].includes(item.status)) return 'closed'
  if (['queued', 'submitting', 'pending_confirmation', 'pending_reconciliation'].includes(item.status)) return 'pending'
  return 'active'
}

function canCancel(item: Pick<ListingItem, 'status' | 'steam_listing_id'>) {
  return item.status === 'active' && Boolean(item.steam_listing_id)
}

function formatRatio(cost: number | null | undefined, proceeds: number | null | undefined) {
  return cost != null && proceeds != null && Number.isFinite(cost) && Number.isFinite(proceeds) && proceeds > 0 ? (cost / proceeds).toFixed(3) : '--'
}

function toggleSet<T>(current: Set<T>, value: T) {
  const next = new Set(current)
  if (next.has(value)) next.delete(value)
  else next.add(value)
  return next
}
