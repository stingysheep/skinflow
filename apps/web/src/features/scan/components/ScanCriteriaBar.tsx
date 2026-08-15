import { CircleDollarSign, Gauge, Store } from 'lucide-react'
import type { AcquisitionPlatform, ScanCriteria, ScanMode } from '../model/types'

type Props = {
  criteria: ScanCriteria
  disabled: boolean
  onChange: (criteria: ScanCriteria) => void
}

export function ScanCriteriaBar({ criteria, disabled, onChange }: Props) {
  const setMode = (mode: ScanMode) => onChange({ ...criteria, mode })
  const togglePlatform = (platform: AcquisitionPlatform) => {
    const selected = criteria.platforms.includes(platform)
    if (selected && criteria.platforms.length === 1) return
    onChange({
      ...criteria,
      platforms: selected
        ? criteria.platforms.filter((value) => value !== platform)
        : [...criteria.platforms, platform],
    })
  }
  return <div className="scan-criteria-bar" aria-label="扫描条件">
    <fieldset className="criteria-group mode-switch" disabled={disabled}>
      <legend>操作方式</legend>
      <button type="button" className={criteria.mode === 'listing' ? 'is-active' : ''} onClick={() => setMode('listing')}>挂底价</button>
      <button type="button" className={criteria.mode === 'buy_order' ? 'is-active' : ''} onClick={() => setMode('buy_order')}>丢求购</button>
    </fieldset>
    <fieldset className="criteria-group platform-switch" disabled={disabled}>
      <legend><Store size={14} aria-hidden="true" />进货平台</legend>
      <label><input type="checkbox" checked={criteria.platforms.includes('buff')} onChange={() => togglePlatform('buff')} />网易 BUFF</label>
      <label><input type="checkbox" checked={criteria.platforms.includes('youpin')} onChange={() => togglePlatform('youpin')} />悠悠有品</label>
    </fieldset>
    <fieldset className="criteria-group price-range" disabled={disabled}>
      <legend><CircleDollarSign size={14} aria-hidden="true" />进货价格</legend>
      <input aria-label="最低价格" inputMode="decimal" placeholder="最低" value={criteria.minPriceYuan} onChange={(event) => onChange({ ...criteria, minPriceYuan: event.target.value })} />
      <span>至</span>
      <input aria-label="最高价格" inputMode="decimal" placeholder="最高" value={criteria.maxPriceYuan} onChange={(event) => onChange({ ...criteria, maxPriceYuan: event.target.value })} />
      <span>元</span>
    </fieldset>
    <label className="criteria-group volume-control"><span><Gauge size={14} aria-hidden="true" />最低日成交量</span><input type="number" min={0} max={1000000} value={criteria.minDailyVolume} disabled={disabled} onChange={(event) => onChange({ ...criteria, minDailyVolume: Math.max(0, Number(event.target.value)) })} /></label>
  </div>
}
