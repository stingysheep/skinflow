import { fireEvent, render, screen } from '@testing-library/react'

import { ScanToolbar } from './ScanToolbar'

describe('ScanToolbar', () => {
  it('connects the visible filter and scan controls', () => {
    const onFilter = vi.fn()
    const onStart = vi.fn()
    render(
      <ScanToolbar
        limit={20}
        onLimit={vi.fn()}
        mode="listing"
        platforms={['buff']}
        status={null}
        query=""
        onQuery={vi.fn()}
        sort="ratio"
        onSort={vi.fn()}
        filter="all"
        onFilter={onFilter}
        starting={false}
        onStart={onStart}
        onCancel={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByRole('combobox', { name: '筛选扫描结果' }), {
      target: { value: 'depth' },
    })
    fireEvent.click(screen.getByRole('button', { name: '扫描' }))

    expect(onFilter).toHaveBeenCalledWith('depth')
    expect(onStart).toHaveBeenCalledOnce()
  })

  it('disables the scan button while a job is being created', () => {
    render(
      <ScanToolbar
        limit={20}
        onLimit={vi.fn()}
        mode="listing"
        platforms={['buff']}
        status={null}
        query=""
        onQuery={vi.fn()}
        sort="ratio"
        onSort={vi.fn()}
        filter="all"
        onFilter={vi.fn()}
        starting
        onStart={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: '扫描' })).toBeDisabled()
  })
})
