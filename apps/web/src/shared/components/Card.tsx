import type { HTMLAttributes, ReactNode } from 'react'

type CardProps = HTMLAttributes<HTMLElement> & {
  children: ReactNode
}

export function Card({ children, className, ...props }: CardProps) {
  const classes = ['ui-card', className].filter(Boolean).join(' ')
  return <section {...props} className={classes}>{children}</section>
}

type KpiCardProps = {
  label: string
  value: ReactNode
  detail?: ReactNode
  tone?: 'default' | 'positive' | 'warning'
}

export function KpiCard({ label, value, detail, tone = 'default' }: KpiCardProps) {
  return (
    <Card className={`kpi-card kpi-card-${tone}`}>
      <span className="kpi-card-label">{label}</span>
      <strong className="kpi-card-value">{value}</strong>
      {detail ? <span className="kpi-card-detail">{detail}</span> : null}
    </Card>
  )
}
