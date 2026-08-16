import { type FormEvent, useEffect, useState } from 'react'
import { Button, Dialog } from '../../../shared/components'
import { deleteHolding, updateHoldingAverageCost, type Holding } from '../api/ledgerApi'

type Props = {
  mode: 'edit' | 'delete'
  holding: Holding | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

export function HoldingMaintenanceDialog({ mode, holding, open, onOpenChange, onSaved }: Props) {
  const [cost, setCost] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !holding) return
    setCost((holding.open_cost / Math.max(holding.open_quantity, 1) / 100).toFixed(2))
    setError(null)
  }, [holding, open])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!holding) return
    setSaving(true)
    setError(null)
    try {
      if (mode === 'edit') {
        const cents = Math.round(Number(cost) * 100)
        if (!Number.isFinite(cents) || cents < 1) throw new Error('invalid')
        await updateHoldingAverageCost(holding.market_hash_name, cents)
      } else {
        await deleteHolding(holding.market_hash_name)
      }
      onSaved()
      onOpenChange(false)
    } catch {
      setError(mode === 'edit' ? '保存失败，请输入有效的均价。' : '删除失败，请稍后重试。')
    } finally {
      setSaving(false)
    }
  }

  if (!holding) return null
  return <Dialog open={open} onOpenChange={onOpenChange} title={mode === 'edit' ? '编辑持仓均价' : '删除未售持仓'} description={mode === 'edit' ? '只会调整未售批次的成本，已成交记录保持不变。' : '删除只会移除未售数量，历史成交记录会保留。'}>
    <form className="ledger-form holding-maintenance-form" onSubmit={submit}>
      <div className="holding-maintenance-item"><strong>{holding.display_name}{holding.wear_text ? ' · ' + holding.wear_text : ''}</strong><small>{holding.open_quantity} 件未售 · {holding.market_hash_name}</small></div>
      {mode === 'edit' ? <label>新的未售均价（元）<input autoFocus required min="0.01" step="0.01" type="number" value={cost} onChange={(event) => setCost(event.target.value)} /></label> : <p className="holding-delete-warning">确认删除这 {holding.open_quantity} 件未售持仓吗？已售数量和成交历史不会被删除。</p>}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      <div className="dialog-actions"><Button variant="ghost" onClick={() => onOpenChange(false)}>取消</Button><Button type="submit" variant={mode === 'delete' ? 'danger' : 'primary'} loading={saving}>{mode === 'delete' ? '确认删除' : '保存均价'}</Button></div>
    </form>
  </Dialog>
}
