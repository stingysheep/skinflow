import { act, fireEvent, render, screen } from '@testing-library/react'

import { getJson, postJson } from '../api/client'
import { ListingNotificationProvider, useListingNotifications } from './useListingNotifications'

vi.mock('../api/client', () => ({
  getJson: vi.fn(),
  postJson: vi.fn(),
}))

const mockedGetJson = vi.mocked(getJson)
const mockedPostJson = vi.mocked(postJson)

function Consumer() {
  const { trackListingRequest } = useListingNotifications()
  return <button type="button" onClick={() => trackListingRequest('request-1')}>跟踪挂单</button>
}

describe('ListingNotificationProvider', () => {
  beforeEach(() => {
    mockedPostJson.mockResolvedValue({})
    mockedGetJson.mockResolvedValue({ id: 'request-1', status: 'submitted', items: [{ status: 'active' }] })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('shows a success notification after background reconciliation', async () => {
    render(<ListingNotificationProvider><Consumer /></ListingNotificationProvider>)

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '跟踪挂单' }))
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(await screen.findByRole('status')).toHaveTextContent('Steam 挂单成功')
    expect(mockedPostJson).toHaveBeenCalledWith('/api/listing-requests/reconcile', {})
  })
})
