import { type FormEvent, type RefObject, useEffect, useState } from 'react'
import { Button, Dialog } from '../../../shared/components'
import { createPurchase, createSale, searchLedgerCatalog, type Holding } from '../api/ledgerApi'
import type { InventoryGroup } from '../../inventory/model/types'

type Props = {
  mode: 'purchase' | 'sale'
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
  finalFocusRef: RefObject<HTMLElement | null>
  holdings?: Holding[]
  inventoryGroups?: InventoryGroup[]
}

type CatalogItem = {
  market_hash_name: string
  display_name: string
  image_url: string
  open_quantity: number
}

export function LedgerEntryDialog({ mode, open, onOpenChange, onSaved, finalFocusRef, holdings = [], inventoryGroups = [] }: Props) {
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [amount, setAmount] = useState('')
  const [venue, setVenue] = useState('BUFF')
  const [pending, setPending] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<CatalogItem[]>([])

  useEffect(() => {
    if (!open) return
    setName('')
    setDisplayName('')
    setQuantity('1')
    setAmount('')
    setVenue('BUFF')
    setPending(false)
    setError(null)
    setSuggestions([])
  }, [mode, open])

  useEffect(() => {
    if (!open || !name.trim() || displayName) {
      setSuggestions([])
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void searchLedgerCatalog(name, controller.signal)
        .then((data) => setSuggestions(data.items))
        .catch(() => undefined)
    }, 180)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [displayName, name, open])

  function choose(item: CatalogItem | Holding | InventoryGroup) {
    setName(item.market_hash_name)
    setDisplayName(item.display_name)
    if (mode === 'sale' && 'open_quantity' in item) setQuantity(String(Math.min(Number(quantity) || 1, item.open_quantity || 1)))
    if (mode === 'purchase' && 'total_quantity' in item) setQuantity(String(Math.max(item.total_quantity, 1)))
    setSuggestions([])
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const cents = Math.round(Number(amount) * 100)
      if (mode === 'purchase') {
        await createPurchase({ market_hash_name: name.trim(), quantity: Number(quantity), cost_each: cents, venue, pending_delivery: pending })
      } else {
        await createSale({ market_hash_name: name.trim(), quantity: Number(quantity), receive_total: cents })
      }
      onSaved()
      onOpenChange(false)
    } catch {
      setError('记录失败，请检查名称、数量和金额是否有效。')
    } finally {
      setSaving(false)
    }
  }

  const inputValue = displayName || name
  return <Dialog open={open} onOpenChange={onOpenChange} finalFocusRef={finalFocusRef} contentClassName="ledger-entry-dialog" title={mode === 'purchase' ? '记录买入' : '记录真实卖出'} description={mode === 'purchase' ? '从当前库存选择物品，或搜索名称后保存买入批次。' : '先从当前持仓中选择要记账的物品，再输入实际到账总额。'}>
    <form className="ledger-form" onSubmit={submit}>
      {mode === 'purchase' ? <section className="ledger-holdings-picker" aria-label="当前库存">
        <div className="ledger-picker-heading"><strong>当前库存</strong><small>选择后自动填入物品和数量</small></div>
        {inventoryGroups.length ? <div className="ledger-holding-list">{inventoryGroups.map((item) => <button type="button" key={item.market_hash_name} className={name === item.market_hash_name ? 'is-selected' : ''} onClick={() => choose(item)}>{item.image_url ? <img src={item.image_url} alt="" /> : <span className="ledger-thumb-placeholder" />}<span><strong>{item.display_name}{item.wear_text ? ` · ${item.wear_text}` : ''}</strong><small>{item.total_quantity} 件 · {item.available_quantity} 可交易</small></span></button>)}</div> : <div className="ledger-picker-empty">暂无已同步库存，请先同步库存。</div>}
      </section> : null}
      {mode === 'sale' ? <section className="ledger-holdings-picker" aria-label="当前持仓">
        <div className="ledger-picker-heading"><strong>当前持仓</strong><small>选择后自动填入物品和数量</small></div>
        {holdings.length ? <div className="ledger-holding-list">{holdings.map((item) => <button type="button" key={item.market_hash_name} className={name === item.market_hash_name ? 'is-selected' : ''} onClick={() => choose(item)}>{item.image_url ? <img src={item.image_url} alt="" /> : <span className="ledger-thumb-placeholder" />}<span><strong>{item.display_name}{item.wear_text ? ` · ${item.wear_text}` : ''}</strong><small>{item.open_quantity} 件 · 均价 ¥{(item.open_cost / Math.max(item.open_quantity, 1) / 100).toFixed(2)}</small></span></button>)}</div> : <div className="ledger-picker-empty">暂无未售持仓，请先记录买入。</div>}
      </section> : null}
      <label className="ledger-name-field">{mode === 'sale' ? '备用搜索' : '选择物品'}<input required maxLength={200} value={inputValue} onChange={(event) => { setName(event.target.value); setDisplayName('') }} placeholder="输入中文名称搜索" />{suggestions.length ? <div className="ledger-suggestions" role="listbox">{suggestions.map((item) => <button type="button" key={item.market_hash_name} onClick={() => choose(item)}><img src={item.image_url} alt="" /><span><strong>{item.display_name || '中文名称待同步'}</strong><small>{item.market_hash_name} · 持有 {item.open_quantity}</small></span></button>)}</div> : null}</label>
      <div className="ledger-form-row"><label>数量<input required min="1" step="1" type="number" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label><label>{mode === 'purchase' ? '单件成本（元）' : '实际实收总额（元）'}<input required min={mode === 'purchase' ? '0.01' : '0'} step="0.01" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} /></label></div>
      {mode === 'purchase' ? <><label>买入平台<input maxLength={40} value={venue} onChange={(event) => setVenue(event.target.value)} /></label><label className="check-line"><input type="checkbox" checked={pending} onChange={(event) => setPending(event.target.checked)} />尚未进入 Steam，先记为待到货</label></> : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      <div className="dialog-actions"><Button variant="ghost" onClick={() => onOpenChange(false)}>取消</Button><Button type="submit" variant="primary" loading={saving}>{mode === 'purchase' ? '保存买入' : '确认卖出'}</Button></div>
    </form>
  </Dialog>
}
