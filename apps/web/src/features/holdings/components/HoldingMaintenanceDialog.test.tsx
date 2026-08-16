import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { HoldingMaintenanceDialog } from './HoldingMaintenanceDialog'
import { deleteHolding, updateHoldingAverageCost } from '../api/ledgerApi'

vi.mock('../api/ledgerApi', async () => {
  const actual = await vi.importActual<typeof import('../api/ledgerApi')>('../api/ledgerApi')
  return { ...actual, deleteHolding: vi.fn(), updateHoldingAverageCost: vi.fn() }
})

const holding = {
  market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | Slate', image_url: '', game: 'cs2',
  quantity: 3, sold_quantity: 1, open_quantity: 2, invested: 3000, open_cost: 2000, lots: 1,
}

describe('HoldingMaintenanceDialog', () => {
  it('saves a replacement average cost for open quantity', async () => {
    const onSaved = vi.fn()
    render(<HoldingMaintenanceDialog mode="edit" holding={holding} open onOpenChange={vi.fn()} onSaved={onSaved} />)
    const input = screen.getByLabelText('新的未售均价（元）')
    fireEvent.change(input, { target: { value: '12.34' } })
    fireEvent.click(screen.getByRole('button', { name: '保存均价' }))
    await waitFor(() => expect(updateHoldingAverageCost).toHaveBeenCalledWith('AK-47 | Slate', 1234))
    expect(onSaved).toHaveBeenCalledOnce()
  })

  it('requires an explicit delete action and preserves the named quantity', async () => {
    const onSaved = vi.fn()
    render(<HoldingMaintenanceDialog mode="delete" holding={holding} open onOpenChange={vi.fn()} onSaved={onSaved} />)
    expect(screen.getByText('确认删除这 2 件未售持仓吗？已售数量和成交历史不会被删除。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }))
    await waitFor(() => expect(deleteHolding).toHaveBeenCalledWith('AK-47 | Slate'))
    expect(onSaved).toHaveBeenCalledOnce()
  })
})
