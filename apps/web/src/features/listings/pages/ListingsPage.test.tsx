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

  it('reconciles Steam state before the periodic refresh', async () => {
    vi.useFakeTimers()
    render(<ListingsPage />)
    await act(async () => { await Promise.resolve() })

    expect(screen.getByText('AK-47 | 板岩')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) })

    expect(getListingRequests).toHaveBeenCalledTimes(2)
    expect(reconcileListingRequests).toHaveBeenCalledTimes(1)
  })

  it('selects all cancellable assets through status and item-group parents', async () => {
    render(<ListingsPage />)

    const statusCheckbox = await screen.findByRole('checkbox', { name: '选择在售下所有可取消挂单' })
    fireEvent.click(statusCheckbox)
    expect(screen.getByRole('button', { name: '取消所选挂单' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: '展开 AK-47 | 板岩' }))
    expect(screen.getByRole('checkbox', { name: '选择取消资产 asset-1' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: '选择AK-47 | 板岩下所有可取消挂单' })).toBeChecked()
  })

  it('does not expose cancellation until an active item has a Steam listing ID', async () => {
    vi.mocked(getListingRequests).mockResolvedValueOnce({ items: [{
      ...request,
      items: [{ ...request.items[0], steam_listing_id: null }],
    }] })
    render(<ListingsPage />)

    const statusCheckbox = await screen.findByRole('checkbox', { name: '选择在售下所有可取消挂单' })
    expect(statusCheckbox).toBeDisabled()
    expect(screen.getByRole('button', { name: '取消所选挂单' })).toBeDisabled()
  })

  it('renders status, item group, and asset levels in order', async () => {
    render(<ListingsPage />)

    expect(await screen.findByText('在售')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '展开 AK-47 | 板岩' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '展开 AK-47 | 板岩' }))
    expect(screen.getByText('资产 asset-1')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '选择在售下所有可取消挂单' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '选择AK-47 | 板岩下所有可取消挂单' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: '选择取消资产 asset-1' })).toBeInTheDocument()
  })

  it('separates queued and mobile-confirmation items from actual active listings', async () => {
    vi.mocked(getListingRequests).mockResolvedValueOnce({ items: [{
      ...request,
      items: [
        { ...request.items[0], id: 'item-queued', status: 'queued', steam_listing_id: null },
        { ...request.items[0], id: 'item-pending', status: 'pending_confirmation', steam_listing_id: null },
        request.items[0],
      ],
    }] })

    render(<ListingsPage />)

    expect(await screen.findByText('等待提交/待确认')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: '展开 AK-47 | 板岩' })[0])
    expect(screen.getByText('等待提交')).toBeInTheDocument()
    expect(screen.getByText('待手机确认')).toBeInTheDocument()
    expect(screen.getByText('在售')).toBeInTheDocument()
  })

  it('keeps grouped totals numeric when legacy rows omit buyer price', async () => {
    vi.mocked(getListingRequests).mockResolvedValueOnce({ items: [{
      ...request,
      items: [{ ...request.items[0], id: 'item-closed', status: 'cancelled', steam_listing_id: null, buyer_pays: Number.NaN, seller_proceeds: Number.NaN }],
    }] })

    render(<ListingsPage />)

    expect(await screen.findByText('已取消/失败')).toBeInTheDocument()
    expect(screen.getAllByText('¥0.00').length).toBeGreaterThan(0)
    expect(screen.queryByText('¥NaN')).not.toBeInTheDocument()
  })

  it('shows a retryable error when the initial request fails', async () => {
    vi.mocked(getListingRequests).mockRejectedValueOnce(new Error('offline'))
    render(<ListingsPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('offline')
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    expect(await screen.findByText('AK-47 | 板岩')).toBeInTheDocument()
  })
})
