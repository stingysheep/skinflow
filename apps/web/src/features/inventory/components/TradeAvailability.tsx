import { useId, type CSSProperties, type MouseEvent, type KeyboardEvent } from 'react'

import type { InventoryGroup } from '../model/types'

export function TradeAvailability({ group, now }: { group: InventoryGroup; now: number }) {
  const tooltipId = useId()
  const available = Math.max(0, group.available_quantity)
  const pending = Math.max(0, group.pending_listing_quantity ?? 0)
  const listed = Math.max(0, group.listed_quantity ?? 0)
  const tradable = Math.min(available, Math.max(0, group.tradable_quantity))
  const cooldown = Math.max(0, available - tradable)
  const hasCooldown = cooldown > 0
  const total = available + pending + listed
  const tradableShare = total ? (tradable / total) * 100 : 0
  const cooldownShare = total ? (cooldown / total) * 100 : 0
  const listedShare = total ? (listed / total) * 100 : 0
  const pendingShare = total ? (pending / total) * 100 : 0
  const style = {
    '--tradable-share': `${tradableShare}%`,
    '--cooldown-share': `${cooldownShare}%`,
    '--listed-share': `${listedShare}%`,
    '--pending-share': `${pendingShare}%`,
  } as CSSProperties

  function stopRowInteraction(event: MouseEvent | KeyboardEvent) {
    event.stopPropagation()
  }

  return (
    <span
      className={`trade-availability${hasCooldown ? ' has-cooldown' : ''}`}
      style={style}
      tabIndex={hasCooldown ? 0 : undefined}
      aria-describedby={hasCooldown ? tooltipId : undefined}
      aria-label={`可交易 ${tradable} 件，冷却中 ${cooldown} 件，待确认 ${pending} 件，在售 ${listed} 件`}
      onClick={stopRowInteraction}
      onKeyDown={stopRowInteraction}
    >
      <span className={tradable ? 'availability-ratio is-tradable' : 'availability-ratio is-cooldown'}>
        <b>{tradable}</b><small>/ {total} 件</small>
      </span>
      <span className="availability-bar" role="img" aria-label={`可交易 ${tradable} 件，冷却中 ${cooldown} 件，待确认 ${pending} 件，在售 ${listed} 件`}>
        <i className="availability-segment is-tradable" />
        <i className="availability-segment is-cooldown" />
        <i className="availability-segment is-pending" />
        <i className="availability-segment is-listed" />
      </span>
      <span className="availability-legend">
        <span>可交易 {tradable}</span><span>冷却 {cooldown}</span><span>待确认 {pending}</span><span>在售 {listed}</span>
      </span>
      {hasCooldown ? (
        <span className="cooldown-popover" id={tooltipId} role="tooltip">
          <span className="cooldown-popover-head"><strong>冷却批次</strong><small>{cooldown} 件</small></span>
          <span className="cooldown-batches">
            {group.cooldown_batches?.length ? group.cooldown_batches.map((batch) => (
              <span className="cooldown-batch" key={`${batch.tradable_after ?? 'unknown'}:${batch.hold_text ?? ''}`}>
                <b>{batch.quantity} 件</b>
                <strong>{remainingText(batch.tradable_after, now)}</strong>
                <small>{unlockText(batch.tradable_after)}</small>
              </span>
            )) : <span className="cooldown-batch is-unknown">等待 Steam 返回批次时间</span>}
          </span>
        </span>
      ) : null}
    </span>
  )
}

function remainingText(tradableAfter: number | null, now: number): string {
  if (tradableAfter == null) return '时间待更新'
  const minutes = Math.max(0, Math.ceil((tradableAfter - now) / 60_000))
  if (!minutes) return '即将可交易'
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const remainder = minutes % 60
  return [days ? `${days}天` : '', hours ? `${hours}小时` : '', remainder ? `${remainder}分` : '']
    .filter(Boolean)
    .join('')
}

function unlockText(tradableAfter: number | null): string {
  if (tradableAfter == null) return '同步库存后更新'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(tradableAfter))
}
