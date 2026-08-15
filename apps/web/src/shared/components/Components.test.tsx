import { fireEvent, render, screen } from '@testing-library/react'

import { Card, FeedbackState, KpiCard, ProgressBar, StatusBadge } from './index'

describe('shared components', () => {
  it('renders card and KPI content', () => {
    render(<Card><KpiCard label="推荐比例" value="1.84%" detail="可执行" /></Card>)
    expect(screen.getByText('推荐比例')).toBeInTheDocument()
    expect(screen.getByText('1.84%')).toBeInTheDocument()
    expect(screen.getByText('可执行')).toBeInTheDocument()
  })

  it('normalizes progress values and exposes progress semantics', () => {
    render(<ProgressBar value={120} label="扫描进度" />)
    expect(screen.getByRole('progressbar', { name: '扫描进度' })).toHaveAttribute('aria-valuenow', '100')
  })

  it('renders an actionable error state', () => {
    const onAction = vi.fn()
    render(<FeedbackState kind="error" title="服务离线" actionLabel="重试" onAction={onAction} />)
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    expect(onAction).toHaveBeenCalledOnce()
  })

  it('renders semantic status tone', () => {
    render(<StatusBadge tone="warning">限流等待</StatusBadge>)
    expect(screen.getByText('限流等待')).toHaveClass('status-badge-warning')
  })
})
