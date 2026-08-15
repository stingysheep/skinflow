import { useMemo, useState } from 'react'
import { calculateRatio } from '../model/ratioCalculator'

const yuanToFen = (value: string) => {
  const parsed = Number(value.replace(',', '.'))
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed * 100) : 0
}
const money = (fen: number | null) => fen === null ? '--' : `¥${(fen / 100).toFixed(2)}`
const ratio = (value: number | null) => value === null ? '--' : value.toFixed(3)
const estimateLabel = (estimate: ReturnType<typeof calculateRatio>) => {
  if (estimate.proceeds === null) return '输入买家支付价'
  return `${estimate.exact ? '' : '≈'}${money(estimate.proceeds)} · ${ratio(estimate.ratio)}`
}

export function RatioCalculator() {
  const [cost, setCost] = useState('')
  const [ask, setAsk] = useState('')
  const [bid, setBid] = useState('')
  const costFen = yuanToFen(cost)
  const askEstimate = useMemo(() => calculateRatio(costFen, yuanToFen(ask)), [ask, costFen])
  const bidEstimate = useMemo(() => calculateRatio(costFen, yuanToFen(bid)), [bid, costFen])

  return <div className="ratio-calculator-inline" aria-label="比例计算器">
    <span className="ratio-calculator-label">比例计算</span>
    <label>均价<input inputMode="decimal" value={cost} onChange={(event) => setCost(event.target.value)} placeholder="均价" /></label>
    <div className="ratio-calculator-side"><label>挂底价<input inputMode="decimal" value={ask} onChange={(event) => setAsk(event.target.value)} placeholder="买家支付" /></label><strong className="ratio-calculator-output">{estimateLabel(askEstimate)}</strong></div>
    <div className="ratio-calculator-side"><label>求购价<input inputMode="decimal" value={bid} onChange={(event) => setBid(event.target.value)} placeholder="买家支付" /></label><strong className="ratio-calculator-output">{estimateLabel(bidEstimate)}</strong></div>
  </div>
}
