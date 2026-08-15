type ProgressBarProps = {
  value: number
  label?: string
  tone?: 'default' | 'positive' | 'warning'
}

export function ProgressBar({ value, label, tone = 'default' }: ProgressBarProps) {
  const normalized = Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0
  return (
    <div className="progress-bar" aria-label={label} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={normalized}>
      <span className={`progress-bar-fill progress-bar-${tone}`} style={{ width: `${normalized}%` }} />
    </div>
  )
}
