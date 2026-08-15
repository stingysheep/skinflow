import type { ReactNode } from 'react'

export type StatusTone = 'success' | 'info' | 'warning' | 'danger' | 'neutral'

type StatusBadgeProps = {
  tone: StatusTone
  children: ReactNode
  className?: string
}

export function StatusBadge({ tone, children, className }: StatusBadgeProps) {
  const classes = ['status-badge', `status-badge-${tone}`, className]
    .filter(Boolean)
    .join(' ')

  return <span className={classes}>{children}</span>
}
