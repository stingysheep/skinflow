import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import { getJson } from '../../shared/api/client'
import { WorkspacePage } from './WorkspacePage'

vi.mock('../../shared/api/client', () => ({
  getJson: vi.fn(),
}))

const mockedGetJson = vi.mocked(getJson)

describe('WorkspacePage history grouping', () => {
  it('groups the same item and cost batch while keeping fill details expandable', async () => {
    mockedGetJson.mockResolvedValue({ items: [
      { id: 'fill-1', purchase_lot_id: 'lot-1', market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '', quantity: 1, cost_total: 100, receive_total: 200, sold_at: 1_700_000_000, source: 'automatic' },
      { id: 'fill-2', purchase_lot_id: 'lot-1', market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '', quantity: 1, cost_total: 100, receive_total: 210, sold_at: 1_700_000_100, source: 'automatic' },
      { id: 'fill-3', purchase_lot_id: 'lot-2', market_hash_name: 'AK-47 | Slate', display_name: 'AK-47 | 板岩', image_url: '', quantity: 1, cost_total: 300, receive_total: 400, sold_at: 1_700_000_200, source: 'manual' },
    ] })

    render(<WorkspacePage mode="history" />)
    await waitFor(() => expect(screen.getAllByText('¥5.00').length).toBeGreaterThan(0))
    expect(screen.getByText(/2 个成本批次/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /AK-47 \| 板岩/ }))

    expect(screen.getAllByText(/Steam 自动同步/).length).toBe(2)
    expect(screen.getByText(/手动记录/)).toBeInTheDocument()
  })
})
