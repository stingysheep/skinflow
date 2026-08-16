import { act, fireEvent, render, screen } from '@testing-library/react'

import {
  cancelListingItems,
  getListingRequests,
  reconcileListingRequests,
  type ListingRequest,
} from '../api/listingsApi'
import { ListingsPage } from './ListingsPage'

vi.mock('../api/listingsApi', () => ({
  cancelListingItems: vi.fn(),
  getListingRequests: vi.fn(),
  reconcileListingRequests: vi.fn(),
}))

const request: ListingRequest = {
  id: 'request-1',
  status: 'submitted',
  created_at: 1_700_000_000_000,
  completed_at: null,
  items: [{
    id: 'item-1',
    assetid: 'asset-1',
    status: 'active',
    steam_listing_id: 'listing-1',
    message: null,
    market_hash_name: 'AK-47 | Slate',
    display_name: 'AK-47 | 板岩',
    image_url: '',
    wear_text: null,
    cost_each: 100,
    buyer_pays: 200,
    seller_proceeds: 170,
  }],
}

describe('ListingsPage', () => {
  beforeEach(() => {
    vi.mocked(getListingRequests).mockResolvedValue({ items: [request] })
    vi.mocked(reconcileListingRequests).mockResolvedValue({ checked: 1, sold: 0, cancelled: 0, errors: 0 })
    vi.mocked(cancelListingItems).mockResolvedValue({ items: [] })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('refreshes listing status every 60 seconds', async () => {
    vi.useFakeTimers()
    render(<ListingsPage />)
    await act(async () => { await Promise.resolve() })

    expect(screen.getByText('AK-47 | 板岩')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })

    expect(getListingRequests).toHaveBeenCalledTimes(2)
  })

  it('shows a retryable error when the initial request fails', async () => {
    vi.mocked(getListingRequests).mockRejectedValueOnce(new Error('offline'))
    render(<ListingsPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('offline')
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    expect(await screen.findByText('AK-47 | 板岩')).toBeInTheDocument()
  })
})
