import { CircleAlert, Inbox } from 'lucide-react'

import { Button } from './Button'

type FeedbackStateProps = {
  kind: 'empty' | 'error'
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

export function FeedbackState({ kind, title, description, actionLabel, onAction }: FeedbackStateProps) {
  const Icon = kind === 'error' ? CircleAlert : Inbox
  return (
    <div className={`feedback-state feedback-state-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <Icon aria-hidden="true" size={20} />
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {actionLabel && onAction ? <Button variant="secondary" onClick={onAction}>{actionLabel}</Button> : null}
    </div>
  )
}
