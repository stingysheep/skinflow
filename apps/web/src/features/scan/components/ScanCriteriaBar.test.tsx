import { fireEvent, render, screen } from '@testing-library/react'

import type { ScanCriteria } from '../model/types'
import { ScanCriteriaBar } from './ScanCriteriaBar'

const criteria: ScanCriteria = {
  candidateLimit: 20,
  mode: 'listing',
  platforms: ['buff'],
  minPriceYuan: '',
  maxPriceYuan: '',
  minDailyVolume: 0,
}

describe('ScanCriteriaBar', () => {
  it('allows both sources but prevents clearing the final source', () => {
    const onChange = vi.fn()
    const view = render(<ScanCriteriaBar criteria={criteria} disabled={false} onChange={onChange} />)

    fireEvent.click(screen.getByRole('checkbox', { name: '网易 BUFF' }))
    expect(onChange).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('checkbox', { name: '悠悠有品' }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ platforms: ['buff', 'youpin'] }))

    view.rerender(<ScanCriteriaBar criteria={{ ...criteria, mode: 'buy_order' }} disabled={false} onChange={onChange} />)
    expect(screen.getByRole('button', { name: '丢求购' })).toHaveClass('is-active')
  })
})
